"""
双均线交叉策略

策略逻辑:
- 金叉（短均线上穿长均线）：买入
- 死叉（短均线下穿长均线）：卖出

参数:
- short_window: 短周期均线窗口（默认 5）
- long_window: 长周期均线窗口（默认 20）
"""
from typing import List
import pandas as pd

from strategy.base import BaseStrategy, Signal, SignalType


class MACrossStrategy(BaseStrategy):
    """双均线交叉策略"""
    
    name = "MA_Cross"
    description = "双均线交叉策略：金叉买入，死叉卖出"
    author = "Quant System"
    version = "1.0.0"
    
    params = {
        "short_window": 5,   # 短周期
        "long_window": 20,   # 长周期
    }
    
    def generate_signals(self, data: pd.DataFrame) -> List[Signal]:
        """
        生成交易信号
        
        基于双均线交叉：
        - 金叉：short_ma 上穿 long_ma → BUY
        - 死叉：short_ma 下穿 long_ma → SELL
        """
        signals = []
        
        short_window = self.params.get("short_window", 5)
        long_window = self.params.get("long_window", 20)
        
        # 计算均线
        data = data.copy()
        data["short_ma"] = data["close"].rolling(window=short_window).mean()
        data["long_ma"] = data["close"].rolling(window=long_window).mean()
        
        # 检测交叉
        data["ma_diff"] = data["short_ma"] - data["long_ma"]
        data["ma_diff_prev"] = data["ma_diff"].shift(1)
        
        for i in range(1, len(data)):
            row = data.iloc[i]
            prev_row = data.iloc[i - 1]
            
            # 跳过数据不足的早期
            if pd.isna(row["short_ma"]) or pd.isna(row["long_ma"]):
                continue
            
            code = row["code"]
            date = row["date"]
            price = row["close"]
            
            # 金叉：之前 diff < 0，现在 diff > 0
            if prev_row["ma_diff"] < 0 and row["ma_diff"] > 0:
                signals.append(Signal(
                    code=code,
                    date=date,
                    signal_type=SignalType.BUY,
                    price=price,
                    reason=f"金叉：{short_window}MA 上穿 {long_window}MA",
                ))
            
            # 死叉：之前 diff > 0，现在 diff < 0
            elif prev_row["ma_diff"] > 0 and row["ma_diff"] < 0:
                signals.append(Signal(
                    code=code,
                    date=date,
                    signal_type=SignalType.SELL,
                    price=price,
                    reason=f"死叉：{short_window}MA 下穿 {long_window}MA",
                ))
        
        return signals
