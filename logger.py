#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交易日志记录辅助工具"""

import os
from datetime import datetime

LOG_FILE = os.path.join(os.path.dirname(__file__), "strategy_log.local.md")


def log_trade(platform, direction, code, name, quantity, price=None, order_type="market", status="pending", order_id=""):
    """记录一笔交易到日志"""
    timestamp = datetime.now().strftime("%Y.%m.%d %H:%M")
    
    price_str = f"{price:.2f}" if price else "-"
    
    line = f"| {timestamp} | {direction} | {code} | {name} | {quantity} | {order_type} | {status} | {order_id} | |"
    
    # 找到交易记录部分并插入
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 查找交易记录表格位置
        if platform == "东方财富":
            marker = "### 交易记录（东方财富）"
        else:
            marker = f"### 交易记录（{platform}）"
        
        if marker not in content:
            # 如果平台记录不存在，创建一个
            new_section = f"\n\n---\n\n### 交易记录（{platform}）\n\n"
            new_section += "| 时间 | 操作 | 代码 | 名称 | 数量 | 委托类型 | 委托状态 | 委托单号 | 备注 |\n"
            new_section += "|------|------|------|------|------|----------|----------|----------|------|\n"
            content += new_section
        
        # 在表格之后插入新行
        lines = content.splitlines()
        for i, line_content in enumerate(lines):
            if "委托状态" in line_content and "备注" in line_content:
                # 找到表头后，在下一行插入
                lines.insert(i + 1, line)
                break
        
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        
        print(f"✅ 已记录交易到日志: {direction} {code} {name}")
        
    except Exception as e:
        print(f"❌ 日志记录失败: {e}")


def log_note(note):
    """记录一条笔记"""
    timestamp = datetime.now().strftime("%Y.%m.%d %H:%M")
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n\n📝 {timestamp}: {note}\n")
        print(f"✅ 已记录笔记: {note}")
    except Exception as e:
        print(f"❌ 笔记记录失败: {e}")


if __name__ == "__main__":
    # 测试
    log_note("测试日志记录功能")

