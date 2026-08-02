"""Low-resource Kronos score generation and A-share backtest integration."""

from __future__ import annotations

import argparse
from pathlib import Path

from .low_resource import configure_low_resource_environment

configure_low_resource_environment()

import pandas as pd

from .data import default_cache_dir, load_public_subset
from .engine import (
    BacktestConfig,
    MembershipResolver,
    StrategySpec,
    prepare_features,
    run_backtest,
)
from .experiments import _flat_result
from .kronos_signal import (
    KronosSignalCache,
    KronosSignalConfig,
    KronosSignalGenerator,
    load_official_predictor,
)
from .kronos_setup import default_source_dir


def kronos_strategy_spec() -> StrategySpec:
    """Frozen first-pass portfolio rule; do not tune it on pilot results."""
    return StrategySpec(
        name="kronos_mean10_10_time10",
        entry_model="external_score",
        max_positions=10,
        stop_loss=-0.08,
        take_profit=0.15,
        max_holding_days=10,
        minimum_external_score=0.0,
    )


def validate_resource_budget(
    codes: list[str],
    max_signal_dates: int | None,
    allow_large_run: bool = False,
) -> None:
    """Prevent an accidental full-universe run on a low-resource machine."""
    if allow_large_run:
        return
    if len(codes) > 20:
        raise ValueError("low-resource mode permits at most 20 symbols")
    if max_signal_dates is None or max_signal_dates > 20:
        raise ValueError("low-resource mode permits at most 20 signal dates")
    if max_signal_dates <= 0:
        raise ValueError("max_signal_dates must be positive")


def _eligible_signal_dates(
    benchmark: pd.DataFrame,
    start_date: str,
    end_date: str,
    horizon: int,
    max_signal_dates: int | None,
) -> list[pd.Timestamp]:
    calendar = list(pd.to_datetime(benchmark["date"]).sort_values().unique())
    eligible = [
        pd.Timestamp(day)
        for index, day in enumerate(calendar)
        if pd.Timestamp(start_date) <= pd.Timestamp(day) <= pd.Timestamp(end_date)
        and index + horizon < len(calendar)
    ]
    return eligible[-max_signal_dates:] if max_signal_dates else eligible


def generate_scores(
    codes: list[str],
    source_dir: Path,
    start_date: str,
    end_date: str,
    max_signal_dates: int | None = 1,
    cache_dir: Path | None = None,
    output_dir: Path | None = None,
    config: KronosSignalConfig | None = None,
    allow_large_run: bool = False,
) -> pd.DataFrame:
    """Generate a bounded set of frozen scores and save resumable results."""
    codes = list(dict.fromkeys(codes))
    config = config or KronosSignalConfig()
    validate_resource_budget(codes, max_signal_dates, allow_large_run)
    cache_root = Path(cache_dir or default_cache_dir())
    output = output_dir or Path(__file__).resolve().parents[1] / "research" / "results"
    output.mkdir(parents=True, exist_ok=True)
    bundle = load_public_subset(codes, cache_root)
    prices = prepare_features(bundle.prices)
    signal_dates = _eligible_signal_dates(
        bundle.benchmark, start_date, end_date, config.horizon, max_signal_dates
    )
    if not signal_dates:
        raise ValueError("no signal dates have a complete future trading calendar")

    predictor = load_official_predictor(source_dir, config)
    generator = KronosSignalGenerator(
        predictor, config, KronosSignalCache(cache_root / "kronos_signals")
    )
    resolver = MembershipResolver(bundle.memberships)
    benchmark_dates = list(pd.to_datetime(bundle.benchmark["date"]).sort_values().unique())
    benchmark_index = {pd.Timestamp(day): index for index, day in enumerate(benchmark_dates)}
    by_code = {code: frame.copy() for code, frame in prices.groupby("code")}
    records: list[dict] = []
    failures: list[dict] = []
    score_path = output / "a_share_kronos_scores.csv"
    failure_path = output / "a_share_kronos_failures.csv"

    def checkpoint() -> None:
        pd.DataFrame(
            records, columns=["date", "code", "external_score"]
        ).to_csv(score_path, index=False, encoding="utf-8-sig")
        pd.DataFrame(
            failures, columns=["date", "code", "error_type", "error"]
        ).to_csv(failure_path, index=False, encoding="utf-8-sig")

    total = len(signal_dates) * len(codes)
    number = 0
    for signal_date in signal_dates:
        start = benchmark_index[signal_date] + 1
        future_dates = benchmark_dates[start : start + config.horizon]
        members = resolver.on(signal_date)
        for code in codes:
            number += 1
            print(f"Kronos score {number}/{total}: {signal_date.date()} {code}", flush=True)
            if code not in members or code not in by_code:
                continue
            symbol = by_code[code]
            try:
                score = generator.score_symbol(code, signal_date, symbol, future_dates)
            except Exception as error:
                failures.append(
                    {
                        "date": signal_date,
                        "code": code,
                        "error_type": type(error).__name__,
                        "error": str(error),
                    }
                )
                print(f"Skipped {code}: {type(error).__name__}: {error}", flush=True)
                checkpoint()
                continue
            records.append(
                {"date": signal_date, "code": code, "external_score": score}
            )
            checkpoint()
    frame = pd.DataFrame(records, columns=["date", "code", "external_score"])
    checkpoint()
    return frame


