#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
量化系统进度汇报脚本
每 30 分钟执行一次，汇报：
1. A 股数据下载进度
2. 后端 API 开发进度
"""
import sys
import os
import json
from datetime import datetime
from pathlib import Path

# 项目根目录
PROJECT_DIR = Path(__file__).parent.parent

def get_download_progress():
    """获取 A 股数据下载进度"""
    progress = {
        "status": "未知",
        "current": 0,
        "total": 3040,
        "percentage": 0,
        "total_klines": 0,
        "last_log": None
    }
    
    # 方法 1：检查下载日志
    log_dir = PROJECT_DIR / "logs"
    if log_dir.exists():
        # 查找最新的下载日志
        log_files = sorted(log_dir.glob("cron_*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
        if log_files:
            latest_log = log_files[0]
            try:
                with open(latest_log, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # 查找进度信息
                    if "成功：" in content:
                        for line in content.split('\n'):
                            if "成功：" in line and "只股票" in line:
                                # 解析 "成功：657/3040 只股票"
                                import re
                                match = re.search(r'成功：(\d+)/(\d+)', line)
                                if match:
                                    progress["current"] = int(match.group(1))
                                    progress["total"] = int(match.group(2))
                                    progress["percentage"] = round(progress["current"] / progress["total"] * 100, 1)
                                    progress["status"] = "进行中"
                                    progress["last_log"] = latest_log.name
                                break
            except Exception as e:
                progress["status"] = f"读取日志失败：{e}"
    
    # 方法 2：检查 ClickHouse 数据量（简化版，避免连接超时）
    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from clickhouse_driver import Client
        client = Client(host='localhost', database='quant', connection_timeout=5)
        result = client.execute("SELECT count() FROM kline_daily")
        if result and result[0][0]:
            progress["total_klines"] = result[0][0]
        client.disconnect()
    except Exception as e:
        progress["db_error"] = f"DB 连接失败：{e}"
    
    return progress


def get_dev_progress():
    """获取后端 API 开发进度"""
    progress = {
        "phase": "未知",
        "completed": [],
        "pending": [],
        "subagents": []
    }
    
    # 读取 DEV_LOG.md
    dev_log_path = PROJECT_DIR / "docs" / "DEV_LOG.md"
    if dev_log_path.exists():
        try:
            with open(dev_log_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # 解析 Phase 1 进度
                in_phase1 = False
                for line in content.split('\n'):
                    if '### Phase 1: 数据库表创建 + 后端 API' in line:
                        in_phase1 = True
                        continue
                    elif in_phase1:
                        if line.startswith('### Phase 2'):
                            break
                        if '- [x]' in line or '- [ ]' in line:
                            task = line.strip()
                            if '- [x]' in task:
                                progress["completed"].append(task.replace('- [x]', '').strip())
                            elif '- [ ]' in task:
                                progress["pending"].append(task.replace('- [ ]', '').strip())
        except Exception as e:
            progress["error"] = str(e)
    
    # 检查子代理状态
    try:
        result = os.popen('openclaw subagents list 2>/dev/null').read()
        if result:
            progress["subagents_raw"] = result[:500]  # 限制长度
    except:
        pass
    
    return progress


def format_report():
    """格式化进度报告"""
    download = get_download_progress()
    dev = get_dev_progress()
    
    report = []
    report.append("📊 **量化系统进度汇报**")
    report.append(f"汇报时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    # A 股数据下载进度
    report.append("📈 **A 股数据下载**")
    if download["status"] == "进行中":
        report.append(f"- 进度：{download['current']}/{download['total']} ({download['percentage']}%)")
        report.append(f"- 总数据量：{download['total_klines']:,} 条 K 线")
        report.append(f"- 状态：✅ 进行中")
    else:
        report.append(f"- 状态：{download['status']}")
        if download.get('total_klines'):
            report.append(f"- 总数据量：{download['total_klines']:,} 条 K 线")
    report.append("")
    
    # 后端 API 开发进度
    report.append("🔧 **后端 API 开发 (Phase 1)**")
    completed_count = len(dev.get("completed", []))
    pending_count = len(dev.get("pending", []))
    total_count = completed_count + pending_count
    
    if total_count > 0:
        percentage = round(completed_count / total_count * 100, 1)
        report.append(f"- 进度：{completed_count}/{total_count} ({percentage}%)")
    
    if dev.get("completed"):
        report.append(f"- ✅ 已完成：{len(dev['completed'])} 项")
    if dev.get("pending"):
        report.append(f"- ⏳ 待完成：{len(dev['pending'])} 项")
        for task in dev["pending"][:3]:  # 只显示前 3 项
            report.append(f"  - {task}")
    report.append("")
    
    # 子代理状态
    report.append("🤖 **子代理状态**")
    try:
        result = os.popen('openclaw subagents list 2>&1 | head -10').read()
        if "active" in result.lower():
            report.append("```")
            report.append(result.strip())
            report.append("```")
        else:
            report.append("- 当前无活跃子代理")
    except:
        report.append("- 无法获取子代理状态")
    
    return "\n".join(report)


def main():
    report = format_report()
    print(report)
    
    # 如果需要发送到 Feishu，可以添加 webhook 调用
    # 这里只输出到 stdout，由 cron 脚本处理发送


if __name__ == "__main__":
    main()
