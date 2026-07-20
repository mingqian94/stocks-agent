#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日收盘检查与记录"""

import os
import json
import subprocess
from datetime import datetime

LOG_FILE = os.path.join(os.path.dirname(__file__), "strategy_log.local.md")

def query_dfcf_balance():
    """查询东方财富账户"""
    import os
    MX_APIKEY = os.environ.get("MX_APIKEY", "")
    MX_API_URL = "https://mkapi2.dfcfs.com/finskillshub"
    
    cmd = [
        "curl", "-s", "-X", "POST",
        f"{MX_API_URL}/api/claw/mockTrading/balance",
        "-H", f"apikey: {MX_APIKEY}",
        "-H", "Content-Type: application/json",
        "-d", '{"moneyUnit": 1}'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception as e:
        print(f"❌ 东方财富查询失败: {e}")
    return None


def query_dfcf_positions():
    """查询东方财富持仓"""
    import os
    MX_APIKEY = os.environ.get("MX_APIKEY", "")
    MX_API_URL = "https://mkapi2.dfcfs.com/finskillshub"
    
    cmd = [
        "curl", "-s", "-X", "POST",
        f"{MX_API_URL}/api/claw/mockTrading/positions",
        "-H", f"apikey: {MX_APIKEY}",
        "-H", "Content-Type: application/json",
        "-d", '{"moneyUnit": 1}'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception as e:
        print(f"❌ 东方财富持仓查询失败: {e}")
    return None


def record_daily():
    """记录每日数据"""
    today = datetime.now().strftime("%Y.%m.%d")
    
    print(f"📊 {today} 每日检查...")
    
    # 查询东方财富
    print("\n--- 东方财富 ---")
    dfcf_balance = query_dfcf_balance()
    
    if dfcf_balance and dfcf_balance.get("code") in ["200", "0", 200, 0]:
        data = dfcf_balance.get("data", {})
        total = data.get("totalAssets", 0)
        avail = data.get("availBalance", 0)
        pos_val = data.get("totalPosValue", 0)
        pos_pct = data.get("totalPosPct", 0)
        
        print(f"总资产: {total:.2f} 元")
        print(f"可用: {avail:.2f} 元")
        print(f"持仓市值: {pos_val:.2f} 元")
        print(f"仓位: {pos_pct:.2f}%")
        
        # 记录到日志
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                content = f.read()
            
            # 检查是否已有净值记录部分
            if "## 📈 净值曲线" not in content:
                new_section = "\n\n## 📈 净值曲线\n\n"
                new_section += "| 日期 | 东方财富总资产 | 东方财富收益率 | 华泰总资产 | 华泰收益率 | 备注 |\n"
                new_section += "|------|----------------|----------------|------------|------------|------|\n"
                content += new_section
            
            # 计算收益率
            initial_capital = 1000000.0
            dfcf_return_pct = ((total - initial_capital) / initial_capital) * 100
            
            # 构建记录行
            line = f"| {today} | {total:.2f} | {dfcf_return_pct:.2f}% | - | - | |"
            
            # 插入到净值表格
            lines = content.splitlines()
            for i, line_content in enumerate(lines):
                if "备注" in line_content and "华泰收益率" in line_content:
                    lines.insert(i + 1, line)
                    break
            
            with open(LOG_FILE, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            
            print(f"\n✅ 净值已记录到日志")
            
        except Exception as e:
            print(f"❌ 记录失败: {e}")
    
    # 查询持仓
    print("\n--- 持仓详情 ---")
    positions = query_dfcf_positions()
    if positions and positions.get("code") in ["200", "0", 200, 0]:
        data = positions.get("data", {})
        pos_list = data.get("posList", [])
        if pos_list:
            print(f"持仓数: {len(pos_list)}")
            for pos in pos_list:
                name = pos.get("secName", "")
                code = pos.get("secCode", "")
                val = pos.get("value", 0)
                profit = pos.get("profit", 0)
                pct = pos.get("posPct", 0)
                print(f"  {name}({code}) - 市值:{val:.2f}元 - 仓位:{pct:.2f}% - 盈亏:{profit:.2f}")
        else:
            print("  暂无持仓（可能尚未成交）")


if __name__ == "__main__":
    record_daily()

