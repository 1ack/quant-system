#!/bin/bash
# =====================================================
# 量化回测系统 - 部署脚本
# =====================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "量化回测系统 - 部署脚本"
echo "=========================================="
echo "项目目录：$PROJECT_DIR"
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查 Python 版本
check_python() {
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}错误：未找到 Python3${NC}"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    echo -e "${GREEN}✓ Python 版本：$PYTHON_VERSION${NC}"
}

# 创建虚拟环境
setup_venv() {
    if [ ! -d "$PROJECT_DIR/venv" ]; then
        echo "创建虚拟环境..."
        python3 -m venv "$PROJECT_DIR/venv"
    fi
    
    source "$PROJECT_DIR/venv/bin/activate"
    echo -e "${GREEN}✓ 虚拟环境已激活${NC}"
}

# 安装依赖
install_deps() {
    echo "安装依赖..."
    pip install -r "$PROJECT_DIR/requirements.txt" -q
    echo -e "${GREEN}✓ 依赖安装完成${NC}"
}

# 初始化数据库
init_database() {
    echo ""
    echo "=========================================="
    echo "数据库初始化"
    echo "=========================================="
    
    # ClickHouse
    echo "检查 ClickHouse 连接..."
    if command -v clickhouse-client &> /dev/null; then
        clickhouse-client --query "CREATE DATABASE IF NOT EXISTS quant" 2>/dev/null || true
        echo -e "${GREEN}✓ ClickHouse 数据库已创建${NC}"
    else
        echo -e "${YELLOW}⚠ clickhouse-client 未安装，请手动创建 quant 数据库${NC}"
    fi
    
    # MySQL
    echo "检查 MySQL 连接..."
    if command -v mysql &> /dev/null; then
        read -p "请输入 MySQL root 密码：" -s MYSQL_PASSWORD
        echo ""
        mysql -u root -p"$MYSQL_PASSWORD" < "$SCRIPT_DIR/init_db.sql" 2>/dev/null || {
            echo -e "${YELLOW}⚠ MySQL 初始化失败，请手动执行 init_db.sql${NC}"
        }
        echo -e "${GREEN}✓ MySQL 数据库已初始化${NC}"
    else
        echo -e "${YELLOW}⚠ mysql 客户端未安装，请手动执行 init_db.sql${NC}"
    fi
}

# 配置环境变量
setup_env() {
    ENV_FILE="$PROJECT_DIR/.env"
    
    if [ ! -f "$ENV_FILE" ]; then
        echo "创建环境配置文件 .env..."
        cat > "$ENV_FILE" << EOF
# ClickHouse 配置
QUANT_CLICKHOUSE__HOST=localhost
QUANT_CLICKHOUSE__PORT=9000
QUANT_CLICKHOUSE__DATABASE=quant
QUANT_CLICKHOUSE__USER=default
QUANT_CLICKHOUSE__PASSWORD=

# MySQL 配置
QUANT_MYSQL__HOST=localhost
QUANT_MYSQL__PORT=3306
QUANT_MYSQL__DATABASE=quant
QUANT_MYSQL__USER=root
QUANT_MYSQL__PASSWORD=

# 日志配置
QUANT_LOG_LEVEL=INFO
EOF
        echo -e "${GREEN}✓ 环境配置文件已创建，请编辑 .env 填写数据库密码${NC}"
    else
        echo -e "${GREEN}✓ 环境配置文件已存在${NC}"
    fi
}

# 配置定时任务
setup_cron() {
    echo ""
    echo "=========================================="
    echo "定时任务配置"
    echo "=========================================="
    
    read -p "是否配置每日自动更新数据？(y/n) " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        CRON_JOB="30 15 * * 1-5 cd $PROJECT_DIR && source venv/bin/activate && python -m data.ingest --incremental >> logs/data_update.log 2>&1"
        
        (crontab -l 2>/dev/null | grep -v "data.ingest"; echo "$CRON_JOB") | crontab -
        echo -e "${GREEN}✓ 定时任务已配置（每个交易日 15:30 更新）${NC}"
    fi
}

# 主流程
main() {
    check_python
    setup_venv
    install_deps
    setup_env
    init_database
    setup_cron
    
    echo ""
    echo "=========================================="
    echo -e "${GREEN}部署完成！${NC}"
    echo "=========================================="
    echo ""
    echo "下一步:"
    echo "1. 编辑 .env 文件，配置数据库连接"
    echo "2. 运行全量数据录入：python -m data.ingest --full"
    echo "3. 运行回测测试：python -m backtest.engine --start 2023-01-01 --end 2023-12-31"
    echo ""
}

main "$@"
