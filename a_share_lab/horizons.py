"""Compare frozen strategy specifications over several trailing horizons.

All horizons share the same end date and the same execution/cost model.  This
runner does not tune any parameter for a horizon; it is meant to reveal regime
sensitivity rather than select a strategy from a short sample.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .data import default_cache_dir, load_public_bundle
from .engine import BacktestConfig, StrategySpec, prepare_features, run_backtest
from .experiments import _flat_result, strategy_presets
from .second_generation import hypotheses


WINDOW_MONTHS = {
    "1_month": 1,
    "3_months": 3,
    "6_months": 6,
    "1_year": 12,
    "3_years": 36,
}


def trailing_windows(end_date: str) -> dict[str, str]:
    """Return inclusive calendar-month windows ending on ``end_date``."""
    end = pd.Timestamp(end_date)
    return {
        name: (end - pd.DateOffset(months=months) + pd.Timedelta(days=1)).date().isoformat()
        for name, months in WINDOW_MONTHS.items()
    }


def all_frozen_specs() -> list[tuple[StrategySpec, str]]:
    """Return the existing strategy, first-pass additions, and post-hoc ideas."""
    first_pass = strategy_presets()
    return [
        *[(first_pass[0], "existing_git")],
        *[(spec, "first_pass_new") for spec in first_pass[1:]],
        *[(spec, "posthoc_new") for spec in hypotheses()],
    ]


def run_horizon_comparison(
    end_date: str = "2026-07-31",
    cache_dir: Path | None = None,
    output_dir: Path | None = None,
) -> pd.DataFrame:
    """Run every frozen configuration on each fixed trailing window."""
    bundle = load_public_bundle(cache_dir or default_cache_dir())
    prices = prepare_features(bundle.prices)
    output = output_dir or Path(__file__).resolve().parents[1] / "research" / "results"
    output.mkdir(parents=True, exist_ok=True)
    config = BacktestConfig()
    specs = all_frozen_specs()
    windows = trailing_windows(end_date)
    window_prices = {
        horizon: prices[
            prices["date"].between(pd.Timestamp(start_date), pd.Timestamp(end_date))
        ]
        for horizon, start_date in windows.items()
    }
    records: list[dict] = []
    total = len(specs) * len(windows)
    number = 0

    for spec, origin in specs:
        for horizon, start_date in windows.items():
            number += 1
            print(f"Horizon {number}/{total}: {spec.name} {horizon}", flush=True)
            # Features were prepared from the full history above, so the
            # execution engine only needs rows inside this cash-start window.
            # Avoid rebuilding a six-year date index for every short horizon.
            result = run_backtest(
                prices=window_prices[horizon],
                memberships=bundle.memberships,
                benchmark=bundle.benchmark,
                spec=spec,
                start_date=start_date,
                end_date=end_date,
                config=config,
            )
            record = _flat_result(result, horizon)
            record["horizon"] = horizon
            record["strategy_origin"] = origin
            record["trading_days"] = int(len(result["equity_curve"]))
            record["positions_observed"] = int(
                record.get("trades", 0) + record.get("open_positions_at_end", 0)
            )
            record["short_sample_warning"] = bool(
                record["trading_days"] < 126 or record["positions_observed"] < 20
            )
            record["validation_status"] = (
                "posthoc_test_seen_not_validated"
                if origin == "posthoc_new"
                else "frozen_before_horizon_comparison"
            )
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
        output / "a_share_multi_horizon.csv", index=False, encoding="utf-8-sig"
    )
    return frame


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run frozen A-share strategies over trailing windows")
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
    frame = run_horizon_comparison(args.end, args.cache_dir, args.output_dir)
    columns = [
        "horizon", "return_rank", "strategy", "strategy_origin", "total_return",
        "max_drawdown", "sharpe", "trades", "benchmark_total_return",
        "excess_total_return", "short_sample_warning",
    ]
    print(frame[columns].to_string(index=False))


if __name__ == "__main__":
    main()
