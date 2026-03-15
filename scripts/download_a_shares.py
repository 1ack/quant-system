#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A 股历史数据批量下载 - 腾讯财经 API

获取所有 A 股近 2 年的历史 K 线数据（前复权）并写入 ClickHouse
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from loguru import logger
from data.storage import DataStorage
from data.models import KLine, StockInfo

# 腾讯财经 K 线 API
TENCENT_KLINE_URL = "http://web.ifzq.gtimg.cn/appstock/app/fqkline/get"

# 新浪财经股票列表 API
SINA_STOCK_LIST_URL = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"


def get_all_a_shares() -> List[Dict]:
    """
    获取所有 A 股股票列表（新浪财经 API）
    返回：[{code, name, market}, ...]
    """
    all_stocks = []
    
    # 获取上交所股票
    try:
        logger.info("获取上交所股票列表...")
        for page in range(1, 20):  # 最多 20 页
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
            
            logger.info(f"  第{page}页，获取{len(data)}只，累计{len(all_stocks)}只")
            
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
            
            logger.info(f"  第{page}页，获取{len(data)}只，累计{len(all_stocks)}只")
            
            if len(data) < 80:
                break
    except Exception as e:
        logger.error(f"获取深交所股票失败：{e}")
    
    logger.info(f"✓ 共获取 {len(all_stocks)} 只 A 股股票")
    return all_stocks


def get_kline_tencent(code: str, count: int = 500) -> List[KLine]:
    """
    从腾讯财经获取单只股票的 K 线数据（前复权）
    
    参数:
        code: 股票代码（不含市场前缀）
        count: 数据条数（500 条约等于 2 年）
    """
    # 市场前缀：00/20/30 开头是 sz，60/68 开头是 sh
    if code[0] in "023":
        market = "sz"
    elif code[0] in "68":
        market = "sh"  # 科创板
    else:
        market = "sh"
    
    symbol = f"{market}{code}"
    
    params = {
        "param": f"{symbol},day,,,{count},qfq",  # 前复权日线
    }
    
    try:
        resp = requests.get(TENCENT_KLINE_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        
        if symbol not in data.get("data", {}):
            return []
        
        stock_data = data["data"][symbol]
        klines_raw = stock_data.get("qfqday", [])  # 前复权日线
        
        if not klines_raw:
            return []
        
        klines = []
        for item in klines_raw:
            # 腾讯格式：[日期，开盘，收盘，最高，最低，成交量] 或 [日期，开盘，收盘，最高，最低，成交量，成交额]
            if len(item) < 6:
                continue
            
            date_str = item[0]
            try:
                date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                continue
            
            # 过滤掉停牌数据（价格为 0）
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


def load_data_to_db(stocks: List[Dict], days: int = 500):
    """
    批量下载股票数据并写入数据库
    
    参数:
        stocks: 股票列表
        days: 下载天数（默认 500 天≈2 年）
    """
    storage = DataStorage()
    
    try:
        # 初始化 ClickHouse 表
        logger.info("初始化 ClickHouse 表...")
        storage.init_clickhouse_tables()
        
        # 保存股票信息到 MySQL（可选，如果 MySQL 未配置则跳过）
        try:
            logger.info(f"保存 {len(stocks)} 只股票信息到 MySQL...")
            stock_infos = [
                StockInfo(code=s["code"], name=s["name"], market=s["market"])
                for s in stocks
            ]
            storage.save_stock_info(stock_infos)
        except Exception as e:
            logger.warning(f"跳过 MySQL 股票信息保存：{e}")
            logger.info("继续下载 K 线数据到 ClickHouse...")
        
        # 批量下载 K 线数据
        logger.info(f"\n开始下载 K 线数据（近{days}天）...")
        logger.info("数据源：腾讯财经（前复权）")
        print("\n" + "=" * 70)
        
        total_stocks = len(stocks)
        success_count = 0
        total_klines = 0
        failed_stocks = []
        
        for i, stock in enumerate(stocks):
            code = stock["code"]
            name = stock["name"]
            
            # 进度显示
            progress = f"[{i+1:4d}/{total_stocks}]"
            print(f"\r{progress} {code} {name}", end=" ", flush=True)
            
            klines = get_kline_tencent(code, count=days)
            
            if klines:
                # 过滤近 2 年的数据
                cutoff_date = datetime.now() - timedelta(days=730)
                recent_klines = [k for k in klines if k.date >= cutoff_date]
                
                if recent_klines:
                    storage.save_klines(recent_klines)
                    success_count += 1
                    total_klines += len(recent_klines)
                    print(f"✓ {len(recent_klines):4d}条", end="")
                else:
                    print(f"⚠ 无近期数据", end="")
            else:
                failed_stocks.append(code)
                print(f"✗ 失败", end="")
        
        # 汇总报告
        print("\n" + "=" * 70)
        logger.info("\n" + "=" * 70)
        logger.info("数据下载完成！")
        logger.info(f"成功：{success_count}/{total_stocks} 只股票")
        logger.info(f"失败：{len(failed_stocks)} 只股票")
        logger.info(f"总数据量：{total_klines:,} 条 K 线")
        
        if failed_stocks:
            logger.warning(f"失败股票列表：{', '.join(failed_stocks[:20])}{'...' if len(failed_stocks) > 20 else ''}")
        
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
        
    finally:
        storage.close()


def main():
    logger.add(sys.stdout, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")
    
    print("=" * 70)
    print("A 股历史数据批量下载")
    print("=" * 70)
    print("数据源：腾讯财经（前复权）")
    print("时间范围：近 2 年（约 500 个交易日）")
    print("目标数据库：ClickHouse")
    print("=" * 70)
    
    # 获取股票列表
    stocks = get_all_a_shares()
    
    if not stocks:
        logger.error("获取股票列表失败，退出")
        return
    
    # 开始下载
    load_data_to_db(stocks, days=500)
    
    logger.info("✓ 所有操作完成")


if __name__ == "__main__":
    main()