def backtest_scores(
    codes: list[str],
    scores: pd.DataFrame,
    start_date: str,
    end_date: str,
    cache_dir: Path | None = None,
    output_dir: Path | None = None,
) -> dict:
    """Backtest frozen scores with observed prices and the existing engine."""
    codes = list(dict.fromkeys(codes))
    cache_root = Path(cache_dir or default_cache_dir())
    output = output_dir or Path(__file__).resolve().parents[1] / "research" / "results"
    output.mkdir(parents=True, exist_ok=True)
    bundle = load_public_subset(codes, cache_root)
    prices = prepare_features(bundle.prices)
    scores = scores.copy()
    scores["date"] = pd.to_datetime(scores["date"])
    prices = prices.merge(scores, on=["date", "code"], how="left")
    result = run_backtest(
        prices,
        bundle.memberships,
        bundle.benchmark,
        kronos_strategy_spec(),
        start_date,
        end_date,
        BacktestConfig(),
    )
    record = _flat_result(result, "kronos")
    record["kronos_universe_symbols"] = len(codes)
    record["validation_status"] = "engineering_pilot_not_performance_test"
    pd.DataFrame([record]).to_csv(
        output / "a_share_kronos_backtest.csv", index=False, encoding="utf-8-sig"
    )
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Low-resource frozen Kronos signal experiment")
    parser.add_argument("--source-dir", type=Path, default=default_source_dir())
    parser.add_argument("--codes", nargs="+", default=["sh.600000"])
    parser.add_argument("--start", default="2026-07-01")
    parser.add_argument("--end", default="2026-07-31")
    parser.add_argument("--max-signal-dates", type=int, default=1)
    parser.add_argument("--cache-dir", type=Path, default=default_cache_dir())
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "research" / "results",
    )
    parser.add_argument("--backtest", action="store_true")
    parser.add_argument(
        "--allow-large-run",
        action="store_true",
        help="Disable the default 20-symbol/20-date safety cap on a larger machine",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    scores = generate_scores(
        codes=args.codes,
        source_dir=args.source_dir,
        start_date=args.start,
        end_date=args.end,
        max_signal_dates=args.max_signal_dates,
        cache_dir=args.cache_dir,
        output_dir=args.output_dir,
        allow_large_run=args.allow_large_run,
    )
    print(scores.to_string(index=False))
    if args.backtest:
        result = backtest_scores(
            args.codes, scores, args.start, args.end, args.cache_dir, args.output_dir
        )
        print(result["metrics"])


if __name__ == "__main__":
    main()
