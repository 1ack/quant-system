#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A 股历史数据批量下载 - 支持断点续传
腾讯财经 API + ClickHouse 存储
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import requests
import time
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
from loguru import logger
from data.storage import DataStorage
from data.models import KLine, StockInfo

# 腾讯财经 K 线 API
TENCENT_KLINE_URL = "http://web.ifzq.gtimg.cn/appstock/app/fqkline/get"

# 新浪财经股票列表 API
SINA_STOCK_LIST_URL = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"

# 配置
DOWNLOAD_DELAY = 0.5  # 每只股票下载间隔（秒），避免被封 IP
BATCH_SIZE = 50  # 每批下载后记录进度
PROGRESS_FILE = "logs/download_progress.json"
FAILED_FILE = "logs/failed_stocks.json"


def get_all_a_shares() -> List[Dict]:
    """获取所有 A 股股票列表（新浪财经 API）"""
    all_stocks = []
    
    # 获取上交所股票
    try:
        logger.info("获取上交所股票列表...")
        for page in range(1, 20):
            params = {
                "page": str(page),
                "num": "80",
                "sort": "symbol",
                "asc": "1",
                "node": "sh_a",
                "_s_r_a": "page"
            }
            resp = requests.get(SINA_STOCK_LIST_URL, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
            if not data:
                break
            
            for item in data:
                all_stocks.append({
                    "code": item["symbol"].lstrip("sh"),
                    "name": item["name"],
                    "market": "SH"
                })
            
            if len(data) < 80:
                break
    except Exception as e:
        logger.error(f"获取上交所股票失败：{e}")
    
    # 获取深交所股票
    try:
        logger.info("获取深交所股票列表...")
        for page in range(1, 20):
            params = {
                "page": str(page),
                "num": "80",
                "sort": "symbol",
                "asc": "1",
                "node": "sz_a",
                "_s_r_a": "page"
            }
            resp = requests.get(SINA_STOCK_LIST_URL, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
            if not data:
                break
            
            for item in data:
                all_stocks.append({
                    "code": item["symbol"].lstrip("sz"),
                    "name": item["name"],
                    "market": "SZ"
                })
            
            if len(data) < 80:
                break
    except Exception as e:
        logger.error(f"获取深交所股票失败：{e}")
    
    logger.info(f"✓ 共获取 {len(all_stocks)} 只 A 股股票")
    return all_stocks


def get_existing_codes(storage: DataStorage) -> Set[str]:
    """从 ClickHouse 获取已下载的股票代码"""
    try:
        client = storage.clickhouse_client
        result = client.execute('SELECT DISTINCT code FROM kline_daily')
        return {row[0] for row in result}
    except Exception as e:
        logger.warning(f"获取已下载代码失败：{e}")
        return set()


def get_kline_tencent(code: str, count: int = 500) -> List[KLine]:
    """从腾讯财经获取单只股票的 K 线数据（前复权）"""
    if code[0] in "023":
        market = "sz"
    elif code[0] in "68":
        market = "sh"
    else:
        market = "sh"
    
    symbol = f"{market}{code}"
    
    params = {
        "param": f"{symbol},day,,,{count},qfq",
    }
    
    try:
        resp = requests.get(TENCENT_KLINE_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        
        if symbol not in data.get("data", {}):
            return []
        
        stock_data = data["data"][symbol]
        klines_raw = stock_data.get("qfqday", [])
        
        if not klines_raw:
            return []
        
        klines = []
        for item in klines_raw:
            # 检查数据格式 - 有些股票可能返回异常数据结构
            if not isinstance(item, (list, tuple)) or len(item) < 6:
                continue
            
            # 检查每个元素是否为基本类型（排除字典等复杂类型）
            try:
                date_str = str(item[0])
                # 跳过包含字典的数据行（检查所有元素）
                if any(isinstance(x, dict) for x in item):
                    continue
            except (TypeError, AttributeError):
                continue
            
            try:
                date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                continue
            
            try:
                open_price = float(item[1])
                close_price = float(item[2])
                if open_price == 0 or close_price == 0:
                    continue
            except (ValueError, TypeError):
                continue
            
            klines.append(KLine(
                code=code,
                date=date,
                open=open_price,
                close=close_price,
                high=float(item[3]) if item[3] else open_price,
                low=float(item[4]) if item[4] else open_price,
                volume=int(float(item[5])) if item[5] else 0,
                amount=float(item[6]) if len(item) > 6 and item[6] else 0,
            ))
        
        return klines
        
    except Exception as e:
        import traceback
        logger.debug(f"  获取 {code} 失败：{e}")
        logger.debug(f"  Traceback: {traceback.format_exc()[:500]}")
        return []


def load_progress() -> Dict:
    """加载下载进度"""
    progress_path = os.path.join(os.path.dirname(__file__), '..', PROGRESS_FILE)
    if os.path.exists(progress_path):
        try:
            with open(progress_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {"completed": [], "failed": [], "start_time": None, "last_update": None}


def save_progress(progress: Dict):
    """保存下载进度"""
    progress_path = os.path.join(os.path.dirname(__file__), '..', PROGRESS_FILE)
    progress["last_update"] = datetime.now().isoformat()
    os.makedirs(os.path.dirname(progress_path), exist_ok=True)
    with open(progress_path, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def save_failed_stocks(failed: List[Dict]):
    """保存失败股票列表"""
    failed_path = os.path.join(os.path.dirname(__file__), '..', FAILED_FILE)
    os.makedirs(os.path.dirname(failed_path), exist_ok=True)
    with open(failed_path, 'w', encoding='utf-8') as f:
        json.dump(failed, f, ensure_ascii=False, indent=2)


def download_batch(stocks: List[Dict], storage: DataStorage, progress: Dict, 
                   existing_codes: Set[str], days: int = 500):
    """批量下载股票数据"""
    total_stocks = len(stocks)
    success_count = 0
    total_klines = 0
    failed_stocks = []
    completed_codes = set(progress.get("completed", []))
    
    logger.info(f"\n开始下载 {total_stocks} 只股票...")
    logger.info(f"数据源：腾讯财经（前复权）")
    logger.info(f"下载间隔：{DOWNLOAD_DELAY}秒")
    print("\n" + "=" * 70)
    
    start_time = datetime.now()
    
    for i, stock in enumerate(stocks):
        code = stock["code"]
        name = stock["name"]
        
        # 跳过已下载的股票
        if code in existing_codes or code in completed_codes:
            continue
        
        # 进度显示
        current_total = len(completed_codes) + success_count
        progress_pct = (current_total / 3040) * 100 if total_stocks > 0 else 0
        progress_str = f"[{current_total:4d}/3040 {progress_pct:5.1f}%]"
        print(f"\r{progress_str} {code} {name}", end=" ", flush=True)
        
        # 添加延时避免被封 IP
        if i > 0 and i % 10 == 0:
            time.sleep(DOWNLOAD_DELAY * 2)  # 每 10 只额外延时
        else:
            time.sleep(DOWNLOAD_DELAY)
        
        klines = get_kline_tencent(code, count=days)
        
        if klines:
            cutoff_date = datetime.now() - timedelta(days=730)
            recent_klines = [k for k in klines if k.date >= cutoff_date]
            
            if recent_klines:
                try:
                    storage.save_klines(recent_klines)
                    success_count += 1
                    total_klines += len(recent_klines)
                    completed_codes.add(code)
                    print(f"✓ {len(recent_klines):4d}条", end="")
                    
                    # 每批保存进度
                    if success_count % BATCH_SIZE == 0:
                        progress["completed"] = list(completed_codes)
                        progress["failed"] = failed_stocks
                        save_progress(progress)
                        logger.info(f"\n  → 已保存进度：{len(completed_codes)} 只股票完成")
                except Exception as e:
                    logger.error(f"  保存 {code} 数据失败：{e}")
                    failed_stocks.append({"code": code, "name": name, "error": str(e)})
                    print(f"✗ 保存失败", end="")
            else:
                print(f"⚠ 无近期数据", end="")
        else:
            failed_stocks.append({"code": code, "name": name, "error": "下载失败"})
            print(f"✗ 失败", end="")
    
    # 最终保存进度
    progress["completed"] = list(completed_codes)
    progress["failed"] = failed_stocks
    progress["end_time"] = datetime.now().isoformat()
    save_progress(progress)
    save_failed_stocks(failed_stocks)
    
    # 汇总报告
    elapsed = (datetime.now() - start_time).total_seconds()
    print("\n" + "=" * 70)
    logger.info("\n" + "=" * 70)
    logger.info("本批次下载完成！")
    logger.info(f"本批成功：{success_count} 只股票")
    logger.info(f"本批失败：{len(failed_stocks)} 只股票")
    logger.info(f"本批数据量：{total_klines:,} 条 K 线")
    logger.info(f"耗时：{elapsed:.1f} 秒")
    logger.info(f"累计完成：{len(completed_codes)} 只股票")
    
    if failed_stocks:
        logger.warning(f"失败股票已保存到 {FAILED_FILE}")
        logger.warning(f"失败示例：{', '.join([f['code'] for f in failed_stocks[:10]])}")
    
    return success_count, len(failed_stocks), total_klines


def main():
    logger.add(sys.stdout, level="INFO", 
               format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")
    
    print("=" * 70)
    print("A 股历史数据批量下载 - 断点续传")
    print("=" * 70)
    print("数据源：腾讯财经（前复权）")
    print("时间范围：近 2 年（约 500 个交易日）")
    print("目标数据库：ClickHouse")
    print("=" * 70)
    
    # 初始化存储
    storage = DataStorage()
    storage.init_clickhouse_tables()
    
    # 加载进度
    progress = load_progress()
    if not progress["start_time"]:
        progress["start_time"] = datetime.now().isoformat()
    
    completed_count = len(progress.get("completed", []))
    failed_count = len(progress.get("failed", []))
    logger.info(f"已加载进度：{completed_count} 只完成，{failed_count} 只失败")
    
    # 获取已下载的股票代码
    existing_codes = get_existing_codes(storage)
    logger.info(f"ClickHouse 中已有 {len(existing_codes)} 只股票数据")
    
    # 获取所有 A 股
    stocks = get_all_a_shares()
    
    if not stocks:
        logger.error("获取股票列表失败，退出")
        storage.close()
        return
    
    # 开始下载
    success, failed, klines = download_batch(
        stocks, storage, progress, existing_codes, days=500
    )
    
    # 验证数据
    print("\n验证数据抽样...")
    sample_codes = ["000001", "600519", "300750"]
    for code in sample_codes:
        klines = storage.get_klines(code)
        if klines:
            latest = max(k.date for k in klines)
            logger.info(f"  {code}: {len(klines)} 条，最新 {latest.strftime('%Y-%m-%d')}")
        else:
            logger.warning(f"  {code}: 无数据")
    
    print("=" * 70 + "\n")
    
    storage.close()
    
    logger.info("✓ 所有操作完成")
    logger.info(f"进度文件：{PROGRESS_FILE}")
    logger.info(f"失败列表：{FAILED_FILE}")


if __name__ == "__main__":
    main()
