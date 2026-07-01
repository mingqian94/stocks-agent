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

# 登录
bs.login()


def get_index_data(code, name, start_date="2016-01-01", end_date="2026-06-07"):
    """获取指数历史数据"""
    try:
        rs = bs.query_history_k_data_plus(
            code,
            "date,open,high,low,close,volume",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="2"
        )
        
        if rs.error_code != "0":
            return None
        
        data_list = []
        while rs.error_code == "0" and rs.next():
            data_list.append(rs.get_row_data())
        
        if not data_list:
            return None
        
        df = pd.DataFrame(data_list, columns=rs.fields)
        df["date"] = pd.to_datetime(df["date"])
        
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        
        return df.dropna().sort_values("date").reset_index(drop=True)
    
    except:
        return None


def ma_cross_strategy(df):
    """均线金叉策略"""
    df = df.copy()
    
    # 均线
    df["ma_short"] = df["close"].rolling(5).mean()
    df["ma_long"] = df["close"].rolling(20).mean()
    
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
    
    # 年化收益
    days = len(df)
    years = days / 252
    if years > 0:
        annual_bh = (df["cum_bh"].iloc[-1] ** (1/years) - 1) * 100
        annual_strat = (df["cum_strat"].iloc[-1] ** (1/years) - 1) * 100
    else:
        annual_bh = annual_strat = 0
    
    return {
        "持有总收益": (df["cum_bh"].iloc[-1] - 1) * 100,
        "策略总收益": (df["cum_strat"].iloc[-1] - 1) * 100,
        "持有年化": annual_bh,
        "策略年化": annual_strat,
        "最大回撤": max_dd,
        "数据天数": len(df)
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
