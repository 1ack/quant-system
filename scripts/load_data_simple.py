#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A 股历史数据录入脚本 - 简化版（无模块导入问题）

从新浪财经 API 获取近两年 A 股数据并存储到 ClickHouse
"""
import sys
import os
import requests
from datetime import datetime
from clickhouse_driver import Client

# 新浪财经 K 线 API
SINA_KLINE_URL = "http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData/getKLineData"

# ClickHouse 配置
CK_HOST = "localhost"
CK_DATABASE = "quant"
CK_USER = "default"
CK_PASSWORD = ""

# 成分股列表（A 股核心股票）
STOCK_CODES = [
    "000001", "000002", "000063", "000333", "000651", "000858", "002415", "002594",
    "600000", "600009", "600016", "600028", "600030", "600031", "600036", "600048",
    "600050", "600104", "600276", "600346", "600519", "600585", "600690", "600809",
    "600887", "600900", "601012", "601088", "601166", "601288", "601318", "601398",
    "601668", "601688", "601857", "601888", "603259", "603288",
]


def get_kline(code, datalen=1022):
    """获取单只股票的 K 线数据"""
    params = {
        "symbol": code,
        "scale": "day",
        "datalen": str(datalen),
    }
    
    try:
        resp = requests.get(SINA_KLINE_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        klines = []
        for item in data:
            date_str = item.get("day", "")
            try:
                date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                continue
            
            klines.append({
                "code": code,
                "date": date,
                "open": float(item.get("open", 0)),
                "high": float(item.get("high", 0)),
                "low": float(item.get("low", 0)),
                "close": float(item.get("close", 0)),
                "volume": int(item.get("volume", 0)),
                "amount": float(item.get("amount", 0)),
            })
        
        return klines
        
    except Exception as e:
        print(f"  ✗ 获取 {code} 失败：{e}")
        return []


def init_clickhouse():
    """初始化 ClickHouse 表"""
    client = Client(host=CK_HOST, database=CK_DATABASE, user=CK_USER, password=CK_PASSWORD)
    
    client.execute("""
        CREATE TABLE IF NOT EXISTS kline_daily (
            code String,
            date Date,
            open Float32,
            high Float32,
            low Float32,
            close Float32,
            volume UInt32,
            amount Float64
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(date)
        ORDER BY (code, date)
        SETTINGS index_granularity = 8192
    """)
    
    return client


def save_klines(client, klines):
    """保存 K 线数据"""
    if not klines:
        return
    
    data = [
        (k["code"], k["date"], k["open"], k["high"], k["low"], k["close"], k["volume"], k["amount"])
        for k in klines
    ]
    
    client.execute("INSERT INTO kline_daily VALUES", data)


def main():
    print("=" * 60)
    print("A 股历史数据录入 - 新浪财经 API")
    print("=" * 60)
    
    # 初始化 ClickHouse
    print("\n连接 ClickHouse...")
    try:
        client = init_clickhouse()
        print("✓ ClickHouse 已连接")
    except Exception as e:
        print(f"✗ ClickHouse 连接失败：{e}")
        return
    
    # 录入数据
    print(f"\n开始录入 {len(STOCK_CODES)} 只股票的历史数据...")
    print("数据源：新浪财经 API")
    print("这可能需要几分钟时间...\n")
    
    count = 0
    total_lines = 0
    
    for i, code in enumerate(STOCK_CODES):
        print(f"[{i+1}/{len(STOCK_CODES)}] 录入 {code}...")
        
        klines = get_kline(code)
        
        if klines:
            save_klines(client, klines)
            count += 1
            total_lines += len(klines)
            print(f"  ✓ 成功录入 {len(klines)} 条数据 (最新：{klines[0]['date'].strftime('%Y-%m-%d')})")
        else:
            print(f"  ⚠ 无数据")
    
    print("\n" + "=" * 60)
    print(f"数据录入完成！")
    print(f"成功：{count}/{len(STOCK_CODES)} 只股票")
    print(f"总数据量：{total_lines} 条 K 线")
    print("=" * 60)
    
    # 验证数据
    print("\n验证数据...")
    for code in ["000001", "600519", "601318"]:
        result = client.execute(
            "SELECT count(), max(date) FROM kline_daily WHERE code = %(code)s",
            {"code": code}
        )
        if result and result[0][0] > 0:
            print(f"{code}: {result[0][0]} 条数据，最新日期 {result[0][1]}")
    
    client.disconnect()
    print("\n✓ 所有操作完成")


if __name__ == "__main__":
    main()
