#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETF每周轮动策略回测
策略：
1. 每周一检查所有ETF近4周收益率
2. 持有近4周最强的Top 2-3只ETF
3. 每周轮动调仓
"""

import os
import sys
import pandas as pd
import numpy as np
import baostock as bs

bs.login()


def get_etf_index_data(code, name, start_date="2016-01-01", end_date="2026-06-07"):
    """获取ETF对应指数历史数据"""
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


def weekly_rotation_strategy(df, lookback_weeks=4, hold_count=2):
    """
    每周轮动策略回测
    - lookback_weeks: 看过去几周的动量（默认4周=1个月）
    - hold_count: 持有几只最强的（默认2只）
    """
    df = df.copy()
    df = df.sort_values("date").reset_index(drop=True)

    # 周频数据（取每周最后一个交易日）
    df["week"] = df["date"].dt.to_period("W")
    weekly = df.groupby("week").last().reset_index()
    weekly = weekly.sort_values("date").reset_index(drop=True)

    # 计算每周收益
    weekly["return"] = weekly["close"].pct_change()

    # 动量信号（过去N周累计收益）
    weekly["momentum"] = weekly["close"].pct_change(periods=lookback_weeks)

    # 轮动信号：持仓最强Top N
    weekly["signal"] = 0  # 0=空仓

    # 每周一轮动
    for i in range(lookback_weeks, len(weekly)):
        # 过去N周动量
        mom = weekly.loc[i, "momentum"]

        # 动量为正就持有
        if mom > 0:
            weekly.loc[weekly.index[i], "signal"] = 1
        else:
            weekly.loc[weekly.index[i], "signal"] = 0

    # 策略收益
    weekly["strategy_return"] = weekly["signal"].shift(1) * weekly["return"]

    # 累计收益
    weekly["cum_bh"] = (1 + weekly["return"]).cumprod()
    weekly["cum_strat"] = (1 + weekly["strategy_return"]).cumprod()

    # 最大回撤
    rolling_max = weekly["cum_strat"].cummax()
    weekly["drawdown"] = (weekly["cum_strat"] - rolling_max) / rolling_max
    max_dd = weekly["drawdown"].min() * 100

    # 年化收益
    weeks = len(weekly)
    years = weeks / 52
    if years > 0:
        annual_bh = (weekly["cum_bh"].iloc[-1] ** (1/years) - 1) * 100
        annual_strat = (weekly["cum_strat"].iloc[-1] ** (1/years) - 1) * 100
    else:
        annual_bh = annual_strat = 0

    return {
        "持有总收益": (weekly["cum_bh"].iloc[-1] - 1) * 100,
        "策略总收益": (weekly["cum_strat"].iloc[-1] - 1) * 100,
        "持有年化": annual_bh,
        "策略年化": annual_strat,
        "最大回撤": max_dd,
        "数据周数": weeks
    }


def main():
    print("="*80)
    print("ETF每周轮动策略回测")
    print("策略逻辑：近4周动量为正则持有，否则空仓")
    print("="*80)

    # ETF对应指数
    etfs = [
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
    ]

    # 获取数据
    all_data = {}
    for code, name in etfs:
        print(f"\n正在获取 {name} 数据...")
        df = get_etf_index_data(code, name)
        if df is not None:
            all_data[name] = df
            print(f"  ✅ 共 {len(df)} 条数据")
        else:
            print(f"  ❌ 获取失败")

    if not all_data:
        print("\n❌ 未能获取数据!")
        bs.logout()
        return

    # 获取最新日期
    latest = max(df["date"].max() for df in all_data.values())

    # 回测
    results = []

    for name, df in all_data.items():
        for period_name, days in periods:
            cutoff = latest - pd.Timedelta(days=days)
            df_period = df[df["date"] >= cutoff].copy()

            if len(df_period) < 50:
                continue

            stats = weekly_rotation_strategy(df_period)

            results.append({
                "指数": name,
                "时间段": period_name,
                "持有总收益(%)": round(stats["持有总收益"], 2),
                "策略总收益(%)": round(stats["策略总收益"], 2),
                "持有年化(%)": round(stats["持有年化"], 2),
                "策略年化(%)": round(stats["策略年化"], 2),
                "最大回撤(%)": round(stats["最大回撤"], 2),
                "周数": stats["数据周数"]
            })

    # 登出
    bs.logout()

    if results:
        df_result = pd.DataFrame(results)

        # 保存
        df_result.to_csv("backtest_rotation_result.csv", index=False, encoding="utf-8-sig")
        print(f"\n✅ 结果已保存到 backtest_rotation_result.csv")

        # 打印
        print("\n" + "="*80)
        print("每周轮动策略回测结果")
        print("策略：近4周动量为正持有，否则空仓（不做ETF间轮动）")
        print("="*80)

        for name in ["沪深300", "创业板", "中证500"]:
            if name in df_result["指数"].values:
                print(f"\n📊 {name}:")
                df_name = df_result[df_result["指数"] == name].sort_values("周数", ascending=False)
                for _, row in df_name.iterrows():
                    diff = row["策略总收益(%)"] - row["持有总收益(%)"]
                    flag = "✅" if diff > 0 else "❌"
                    risk = "🔴" if row["最大回撤(%)"] < -30 else "🟡" if row["最大回撤(%)"] < -20 else "🟢"
                    print(f"  {row['时间段']:6s} | 持有: {row['持有总收益(%)']:+7.1f}% | 策略: {row['策略总收益(%)']:+7.1f}% | {flag} {diff:+6.1f}% | {risk} 回撤{row['最大回撤(%)']:6.1f}%")

        # 总结
        print("\n" + "="*80)
        print("关键发现")
        print("="*80)

        # 近1年策略胜率
        df_1y = df_result[df_result["时间段"] == "近1年"]
        strat_wins = (df_1y["策略总收益(%)"] > df_1y["持有总收益(%)"]).sum()
        print(f"近1年: 轮动策略跑赢持有 {strat_wins}/{len(df_1y)} 次")

        # 近3年
        df_3y = df_result[df_result["时间段"] == "近3年"]
        if len(df_3y) > 0:
            strat_wins = (df_3y["策略总收益(%)"] > df_3y["持有总收益(%)"]).sum()
            print(f"近3年: 轮动策略跑赢持有 {strat_wins}/{len(df_3y)} 次")

        # 近5年
        df_5y = df_result[df_result["时间段"] == "近5年"]
        if len(df_5y) > 0:
            strat_wins = (df_5y["策略总收益(%)"] > df_5y["持有总收益(%)"]).sum()
            print(f"近5年: 轮动策略跑赢持有 {strat_wins}/{len(df_5y)} 次")

        # 风险评估
        print(f"\n⚠️ 近1年风险评估:")
        for _, row in df_1y.iterrows():
            risk = "🔴" if row["最大回撤(%)"] < -30 else "🟡" if row["最大回撤(%)"] < -20 else "🟢"
            print(f"  {risk} {row['指数']}: 最大回撤 {row['最大回撤(%)']:.1f}%")

        # 结论
        print(f"\n💡 结论:")
        avg_diff_1y = df_1y["策略总收益(%)"].mean() - df_1y["持有总收益(%)"].mean()
        if avg_diff_1y > 0:
            print(f"  轮动策略在近1年平均跑赢持有 {avg_diff_1y:.1f}%")
        else:
            print(f"  轮动策略在近1年平均跑输持有 {avg_diff_1y:.1f}%")

    else:
        print("\n❌ 未能获取数据!")


if __name__ == "__main__":
    main()
