#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A 股历史数据录入脚本

从新浪财经 API 获取近两年 A 股数据并存储到 ClickHouse
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from data.ingest import DataIngestor
from data.storage import DataStorage


def main():
    print("=" * 60)
    print("A 股历史数据录入")
    print("=" * 60)
    
    # 初始化
    ingestor = DataIngestor()
    storage = DataStorage()
    
    # 初始化 ClickHouse 表
    print("\n初始化 ClickHouse 数据表...")
    storage.init_clickhouse_tables()
    print("✓ ClickHouse 表已创建")
    
    # 录入数据
    start_date = datetime(2024, 1, 1)
    print(f"\n开始录入数据，起始日期：{start_date.strftime('%Y-%m-%d')}")
    print("这可能需要几分钟时间...\n")
    
    # 录入部分成分股作为测试
    test_codes = [
        "000001",  # 平安银行
        "000002",  # 万科 A
        "000063",  # 中兴通讯
        "000333",  # 美的集团
        "000651",  # 格力电器
        "000858",  # 五粮液
        "002415",  # 海康威视
        "002594",  # 比亚迪
        "600000",  # 浦发银行
        "600009",  # 上海机场
        "600016",  # 民生银行
        "600028",  # 中国石化
        "600030",  # 中信证券
        "600031",  # 三一重工
        "600036",  # 招商银行
        "600048",  # 保利地产
        "600050",  # 中国联通
        "600104",  # 上汽集团
        "600276",  # 恒瑞医药
        "600346",  # 恒力石化
        "600519",  # 贵州茅台
        "600585",  # 海螺水泥
        "600690",  # 海尔智家
        "600809",  # 山西汾酒
        "600887",  # 伊利股份
        "600900",  # 长江电力
        "601012",  # 隆基股份
        "601088",  # 中国神华
        "601166",  # 兴业银行
        "601288",  # 农业银行
        "601318",  # 中国平安
        "601398",  # 工商银行
        "601668",  # 中国建筑
        "601688",  # 华泰证券
        "601857",  # 中国石油
        "601888",  # 中国中免
        "603259",  # 药明康德
        "603288",  # 海天味业
    ]
    
    count = 0
    total = len(test_codes)
    
    for i, code in enumerate(test_codes):
        try:
            print(f"[{i+1}/{total}] 录入 {code}...")
            klines = ingestor.get_kline(code, start_date=start_date)
            
            if klines:
                storage.save_klines(klines)
                count += 1
                print(f"  ✓ 成功录入 {len(klines)} 条数据")
            else:
                print(f"  ⚠ 无数据")
        except Exception as e:
            print(f"  ✗ 失败：{e}")
    
    print("\n" + "=" * 60)
    print(f"数据录入完成！")
    print(f"成功：{count}/{total} 只股票")
    print("=" * 60)
    
    # 验证数据
    print("\n验证数据...")
    for code in ["000001", "600519", "601318"]:
        klines = storage.get_klines(code)
        if klines:
            print(f"{code}: {len(klines)} 条数据，最新日期 {klines[0].date}")
    
    storage.close()


if __name__ == "__main__":
    main()
