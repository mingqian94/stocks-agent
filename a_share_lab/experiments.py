"""Strategy presets and reproducible train/test experiment runner."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from .data import default_cache_dir, download_public_bundle, load_public_bundle
from .engine import BacktestConfig, StrategySpec, prepare_features, run_backtest


def strategy_presets() -> list[StrategySpec]:
    """Small, theory-driven comparison set rather than a fine parameter search."""
    return [
        StrategySpec(
            name="daily_breakout_2_fixed",
            entry_model="daily_breakout",
            max_positions=2,
            stop_loss=-0.05,
            take_profit=0.08,
            max_holding_days=None,
        ),
        StrategySpec(
            name="daily_rank_10_time1",
            entry_model="daily_rank",
            max_positions=10,
            stop_loss=-0.08,
            take_profit=None,
            max_holding_days=1,
            require_previous_day_up=False,
        ),
        StrategySpec(
            name="daily_rank_10_time2",
            entry_model="daily_rank",
            max_positions=10,
            stop_loss=-0.08,
            take_profit=None,
            max_holding_days=2,
            require_previous_day_up=False,
        ),
        StrategySpec(
            name="daily_rank_no_touch_10_time1",
            entry_model="daily_rank",
            max_positions=10,
            stop_loss=-0.08,
            take_profit=None,
            max_holding_days=1,
            require_previous_day_up=False,
            exclude_limit_touch=True,
        ),
        StrategySpec(
            name="daily_rank_no_touch_10_time2",
            entry_model="daily_rank",
            max_positions=10,
            stop_loss=-0.08,
            take_profit=None,
            max_holding_days=2,
            require_previous_day_up=False,
            exclude_limit_touch=True,
        ),
        StrategySpec(
            name="daily_breakout_2_time1",
            entry_model="daily_breakout",
            max_positions=2,
            stop_loss=-0.05,
            take_profit=0.08,
            max_holding_days=1,
        ),
        StrategySpec(
            name="daily_breakout_2_time2",
            entry_model="daily_breakout",
            max_positions=2,
            stop_loss=-0.05,
            take_profit=0.08,
            max_holding_days=2,
        ),
        StrategySpec(
            name="daily_breakout_2_time3",
            entry_model="daily_breakout",
            max_positions=2,
            stop_loss=-0.05,
            take_profit=0.08,
            max_holding_days=3,
        ),
        StrategySpec(
            name="daily_breakout_2_time5",
            entry_model="daily_breakout",
            max_positions=2,
            stop_loss=-0.05,
            take_profit=0.08,
            max_holding_days=5,
        ),
        StrategySpec(
            name="daily_breakout_2_time5_market_ma20",
            entry_model="daily_breakout",
            max_positions=2,
            stop_loss=-0.05,
            take_profit=0.08,
            max_holding_days=5,
            market_gate="ma20",
        ),
        StrategySpec(
            name="daily_breakout_2_time5_market_ma60",
            entry_model="daily_breakout",
            max_positions=2,
            stop_loss=-0.05,
            take_profit=0.08,
            max_holding_days=5,
            market_gate="ma60",
        ),
        StrategySpec(
            name="daily_breakout_2_time10",
            entry_model="daily_breakout",
            max_positions=2,
            stop_loss=-0.05,
            take_profit=0.08,
            max_holding_days=10,
        ),
        StrategySpec(
            name="daily_breakout_4_time10",
            entry_model="daily_breakout",
            max_positions=4,
            stop_loss=-0.05,
            take_profit=0.08,
            max_holding_days=10,
        ),
        StrategySpec(
            name="momentum5_4_time10",
            entry_model="momentum_5d",
            max_positions=4,
            stop_loss=-0.06,
            take_profit=0.12,
            max_holding_days=10,
            exit_model="momentum_5d",
            maximum_daily_return=0.06,
        ),
        StrategySpec(
            name="risk_adjusted20_4_ma20",
            entry_model="risk_adjusted_20d",
            max_positions=4,
            stop_loss=-0.08,
            take_profit=0.15,
            max_holding_days=20,
            exit_model="ma20",
        ),
        StrategySpec(
            name="risk_adjusted20_6_ma20",
            entry_model="risk_adjusted_20d",
            max_positions=6,
            stop_loss=-0.08,
            take_profit=0.15,
            max_holding_days=20,
            exit_model="ma20",
        ),
        StrategySpec(
            name="reversal10_4_time5",
            entry_model="reversal_10d",
            max_positions=4,
            stop_loss=-0.08,
            take_profit=0.10,
            max_holding_days=5,
        ),
    ]


def _data_quality(bundle, requested_end: str) -> dict:
    prices = bundle.prices
    membership_codes = set(bundle.memberships["code"].unique())
    price_codes = set(prices["code"].unique())
    missing_columns = {
        column: float(prices[column].isna().mean())
        for column in ["open", "high", "low", "close", "preclose", "amount", "pctChg"]
        if column in prices
    }
    raw_return = prices["close"] / prices["preclose"] - 1.0
    action_gap = (raw_return - prices["pctChg"] / 100.0).abs()
    last_dates = prices.groupby("code")["date"].max()
    stale_cutoff = pd.Timestamp(requested_end) - pd.Timedelta(days=45)
    return {
        "rows": int(len(prices)),
        "symbols": int(len(price_codes)),
        "membership_symbols": int(len(membership_codes)),
        "missing_membership_symbols": sorted(membership_codes - price_codes),
        "duplicate_date_code_rows": int(prices.duplicated(["date", "code"]).sum()),
        "min_date": prices["date"].min().date().isoformat(),
        "max_date": prices["date"].max().date().isoformat(),
        "adjustflags": sorted(int(value) for value in prices["adjustflag"].dropna().unique()),
        "missing_fraction": missing_columns,
        "suspended_rows": int((prices["tradestatus"] != 1).sum()),
        "st_rows": int((prices["isST"] == 1).sum()),
        "corporate_action_gap_rows_over_50bp": int((action_gap > 0.005).sum()),
        "symbols_ending_over_45_days_early": int((last_dates < stale_cutoff).sum()),
        "membership_snapshots": int(bundle.memberships["snapshot_date"].nunique()),
        "benchmark_rows": int(len(bundle.benchmark)),
    }


def _flat_result(result: dict, split: str) -> dict:
    metrics = result["metrics"]
    benchmark = result["benchmark_metrics"]
    equal_weight = result.get("equal_weight_metrics", {})
    audit = result.get("execution_audit", {})
    return {
        "strategy": result["strategy"],
        "split": split,
        "start_date": result["start_date"],
        "end_date": result["end_date"],
        **metrics,
        "benchmark_total_return": benchmark.get("total_return", 0.0),
        "benchmark_max_drawdown": benchmark.get("max_drawdown", 0.0),
        "equal_weight_total_return": equal_weight.get("total_return", 0.0),
        "equal_weight_max_drawdown": equal_weight.get("max_drawdown", 0.0),
        "excess_total_return": metrics.get("total_return", 0.0) - benchmark.get("total_return", 0.0),
        "excess_vs_equal_weight": metrics.get("total_return", 0.0) - equal_weight.get("total_return", 0.0),
        "buy_attempts": audit.get("buy_attempts", 0),
        "buy_blocked_limit": audit.get("buy_blocked_limit", 0),
        "buy_capacity_limited": audit.get("buy_capacity_limited", 0),
        "sell_blocked_limit": audit.get("sell_blocked_limit", 0),
        "sell_blocked_suspension": audit.get("sell_blocked_suspension", 0),
        "t1_stop_triggered": audit.get("t1_stop_triggered", 0),
        "market_gate_blocked_days": audit.get("market_gate_blocked_days", 0),
        "open_positions_at_end": audit.get("open_positions_at_end", 0),
    }


def _annual_rows(result: dict, split: str) -> list[dict]:
    curve = result["equity_curve"].copy()
    if curve.empty:
        return []
    curve["daily_return"] = curve["equity"].pct_change().fillna(0.0)
    curve["year"] = curve["date"].dt.year
    rows = []
    for year, group in curve.groupby("year"):
        compounded = float((1.0 + group["daily_return"]).prod() - 1.0)
        drawdown = float((group["equity"] / group["equity"].cummax() - 1.0).min())
        rows.append(
            {
                "strategy": result["strategy"],
                "split": split,
                "year": int(year),
                "return": compounded,
                "max_drawdown_within_year": drawdown,
                "average_exposure": float(group["exposure"].mean()),
            }
        )
    return rows


def run_experiments(
    start_date: str,
    train_end: str,
    test_start: str,
    end_date: str,
    cache_dir: Path,
    output_dir: Path,
    download: bool = False,
    refresh: bool = False,
) -> pd.DataFrame:
    bundle = (
        download_public_bundle(start_date, end_date, cache_dir=cache_dir, refresh=refresh)
        if download
        else load_public_bundle(cache_dir)
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "a_share_data_quality.json").write_text(
        json.dumps(_data_quality(bundle, end_date), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    config = BacktestConfig()
    print("Preparing lag-safe features once for all experiments", flush=True)
    prepared_prices = prepare_features(bundle.prices)
    records: list[dict] = []
    annual_records: list[dict] = []
    all_specs = strategy_presets()
    for number, spec in enumerate(all_specs, start=1):
        print(f"Experiment {number}/{len(all_specs)}: {spec.name}", flush=True)
        for split, split_start, split_end in (
            ("train", start_date, train_end),
            ("test", test_start, end_date),
        ):
            result = run_backtest(
                prices=prepared_prices,
                memberships=bundle.memberships,
                benchmark=bundle.benchmark,
                spec=spec,
                start_date=split_start,
                end_date=split_end,
                config=config,
            )
            records.append(_flat_result(result, split))
            annual_records.extend(_annual_rows(result, split))

    summary = pd.DataFrame(records).sort_values(["split", "sharpe"], ascending=[True, False])
    summary.to_csv(output_dir / "a_share_strategy_summary.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(annual_records).to_csv(
        output_dir / "a_share_strategy_annual.csv", index=False, encoding="utf-8-sig"
    )
    (output_dir / "a_share_strategy_specs.json").write_text(
        json.dumps([asdict(spec) for spec in all_specs], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Cost stress is deliberately limited to the three training-selected
    # candidates.  The selection never uses test returns.
    eligible_train = summary[(summary["split"] == "train") & (summary["trades"] >= 20)]
    top_names = eligible_train.sort_values(["sharpe", "max_drawdown"], ascending=False)[
        "strategy"
    ].head(3)
    specs_by_name = {spec.name: spec for spec in all_specs}
    stress_records: list[dict] = []
    high_cost = BacktestConfig(commission_rate=0.0005, slippage_bps=10.0)
    for name in top_names:
        result = run_backtest(
            prices=prepared_prices,
            memberships=bundle.memberships,
            benchmark=bundle.benchmark,
            spec=specs_by_name[name],
            start_date=test_start,
            end_date=end_date,
            config=high_cost,
        )
        record = _flat_result(result, "test")
        record["cost_case"] = "high_10bp_slippage_5bp_commission"
        stress_records.append(record)
    pd.DataFrame(stress_records).to_csv(
        output_dir / "a_share_cost_stress.csv", index=False, encoding="utf-8-sig"
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run reproducible public-data A-share strategy experiments")
    parser.add_argument("--start", default="2021-01-01")
    parser.add_argument("--train-end", default="2024-12-31")
    parser.add_argument("--test-start", default="2025-01-01")
    parser.add_argument("--end", default="2026-07-31")
    parser.add_argument("--cache-dir", type=Path, default=default_cache_dir())
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "research" / "results",
    )
    parser.add_argument("--download", action="store_true", help="Download or resume the public BaoStock cache")
    parser.add_argument("--refresh", action="store_true", help="Replace existing cache files")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = run_experiments(
        start_date=args.start,
        train_end=args.train_end,
        test_start=args.test_start,
        end_date=args.end,
        cache_dir=args.cache_dir,
        output_dir=args.output_dir,
        download=args.download,
        refresh=args.refresh,
    )
    display_columns = [
        "strategy", "split", "total_return", "annual_return", "max_drawdown", "sharpe",
        "trades", "win_rate", "average_exposure", "excess_total_return",
    ]
    print(summary[display_columns].to_string(index=False))


if __name__ == "__main__":
    main()
