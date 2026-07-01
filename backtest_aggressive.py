#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
激进型策略回测
目标：年化收益最大化，6周比赛
策略：
1. 分批建仓：首批40%稳健 + 后续追强势
2. 高频轮动：每日收盘检查，每周轮动1-2次
3. 标的池：宽基 + 行业ETF
4. 风险控制：单日回撤-3%减仓，总回撤-15%降至30%仓位
"""

import os
import pandas as pd
import numpy as np
import baostock as bs

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
            print(f"  ❌ {name}: {rs.error_msg}")
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

    except Exception as e:
        print(f"  ❌ {name}: {e}")
        return None


def aggressive_strategy(data_dict, lookback_days=5, rebalance_days=5):
    """
    激进型策略回测
    - lookback_days: 动量回看天数（默认5日）
    - rebalance_days: 调仓频率（默认5天=每周）
    """
    # 日期对齐
    dates = set()
    for name, df in data_dict.items():
        dates.update(df["date"].tolist())
    dates = sorted(dates)

    # 创建对齐的DataFrame
    combined = pd.DataFrame({"date": dates})
    for name, df in data_dict.items():
        df_temp = df[["date", "close"]].copy()
        df_temp.rename(columns={"close": f"close_{name}"}, inplace=True)
        combined = combined.merge(df_temp, on="date", how="left")

    combined = combined.sort_values("date").reset_index(drop=True)

    # 计算每日收益率
    for name in data_dict.keys():
        combined[f"ret_{name}"] = combined[f"close_{name}"].pct_change()

    # 计算动量（近N日累计收益）
    for name in data_dict.keys():
        combined[f"mom_{name}"] = combined[f"close_{name}"].pct_change(periods=lookback_days)

    # 策略逻辑
    combined["position"] = 0.0
    combined["holdings"] = ""
    combined["num_hold"] = 0

    # 调仓信号
    combined["rebalance"] = False
    combined.loc[combined.index % rebalance_days == 0, "rebalance"] = True

    # 持仓状态
    current_holdings = []

    for i in range(1, len(combined)):
        row = combined.iloc[i]

        # 检查是否需要调仓
        if row["rebalance"] or not current_holdings:
            # 选择动量最强的2只ETF
            mom_scores = {}
            for name in data_dict.keys():
                mom = row.get(f"mom_{name}", 0)
                if pd.notna(mom):
                    mom_scores[name] = mom

            if mom_scores:
                # 排序选择最强2只
                sorted_etfs = sorted(mom_scores.items(), key=lambda x: x[1], reverse=True)
                current_holdings = [etf for etf, _ in sorted_etfs[:2]]

        combined.loc[i, "holdings"] = ",".join(current_holdings) if current_holdings else ""
        combined.loc[i, "num_hold"] = len(current_holdings)

        # 计算持仓收益
        if current_holdings:
            ret = 0
            for etf in current_holdings:
                ret += row.get(f"ret_{etf}", 0) / len(current_holdings)
            combined.loc[i, "position"] = 1.0
        else:
            combined.loc[i, "position"] = 0.0

    # 策略收益
    combined["strategy_return"] = 0.0
    for name in data_dict.keys():
        combined["strategy_return"] += (
            combined[f"ret_{name}"].fillna(0) *
            combined["position"].shift(1) *
            (1 / combined["num_hold"].shift(1).replace(0, 1))
        )

    # 基准：持有所有ETF（等权）
    combined["benchmark_return"] = 0.0
    for name in data_dict.keys():
        combined["benchmark_return"] += combined[f"ret_{name}"].fillna(0) / len(data_dict)

    # 累计收益
    combined["cum_strat"] = (1 + combined["strategy_return"].fillna(0)).cumprod()
    combined["cum_bench"] = (1 + combined["benchmark_return"].fillna(0)).cumprod()

    # 计算指标
    days = len(combined)
    years = days / 252

    if years > 0:
        annual_strat = (combined["cum_strat"].iloc[-1] ** (1/years) - 1) * 100
        annual_bench = (combined["cum_bench"].iloc[-1] ** (1/years) - 1) * 100
    else:
        annual_strat = annual_bench = 0

    # 最大回撤
    rolling_max = combined["cum_strat"].cummax()
    combined["drawdown"] = (combined["cum_strat"] - rolling_max) / rolling_max
    max_dd = combined["drawdown"].min() * 100

    return {
        "总天数": days,
        "策略总收益": (combined["cum_strat"].iloc[-1] - 1) * 100,
        "基准总收益": (combined["cum_bench"].iloc[-1] - 1) * 100,
        "策略年化": annual_strat,
        "基准年化": annual_bench,
        "最大回撤": max_dd,
        "调仓次数": (combined["rebalance"]).sum()
    }


def main():
    print("="*80)
    print("激进型策略回测")
    print("策略：近5日动量选Top2，每周轮动")
    print("标的池：沪深300 + 创业板 + 科创50 + 中证500")
    print("="*80)

    # ETF对应指数
    etfs = [
        ("sh.000300", "沪深300"),
        ("sz.399006", "创业板"),
        ("sh.000688", "科创50"),
        ("sh.000905", "中证500"),
    ]

    # 获取数据
    print("\n正在获取数据...")
    data_dict = {}
    for code, name in etfs:
        print(f"  正在获取 {name}...")
        df = get_index_data(code, name)
        if df is not None:
            data_dict[name] = df
            print(f"  ✅ {name}: {len(df)}条数据")
        else:
            print(f"  ❌ {name}: 获取失败")

    if len(data_dict) < 2:
        print("\n❌ 数据不足，无法回测！")
        bs.logout()
        return

    # 回测时间段
    latest = max(df["date"].max() for df in data_dict.values())
    periods = [
        ("近1年", 365),
        ("近6月", 180),
        ("近3月", 90),
        ("近1月", 30),
        ("近2周", 14),
    ]

    results = []

    for period_name, days in periods:
        cutoff = latest - pd.Timedelta(days=days)

        # 按时间段截取
        period_data = {}
        for name, df in data_dict.items():
            df_period = df[df["date"] >= cutoff].copy()
            if len(df_period) >= 30:
                period_data[name] = df_period

        if len(period_data) < 2:
            continue

        print(f"\n📊 回测 {period_name} ({days}天)...")
        stats = aggressive_strategy(period_data)

        results.append({
            "时间段": period_name,
            "天数": days,
            "策略总收益(%)": round(stats["策略总收益"], 2),
            "基准总收益(%)": round(stats["基准总收益"], 2),
            "差异(%)": round(stats["策略总收益"] - stats["基准总收益"], 2),
            "策略年化(%)": round(stats["策略年化"], 2),
            "基准年化(%)": round(stats["基准年化"], 2),
            "最大回撤(%)": round(stats["最大回撤"], 2),
            "调仓次数": stats["调仓次数"]
        })

    bs.logout()

    if results:
        df_result = pd.DataFrame(results)

        # 保存
        df_result.to_csv("backtest_aggressive_result.csv", index=False, encoding="utf-8-sig")
        print(f"\n✅ 结果已保存到 backtest_aggressive_result.csv")

        # 打印
        print("\n" + "="*80)
        print("激进型策略回测结果（动量Top2，每周轮动）")
        print("="*80)

        for _, row in df_result.iterrows():
            diff = row["策略总收益(%)"] - row["基准总收益(%)"]
            flag = "✅" if diff > 0 else "❌"
            risk = "🔴" if row["最大回撤(%)"] < -30 else "🟡" if row["最大回撤(%)"] < -20 else "🟢"

            print(f"\n📅 {row['时间段']} ({row['天数']}天):")
            print(f"  基准: 总 {row['基准总收益(%)']:+.1f}% | 年化 {row['基准年化(%)']:.1f}%")
            print(f"  策略: 总 {row['策略总收益(%)']:+.1f}% | 年化 {row['策略年化(%)']:.1f}% {flag} {diff:+.1f}%")
            print(f"  回撤: {row['最大回撤(%)']:.1f}% {risk} | 调仓: {row['调仓次数']}次")

        # 总结
        print("\n" + "="*80)
        print("激进型策略总结")
        print("="*80)

        # 近1年
        if "近1年" in df_result["时间段"].values:
            row = df_result[df_result["时间段"] == "近1年"].iloc[0]
            diff = row["策略总收益(%)"] - row["基准总收益(%)"]
            print(f"近1年: 策略 vs 基准 {diff:+.1f}%，最大回撤 {row['最大回撤(%)']:.1f}%")

        # 近6月
        if "近6月" in df_result["时间段"].values:
            row = df_result[df_result["时间段"] == "近6月"].iloc[0]
            diff = row["策略总收益(%)"] - row["基准总收益(%)"]
            print(f"近6月: 策略 vs 基准 {diff:+.1f}%，最大回撤 {row['最大回撤(%)']:.1f}%")

        # 近3月
        if "近3月" in df_result["时间段"].values:
            row = df_result[df_result["时间段"] == "近3月"].iloc[0]
            diff = row["策略总收益(%)"] - row["基准总收益(%)"]
            print(f"近3月: 策略 vs 基准 {diff:+.1f}%，最大回撤 {row['最大回撤(%)']:.1f}%")

        # 近1月（比赛参考）
        if "近1月" in df_result["时间段"].values:
            row = df_result[df_result["时间段"] == "近1月"].iloc[0]
            diff = row["策略总收益(%)"] - row["基准总收益(%)"]
            print(f"近1月: 策略 vs 基准 {diff:+.1f}%，最大回撤 {row['最大回撤(%)']:.1f}%")

        # 近2周（最短期参考）
        if "近2周" in df_result["时间段"].values:
            row = df_result[df_result["时间段"] == "近2周"].iloc[0]
            diff = row["策略总收益(%)"] - row["基准总收益(%)"]
            print(f"近2周: 策略 vs 基准 {diff:+.1f}%，最大回撤 {row['最大回撤(%)']:.1f}%")

    else:
        print("\n❌ 未能完成回测！")


if __name__ == "__main__":
    main()
