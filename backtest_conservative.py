#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
稳健型策略回测
目标：年化8%，回撤-20%以内
策略：
1. 均衡配置3只ETF：沪深300(40%) + 中证500(30%) + 创业板(30%)
2. 简单持有，不频繁交易
3. 最大回撤超过-10%时减仓到半仓
4. 年化收益目标8%
"""

import os
import sys
import pandas as pd
import numpy as np
import baostock as bs
from backtest_common import get_index_data, calc_max_drawdown_pct, calc_annualized_return_pct

bs.login()


def conservative_strategy(df_hs300, df_cyb, df_zz500):
    """
    稳健型策略回测
    - 配置比例：沪深300 40% + 创业板 30% + 中证500 30%
    - 简单持有，最大回撤-10%时减仓到半仓
    """
    # 日期对齐
    combined = pd.merge(df_hs300[["date", "close"]],
                        df_cyb[["date", "close"]],
                        on="date", suffixes=("_hs300", "_cyb"))
    combined = pd.merge(combined,
                        df_zz500[["date", "close"]],
                        on="date")
    combined.rename(columns={"close": "close_zz500"}, inplace=True)
    combined = combined.sort_values("date").reset_index(drop=True)

    # 计算各ETF收益
    combined["ret_hs300"] = combined["close_hs300"].pct_change()
    combined["ret_cyb"] = combined["close_cyb"].pct_change()
    combined["ret_zz500"] = combined["close_zz500"].pct_change()

    # 初始配置
    weights = {"hs300": 0.4, "cyb": 0.3, "zz500": 0.3}

    # 组合收益
    combined["portfolio_return"] = (
        combined["ret_hs300"] * weights["hs300"] +
        combined["ret_cyb"] * weights["cyb"] +
        combined["ret_zz500"] * weights["zz500"]
    )

    # 累计收益
    combined["cum_bh"] = (1 + combined["portfolio_return"]).cumprod()

    # 回撤控制：最大回撤超过-10%时减仓到半仓
    combined["position"] = 1.0  # 1.0=满仓，0.5=半仓
    combined["drawdown"] = 0.0
    rolling_max = combined["cum_bh"].iloc[0]

    for i in range(1, len(combined)):
        current_val = combined["cum_bh"].iloc[i]

        if current_val > rolling_max:
            rolling_max = current_val

        dd = (current_val - rolling_max) / rolling_max
        combined.loc[i, "drawdown"] = dd

        if dd < -0.10:
            # 回撤超过-10%，半仓
            combined.loc[i, "position"] = 0.5
        else:
            # 否则保持上一天的仓位
            combined.loc[i, "position"] = combined.loc[i-1, "position"]

    # 策略收益（带仓位控制）
    combined["strategy_return"] = combined["portfolio_return"] * combined["position"].shift(1)
    combined["cum_strat"] = (1 + combined["strategy_return"]).cumprod()

    # 计算指标
    days = len(combined)

    return {
        "总天数": days,
        "持有总收益": (combined["cum_bh"].iloc[-1] - 1) * 100,
        "策略总收益": (combined["cum_strat"].iloc[-1] - 1) * 100,
        "持有年化": calc_annualized_return_pct(combined["cum_bh"].iloc[-1], days),
        "策略年化": calc_annualized_return_pct(combined["cum_strat"].iloc[-1], days),
        "最大回撤": calc_max_drawdown_pct(combined["cum_strat"])
    }


def main():
    print("="*80)
    print("稳健型策略回测")
    print("配置：沪深300(40%) + 创业板(30%) + 中证500(30%)")
    print("规则：回撤超过-10%时减仓到半仓")
    print("目标：年化8%，最大回撤-20%以内")
    print("="*80)

    # 获取数据
    print("\n正在获取数据...")
    df_hs300 = get_index_data("sh.000300", "沪深300")
    df_cyb = get_index_data("sz.399006", "创业板")
    df_zz500 = get_index_data("sh.000905", "中证500")

    if not (df_hs300 is not None and df_cyb is not None and df_zz500 is not None):
        print("\n❌ 数据获取失败！")
        bs.logout()
        return

    print(f"✅ 沪深300: {len(df_hs300)}条数据")
    print(f"✅ 创业板: {len(df_cyb)}条数据")
    print(f"✅ 中证500: {len(df_zz500)}条数据")

    # 回测时间段
    latest = max(df_hs300["date"].max(), df_cyb["date"].max(), df_zz500["date"].max())
    periods = [
        ("近5年", 365*5),
        ("近3年", 365*3),
        ("近1年", 365),
        ("近6月", 180),
    ]

    results = []

    for period_name, days in periods:
        cutoff = latest - pd.Timedelta(days=days)

        # 按时间段截取
        df_h = df_hs300[df_hs300["date"] >= cutoff].copy()
        df_c = df_cyb[df_cyb["date"] >= cutoff].copy()
        df_z = df_zz500[df_zz500["date"] >= cutoff].copy()

        if len(df_h) < 100 or len(df_c) < 100 or len(df_z) < 100:
            continue

        stats = conservative_strategy(df_h, df_c, df_z)

        results.append({
            "时间段": period_name,
            "总天数": stats["总天数"],
            "持有总收益(%)": round(stats["持有总收益"], 2),
            "策略总收益(%)": round(stats["策略总收益"], 2),
            "持有年化(%)": round(stats["持有年化"], 2),
            "策略年化(%)": round(stats["策略年化"], 2),
            "最大回撤(%)": round(stats["最大回撤"], 2),
        })

    bs.logout()

    if results:
        df_result = pd.DataFrame(results)

        # 保存
        df_result.to_csv("backtest_conservative_result.csv", index=False, encoding="utf-8-sig")
        print(f"\n✅ 结果已保存到 backtest_conservative_result.csv")

        # 打印
        print("\n" + "="*80)
        print("稳健型策略回测结果")
        print("="*80)

        for _, row in df_result.iterrows():
            # 目标是否达成
            target_annual = 8.0
            target_dd = -20.0

            annual_ok = row["策略年化(%)"] >= target_annual
            dd_ok = row["最大回撤(%)"] >= target_dd

            flag_annual = "✅" if annual_ok else "❌"
            flag_dd = "🟢" if dd_ok else "🔴"

            print(f"\n📅 {row['时间段']}:")
            print(f"  持有: 总 {row['持有总收益(%)']:+.1f}% | 年化 {row['持有年化(%)']:.1f}%")
            print(f"  策略: 总 {row['策略总收益(%)']:+.1f}% | 年化 {row['策略年化(%)']:.1f}% {flag_annual}")
            print(f"  最大回撤: {row['最大回撤(%)']:.1f}% {flag_dd}")

        # 总结
        print("\n" + "="*80)
        print("策略总结")
        print("="*80)

        # 近1年是否达标
        if "近1年" in df_result["时间段"].values:
            row_1y = df_result[df_result["时间段"] == "近1年"].iloc[0]
            if row_1y["策略年化(%)"] >= 8 and row_1y["最大回撤(%)"] >= -20:
                print(f"🎉 近1年策略达标：年化{row_1y['策略年化(%)']:.1f}%，最大回撤{row_1y['最大回撤(%)']:.1f}%")
            else:
                print(f"⚠️ 近1年策略需优化：年化{row_1y['策略年化(%)']:.1f}%，最大回撤{row_1y['最大回撤(%)']:.1f}%")

        # 近3年
        if "近3年" in df_result["时间段"].values:
            row_3y = df_result[df_result["时间段"] == "近3年"].iloc[0]
            if row_3y["策略年化(%)"] >= 8 and row_3y["最大回撤(%)"] >= -20:
                print(f"🎉 近3年策略达标：年化{row_3y['策略年化(%)']:.1f}%，最大回撤{row_3y['最大回撤(%)']:.1f}%")
            else:
                print(f"⚠️ 近3年策略需优化：年化{row_3y['策略年化(%)']:.1f}%，最大回撤{row_3y['最大回撤(%)']:.1f}%")

    else:
        print("\n❌ 未能完成回测！")


if __name__ == "__main__":
    main()
