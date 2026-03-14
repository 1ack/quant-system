"""
数据模型定义

ClickHouse: 存储 K 线、分时等时序数据
MySQL: 存储股票列表、策略、回测结果等关系型数据
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class StockInfo:
    """股票基本信息（MySQL）"""
    code: str          # 股票代码，如 000001
    name: str          # 股票名称
    market: str        # 市场：SH/SZ
    industry: Optional[str] = None  # 行业
    list_date: Optional[datetime] = None  # 上市日期


@dataclass
class KLine:
    """K 线数据（ClickHouse）"""
    code: str          # 股票代码
    date: datetime     # 日期
    open: float        # 开盘价
    high: float        # 最高价
    low: float         # 最低价
    close: float       # 收盘价
    volume: int        # 成交量（手）
    amount: float      # 成交额（元）
    
    def to_tuple(self) -> tuple:
        """转换为 ClickHouse 插入用的元组"""
        return (
            self.code,
            self.date,
            self.open,
            self.high,
            self.low,
            self.close,
            self.volume,
            self.amount,
        )


@dataclass
class AdjustedKLine:
    """复权 K 线数据（ClickHouse）"""
    code: str
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float
    adj_factor: float  # 复权因子
    adj_type: str      # forward/backward/none


@dataclass
class TradeRecord:
    """交易记录（MySQL）"""
    id: Optional[int]
    strategy_id: int
    code: str
    trade_date: datetime
    direction: str     # buy/sell
    price: float
    volume: int
    amount: float
    commission: float
    created_at: datetime


@dataclass
class BacktestResult:
    """回测结果（MySQL）"""
    id: Optional[int]
    strategy_id: int
    strategy_name: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    total_return: float      # 总收益率
    annual_return: float     # 年化收益
    sharpe_ratio: float      # 夏普比率
    max_drawdown: float      # 最大回撤
    win_rate: float          # 胜率
    total_trades: int        # 总交易次数
    created_at: datetime
