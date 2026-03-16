#!/bin/bash
# A 股数据定时下载脚本（增量更新）
# 每个交易日 15:30 自动执行，只下载当天数据

set -e

PROJECT_DIR="/home/admin/.openclaw/workspace/quant-backtest"
LOG_DIR="/home/admin/.openclaw/workspace/quant-backtest/logs"
LOG_FILE="$LOG_DIR/cron_incremental_$(date +%Y%m%d).log"

# 创建日志目录
mkdir -p "$LOG_DIR"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始增量更新" >> "$LOG_FILE"

cd "$PROJECT_DIR"

# 激活虚拟环境
source venv/bin/activate

# 执行增量下载脚本（只下载当天数据）
python scripts/download_incremental.py >> "$LOG_FILE" 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 增量更新完成" >> "$LOG_FILE"
