#!/bin/bash
# 进度汇报定时任务
# 每 30 分钟执行一次，向用户汇报项目进度

set -e

PROJECT_DIR="/home/admin/.openclaw/workspace/quant-backtest"
LOG_DIR="/home/admin/.openclaw/workspace/quant-backtest/logs"
LOG_FILE="$LOG_DIR/progress_report_$(date +%Y%m%d).log"
REPORT_FILE="/tmp/quant_progress_report.txt"

# 创建日志目录
mkdir -p "$LOG_DIR"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 生成进度报告" >> "$LOG_FILE"

cd "$PROJECT_DIR"

# 激活虚拟环境
source venv/bin/activate

# 生成报告
REPORT=$(python scripts/progress_report.py 2>&1)

echo "$REPORT" >> "$LOG_FILE"
echo "$REPORT"

# 写入临时文件，供 OpenClaw 读取并发送
echo "$REPORT" > "$REPORT_FILE"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 报告已保存到 $REPORT_FILE" >> "$LOG_FILE"

# 尝试立即发送报告
python scripts/send_report_feishu.py >> "$LOG_FILE" 2>&1 || true
