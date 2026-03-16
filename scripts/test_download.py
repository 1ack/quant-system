#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试下载脚本 - 调试用
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import requests
import time
from datetime import datetime, timedelta
from typing import List, Dict
from loguru import logger
from data.storage import DataStorage
from data.models import KLine

TENCENT_KLINE_URL = "http://web.ifzq.gtimg.cn/appstock/app/fqkline/get"


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
            logger.debug(f"{code}: No data in response")
            return []
        
        stock_data = data["data"][symbol]
        klines_raw = stock_data.get("qfqday", [])
        
        if not klines_raw:
            logger.debug(f"{code}: No qfqday data")
            return []
        
        klines = []
        for item in klines_raw:
            # 检查数据格式
            if not isinstance(item, (list, tuple)) or len(item) < 6:
                continue
            
            # 检查每个元素是否为基本类型
            try:
                date_str = str(item[0])
                # 跳过包含字典的数据行（检查所有元素）
                if any(isinstance(x, dict) for x in item):
                    logger.debug(f"{code}: Skipping row with dict: {item}")
                    continue
            except (TypeError, AttributeError) as e:
                logger.debug(f"{code}: Date parse error: {e}")
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
            except (ValueError, TypeError) as e:
                logger.debug(f"{code}: Price parse error: {e}, item[1]={item[1]} ({type(item[1]).__name__})")
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
        logger.error(f"  获取 {code} 异常：{e}")
        logger.error(f"  Traceback: {traceback.format_exc()}")
        return []


def main():
    logger.add(sys.stdout, level="DEBUG", 
               format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")
    
    # 测试几只股票
    test_codes = ["600000", "600004", "600022", "600023", "000001", "000002"]
    
    storage = DataStorage()
    storage.init_clickhouse_tables()
    
    for code in test_codes:
        logger.info(f"\nTesting {code}...")
        klines = get_kline_tencent(code, count=500)
        
        if klines:
            logger.info(f"  ✓ Got {len(klines)} klines")
            
            # 保存到数据库
            cutoff_date = datetime.now() - timedelta(days=730)
            recent_klines = [k for k in klines if k.date >= cutoff_date]
            
            if recent_klines:
                storage.save_klines(recent_klines)
                logger.info(f"  ✓ Saved {len(recent_klines)} recent klines")
        else:
            logger.warning(f"  ✗ No data")
        
        time.sleep(0.5)
    
    storage.close()
    logger.info("\n✓ Test complete")


if __name__ == "__main__":
    main()
