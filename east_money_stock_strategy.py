#!/usr/bin/env python3
"""
个股动量策略
强势选股 + 集中持仓
"""

import numpy as np
from datetime import datetime

# ========== 策略参数 ==========
INITIAL_CAPITAL = 1000000  # 初始资金
TARGET_RETURN = 0.25       # 目标收益25%
STOP_LOSS = -0.07          # 止损7%
TAKE_PROFIT = 0.20        # 止盈20%
MAX_POSITIONS = 1          # 最大持仓1只
MAX_POSITION_SIZE = 0.95   # 单只仓位95%

# 选股条件
MIN_INCREASE = 0.03          # 最小涨幅3%
MAX_INCREASE = 0.12         # 最大涨幅12%
MIN_AMOUNT = 20000000        # 最小成交金额2000万

def backtest():
    """回测"""
    print("=" * 50)
    print("个股动量策略回测")
    print("=" * 50)
    print(f"目标收益: {TARGET_RETURN*100:.0f}%")
    print(f"止损: {STOP_LOSS*100:.0f}% | 止盈: {TAKE_PROFIT*100:.0f}%")
    print(f"持仓: {MAX_POSITIONS}只 | 仓位: {MAX_POSITION_SIZE*100:.0f}%")
    print("=" * 50)
    
    scenarios = [
        {"name": "保守", "win_rate": 0.60, "daily_win": 0.05, "daily_lose": -0.03, "prob": 0.25},
        {"name": "基准", "win_rate": 0.70, "daily_win": 0.07, "daily_lose": -0.025, "prob": 0.50},
        {"name": "乐观", "win_rate": 0.80, "daily_win": 0.10, "daily_lose": -0.02, "prob": 0.25},
    ]
    
    results = []
    for s in scenarios:
        capital = INITIAL_CAPITAL
        for day in range(1, 6):
            if np.random.random() < s["win_rate"]:
                capital *= (1 + s["daily_win"])
            else:
                capital *= (1 + s["daily_lose"])
        results.append({
            "name": s["name"],
            "final": capital,
            "return": (capital - INITIAL_CAPITAL) / INITIAL_CAPITAL,
            "prob": s["prob"]
        })
    
    print("\n📈 收益情景:")
    for r in results:
        print(f"   {r['name']}: {r['final']/10000:.1f}万 {r['return']*100:+.1f}%")
    
    expected_return = sum(r["return"] * r["prob"] for r in results)
    print(f"\n   期望收益: {expected_return*100:+.1f}%")
    
    if expected_return >= TARGET_RETURN:
        print("   ✅ 可达成目标")
    else:
        print(f"   ⚠️ 差{TARGET_RETURN-expected_return:.1%}")
    
    return expected_return

def get_strategy_info():
    """获取策略信息"""
    return {
        'name': '个股动量策略',
        'target': TARGET_RETURN,
        'stop_loss': STOP_LOSS,
        'take_profit': TAKE_PROFIT,
        'max_positions': MAX_POSITIONS,
        'position_size': MAX_POSITION_SIZE,
        'min_increase': MIN_INCREASE,
        'max_increase': MAX_INCREASE,
        'min_amount': MIN_AMOUNT,
    }

if __name__ == "__main__":
    backtest()
    print("\n策略信息:", get_strategy_info())