#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETF策略回测 v3
使用 baostock 获取数据
"""

import os
import sys
import pandas as pd
import numpy as np
import baostock as bs

# 登录baostock
bs.login()


def get_index_data(code, name, start_date="2020-01-01", end_date="2026-06-07"):
    """获取指数历史数据"""
    print(f"\n正在获取 {name} ({code}) 数据...")
    try:
        rs = bs.query_history_k_data_plus(
            code,
            "date,open,high,low,close,volume",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="2"  # 前复权
        )
        
        if rs.error_code != "0":
            print(f"  ❌ 获取失败: {rs.error_msg}")
            return None
        
        data_list = []
        while (rs.error_code == "0") & rs.next():
            data_list.append(rs.get_row_data())
        
        if not data_list:
            print(f"  ❌ 无数据")
            return None
        
        df = pd.DataFrame(data_list, columns=rs.fields)
        df["date"] = pd.to_datetime(df["date"])
        
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        
        df = df.dropna().sort_values("date").reset_index(drop=True)
        
        print(f"  ✅ 数据范围: {df['date'].min().date()} → {df['date'].max().date()}")
        print(f"  ✅ 共 {len(df)} 条数据")
        
        return df
    
    except Exception as e:
        print(f"  ❌ 获取失败: {e}")
        return None


def ma_cross_strategy(df, short=5, long=20):
    """均线金叉策略"""
    df = df.copy()
    
    # 均线
    df["ma_short"] = df["close"].rolling(short).mean()
    df["ma_long"] = df["close"].rolling(long).mean()
    
    # 信号
    df["signal"] = 0
    df.loc[(df["ma_short"] > df["ma_long"]) & (df["ma_short"].shift(1) <= df["ma_long"].shift(1)), "signal"] = 1
    df.loc[(df["ma_short"] < df["ma_long"]) & (df["ma_short"].shift(1) >= df["ma_long"].shift(1)), "signal"] = -1
    
    # 持仓
    df["position"] = df["signal"].replace(-1, 0).cumsum().clip(lower=0)
    df["position"] = df["position"].apply(lambda x: 1 if x > 0 else 0)
    
    # 收益
    df["daily_return"] = df["close"].pct_change()
    df["strategy_return"] = df["position"].shift(1) * df["daily_return"]
    
    # 累计
    df["cum_bh"] = (1 + df["daily_return"]).cumprod()
    df["cum_strat"] = (1 + df["strategy_return"]).cumprod()
    
    # 最大回撤
    rolling_max = df["cum_strat"].cummax()
    df["drawdown"] = (df["cum_strat"] - rolling_max) / rolling_max
    max_dd = df["drawdown"].min() * 100
    
    # 夏普
    strat_std = df["strategy_return"].std()
    if strat_std > 0:
        sharpe = (df["strategy_return"].mean() * 252 - 0.03) / (strat_std * np.sqrt(252))
    else:
        sharpe = 0
    
    return {
        "total_bh": (df["cum_bh"].iloc[-1] - 1) * 100,
        "total_strat": (df["cum_strat"].iloc[-1] - 1) * 100,
        "max_dd": max_dd,
        "sharpe": sharpe,
        "data_len": len(df)
    }


def main():
    print("="*70)
    print("ETF/指数均线金叉策略回测")
    print("="*70)
    print(f"策略: 5日均线 > 20日均线 买入，5日均线 < 20日均线 卖出")
    print(f"回测区间: 2020-01-01 ~ 2026-06-07")
    print("="*70)
    
    # 用指数代替ETF（相关性很高）
    indices = [
        ("sh.000300", "沪深300指数"),  # 代替510300
        ("sz.399006", "创业板指数"),   # 代替159915
        ("sh.000688", "科创50指数"),   # 代替588000
        ("sh.000905", "中证500指数"),  # 代替510500
    ]
    
    results = []
    
    for code, name in indices:
        df = get_index_data(code, name)
        
        if df is not None and len(df) > 100:
            # 只取近1年数据
            cutoff = pd.Timestamp.now() - pd.Timedelta(days=365)
            df = df[df["date"] >= cutoff].copy()
            
            if len(df) > 50:
                stats = ma_cross_strategy(df)
                
                results.append({
                    "指数": name,
                    "代码": code,
                    "持有收益(%)": round(stats["total_bh"], 2),
                    "策略收益(%)": round(stats["total_strat"], 2),
                    "最大回撤(%)": round(stats["max_dd"], 2),
                    "夏普比率": round(stats["sharpe"], 2),
                    "数据天数": stats["data_len"]
                })
    
    # 登出
    bs.logout()
    
    # 打印结果
    if results:
        print("\n" + "="*70)
        print("回测结果汇总 (近1年)")
        print("="*70)
        
        df_result = pd.DataFrame(results)
        print(df_result.to_string(index=False))
        
        # 保存
        df_result.to_csv("backtest_result.csv", index=False, encoding="utf-8-sig")
        print(f"\n✅ 结果已保存到 backtest_result.csv")
        
        print("\n" + "="*70)
        print("策略解读")
        print("="*70)
        
        best = max(results, key=lambda x: x["策略收益(%)"])
        print(f"🏆 策略收益最高: {best['指数']}")
        print(f"   策略: {best['策略收益(%)']}% | 持有: {best['持有收益(%)']}% | 最大回撤: {best['最大回撤(%)']}%")
        
        print("\n📊 策略 vs 持有收益:")
        for r in results:
            diff = r["策略收益(%)"] - r["持有收益(%)"]
            flag = "✅" if diff > 0 else "❌"
            print(f"   {flag} {r['指数']}: 策略 {r['策略收益(%)']}% vs 持有 {r['持有收益(%)']}% (差异 {diff:+.1f}%)")
        
        print("\n💡 结论:")
        strat_wins = sum(1 for r in results if r["策略收益(%)"] > r["持有收益(%)"])
        print(f"   均线策略在 {strat_wins}/{len(results)} 个指数上跑赢持有")
        
        # 风险评估
        print(f"\n⚠️ 风险评估:")
        for r in results:
            risk = "🔴" if r["最大回撤(%)"] < -30 else "🟡" if r["最大回撤(%)"] < -20 else "🟢"
            print(f"   {risk} {r['指数']}: 最大回撤 {r['最大回撤(%)']}%")
        
    else:
        print("\n❌ 未能获取任何数据!")


if __name__ == "__main__":
    main()
