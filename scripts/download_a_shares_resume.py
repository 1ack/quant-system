#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A 股历史数据批量下载 - 支持断点续传

获取所有 A 股近 2 年的历史 K 线数据（前复权）并写入 ClickHouse
每下载 50 只股票保存一次进度，支持中断后恢复
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import requests
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Set
from pathlib import Path
from loguru import logger
from data.storage import DataStorage
from data.models import KLine, StockInfo

# 腾讯财经 K 线 API
TENCENT_KLINE_URL = "http://web.ifzq.gtimg.cn/appstock/app/fqkline/get"

# 新浪财经股票列表 API
SINA_STOCK_LIST_URL = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"

# 进度文件
PROGRESS_FILE = Path(__file__).parent.parent / "logs" / "download_progress.json"


def get_all_a_shares() -> List[Dict]:
    """获取所有 A 股股票列表"""
    all_stocks = []
    
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


def load_progress() -> Dict:
    """加载下载进度"""
    if PROGRESS_FILE.exists():
        try:
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {"completed": [], "failed": [], "start_time": datetime.now().isoformat()}


def save_progress(progress: Dict):
    """保存下载进度"""
    progress["last_update"] = datetime.now().isoformat()
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def get_kline_tencent(code: str, count: int = 500) -> List[KLine]:
    """从腾讯财经获取 K 线数据"""
    if code[0] in "023":
        market = "sz"
    elif code[0] in "68":
        market = "sh"
    else:
        market = "sh"
    
    symbol = f"{market}{code}"
    params = {"param": f"{symbol},day,,,{count},qfq"}
    
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
            if len(item) < 6:
                continue
            
            date_str = item[0]
            try:
                date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                continue
            
            try:
                # Handle case where data might be dict or other unexpected types
                open_val = item[1]
                close_val = item[2]
                if isinstance(open_val, dict) or isinstance(close_val, dict):
                    continue
                open_price = float(open_val)
                close_price = float(close_val)
                if open_price == 0 or close_price == 0:
                    continue
            except (ValueError, TypeError):
                continue
            
            try:
                high_val = item[3]
                low_val = item[4]
                high = float(high_val) if high_val and not isinstance(high_val, dict) else open_price
                low = float(low_val) if low_val and not isinstance(low_val, dict) else open_price
                volume = int(float(item[5])) if item[5] and not isinstance(item[5], dict) else 0
                amount = float(item[6]) if len(item) > 6 and item[6] and not isinstance(item[6], dict) else 0
            except (ValueError, TypeError):
                continue
            
            klines.append(KLine(
                code=code,
                date=date,
                open=open_price,
                close=close_price,
                high=high,
                low=low,
                volume=volume,
                amount=amount,
            ))
        
        return klines
        
    except Exception as e:
        logger.debug(f"  获取 {code} 失败：{e}")
        return []


def load_incremental_to_db(stocks: List[Dict], completed_codes: Set[str], days: int = 500):
    """批量下载股票数据并写入数据库"""
    storage = DataStorage()
    
    try:
        logger.info("初始化 ClickHouse 表...")
        storage.init_clickhouse_tables()
        
        # 过滤已完成的股票
        remaining_stocks = [s for s in stocks if s["code"] not in completed_codes]
        total_stocks = len(remaining_stocks)
        
        logger.info(f"✓ 剩余待下载：{total_stocks} 只股票")
        logger.info(f"\n开始下载 K 线数据（近{days}天）...")
        logger.info("数据源：腾讯财经（前复权）")
        print("\n" + "=" * 70)
        
        success_count = 0
        total_klines = 0
        failed_stocks = []
        batch_size = 50  # 每 50 只保存一次进度
        
        for i, stock in enumerate(remaining_stocks):
            code = stock["code"]
            name = stock["name"]
            
            # 进度显示
            progress_str = f"[{i+1:4d}/{total_stocks}]"
            print(f"\r{progress_str} {code} {name}", end=" ", flush=True)
            
            klines = get_kline_tencent(code, count=days)
            
            # Add delay to avoid rate limiting
            time.sleep(1.5)
            
            if klines:
                cutoff_date = datetime.now() - timedelta(days=730)
                recent_klines = [k for k in klines if k.date >= cutoff_date]
                
                if recent_klines:
                    storage.save_klines(recent_klines)
                    success_count += 1
                    total_klines += len(recent_klines)
                    print(f"✓ {len(recent_klines):4d}条", end="")
                    
                    # 更新进度
                    completed_codes.add(code)
                else:
                    print(f"⚠ 无近期数据", end="")
            else:
                failed_stocks.append({"code": code, "name": name, "error": "下载失败"})
                print(f"✗ 失败", end="")
            
            # 每 50 只股票保存一次进度
            if (i + 1) % batch_size == 0:
                progress_data = {
                    "completed": list(completed_codes),
                    "failed": failed_stocks,
                    "start_time": datetime.now().isoformat(),
                }
                save_progress(progress_data)
                print(f" [进度已保存]", end="")
        
        # 最终保存
        progress_data = {
            "completed": list(completed_codes),
            "failed": failed_stocks,
            "start_time": datetime.now().isoformat(),
        }
        save_progress(progress_data)
        
        # 汇总报告
        print("\n" + "=" * 70)
        logger.info("\n" + "=" * 70)
        logger.info("数据下载完成！")
        logger.info(f"本次成功：{success_count}/{total_stocks} 只股票")
        logger.info(f"本次失败：{len(failed_stocks)} 只股票")
        logger.info(f"新增数据：{total_klines:,} 条 K 线")
        
        if failed_stocks:
            logger.warning(f"失败股票列表：{', '.join(f['code'] for f in failed_stocks[:20])}{'...' if len(failed_stocks) > 20 else ''}")
        
        # 验证数据
        print("\n验证数据总量...")
        try:
            from clickhouse_driver import Client
            client = Client(host='localhost', database='quant', connection_timeout=5)
            result = client.execute("SELECT count() FROM kline_daily")
            if result and result[0][0]:
                logger.info(f"  ClickHouse 总数据量：{result[0][0]:,} 条 K 线")
            client.disconnect()
        except Exception as e:
            logger.warning(f"  验证失败：{e}")
        
        print("=" * 70 + "\n")
        
    finally:
        storage.close()


def main():
    logger.add(sys.stdout, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")
    
    print("=" * 70)
    print("A 股历史数据批量下载（支持断点续传）")
    print("=" * 70)
    print("数据源：腾讯财经（前复权）")
    print("时间范围：近 2 年（约 500 个交易日）")
    print("目标数据库：ClickHouse")
    print("=" * 70)
    
    # 加载进度
    progress = load_progress()
    completed_codes = set(progress.get("completed", []))
    print(f"\n已下载：{len(completed_codes)} 只股票")
    
    # 获取股票列表
    stocks = get_all_a_shares()
    
    if not stocks:
        logger.error("获取股票列表失败，退出")
        return
    
    # 开始下载
    load_incremental_to_db(stocks, completed_codes, days=500)
    
    logger.info("✓ 所有操作完成")


if __name__ == "__main__":
    main()
