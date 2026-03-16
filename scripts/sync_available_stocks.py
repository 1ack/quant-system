#!/usr/bin/env python3
"""
同步 ClickHouse 中的股票数据到 PostgreSQL available_stocks 表
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from clickhouse_driver import Client
from sqlalchemy import create_engine, text
from datetime import datetime


def sync_available_stocks():
    """同步股票数据"""
    # ClickHouse 连接
    ck_client = Client(
        host='localhost',
        port=9000,
        database='quant',
        user='default',
        password='',
    )
    
    # PostgreSQL 连接
    pg_engine = create_engine("postgresql+psycopg2://postgres:admin%40123@localhost:5432/quant")
    
    print("从 ClickHouse 查询股票数据...")
    
    # 查询每个股票的数据量和日期范围
    result = ck_client.execute("""
        SELECT 
            code,
            count() as kline_count,
            min(date) as data_start,
            max(date) as data_end
        FROM kline_daily
        GROUP BY code
        ORDER BY code
    """)
    
    print(f"找到 {len(result)} 只股票")
    
    # 简单的股票名称映射（实际应该从交易所 API 获取）
    stock_names = {
        "600900": "长江电力",
        "600538": "国发股份",
        "600519": "贵州茅台",
        "601318": "中国平安",
        "600036": "招商银行",
        "600000": "浦发银行",
        "000002": "万科 A",
        "000001": "平安银行",
    }
    
    inserted = 0
    updated = 0
    
    with pg_engine.connect() as conn:
        for row in result:
            code, kline_count, data_start, data_end = row
            
            # 确定市场
            market = "SH" if code.startswith("6") else "SZ"
            
            # 获取股票名称
            name = stock_names.get(code, f"股票{code}")
            
            # 插入或更新
            try:
                conn.execute(
                    text("""
                    INSERT INTO available_stocks (code, name, market, data_start, data_end, kline_count, updated_at)
                    VALUES (:code, :name, :market, :data_start, :data_end, :kline_count, NOW())
                    ON CONFLICT (code) DO UPDATE SET
                        name = EXCLUDED.name,
                        market = EXCLUDED.market,
                        data_start = EXCLUDED.data_start,
                        data_end = EXCLUDED.data_end,
                        kline_count = EXCLUDED.kline_count,
                        updated_at = NOW()
                    """),
                    {
                        "code": code,
                        "name": name,
                        "market": market,
                        "data_start": data_start,
                        "data_end": data_end,
                        "kline_count": kline_count,
                    }
                )
                
                inserted += 1
                if inserted % 100 == 0:
                    print(f"已处理 {inserted} 只股票...")
                    
            except Exception as e:
                print(f"处理股票 {code} 失败：{e}")
        
        conn.commit()
    
    print(f"同步完成！共处理 {inserted} 只股票")


if __name__ == "__main__":
    sync_available_stocks()
