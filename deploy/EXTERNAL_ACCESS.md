# 外部访问配置指南

## 当前配置

### 服务监听
- **地址**: `0.0.0.0:8000`（监听所有网络接口）
- **协议**: HTTP
- **状态**: ✅ 运行中

### 访问地址

**局域网内访问**:
```
http://172.19.28.139:8000
```

**本机访问**:
```
http://localhost:8000
```

---

## 从外部访问

### 方案 A：局域网访问（推荐）

如果你的电脑和服务器在同一局域网：

1. **获取服务器内网 IP**：
   ```bash
   hostname -I | awk '{print $1}'
   # 输出：172.19.28.139
   ```

2. **浏览器访问**：
   ```
   http://172.19.28.139:8000
   ```

3. **API 文档**：
   ```
   http://172.19.28.139:8000/docs
   ```

---

### 方案 B：云服务器公网访问

如果服务器在云上（阿里云/腾讯云等）：

1. **配置安全组**：
   - 登录云控制台
   - 找到实例的安全组
   - 添加入站规则：
     - 端口：`8000`
     - 协议：`TCP`
     - 授权对象：`0.0.0.0/0`（或指定 IP）

2. **获取公网 IP**：
   ```bash
   curl ifconfig.me
   ```

3. **浏览器访问**：
   ```
   http://<公网 IP>:8000
   ```

---

### 方案 C：本地服务器 + 内网穿透

如果服务器在本地网络，需要从外网访问：

#### 使用 frp 内网穿透

1. **安装 frp**：
   ```bash
   # 下载 frp
   wget https://github.com/fatedier/frp/releases/download/v0.50.0/frp_0.50.0_linux_amd64.tar.gz
   tar -xzf frp_0.50.0_linux_amd64.tar.gz
   cd frp_0.50.0_linux_amd64
   ```

2. **配置 frpc.ini**：
   ```ini
   [common]
   server_addr = <frp 服务器 IP>
   server_port = 7000

   [quant_web]
   type = tcp
   local_ip = 127.0.0.1
   local_port = 8000
   remote_port = 8000
   ```

3. **启动 frp**：
   ```bash
   ./frpc -c frpc.ini
   ```

4. **外部访问**：
   ```
   http://<frp 服务器 IP>:8000
   ```

---

## 防火墙配置

### 如果启用了防火墙

**Ubuntu (ufw)**:
```bash
sudo ufw allow 8000/tcp
sudo ufw reload
```

**CentOS (firewalld)**:
```bash
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

**直接使用 iptables**:
```bash
sudo iptables -A INPUT -p tcp --dport 8000 -j ACCEPT
```

---

## 测试连接

**从其他机器测试**:
```bash
# 测试连通性
ping 172.19.28.139

# 测试端口
telnet 172.19.28.139 8000

# 或使用 curl
curl http://172.19.28.139:8000/api/health
```

**预期响应**:
```json
{"status":"ok","timestamp":"2026-03-16T11:53:26.975681"}
```

---

## 安全建议

⚠️ **重要**：当前配置允许任何人访问，建议：

1. **生产环境**：
   - 添加用户认证
   - 使用 HTTPS
   - 限制访问 IP

2. **临时测试**：
   - 使用 SSH 隧道：
     ```bash
     ssh -L 8000:localhost:8000 user@server
     ```
   - 然后本地访问：`http://localhost:8000`

3. **监控日志**：
   ```bash
   tail -f logs/web.log
   ```

---

**最后更新**: 2026-03-16 11:53
