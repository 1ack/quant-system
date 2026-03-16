#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A 股数据增量更新 - 腾讯财经 API

每日定时任务：获取所有 A 股当天的 K 线数据（前复权）并写入 ClickHouse
只下载最新一天的数据，避免重复
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import requests
from datetime import datetime, timedelta
from typing import List, Dict
from loguru import logger
from data.storage import DataStorage
from data.models import KLine

# 腾讯财经 K 线 API
TENCENT_KLINE_URL = "http://web.ifzq.gtimg.cn/appstock/app/fqkline/get"

# 新浪财经股票列表 API
SINA_STOCK_LIST_URL = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"


def get_all_a_shares() -> List[Dict]:
    """获取所有 A 股股票列表"""
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


def get_latest_kline_tencent(code: str) -> List[KLine]:
    """
    从腾讯财经获取单只股票最新 1 条 K 线数据（前复权）
    
    参数:
        code: 股票代码（不含市场前缀）
    """
    if code[0] in "023":
        market = "sz"
    elif code[0] in "68":
        market = "sh"
    else:
        market = "sh"
    
    symbol = f"{market}{code}"
    
    # 只获取最新 1 条数据
    params = {
        "param": f"{symbol},day,,,1,qfq",
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
            if len(item) < 6:
                continue
            
            date_str = item[0]
            try:
                date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                continue
            
            # 过滤停牌数据
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
        logger.debug(f"  获取 {code} 失败：{e}")
        return []


def load_incremental_to_db(stocks: List[Dict]):
    """
    增量下载股票数据并写入数据库
    只下载最新一天的数据，如果已存在则跳过
    """
    storage = DataStorage()
    
    try:
        logger.info("开始增量更新（只下载当天数据）...")
        logger.info("数据源：腾讯财经（前复权）")
        print("\n" + "=" * 70)
        
        total_stocks = len(stocks)
        success_count = 0
        skip_count = 0
        failed_stocks = []
        today = datetime.now().date()
        
        for i, stock in enumerate(stocks):
            code = stock["code"]
            name = stock["name"]
            
            # 进度显示
            progress = f"[{i+1:4d}/{total_stocks}]"
            print(f"\r{progress} {code} {name}", end=" ", flush=True)
            
            klines = get_latest_kline_tencent(code)
            
            if klines:
                kline = klines[0]
                
                # 检查是否已存在
                existing = storage.get_klines(code, start_date=today - timedelta(days=1), end_date=today + timedelta(days=1))
                
                if existing and any(k.date.date() == kline.date.date() for k in existing):
                    skip_count += 1
                    print(f"⊘ 已存在", end="")
                else:
                    storage.save_klines([kline])
                    success_count += 1
                    print(f"✓ {kline.date.strftime('%Y-%m-%d')}", end="")
            else:
                failed_stocks.append(code)
                print(f"✗ 失败", end="")
        
        # 汇总报告
        print("\n" + "=" * 70)
        logger.info("\n" + "=" * 70)
        logger.info("增量更新完成！")
        logger.info(f"新增：{success_count} 只股票")
        logger.info(f"跳过：{skip_count} 只股票（已存在）")
        logger.info(f"失败：{len(failed_stocks)} 只股票")
        
        if failed_stocks:
            logger.warning(f"失败股票列表：{', '.join(failed_stocks[:20])}{'...' if len(failed_stocks) > 20 else ''}")
        
        # 验证数据
        print("\n验证数据总量...")
        total_klines = storage.get_all_klines_count()
        logger.info(f"  ClickHouse 总数据量：{total_klines:,} 条 K 线")
        
        print("=" * 70 + "\n")
        
    finally:
        storage.close()


def main():
    logger.add(sys.stdout, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")
    
    print("=" * 70)
    print("A 股数据增量更新（每日定时任务）")
    print("=" * 70)
    print("数据源：腾讯财经（前复权）")
    print("更新范围：当天数据")
    print("目标数据库：ClickHouse")
    print("=" * 70)
    
    # 获取股票列表
    stocks = get_all_a_shares()
    
    if not stocks:
        logger.error("获取股票列表失败，退出")
        return
    
    # 开始增量下载
    load_incremental_to_db(stocks)
    
    logger.info("✓ 所有操作完成")


if __name__ == "__main__":
    main()
