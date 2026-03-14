"""
系统配置管理

使用环境变量或 .env 文件覆盖默认配置
"""
import os
from pydantic import BaseModel
from typing import Optional


class ClickHouseConfig(BaseModel):
    host: str = "localhost"
    port: int = 9000
    database: str = "quant"
    user: str = "default"
    password: str = ""


class MySQLConfig(BaseModel):
    host: str = "localhost"
    port: int = 3306
    database: str = "quant"
    user: str = "root"
    password: str = ""


class Settings(BaseModel):
    # 项目根目录
    base_dir: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 数据库配置
    clickhouse: ClickHouseConfig = ClickHouseConfig()
    mysql: MySQLConfig = MySQLConfig()
    
    # 数据源配置
    sina_api_base: str = "http://hq.sinajs.cn"
    sina_kline_url: str = "http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData/getKLineData"
    
    # 回测配置
    default_capital: float = 1000000.0  # 默认本金 100 万
    default_commission: float = 0.0003   # 手续费万三
    default_slippage: float = 0.001      # 滑点 0.1%
    
    # 日志配置
    log_level: str = "INFO"
    log_file: Optional[str] = None


def load_settings() -> Settings:
    """加载配置，支持 .env 文件和环境变量覆盖"""
    from dotenv import load_dotenv
    
    # 尝试加载 .env 文件
    env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
    load_dotenv(env_file)
    
    return Settings(
        clickhouse=ClickHouseConfig(
            host=os.getenv("QUANT_CLICKHOUSE__HOST", "localhost"),
            port=int(os.getenv("QUANT_CLICKHOUSE__PORT", "9000")),
            database=os.getenv("QUANT_CLICKHOUSE__DATABASE", "quant"),
            user=os.getenv("QUANT_CLICKHOUSE__USER", "default"),
            password=os.getenv("QUANT_CLICKHOUSE__PASSWORD", ""),
        ),
        mysql=MySQLConfig(
            host=os.getenv("QUANT_MYSQL__HOST", "localhost"),
            port=int(os.getenv("QUANT_MYSQL__PORT", "3306")),
            database=os.getenv("QUANT_MYSQL__DATABASE", "quant"),
            user=os.getenv("QUANT_MYSQL__USER", "root"),
            password=os.getenv("QUANT_MYSQL__PASSWORD", ""),
        ),
        log_level=os.getenv("QUANT_LOG_LEVEL", "INFO"),
    )


settings = load_settings()
