# A 股量化回测系统

面向中国 A 股的量化回测系统，支持策略自动回测和绩效分析。

## 技术栈

- **语言**: Python 3.10+
- **数据库**: 
  - ClickHouse（K 线、分时等时序数据）
  - MySQL（策略、回测结果等关系型数据）
- **数据源**: 新浪财经 API
- **部署**: 本地服务器，支持 Git 同步迁移

## 快速开始

### 1. 环境准备

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置数据库

编辑 `config/settings.py`，配置 ClickHouse 和 MySQL 连接信息。

```bash
# 初始化数据库
mysql -u root -p < scripts/init_db.sql
```

### 3. 数据录入

```bash
# 录入历史数据（全量）
python -m data.ingest --full

# 增量更新（每日定时任务）
python -m data.ingest --incremental
```

### 4. 运行回测

```bash
# 使用示例策略回测
python -m backtest.engine --strategy examples.ma_cross --start 2023-01-01 --end 2023-12-31
```

## 目录结构

```
quant-backtest/
├── config/           # 配置管理
├── data/             # 数据获取与存储
├── strategy/         # 策略定义
├── backtest/         # 回测引擎
├── scripts/          # 部署与运维脚本
└── tests/            # 单元测试
```

## 策略开发

继承 `strategy.base.BaseStrategy`，实现 `generate_signals` 方法：

```python
from strategy.base import BaseStrategy

class MyStrategy(BaseStrategy):
    def generate_signals(self, data):
        # 返回：buy/sell 信号
        pass
```

## 定时任务

配置 cron 每日自动更新数据：

```bash
# 编辑 crontab
crontab -e

# 添加（每个交易日 15:30 更新）
30 15 * * 1-5 cd /path/to/quant-backtest && source venv/bin/activate && python -m data.ingest --incremental
```

## License

MIT
