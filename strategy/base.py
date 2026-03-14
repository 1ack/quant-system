"""
策略基类

所有策略需继承 BaseStrategy 并实现 generate_signals 方法
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
import pandas as pd


class SignalType(Enum):
    """信号类型"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class Signal:
    """交易信号"""
    code: str
    date: datetime
    signal_type: SignalType
    price: float
    volume: Optional[int] = None  # 建议数量，None 表示由仓位管理决定
    reason: Optional[str] = None  # 信号原因/备注


class BaseStrategy(ABC):
    """策略基类"""
    
    # 策略元信息
    name: str = "BaseStrategy"
    description: str = ""
    author: str = ""
    version: str = "1.0.0"
    
    # 策略参数（可配置）
    params: Dict[str, Any] = {}
    
    def __init__(self, params: Optional[Dict[str, Any]] = None):
        """
        初始化策略
        
        Args:
            params: 策略参数，覆盖默认值
        """
        if params:
            self.params = {**self.params, **params}
    
    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> List[Signal]:
        """
        生成交易信号
        
        Args:
            data: 股票数据，包含 columns:
                  [code, date, open, high, low, close, volume, amount]
        
        Returns:
            信号列表
        """
        pass
    
    def init(self, data: pd.DataFrame):
        """
        策略初始化（可选）
        
        在 generate_signals 之前调用，可用于计算指标等
        
        Args:
            data: 完整的股票数据
        """
        pass
    
    def on_bar(self, bar: pd.Series, signals: List[Signal]) -> Optional[Signal]:
        """
        单根 K 线处理（可选）
        
        用于逐根 K 线生成信号
        
        Args:
            bar: 当前 K 线
            signals: 已生成的信号列表
        
        Returns:
            新信号或 None
        """
        return None
    
    def get_params_info(self) -> str:
        """获取策略参数说明"""
        lines = [f"策略：{self.name}", f"版本：{self.version}"]
        if self.description:
            lines.append(f"说明：{self.description}")
        if self.params:
            lines.append("参数:")
            for k, v in self.params.items():
                lines.append(f"  - {k}: {v}")
        return "\n".join(lines)


class PositionManager:
    """简易仓位管理器"""
    
    def __init__(self, initial_capital: float, max_position: float = 0.95):
        """
        初始化仓位管理
        
        Args:
            initial_capital: 初始资金
            max_position: 最大仓位比例（默认 95%，留 5% 现金）
        """
        self.initial_capital = initial_capital
        self.max_position = max_position
        self.cash = initial_capital
        self.positions: Dict[str, int] = {}  # {code: volume}
        self.position_cost: Dict[str, float] = {}  # {code: avg_cost}
    
    def get_available_cash(self) -> float:
        """获取可用资金"""
        return self.cash
    
    def get_position(self, code: str) -> int:
        """获取某股票持仓"""
        return self.positions.get(code, 0)
    
    def get_total_position_value(self, prices: Dict[str, float]) -> float:
        """计算当前持仓总市值"""
        total = 0
        for code, volume in self.positions.items():
            if volume > 0 and code in prices:
                total += volume * prices[code]
        return total
    
    def can_buy(self, code: str, price: float, volume: int) -> bool:
        """检查是否可以买入"""
        cost = price * volume
        return cost <= self.cash
    
    def can_sell(self, code: str, volume: int) -> bool:
        """检查是否可以卖出"""
        return self.positions.get(code, 0) >= volume
    
    def buy(self, code: str, price: float, volume: int) -> bool:
        """
        买入操作
        
        Returns:
            是否成功
        """
        cost = price * volume
        if cost > self.cash:
            return False
        
        self.cash -= cost
        
        # 更新持仓
        old_volume = self.positions.get(code, 0)
        old_cost = self.position_cost.get(code, 0)
        
        new_volume = old_volume + volume
        new_cost = (old_cost * old_volume + cost) / new_volume if new_volume > 0 else 0
        
        self.positions[code] = new_volume
        self.position_cost[code] = new_cost
        
        return True
    
    def sell(self, code: str, price: float, volume: int) -> bool:
        """
        卖出操作
        
        Returns:
            是否成功
        """
        if self.positions.get(code, 0) < volume:
            return False
        
        self.cash += price * volume
        self.positions[code] -= volume
        
        if self.positions[code] == 0:
            del self.positions[code]
            del self.position_cost[code]
        
        return True
    
    def get_position_summary(self) -> Dict[str, Any]:
        """获取持仓汇总"""
        return {
            "cash": self.cash,
            "positions": dict(self.positions),
            "position_count": len(self.positions),
        }
