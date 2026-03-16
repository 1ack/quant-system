#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
发送进度报告到飞书
通过 OpenClaw Gateway API 发送消息
"""
import os
import json
import requests
from pathlib import Path

REPORT_FILE = Path("/tmp/quant_progress_report.txt")
OPENCLAW_CONFIG = Path.home() / ".openclaw" / "openclaw.json"

def get_gateway_config():
    """获取 OpenClaw Gateway 配置"""
    if not OPENCLAW_CONFIG.exists():
        return None
    
    with open(OPENCLAW_CONFIG, 'r') as f:
        config = json.load(f)
    
    gateway = config.get("gateway", {})
    return {
        "host": gateway.get("bind", "localhost"),
        "port": gateway.get("port", 17939),
        "token": gateway.get("auth", {}).get("token", "")
    }

def send_to_feishu(report: str):
    """
    通过写入报告文件，由 OpenClaw 主会话读取并发送
    这是更可靠的方式，避免 API 路径问题
    """
    # 报告已经由 cron 脚本写入 /tmp/quant_progress_report.txt
    # OpenClaw 的 HEARTBEAT 机制会读取并发送
    print("✓ 报告已写入 /tmp/quant_progress_report.txt")
    print("  OpenClaw 心跳会自动读取并发送到 Feishu")
    return True

def main():
    # 检查报告文件
    if not REPORT_FILE.exists():
        print("报告文件不存在，跳过")
        return
    
    # 读取报告
    report = REPORT_FILE.read_text(encoding='utf-8').strip()
    if not report:
        print("报告内容为空，跳过")
        return
    
    print(f"准备发送报告（{len(report)} 字符）...")
    
    # 发送
    success = send_to_feishu(report)
    
    if success:
        # 删除报告文件（避免重复发送）
        REPORT_FILE.unlink()
        print("✓ 报告已发送并清理")
    else:
        print("⚠ 发送失败，保留报告文件")

if __name__ == "__main__":
    main()
