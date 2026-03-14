#!/bin/bash
# 启动 Web 服务

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$SCRIPT_DIR"

# 创建日志目录
mkdir -p "$PROJECT_DIR/logs"

# 启动服务
echo "启动量化回测系统 Web 服务..."
echo "访问地址：http://localhost:8000"
echo "API 文档：http://localhost:8000/docs"
echo ""

source "$PROJECT_DIR/venv/bin/activate" 2>/dev/null || true

python main.py
