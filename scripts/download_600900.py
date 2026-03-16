#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
下载长江电力 (600900) 数据
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from datetime import datetime
from clickhouse_driver import Client
from data.storage import DataStorage
from data.models import KLine

# 新浪财经 K 线 API
SINA_KLINE_URL = "http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData/getKLineData"

def get_kline_sina(code: str, count: int = 500):
    """从新浪财经获取 K 线数据"""
    market = "sh" if code[0] == '6' else "sz"
    symbol = f"{market}{code}"
    
    params = {
        "symbol": symbol,
        "scale": "240",  # 日线
        "datalen": str(count),
    }
    
    try:
        resp = requests.get(SINA_KLINE_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        
        if not data or not isinstance(data, list):
            return []
        
        klines = []
        for item in data:
            if not isinstance(item, dict):
                continue
            
            date_str = item.get("day", "")
            try:
                date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                continue
            
            try:
                open_price = float(item.get("open", 0))
                close_price = float(item.get("close", 0))
                if open_price == 0 or close_price == 0:
                    continue
            except (ValueError, TypeError):
                continue
            
            klines.append(KLine(
                code=code,
                date=date,
                open=open_price,
                close=close_price,
                high=float(item.get("high", open_price)),
                low=float(item.get("low", open_price)),
                volume=int(item.get("volume", 0)),
                amount=float(item.get("amount", 0)),
            ))
        
        return klines
        
    except Exception as e:
        print(f"获取 {code} 失败：{e}")
        return []


def main():
    print("=" * 60)
    print("下载长江电力 (600900) 数据")
    print("=" * 60)
    
    # 初始化 ClickHouse
    storage = DataStorage()
    storage.init_clickhouse_tables()
    
    # 下载数据
    print("\n下载长江电力 (600900) 历史数据...")
    klines = get_kline_sina("600900", count=500)
    
    if klines:
        # 过滤近 6 个月
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=180)
        recent = [k for k in klines if k.date >= cutoff]
        
        if recent:
            storage.save_klines(recent)
            print(f"✓ 成功保存 {len(recent)} 条 K 线数据")
            print(f"  日期范围：{min(k.date for k in recent)} 至 {max(k.date for k in recent)}")
        else:
            print("⚠ 无近 6 个月数据")
    else:
        print("✗ 下载失败")
    
    storage.close()
    
    # 验证
    print("\n验证数据...")
    client = Client(host='localhost', database='quant')
    result = client.execute("""
        SELECT count(), max(date), min(date)
        FROM kline_daily
        WHERE code = '600900'
    """)
    if result and result[0][0] > 0:
        print(f"✓ ClickHouse 中有 {result[0][0]} 条数据")
        print(f"  日期范围：{result[0][2]} 至 {result[0][1]}")
    else:
        print("✗ ClickHouse 中无数据")
    
    client.disconnect()
    print("\n✅ 完成")


if __name__ == "__main__":
    main()
