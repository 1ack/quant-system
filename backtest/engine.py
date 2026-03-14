"""
回测引擎

核心功能:
- 加载股票数据
- 执行策略信号
- 模拟订单撮合
- 计算绩效指标
"""
from datetime import datetime
from typing import List, Dict, Optional, Type
from dataclasses import dataclass, field
from loguru import logger
import pandas as pd

from strategy.base import BaseStrategy, Signal, SignalType, PositionManager
from data.storage import DataStorage
from .performance import PerformanceAnalyzer


@dataclass
class BacktestConfig:
    """回测配置"""
    start_date: datetime
    end_date: datetime
    initial_capital: float = 1000000.0
    commission_rate: float = 0.0003  # 万三
    slippage_rate: float = 0.001     # 0.1%
    
    # 交易限制
    max_position_per_stock: float = 0.2  # 单只股票最大仓位 20%
    min_trade_volume: int = 100          # 最小交易数量（1 手）


@dataclass
class Trade:
    """成交记录"""
    code: str
    date: datetime
    direction: str  # buy/sell
    price: float
    volume: int
    amount: float
    commission: float
    slippage: float


@dataclass
class BacktestResult:
    """回测结果"""
    strategy_name: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    
    # 绩效指标
    total_return: float = 0.0      # 总收益率
    annual_return: float = 0.0     # 年化收益
    sharpe_ratio: float = 0.0      # 夏普比率
    max_drawdown: float = 0.0      # 最大回撤
    win_rate: float = 0.0          # 胜率
    total_trades: int = 0          # 总交易次数
    
    # 详细数据
    trades: List[Trade] = field(default_factory=list)
    daily_values: pd.DataFrame = None
    
    def summary(self) -> str:
        """输出回测摘要"""
        lines = [
            "=" * 60,
            f"策略：{self.strategy_name}",
            f"区间：{self.start_date.date()} ~ {self.end_date.date()}",
            "=" * 60,
            f"初始资金：{self.initial_capital:,.2f}",
            f"最终资金：{self.final_capital:,.2f}",
            f"总收益率：{self.total_return * 100:.2f}%",
            f"年化收益：{self.annual_return * 100:.2f}%",
            f"夏普比率：{self.sharpe_ratio:.2f}",
            f"最大回撤：{self.max_drawdown * 100:.2f}%",
            f"胜率：{self.win_rate * 100:.2f}%",
            f"总交易：{self.total_trades} 笔",
            "=" * 60,
        ]
        return "\n".join(lines)


