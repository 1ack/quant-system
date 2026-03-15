#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A 股历史数据录入 - 腾讯财经 API

从腾讯财经获取 A 股历史 K 线数据
"""
import requests
from datetime import datetime
from clickhouse_driver import Client

# 腾讯财经 K 线 API
# http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sz000001,day,,,2000,qfq
Tencent_KLINE_URL = "http://web.ifzq.gtimg.cn/appstock/app/fqkline/get"

# ClickHouse 配置
CK_HOST = "localhost"
CK_DATABASE = "quant"
CK_USER = "default"

# 成分股列表
STOCK_CODES = [
    "000001", "000002", "000063", "000333", "000651", "000858", "002415", "002594",
    "600000", "600009", "600016", "600028", "600030", "600031", "600036", "600048",
    "600050", "600104", "600276", "600346", "600519", "600585", "600690", "600809",
    "600887", "600900", "601012", "601088", "601166", "601288", "601318", "601398",
    "601668", "601688", "601857", "601888", "603259", "603288",
]


def get_kline(code, count=500):
    """
    获取单只股票的 K 线数据（腾讯财经）
    
    参数:
        code: 股票代码
        count: 数据条数
    """
    # 市场前缀：00/20/30 开头是 sz，60 开头是 sh
    market = "sz" if code[0] in "023" else "sh"
    symbol = f"{market}{code}"
    
    params = {
        "param": f"{symbol},day,,,{count},qfq",  # 前复权日线
    }
    
    try:
        resp = requests.get(Tencent_KLINE_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        # 解析返回数据
        if symbol not in data.get("data", {}):
            return []
        
        stock_data = data["data"][symbol]
        klines_raw = stock_data.get("qfqday", [])  # 前复权日线
        
        if not klines_raw:
            return []
        
        klines = []
        for item in klines_raw:
            # 腾讯格式：[日期，开盘，收盘，最高，最低，成交量，成交额...]
            if len(item) < 7:
                continue
            
            date_str = item[0]
            try:
                date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                continue
            
            klines.append({
                "code": code,
                "date": date,
                "open": float(item[1]),
                "close": float(item[2]),
                "high": float(item[3]),
                "low": float(item[4]),
                "volume": int(float(item[5])),
                "amount": float(item[6]) if item[6] else 0,
            })
        
        return klines
        
    except Exception as e:
        print(f"  ✗ 获取 {code} 失败：{e}")
        return []


def init_clickhouse():
    """初始化 ClickHouse 表"""
    client = Client(host=CK_HOST, database=CK_DATABASE, user=CK_USER)
    
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
    print("A 股历史数据录入 - 腾讯财经 API")
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
    print("数据源：腾讯财经（前复权）")
    print("这可能需要几分钟时间...\n")
    
    count = 0
    total_lines = 0
    
    for i, code in enumerate(STOCK_CODES):
        print(f"[{i+1}/{len(STOCK_CODES)}] 录入 {code}...")
        
        klines = get_kline(code, count=500)
        
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
