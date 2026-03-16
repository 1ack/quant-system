# 量化系统部署指南

## ⚠️ 重要配置规则

**每次部署必须监听全局端口（0.0.0.0），以支持外部访问！**

---

## 快速部署

### 1. 启动 Web 服务

```bash
cd /home/admin/.openclaw/workspace/quant-backtest
source venv/bin/activate

# 监听全局地址（重要！）
nohup python -m web.main > logs/web.log 2>&1 &

# 验证服务
curl http://localhost:8000/api/health
```

### 2. 配置要求

**web/main.py** 中的启动配置：

```python
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host="0.0.0.0",  # ⚠️ 必须监听全局地址
        port=8000,
        log_level="info",
    )
```

**❌ 错误配置**（只监听本地）：
```python
host="127.0.0.1"  # 无法外部访问
```

**✅ 正确配置**（监听全局）：
```python
host="0.0.0.0"  # 允许外部访问
```

---

## 访问地址

### 局域网访问

获取服务器内网 IP：
```bash
hostname -I | awk '{print $1}'
# 输出：172.19.28.139
```

**浏览器访问**：
```
http://172.19.28.139:8000
```

**API 文档**：
```
http://172.19.28.139:8000/docs
```

---

### 云服务器公网访问

如果在阿里云/腾讯云等云平台：

1. **配置安全组**：
   - 登录云控制台
   - 找到实例的安全组
   - 添加入站规则：
     - 端口：`8000`
     - 协议：`TCP`
     - 授权对象：`0.0.0.0/0`

2. **获取公网 IP**：
   ```bash
   curl ifconfig.me
   ```

3. **浏览器访问**：
   ```
   http://<公网 IP>:8000
   ```

---

## Systemd 服务配置（推荐）

使用 systemd 管理 Web 服务，确保开机自启：

### 1. 创建服务文件

```bash
sudo nano /etc/systemd/system/quant-web.service
```

内容：
```ini
[Unit]
Description=Quant Backtest Web Service
After=network.target postgresql.service clickhouse-server.service

[Service]
Type=simple
User=admin
WorkingDirectory=/home/admin/.openclaw/workspace/quant-backtest
Environment="PATH=/home/admin/.openclaw/workspace/quant-backtest/venv/bin"
ExecStart=/home/admin/.openclaw/workspace/quant-backtest/venv/bin/python -m web.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 2. 启动服务

```bash
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

---

## 防火墙配置

### Ubuntu (ufw)
```bash
sudo ufw allow 8000/tcp
sudo ufw reload
```

### CentOS (firewalld)
```bash
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

### 直接使用 iptables
```bash
sudo iptables -A INPUT -p tcp --dport 8000 -j ACCEPT
```

---

## 测试连接

### 从其他机器测试

```bash
# 测试连通性
ping 172.19.28.139

# 测试端口
telnet 172.19.28.139 8000

# 或使用 curl
curl http://172.19.28.139:8000/api/health
```

**预期响应**：
```json
{"status":"ok","timestamp":"2026-03-16T12:00:00.000000"}
```

---

## 部署检查清单

每次部署时检查：

- [ ] **监听地址**: `host="0.0.0.0"` ✅
- [ ] **端口**: `8000` ✅
- [ ] **防火墙**: 开放 8000 端口 ✅
- [ ] **云服务**: 安全组规则已配置 ✅
- [ ] **服务状态**: `systemctl status quant-web` ✅
- [ ] **外部访问测试**: 从其他设备访问 ✅

---

## 故障排查

### 无法外部访问

1. **检查监听地址**：
   ```bash
   netstat -tlnp | grep 8000
   # 应该显示：0.0.0.0:8000
   ```

2. **检查防火墙**：
   ```bash
   sudo ufw status
   # 应该有：8000/tcp ALLOW
   ```

3. **检查安全组**（云服务器）：
   - 登录云控制台
   - 确认 8000 端口已开放

### 服务未运行

```bash
# 查看进程
ps aux | grep web.main

# 查看日志
tail -f logs/web.log

# 重启服务
sudo systemctl restart quant-web
```

---

**最后更新**: 2026-03-16 12:43  
**配置要求**: 必须监听 `0.0.0.0:8000` 以支持外部访问
