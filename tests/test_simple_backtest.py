#!/usr/bin/env python3
"""
简单回测测试 - 直接使用回测引擎
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime
from backtest.engine import BacktestEngine, BacktestConfig
from strategy.base import BaseStrategy, Signal, SignalType
import pandas as pd

# 简单策略：第一天买入，最后一天卖出
class SimpleStrategy(BaseStrategy):
    """简单买卖策略"""
    
    name = "SimpleBuySell"
    bought = False
    
    def init(self, data: pd.DataFrame):
        """初始化，记录第一个和最后一个日期"""
        self.first_date = data["date"].min()
        self.last_date = data["date"].max()
        print(f"策略初始化：数据范围 {self.first_date} 至 {self.last_date}")
    
    def generate_signals(self, df: pd.DataFrame) -> list:
        signals = []
        
        code = df["code"].iloc[0]
        date = df["date"].iloc[0]
        price = df["close"].iloc[0]
        
        # 第一天买入
        if date == self.first_date and not self.bought:
            signals.append(Signal(
                code=code,
                date=date,
                signal_type=SignalType.BUY,
                price=price,
            ))
            self.bought = True
            print(f"买入信号：{code} @ {price:.2f} ({date})")
        
        # 最后一天卖出
        elif date == self.last_date and self.bought:
            signals.append(Signal(
                code=code,
                date=date,
                signal_type=SignalType.SELL,
                price=price,
            ))
            print(f"卖出信号：{code} @ {price:.2f} ({date})")
        
        return signals

def test_simple_backtest():
    """测试简单回测"""
    print("测试简单买卖策略回测...\n")
    
    # 配置
    config = BacktestConfig(
        start_date=datetime(2026, 1, 1),
        end_date=datetime(2026, 3, 13),
        initial_capital=1000000.0,
        commission_rate=0.0003,
        slippage_rate=0.001,
    )
    
    # 引擎
    engine = BacktestEngine(config)
    
    # 策略
    strategy = SimpleStrategy()
    
    # 股票代码
    codes = ["600900"]
    
    try:
        # 运行回测
        result = engine.run(strategy, codes)
        
        print("\n" + result.summary())
        
        print(f"\n交易明细:")
        for trade in result.trades:
            print(f"  {trade.date}: {trade.direction.upper()} {trade.code} {trade.volume}股 @ {trade.price:.2f} (金额：{trade.amount:.2f})")
        
        return True
        
    except Exception as e:
        print(f"回测失败：{e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_simple_backtest()
    exit(0 if success else 1)
