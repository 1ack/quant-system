"""
绩效分析模块

计算各类量化绩效指标
"""
import pandas as pd
import numpy as np
from typing import Optional


class PerformanceAnalyzer:
    """绩效分析器"""
    
    def __init__(self, daily_values: pd.DataFrame):
        """
        初始化分析器
        
        Args:
            daily_values: 包含 date, total_value 列的 DataFrame
        """
        self.df = daily_values.copy()
        self.df = self.df.sort_values("date").reset_index(drop=True)
        
        if "daily_return" not in self.df.columns:
            self.df["daily_return"] = self.df["total_value"].pct_change()
    
    def total_return(self) -> float:
        """总收益率"""
        if len(self.df) < 2:
            return 0.0
        
        initial = self.df["total_value"].iloc[0]
        final = self.df["total_value"].iloc[-1]
        
        return (final - initial) / initial
    
    def annual_return(self, trading_days_per_year: int = 252) -> float:
        """年化收益率"""
        total_return = self.total_return()
        
        if len(self.df) < 2:
            return 0.0
        
        # 计算交易天数
        days = (self.df["date"].iloc[-1] - self.df["date"].iloc[0]).days
        
        if days <= 0:
            return 0.0
        
        years = days / trading_days_per_year
        
        if years <= 0:
            return 0.0
        
        return (1 + total_return) ** (1 / years) - 1
    
    def volatility(self, annualize: bool = True) -> float:
        """波动率"""
        returns = self.df["daily_return"].dropna()
        
        if len(returns) < 2:
            return 0.0
        
        vol = returns.std()
        
        if annualize:
            vol *= np.sqrt(252)
        
        return vol
    
    def sharpe_ratio(self, risk_free_rate: float = 0.03) -> float:
        """
        夏普比率
        
        Args:
            risk_free_rate: 无风险利率（年化，默认 3%）
        """
        excess_return = self.annual_return() - risk_free_rate
        vol = self.volatility(annualize=True)
        
        if vol == 0:
            return 0.0
        
        return excess_return / vol
    
    def max_drawdown(self) -> float:
        """最大回撤"""
        values = self.df["total_value"].values
        
        if len(values) < 2:
            return 0.0
        
        # 计算累计最大值
        cummax = np.maximum.accumulate(values)
        
        # 计算回撤
        drawdown = (values - cummax) / cummax
        
        return abs(drawdown.min())
    
    def win_rate(self) -> float:
        """胜率（盈利交易占比）"""
        returns = self.df["daily_return"].dropna()
        
        if len(returns) == 0:
            return 0.0
        
        wins = (returns > 0).sum()
        return wins / len(returns)
    
    def calmar_ratio(self) -> float:
        """Calmar 比率（年化收益 / 最大回撤）"""
        annual_return = self.annual_return()
        max_dd = self.max_drawdown()
        
        if max_dd == 0:
            return 0.0
        
        return annual_return / max_dd
    
    def sortino_ratio(self, risk_free_rate: float = 0.03) -> float:
        """
        Sortino 比率（只考虑下行波动）
        """
        returns = self.df["daily_return"].dropna()
        
        if len(returns) < 2:
            return 0.0
        
        excess_return = self.annual_return() - risk_free_rate
        
        # 下行标准差
        downside_returns = returns[returns < 0]
        if len(downside_returns) == 0:
            return float('inf') if excess_return > 0 else 0.0
        
        downside_std = downside_returns.std() * np.sqrt(252)
        
        if downside_std == 0:
            return 0.0
        
        return excess_return / downside_std
    
    def summary(self) -> dict:
        """绩效摘要"""
        return {
            "total_return": self.total_return(),
            "annual_return": self.annual_return(),
            "volatility": self.volatility(),
            "sharpe_ratio": self.sharpe_ratio(),
            "max_drawdown": self.max_drawdown(),
            "win_rate": self.win_rate(),
            "calmar_ratio": self.calmar_ratio(),
            "sortino_ratio": self.sortino_ratio(),
        }
    
    def summary_str(self) -> str:
        """绩效摘要（字符串格式）"""
        s = self.summary()
        lines = [
            "绩效指标:",
            f"  总收益率：  {s['total_return'] * 100:.2f}%",
            f"  年化收益：  {s['annual_return'] * 100:.2f}%",
            f"  波动率：    {s['volatility'] * 100:.2f}%",
            f"  夏普比率：  {s['sharpe_ratio']:.2f}",
            f"  最大回撤：  {s['max_drawdown'] * 100:.2f}%",
            f"  胜率：      {s['win_rate'] * 100:.2f}%",
            f"  Calmar 比率：{s['calmar_ratio']:.2f}",
            f"  Sortino 比率：{s['sortino_ratio']:.2f}",
        ]
        return "\n".join(lines)
