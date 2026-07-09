#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETF策略全时间段回测
"""

import os
import sys
import pandas as pd
import numpy as np
import baostock as bs
from backtest_common import get_index_data, ma_cross_signal, calc_max_drawdown_pct, calc_annualized_return_pct

# 登录
bs.login()


def ma_cross_strategy(df):
    """均线金叉策略，统计持有/策略的总收益、年化收益、最大回撤"""
    df = ma_cross_signal(df, short_period=5, long_period=20)
    days = len(df)

    return {
        "持有总收益": (df["cum_bh"].iloc[-1] - 1) * 100,
        "策略总收益": (df["cum_strat"].iloc[-1] - 1) * 100,
        "持有年化": calc_annualized_return_pct(df["cum_bh"].iloc[-1], days),
        "策略年化": calc_annualized_return_pct(df["cum_strat"].iloc[-1], days),
        "最大回撤": calc_max_drawdown_pct(df["cum_strat"]),
        "数据天数": days
    }


def main():
    print("="*80)
    print("ETF均线金叉策略全时间段回测")
    print("策略: 5日均线 > 20日均线 买入，5日均线 < 20日均线 卖出")
    print("="*80)
    
    # 指数列表
    indices = [
        ("sh.000300", "沪深300"),
        ("sz.399006", "创业板"),
        ("sh.000905", "中证500"),
    ]
    
    # 回测时间段
    periods = [
        ("近5年", 365*5),
        ("近3年", 365*3),
        ("近1年", 365),
        ("近6月", 180),
        ("近3月", 90),
        ("近1月", 30),
        ("近2周", 14),
    ]
    
    # 获取完整数据
    all_data = {}
    for code, name in indices:
        print(f"\n正在获取 {name} 数据...")
        df = get_index_data(code, name)
        if df is not None:
            all_data[name] = df
            print(f"  ✅ 获取成功，共 {len(df)} 条数据")
        else:
            print(f"  ❌ 获取失败")
    
    if not all_data:
        print("\n❌ 未能获取任何数据!")
        bs.logout()
        return
    
    # 回测
    results = []
    
    for name, df in all_data.items():
        latest = df["date"].max()
        
        for period_name, days in periods:
            cutoff = latest - pd.Timedelta(days=days)
            df_period = df[df["date"] >= cutoff].copy()
            
            if len(df_period) < 20:
                continue
            
            stats = ma_cross_strategy(df_period)
            
            results.append({
                "指数": name,
                "时间段": period_name,
                "持有总收益(%)": round(stats["持有总收益"], 2),
                "策略总收益(%)": round(stats["策略总收益"], 2),
                "持有年化(%)": round(stats["持有年化"], 2),
                "策略年化(%)": round(stats["策略年化"], 2),
                "最大回撤(%)": round(stats["最大回撤"], 2),
                "天数": stats["数据天数"]
            })
    
    # 登出
    bs.logout()
    
    if results:
        df_result = pd.DataFrame(results)
        
        # 保存
        df_result.to_csv("backtest_full_result.csv", index=False, encoding="utf-8-sig")
        print(f"\n✅ 结果已保存到 backtest_full_result.csv")
        
        # 打印
        print("\n" + "="*80)
        print("回测结果汇总")
        print("="*80)
        
        for name in ["沪深300", "创业板", "中证500"]:
            if name in df_result["指数"].values:
                print(f"\n📊 {name}:")
                df_name = df_result[df_result["指数"] == name].sort_values("天数", ascending=False)
                for _, row in df_name.iterrows():
                    diff = row["策略总收益(%)"] - row["持有总收益(%)"]
                    flag = "✅" if diff > 0 else "❌"
                    risk = "🔴" if row["最大回撤(%)"] < -30 else "🟡" if row["最大回撤(%)"] < -20 else "🟢"
                    print(f"  {row['时间段']:6s} | 持有: {row['持有总收益(%)']:+7.1f}% | 策略: {row['策略总收益(%)']:+7.1f}% | {flag} {diff:+6.1f}% | {risk} 回撤{row['最大回撤(%)']:6.1f}%")
        
        # 总结
        print("\n" + "="*80)
        print("关键发现")
        print("="*80)
        
        # 短期策略胜率
        short_periods = ["近1月", "近2周"]
        for period in short_periods:
            df_period = df_result[df_result["时间段"] == period]
            strat_wins = (df_period["策略总收益(%)"] > df_period["持有总收益(%)"]).sum()
            total = len(df_period)
            if total > 0:
                print(f"  {period}: 策略跑赢持有 {strat_wins}/{total} 次")
        
        # 最大回撤风险
        print(f"\n⚠️ 风险提示:")
        for _, row in df_result[df_result["时间段"] == "近1年"].iterrows():
            risk = "🔴" if row["最大回撤(%)"] < -30 else "🟡" if row["最大回撤(%)"] < -20 else "🟢"
            print(f"  {risk} {row['指数']} 近1年最大回撤: {row['最大回撤(%)']:.1f}%")
        
        # 建议
        print(f"\n💡 操作建议:")
        
        # 找短期最好的
        df_short = df_result[df_result["时间段"] == "近3月"].copy()
        if len(df_short) > 0:
            best_3m = df_short.loc[df_short["策略总收益(%)"].idxmax()]
            print(f"  近3月策略最佳: {best_3m['指数']} (策略收益 {best_3m['策略总收益(%)']:.1f}%)")
        
        df_short = df_result[df_result["时间段"] == "近1月"].copy()
        if len(df_short) > 0:
            best_1m = df_short.loc[df_short["策略总收益(%)"].idxmax()]
            print(f"  近1月策略最佳: {best_1m['指数']} (策略收益 {best_1m['策略总收益(%)']:.1f}%)")
        
        df_short = df_result[df_result["时间段"] == "近2周"].copy()
        if len(df_short) > 0:
            best_2w = df_short.loc[df_short["策略总收益(%)"].idxmax()]
            print(f"  近2周策略最佳: {best_2w['指数']} (策略收益 {best_2w['策略总收益(%)']:.1f}%)")
        
    else:
        print("\n❌ 未能获取任何数据!")


if __name__ == "__main__":
    main()
