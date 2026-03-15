"""
数据库连接管理
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clickhouse_driver import Client
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .settings import settings


def get_clickhouse_client() -> Client:
    """获取 ClickHouse 客户端"""
    return Client(
        host=settings.clickhouse.host,
        port=settings.clickhouse.port,
        database=settings.clickhouse.database,
        user=settings.clickhouse.user,
        password=settings.clickhouse.password,
    )


def get_mysql_engine():
    """获取 MySQL 引擎"""
    url = f"mysql+pymysql://{settings.mysql.user}:{settings.mysql.password}@{settings.mysql.host}:{settings.mysql.port}/{settings.mysql.database}"
    return create_engine(url, echo=False)


def get_mysql_session():
    """获取 MySQL 会话"""
    engine = get_mysql_engine()
    Session = sessionmaker(bind=engine)
    return Session()


__all__ = ["get_clickhouse_client", "get_mysql_engine", "get_mysql_session"]
