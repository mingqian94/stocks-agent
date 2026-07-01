#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单ETF策略回测
策略思路：
1. 宽基ETF均衡配置（510300, 159915, 588000, 510500）
2. 简单均线策略：
   - 5日 > 20日 → 买入持有
   - 5日 < 20日 → 减仓/卖出
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# 首先尝试安装需要的包
try:
    import akshare as ak
except ImportError:
    print("正在安装 akshare ...")
    os.system("pip3 install akshare -i https://pypi.tuna.tsinghua.edu.cn/simple")
    import akshare as ak


def get_etf_history(code, name, start_date="20250101", end_date="20260607"):
    """
    获取ETF历史数据
    """
    print(f"\n正在获取 {name} ({code}) 数据 ...")
    try:
        # 用akshare获取ETF历史数据
        df = ak.fund_etf_hist_sina(symbol=code)
        
        if df is None or len(df) < 2:
            print(f"  获取失败或数据太少")
            return None
        
        # 转换日期格式并排序
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        
        # 只取需要的列
        df = df[["date", "open", "high", "low", "close", "volume"]]
        print(f"  数据范围: {df['date'].min()} → {df['date'].max()}")
        print(f"  共 {len(df)} 条数据")
        
        return df
    
    except Exception as e:
        print(f"  获取失败: {e}")
        return None


def simple_ma_strategy(df, short_period=5, long_period=20):
    """
    简单均线策略回测
    """
    df = df.copy()
    
    # 计算均线
    df["ma_short"] = df["close"].rolling(short_period).mean()
    df["ma_long"] = df["close"].rolling(long_period).mean()
    
    # 生成信号
    df["signal"] = 0
    # 5日均线上穿20日均线：买入信号
    df.loc[(df["ma_short"] > df["ma_long"]) & (df["ma_short"].shift(1) <= df["ma_long"].shift(1)), "signal"] = 1
    # 5日均线下穿20日均线：卖出信号
    df.loc[(df["ma_short"] < df["ma_long"]) & (df["ma_short"].shift(1) >= df["ma_long"].shift(1)), "signal"] = -1
    
    # 计算持仓
    df["position"] = df["signal"].replace(-1, 0).cumsum()
    df["position"] = df["position"].clip(lower=0, upper=1)
    
    # 计算策略收益
    df["return"] = df["close"].pct_change()
    df["strategy_return"] = df["return"] * df["position"].shift(1)
    
    # 累计收益
    df["cum_return"] = (1 + df["return"]).cumprod()
    df["cum_strategy_return"] = (1 + df["strategy_return"]).cumprod()
    
    return df


def main():
    print("="*60)
    print("ETF策略回测")
    print("="*60)
    
    # 我们的目标ETF
    etfs = [
        {"code": "510300", "name": "沪深300ETF"},
        {"code": "159915", "name": "创业板ETF"},
        {"code": "588000", "name": "科创50ETF"},
        {"code": "510500", "name": "中证500ETF"},
    ]
    
    results = []
    
    for etf in etfs:
        df = get_etf_history(etf["code"], etf["name"])
        
        if df is not None and len(df) > 50:
            # 策略回测
            df_strat = simple_ma_strategy(df)
            
            # 计算指标
            total_buy_hold = (df_strat["cum_return"].iloc[-1] - 1) * 100
            total_strategy = (df_strat["cum_strategy_return"].iloc[-1] - 1) * 100
            max_drawdown = (df_strat["cum_strategy_return"] / df_strat["cum_strategy_return"].cummax() - 1).min() * 100
            
            results.append({
                "ETF": etf["name"],
                "代码": etf["code"],
                "持有收益(%)": round(total_buy_hold, 2),
                "策略收益(%)": round(total_strategy, 2),
                "最大回撤(%)": round(max_drawdown, 2),
                "数据天数": len(df_strat)
            })
    
    # 打印结果
    if results:
        print("\n" + "="*60)
        print("回测结果汇总")
        print("="*60)
        
        df_result = pd.DataFrame(results)
        print(df_result.to_string(index=False))
        
        # 保存结果
        df_result.to_csv("backtest_result.csv", index=False, encoding="utf-8-sig")
        print(f"\n结果已保存到 backtest_result.csv")
        
        print("\n" + "="*60)
        print("结论参考")
        print("="*60)
        print("1. 优先选策略收益 > 持有收益，且最大回撤可控的")
        print("2. 比赛只有一周，简单粗暴直接上，先保证建仓")
        
    else:
        print("\n未获取到任何数据！")


if __name__ == "__main__":
    main()