class BacktestEngine:
    """回测引擎"""
    
    def __init__(self, config: BacktestConfig):
        """
        初始化回测引擎
        
        Args:
            config: 回测配置
        """
        self.config = config
        self.storage = DataStorage()
        self.position_manager = None
        self.trades: List[Trade] = []
        self.daily_values = []
    
    def run(self, strategy: BaseStrategy, codes: List[str]) -> BacktestResult:
        """
        执行回测
        
        Args:
            strategy: 策略实例
            codes: 股票代码列表
        
        Returns:
            回测结果
        """
        logger.info(f"开始回测：{strategy.name}")
        logger.info(f"股票数量：{len(codes)}")
        logger.info(f"时间区间：{self.config.start_date} ~ {self.config.end_date}")
        
        # 初始化
        self.position_manager = PositionManager(
            self.config.initial_capital,
            max_position=1.0 - self.config.max_position_per_stock,
        )
        self.trades = []
        self.daily_values = []
        
        # 加载所有股票数据
        all_data = {}
        for code in codes:
            klines = self.storage.get_klines(
                code,
                start_date=self.config.start_date,
                end_date=self.config.end_date,
            )
            if klines:
                df = pd.DataFrame([
                    {
                        "code": k.code,
                        "date": k.date,
                        "open": k.open,
                        "high": k.high,
                        "low": k.low,
                        "close": k.close,
                        "volume": k.volume,
                        "amount": k.amount,
                    }
                    for k in klines
                ])
                all_data[code] = df
        
        if not all_data:
            raise ValueError("未找到任何股票数据")
        
        # 策略初始化
        strategy.init(pd.concat(all_data.values(), ignore_index=True))
        
        # 获取所有交易日期
        all_dates = sorted(set(
            df["date"].unique()
            for df in all_data.values()
        ))
        all_dates = pd.to_datetime(all_dates).unique()
        all_dates = sorted(all_dates)
        
        # 逐日回测
        current_date_idx = 0
        for date in all_dates:
            current_date_idx += 1
            if current_date_idx % 250 == 0:
                logger.info(f"回测进度：{current_date_idx}/{len(all_dates)} 交易日")
            
            # 获取当日数据
            day_data = {}
            for code, df in all_data.items():
                day_df = df[df["date"] == date]
                if len(day_df) > 0:
                    day_data[code] = day_df
            
            if not day_data:
                continue
            
            # 为每只股票生成信号
            for code, df in day_data.items():
                signals = strategy.generate_signals(df)
                
                # 执行信号
                for signal in signals:
                    if signal.date != date:
                        continue
                    
                    self._execute_signal(signal, df.iloc[-1])
            
            # 记录当日净值
            prices = {code: df.iloc[-1]["close"] for code, df in day_data.items()}
            daily_value = self._calculate_daily_value(prices)
            self.daily_values.append({
                "date": date,
                "cash": self.position_manager.cash,
                "position_value": daily_value["position_value"],
                "total_value": daily_value["total_value"],
            })
        
        # 计算绩效
        result = self._calculate_performance(strategy.name)
        
        logger.info(f"回测完成")
        logger.info(result.summary())
        
        return result
    
    def _execute_signal(self, signal: Signal, bar: pd.Series):
        """执行交易信号"""
        code = signal.code
        price = signal.price
        direction = signal.signal_type.value
        
        if direction == "buy":
            self._execute_buy(code, price, bar)
        elif direction == "sell":
            self._execute_sell(code, price, bar)
    
    def _execute_buy(self, code: str, price: float, bar: pd.Series):
        """执行买入"""
        # 计算可买数量
        available_cash = self.position_manager.get_available_cash()
        max_buy_value = available_cash * (1 - self.position_manager.get_total_position_value(
            {code: price}
        ) / self.config.initial_capital)
        
        # 考虑滑点和手续费
        actual_price = price * (1 + self.config.slippage_rate)
        
        # 计算最大可买股数（考虑最小交易单位）
        max_volume = int(max_buy_value / actual_price / 100) * 100
        max_volume = max(max_volume, 0)
        
        if max_volume < self.config.min_trade_volume:
            return
        
        # 执行买入
        volume = max_volume
        amount = volume * actual_price
        commission = amount * self.config.commission_rate
        
        if self.position_manager.buy(code, actual_price, volume):
            self.trades.append(Trade(
                code=code,
                date=bar["date"],
                direction="buy",
                price=actual_price,
                volume=volume,
                amount=amount,
                commission=commission,
                slippage=volume * (actual_price - price),
            ))
            logger.debug(f"买入 {code}: {volume}股 @ {actual_price:.2f}")
    
    def _execute_sell(self, code: str, price: float, bar: pd.Series):
        """执行卖出"""
        position = self.position_manager.get_position(code)
        if position <= 0:
            return
        
        # 考虑滑点
        actual_price = price * (1 - self.config.slippage_rate)
        
        # 执行卖出
        amount = position * actual_price
        commission = amount * self.config.commission_rate
        
        if self.position_manager.sell(code, actual_price, position):
            self.trades.append(Trade(
                code=code,
                date=bar["date"],
                direction="sell",
                price=actual_price,
                volume=position,
                amount=amount,
                commission=commission,
                slippage=position * (price - actual_price),
            ))
            logger.debug(f"卖出 {code}: {position}股 @ {actual_price:.2f}")
    
    def _calculate_daily_value(self, prices: Dict[str, float]) -> Dict[str, float]:
        """计算当日净值"""
        position_value = self.position_manager.get_total_position_value(prices)
        cash = self.position_manager.cash
        return {
            "position_value": position_value,
            "cash": cash,
            "total_value": position_value + cash,
        }
    
    def _calculate_performance(self, strategy_name: str) -> BacktestResult:
        """计算绩效指标"""
        if not self.daily_values:
            raise ValueError("无回测数据")
        
        df = pd.DataFrame(self.daily_values)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        
        # 计算收益率序列
        df["daily_return"] = df["total_value"].pct_change()
        
        # 绩效分析器
        analyzer = PerformanceAnalyzer(df)
        
        return BacktestResult(
            strategy_name=strategy_name,
            start_date=self.config.start_date,
            end_date=self.config.end_date,
            initial_capital=self.config.initial_capital,
            final_capital=df["total_value"].iloc[-1],
            total_return=analyzer.total_return(),
            annual_return=analyzer.annual_return(),
            sharpe_ratio=analyzer.sharpe_ratio(),
            max_drawdown=analyzer.max_drawdown(),
            win_rate=analyzer.win_rate(),
            total_trades=len(self.trades),
            trades=self.trades,
            daily_values=df,
        )


if __name__ == "__main__":
    import argparse
    from strategy.examples import MACrossStrategy
    
    parser = argparse.ArgumentParser(description="回测引擎")
    parser.add_argument("--strategy", type=str, default="ma_cross", help="策略名称")
    parser.add_argument("--start", type=str, required=True, help="开始日期 (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, required=True, help="结束日期 (YYYY-MM-DD)")
    parser.add_argument("--code", type=str, action="append", help="股票代码（可多个）")
    parser.add_argument("--capital", type=float, default=1000000, help="初始资金")
    
    args = parser.parse_args()
    
    # 配置
    config = BacktestConfig(
        start_date=datetime.strptime(args.start, "%Y-%m-%d"),
        end_date=datetime.strptime(args.end, "%Y-%m-%d"),
        initial_capital=args.capital,
    )
    
    # 引擎
    engine = BacktestEngine(config)
    
    # 策略
    strategy = MACrossStrategy()
    
    # 股票代码
    codes = args.code or ["000001", "600000", "601318"]
    
    # 运行回测
    result = engine.run(strategy, codes)
    print(result.summary())
