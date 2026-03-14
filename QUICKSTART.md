# 量化回测系统 - 环境变量配置
cp .env.example .env

# 编辑 .env 文件，配置数据库连接
vim .env

# 初始化数据库
mysql -u root -p < scripts/init_db.sql

# 安装依赖
pip install -r requirements.txt

# 录入历史数据（可选，先用小数据集测试）
python -m data.ingest --code 000001 --code 600000 --start-date 2023-01-01

# 启动 Web 服务
./web/run.sh

# 访问 http://localhost:8000
