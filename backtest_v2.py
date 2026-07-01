#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETF策略回测 v2
使用 akshare 东财接口获取数据
"""

import os
import sys
import pandas as pd
import numpy as np

try:
    import akshare as ak
except ImportError:
    print("请先安装: pip3 install akshare")
    sys.exit(1)


def get_etf_data_eastmoney(code, name):
    """使用东财接口获取ETF历史数据"""
    print(f"\n正在获取 {name} ({code}) 数据...")
    try:
        # 东财ETF历史数据
        df = ak.fund_etf_hist_em(symbol=code)
        
        if df is None or len(df) < 10:
            print(f"  数据为空，尝试其他接口...")
            return None
        
        # 东财数据列名
        df = df.copy()
        # 转换日期
        df["date"] = pd.to_datetime(df["日期"])
        df = df.sort_values("date").reset_index(drop=True)
        
        # 计算前复权价格（简单用收盘价）
        df["close"] = df["收盘价"].astype(float)
        df["open"] = df["开盘价"].astype(float)
        df["high"] = df["最高价"].astype(float)
        df["low"] = df["最低价"].astype(float)
        df["volume"] = df["成交量"].astype(float)
        
        print(f"  ✅ 数据范围: {df['date'].min().date()} → {df['date'].max().date()}")
        print(f"  ✅ 共 {len(df)} 条数据")
        
        return df[["date", "open", "high", "low", "close", "volume"]]
    
    except Exception as e:
        print(f"  ❌ 获取失败: {e}")
        return None


def ma_cross_strategy(df, short=5, long=20):
    """
    均线金叉策略回测
    买入: 短期均线 > 长期均线 且 前一天短期均线 <= 前一天长期均线
    卖出: 短期均线 < 长期均线 且 前一天短期均线 >= 前一天长期均线
    """
    df = df.copy()
    
    # 均线
    df["ma_short"] = df["close"].rolling(short).mean()
    df["ma_long"] = df["close"].rolling(long).mean()
    
    # 信号
    df["signal"] = 0
    # 金叉买入
    df.loc[
        (df["ma_short"] > df["ma_long"]) & 
        (df["ma_short"].shift(1) <= df["ma_long"].shift(1)),
        "signal"
    ] = 1
    # 死叉卖出
    df.loc[
        (df["ma_short"] < df["ma_long"]) & 
        (df["ma_short"].shift(1) >= df["ma_long"].shift(1)),
        "signal"
    ] = -1
    
    # 持仓(简化: 1=持有, 0=空仓)
    df["position"] = df["signal"].replace(-1, 0)
    # 持仓累加(持仓状态持续)
    df["position"] = df["position"].cumsum().clip(lower=0)
    df["position"] = df["position"].apply(lambda x: 1 if x > 0 else 0)
    
    # 收益
    df["daily_return"] = df["close"].pct_change()
    # 策略收益 = 持仓状态 * 日收益
    df["strategy_return"] = df["position"].shift(1) * df["daily_return"]
    
    # 累计收益
    df["cum_bh"] = (1 + df["daily_return"]).cumprod()
    df["cum_strat"] = (1 + df["strategy_return"]).cumprod()
    
    # 最大回撤
    rolling_max = df["cum_strat"].cummax()
    df["drawdown"] = (df["cum_strat"] - rolling_max) / rolling_max
    max_dd = df["drawdown"].min() * 100
    
    # 夏普比率(简化)
    daily_rf = 0.03 / 252  # 无风险利率年化3%
    excess_return = df["strategy_return"].mean() * 252 - 0.03
    if df["strategy_return"].std() > 0:
        sharpe = excess_return / (df["strategy_return"].std() * np.sqrt(252))
    else:
        sharpe = 0
    
    return {
        "total_bh": (df["cum_bh"].iloc[-1] - 1) * 100,
        "total_strat": (df["cum_strat"].iloc[-1] - 1) * 100,
        "max_dd": max_dd,
        "sharpe": sharpe,
        "win_rate": (df["strategy_return"] > 0).sum() / (df["strategy_return"] != 0).sum() * 100 if (df["strategy_return"] != 0).sum() > 0 else 0,
        "data_len": len(df)
    }


def main():
    print("="*70)
    print("ETF均线金叉策略回测")
    print("="*70)
    print(f"回测参数: 5日均线 vs 20日均线金叉/死叉")
    print(f"回测区间: 近1年")
    
    # ETF列表
    etfs = [
        ("510300", "沪深300ETF"),  # 沪市
        ("159915", "创业板ETF"),   # 深市
        ("588000", "科创50ETF"),  # 科创板
        ("510500", "中证500ETF"), # 沪市
        ("159919", "沪深300ETF(深)"),  # 深市
    ]
    
    results = []
    
    for code, name in etfs:
        df = get_etf_data_eastmoney(code, name)
        
        if df is not None and len(df) > 50:
            # 只取近1年数据
            cutoff = pd.Timestamp.now() - pd.Timedelta(days=365)
            df = df[df["date"] >= cutoff].copy()
            
            if len(df) > 50:
                stats = ma_cross_strategy(df)
                
                results.append({
                    "ETF": name,
                    "代码": code,
                    "持有收益(%)": round(stats["total_bh"], 2),
                    "策略收益(%)": round(stats["total_strat"], 2),
                    "最大回撤(%)": round(stats["max_dd"], 2),
                    "夏普比率": round(stats["sharpe"], 2),
                    "胜率(%)": round(stats["win_rate"], 1),
                    "数据天数": stats["data_len"]
                })
    
    # 打印结果
    if results:
        print("\n" + "="*70)
        print("回测结果汇总")
        print("="*70)
        
        df_result = pd.DataFrame(results)
        print(df_result.to_string(index=False))
        
        # 保存
        df_result.to_csv("backtest_result.csv", index=False, encoding="utf-8-sig")
        print(f"\n✅ 结果已保存到 backtest_result.csv")
        
        print("\n" + "="*70)
        print("策略解读")
        print("="*70)
        
        # 找最优
        best = max(results, key=lambda x: x["策略收益(%)"])
        print(f"🏆 策略收益最高: {best['ETF']} ({best['代码']})")
        print(f"   策略收益: {best['策略收益(%)']}% vs 持有: {best['持有收益(%)']}%")
        
        print(f"\n📊 策略 vs 持有收益对比:")
        for r in results:
            diff = r["策略收益(%)"] - r["持有收益(%)"]
            flag = "✅" if diff > 0 else "❌"
            print(f"   {flag} {r['ETF']}: 策略 {r['策略收益(%)']}% vs 持有 {r['持有收益(%)']}% (差异 {diff:+.2f}%)")
        
        print("\n💡 建议:")
        print("   1. 选择策略收益 > 持有收益的ETF")
        print("   2. 最大回撤控制在 -30% 以内（你的风险接受度）")
        print("   3. 比赛只有一周，简单持有可能更稳")
    else:
        print("\n❌ 未能获取任何数据!")


if __name__ == "__main__":
    main()
