"""Independent, low-resource tests of three Sequoia-X-inspired hypotheses.

Only the public rule descriptions are reproduced.  Data, point-in-time
universe handling, portfolio construction and execution remain inside this
project's A-share research engine.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from .data import default_cache_dir, load_public_bundle
from .engine import BacktestConfig, StrategySpec, prepare_features, run_backtest
from .experiments import _flat_result
from .horizons import trailing_windows


def prepare_sequoia_features(prices: pd.DataFrame) -> pd.DataFrame:
    """Add only the expensive rolling features required by these hypotheses."""
    frame = prepare_features(prices)
    grouped = frame.groupby("code", group_keys=False)
    signal_scale = frame["signal_price"] / frame["close"]
    frame["signal_high"] = frame["high"] * signal_scale
    frame["signal_low"] = frame["low"] * signal_scale
    signal_grouped = frame.groupby("code", group_keys=False)["signal_price"]
    frame["return_120d"] = signal_grouped.pct_change(120, fill_method=None)
    frame["ma5"] = signal_grouped.transform(lambda values: values.rolling(5).mean())
    frame["ma5_previous"] = grouped["ma5"].shift(1)
    frame["ma20_previous"] = grouped["ma20"].shift(1)
    frame["volume20_lag1"] = grouped["volume"].transform(
        lambda values: values.rolling(20).mean().shift(1)
    )
    frame["volume20"] = grouped["volume"].transform(
        lambda values: values.rolling(20).mean()
    )
    for window in (10, 40, 120):
        frame[f"high{window}"] = grouped["signal_high"].transform(
            lambda values, window=window: values.rolling(window).max()
        )
        if window != 120:
            frame[f"low{window}"] = grouped["signal_low"].transform(
                lambda values, window=window: values.rolling(window).min()
            )
    return frame.replace([np.inf, -np.inf], np.nan)


def sequoia_x_specs() -> list[StrategySpec]:
    """Return three frozen entry hypotheses under one portfolio shell."""
    common = {
        "max_positions": 4,
        "stop_loss": -0.08,
        "take_profit": 0.15,
        "max_holding_days": 20,
        "exit_model": "ma20",
    }
    return [
        StrategySpec(
            name="high_tight_flag_40_10",
            entry_model="high_tight_flag",
            minimum_history=40,
            **common,
        ),
        StrategySpec(
            name="rps120_near_high",
            entry_model="rps120_near_high",
            minimum_history=121,
            **common,
        ),
        StrategySpec(
            name="ma5_cross_ma20_volume15",
            entry_model="ma5_cross_ma20_volume15",
            minimum_history=21,
            **common,
        ),
    ]


def run_sequoia_x_horizons(
    end_date: str = "2026-07-31",
    cache_dir: Path | None = None,
    output_dir: Path | None = None,
) -> pd.DataFrame:
    """Run the frozen hypotheses over the project's five standard horizons."""
    bundle = load_public_bundle(cache_dir or default_cache_dir())
    prices = prepare_sequoia_features(bundle.prices)
    output = output_dir or Path(__file__).resolve().parents[1] / "research" / "results"
    output.mkdir(parents=True, exist_ok=True)
    windows = trailing_windows(end_date)
    window_prices = {
        horizon: prices[
            prices["date"].between(pd.Timestamp(start_date), pd.Timestamp(end_date))
        ]
        for horizon, start_date in windows.items()
    }
    records: list[dict] = []
    specs = sequoia_x_specs()
    total = len(specs) * len(windows)
    number = 0
    for spec in specs:
        for horizon, start_date in windows.items():
            number += 1
            print(f"Sequoia-X {number}/{total}: {spec.name} {horizon}", flush=True)
            result = run_backtest(
                prices=window_prices[horizon],
                memberships=bundle.memberships,
                benchmark=bundle.benchmark,
                spec=spec,
                start_date=start_date,
                end_date=end_date,
                config=BacktestConfig(),
            )
            record = _flat_result(result, horizon)
            record["horizon"] = horizon
            record["strategy_origin"] = "sequoia_x_independent_reimplementation"
            record["validation_status"] = "exploratory_hypothesis_test_seen"
            records.append(record)

    frame = pd.DataFrame(records)
    order = {name: index for index, name in enumerate(windows)}
    frame["horizon_order"] = frame["horizon"].map(order)
    frame = frame.sort_values(
        ["horizon_order", "total_return", "max_drawdown"],
        ascending=[True, False, False],
    ).drop(columns="horizon_order")
    frame["return_rank"] = frame.groupby("horizon")["total_return"].rank(
        method="min", ascending=False
    ).astype(int)
    frame.to_csv(
        output / "a_share_sequoia_x_horizons_2026-10-10.csv",
        index=False,
        encoding="utf-8-sig",
    )
    return frame


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run three Sequoia-X-inspired hypotheses over fixed horizons"
    )
    parser.add_argument("--end", default="2026-07-31")
    parser.add_argument("--cache-dir", type=Path, default=default_cache_dir())
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "research" / "results",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    frame = run_sequoia_x_horizons(args.end, args.cache_dir, args.output_dir)
    columns = [
        "horizon",
        "return_rank",
        "strategy",
        "total_return",
        "max_drawdown",
        "sharpe",
        "trades",
        "benchmark_total_return",
        "excess_total_return",
    ]
    print(frame[columns].to_string(index=False))


if __name__ == "__main__":
    main()
