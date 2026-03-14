"""
数据存储模块

ClickHouse: K 线等时序数据
MySQL: 股票列表、策略、回测结果
"""
from datetime import datetime
from typing import List, Optional
from loguru import logger

from .models import KLine, StockInfo, BacktestResult, TradeRecord
from ..config import get_clickhouse_client, get_mysql_session


class DataStorage:
    """数据存储管理器"""
    
    # ClickHouse 表名
    CK_TABLE_KLINE = "kline_daily"
    CK_TABLE_KLINE_ADJ = "kline_adjusted"
    
    def __init__(self):
        self.ck_client = None
        self.mysql_session = None
    
    def _ensure_ck(self):
        """确保 ClickHouse 连接"""
        if self.ck_client is None:
            self.ck_client = get_clickhouse_client()
    
    def _ensure_mysql(self):
        """确保 MySQL 连接"""
        if self.mysql_session is None:
            self.mysql_session = get_mysql_session()
    
    def init_clickhouse_tables(self):
        """初始化 ClickHouse 表"""
        self._ensure_ck()
        
        # K 线日线表
        self.ck_client.execute("""
            CREATE TABLE IF NOT EXISTS kline_daily (
                code String,
                date Date,
                open Float32,
                high Float32,
                low Float32,
                close Float32,
                volume UInt32,
                amount Float64
            ) ENGINE = MergeTree()
            PARTITION BY toYYYYMM(date)
            ORDER BY (code, date)
            SETTINGS index_granularity = 8192
        """)
        
        # 复权 K 线表
        self.ck_client.execute("""
            CREATE TABLE IF NOT EXISTS kline_adjusted (
                code String,
                date Date,
                open Float32,
                high Float32,
                low Float32,
                close Float32,
                volume UInt32,
                amount Float64,
                adj_factor Float32,
                adj_type String
            ) ENGINE = MergeTree()
            PARTITION BY toYYYYMM(date)
            ORDER BY (code, date)
            SETTINGS index_granularity = 8192
        """)
        
        logger.info("ClickHouse 表初始化完成")
    
    def save_klines(self, klines: List[KLine]):
        """保存 K 线数据到 ClickHouse"""
        self._ensure_ck()
        
        if not klines:
            return
        
        data = [k.to_tuple() for k in klines]
        
        self.ck_client.execute(
            f"INSERT INTO {self.CK_TABLE_KLINE} VALUES",
            data,
        )
        
        logger.debug(f"保存 {len(klines)} 条 K 线到 ClickHouse")
    
    def get_klines(self, code: str, start_date: datetime = None, 
                   end_date: datetime = None) -> List[KLine]:
        """从 ClickHouse 获取 K 线数据"""
        self._ensure_ck()
        
        where_clauses = ["code = %(code)s"]
        params = {"code": code}
        
        if start_date:
            where_clauses.append("date >= %(start_date)s")
            params["start_date"] = start_date
        
        if end_date:
            where_clauses.append("date <= %(end_date)s")
            params["end_date"] = end_date
        
        where_sql = " AND ".join(where_clauses)
        
        result = self.ck_client.execute(
            f"""
            SELECT code, date, open, high, low, close, volume, amount
            FROM {self.CK_TABLE_KLINE}
            WHERE {where_sql}
            ORDER BY date
            """,
            params,
        )
        
        return [
            KLine(
                code=row[0],
                date=row[1],
                open=float(row[2]),
                high=float(row[3]),
                low=float(row[4]),
                close=float(row[5]),
                volume=int(row[6]),
                amount=float(row[7]),
            )
            for row in result
        ]
    
    def get_last_kline_date(self, code: str) -> Optional[datetime]:
        """获取某股票最后一条 K 线日期"""
        self._ensure_ck()
        
        result = self.ck_client.execute(
            f"""
            SELECT max(date)
            FROM {self.CK_TABLE_KLINE}
            WHERE code = %(code)s
            """,
            {"code": code},
        )
        
        if result and result[0][0]:
            return result[0][0]
        return None
    
    def save_stock_info(self, stocks: List[StockInfo]):
        """保存股票信息到 MySQL"""
        self._ensure_mysql()
        
        from sqlalchemy import text
        
        for stock in stocks:
            self.mysql_session.execute(
                text("""
                INSERT INTO stock_info (code, name, market, industry, list_date)
                VALUES (:code, :name, :market, :industry, :list_date)
                ON DUPLICATE KEY UPDATE
                    name = VALUES(name),
                    market = VALUES(market)
                """),
                {
                    "code": stock.code,
                    "name": stock.name,
                    "market": stock.market,
                    "industry": stock.industry,
                    "list_date": stock.list_date,
                },
            )
        
        self.mysql_session.commit()
        logger.info(f"保存 {len(stocks)} 只股票信息到 MySQL")
    
    def save_backtest_result(self, result: BacktestResult) -> int:
        """保存回测结果到 MySQL"""
        self._ensure_mysql()
        
        from sqlalchemy import text
        
        cursor = self.mysql_session.execute(
            text("""
            INSERT INTO backtest_result 
            (strategy_id, strategy_name, start_date, end_date, initial_capital,
             final_capital, total_return, annual_return, sharpe_ratio, 
             max_drawdown, win_rate, total_trades, created_at)
            VALUES 
            (:strategy_id, :strategy_name, :start_date, :end_date, :initial_capital,
             :final_capital, :total_return, :annual_return, :sharpe_ratio,
             :max_drawdown, :win_rate, :total_trades, :created_at)
            """),
            {
                "strategy_id": result.strategy_id,
                "strategy_name": result.strategy_name,
                "start_date": result.start_date,
                "end_date": result.end_date,
                "initial_capital": result.initial_capital,
                "final_capital": result.final_capital,
                "total_return": result.total_return,
                "annual_return": result.annual_return,
                "sharpe_ratio": result.sharpe_ratio,
                "max_drawdown": result.max_drawdown,
                "win_rate": result.win_rate,
                "total_trades": result.total_trades,
                "created_at": result.created_at or datetime.now(),
            },
        )
        
        self.mysql_session.commit()
        return cursor.lastrowid
    
    def close(self):
        """关闭连接"""
        if self.ck_client:
            self.ck_client.disconnect()
        if self.mysql_session:
            self.mysql_session.close()
