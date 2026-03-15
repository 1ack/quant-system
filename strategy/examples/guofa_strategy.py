#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
国发股份 (600538) 简单回测策略

策略：双均线交叉 + RSI 超买超卖过滤
- 金叉 + RSI<30：买入
- 死叉 + RSI>70：卖出
"""
import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from datetime import datetime, timedelta
from typing import List
import pandas as pd

from strategy.base import BaseStrategy, Signal, SignalType


class SimpleMAStrategy(BaseStrategy):
    """国发股份简单均线策略"""
    
    name = "Simple_MA_538"
    description = "国发股份专用：双均线交叉 + RSI 过滤"
    author = "Quant System"
    version = "1.0.0"
    
    params = {
        "short_window": 5,    # 短周期均线
        "long_window": 20,    # 长周期均线
        "rsi_period": 14,     # RSI 周期
        "rsi_oversold": 30,   # RSI 超卖线
        "rsi_overbought": 70, # RSI 超买线
    }
    
    def generate_signals(self, data: pd.DataFrame) -> List[Signal]:
        """生成交易信号"""
        signals = []
        
        if len(data) < self.params["long_window"]:
            return signals
        
        short_window = self.params["short_window"]
        long_window = self.params["long_window"]
        rsi_period = self.params["rsi_period"]
        rsi_oversold = self.params["rsi_oversold"]
        rsi_overbought = self.params["rsi_overbought"]
        
        data = data.copy()
        
        # 计算均线
        data["short_ma"] = data["close"].rolling(window=short_window).mean()
        data["long_ma"] = data["close"].rolling(window=long_window).mean()
        
        # 计算 RSI
        delta = data["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
        rs = gain / loss
        data["rsi"] = 100 - (100 / (1 + rs))
        
        # 检测交叉
        data["ma_diff"] = data["short_ma"] - data["long_ma"]
        data["ma_diff_prev"] = data["ma_diff"].shift(1)
        
        for i in range(1, len(data)):
            row = data.iloc[i]
            prev_row = data.iloc[i - 1]
            
            # 跳过数据不足的早期
            if pd.isna(row["short_ma"]) or pd.isna(row["long_ma"]) or pd.isna(row["rsi"]):
                continue
            
            code = row["code"]
            date = row["date"]
            price = row["close"]
            rsi = row["rsi"]
            
            # 金叉 + RSI 超卖：买入
            if prev_row["ma_diff"] < 0 and row["ma_diff"] > 0 and rsi < rsi_oversold:
                signals.append(Signal(
                    code=str(code),
                    date=pd.Timestamp(date).to_pydatetime(),
                    signal_type=SignalType.BUY,
                    price=float(price),
                    reason=f"金叉+RSI 超卖 (RSI={rsi:.1f})",
                ))
            
            # 死叉 + RSI 超买：卖出
            elif prev_row["ma_diff"] > 0 and row["ma_diff"] < 0 and rsi > rsi_overbought:
                signals.append(Signal(
                    code=str(code),
                    date=pd.Timestamp(date).to_pydatetime(),
                    signal_type=SignalType.SELL,
                    price=float(price),
                    reason=f"死叉+RSI 超买 (RSI={rsi:.1f})",
                ))
        
        return signals


def run_backtest():
    """运行回测"""
    from backtest.engine import BacktestEngine, BacktestConfig
    from data.storage import DataStorage
    
    print("=" * 70)
    print("国发股份 (600538) 策略回测")
    print("=" * 70)
    
    # 配置：最近 2 个月
    end_date = datetime(2026, 3, 13)
    start_date = end_date - timedelta(days=60)
    
    config = BacktestConfig(
        start_date=start_date,
        end_date=end_date,
        initial_capital=100000.0,  # 10 万本金
        commission_rate=0.0003,    # 万三手续费
        slippage_rate=0.001,       # 0.1% 滑点
    )
    
    # 创建引擎
    engine = BacktestEngine(config)
    
    # 创建策略
    strategy = SimpleMAStrategy(params={
        "short_window": 5,
        "long_window": 20,
        "rsi_period": 14,
        "rsi_oversold": 35,   # 稍微放宽超卖线
        "rsi_overbought": 65, # 稍微放宽超买线
    })
    
    # 运行回测
    result = engine.run(strategy, ["600538"])
    
    # 输出结果
    print("\n" + result.summary())
    
    # 输出交易记录
    if result.trades:
        print("\n📋 交易记录:")
        print("-" * 70)
        for i, trade in enumerate(result.trades, 1):
            direction = "买入" if trade.direction == "buy" else "卖出"
            print(f"{i:2d}. {trade.date.strftime('%Y-%m-%d')} {direction} "
                  f"{trade.volume:6d}股 @ {trade.price:6.2f}元 "
                  f"(手续费：{trade.commission:.2f}元)")
    
    # 保存结果
    output_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'backtest_result_538.csv')
    if result.daily_values is not None:
        result.daily_values.to_csv(output_path, index=False)
        print(f"\n💾 详细结果已保存：{output_path}")
    
    return result


if __name__ == "__main__":
    run_backtest()
