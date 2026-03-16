# 部署指南

## 1. Cron 定时任务（已配置）

A 股数据下载已配置为每个交易日 15:30 自动执行。

```bash
# 查看当前 cron 配置
crontab -l

# 手动执行一次测试
./scripts/cron_download.sh
```

## 2. Systemd Web 服务

### 安装服务

```bash
# 复制服务文件（需要 sudo 权限）
sudo ln -sf /home/admin/.openclaw/workspace/quant-backtest/deploy/quant-web.service /etc/systemd/system/

# 重新加载 systemd
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start quant-web

# 设置开机自启
sudo systemctl enable quant-web

# 查看状态
sudo systemctl status quant-web

# 查看日志
sudo journalctl -u quant-web -f
```

### 手动运行（无 systemd）

```bash
cd /home/admin/.openclaw/workspace/quant-backtest
source venv/bin/activate
nohup python -m web.main > logs/web.log 2>&1 &

# 查看进程
ps aux | grep "web.main"
```

## 3. 开发进度追踪

使用 `HEARTBEAT.md` 追踪开发进度，每次会话启动时自动读取。

---

**配置日期**: 2026-03-16
