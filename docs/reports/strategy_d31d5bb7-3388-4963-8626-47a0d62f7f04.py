from strategy.base import BaseStrategy, Signal, SignalType
class SimpleStrategy(BaseStrategy):
    name="Simple"
    def generate_signals(self, df):
        if len(df) < 20: return []
        ma5 = df["close"].rolling(5).mean().iloc[-1]
        ma10 = df["close"].rolling(10).mean().iloc[-1]
        prev_ma5 = df["close"].rolling(5).mean().iloc[-2]
        prev_ma10 = df["close"].rolling(10).mean().iloc[-2]
        signals = []
        if prev_ma5 <= prev_ma10 and ma5 > ma10:
            signals.append(Signal(SignalType.BUY, df.index[-1], df["close"].iloc[-1]))
        elif prev_ma5 >= prev_ma10 and ma5 < ma10:
            signals.append(Signal(SignalType.SELL, df.index[-1], df["close"].iloc[-1]))
        return signals