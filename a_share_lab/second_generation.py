"""Post-hoc, low-turnover hypotheses prompted by first-pass cost attribution.

These variants are explicitly *not* a fresh out-of-sample test: their design
was informed by viewing the 2025-2026 results.  They may define a future paper
trading version, but cannot promote themselves to validated strategies.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .data import default_cache_dir, load_public_bundle
from .engine import BacktestConfig, StrategySpec, prepare_features, run_backtest
from .experiments import _flat_result


def hypotheses() -> list[StrategySpec]:
    return [
        StrategySpec(
            name="posthoc_risk20_4_ma60_hold40",
            entry_model="risk_adjusted_20d",
            max_positions=4,
            stop_loss=-0.10,
            take_profit=None,
            max_holding_days=40,
            exit_model="ma60",
        ),
        StrategySpec(
            name="posthoc_risk20_4_ma60_hold60",
            entry_model="risk_adjusted_20d",
            max_positions=4,
            stop_loss=-0.10,
            take_profit=None,
            max_holding_days=60,
            exit_model="ma60",
        ),
        StrategySpec(
            name="posthoc_risk20_6_ma60_hold40",
            entry_model="risk_adjusted_20d",
            max_positions=6,
            stop_loss=-0.10,
            take_profit=None,
            max_holding_days=40,
            exit_model="ma60",
        ),
        StrategySpec(
            name="posthoc_risk20_6_ma60_hold60",
            entry_model="risk_adjusted_20d",
            max_positions=6,
            stop_loss=-0.10,
            take_profit=None,
            max_holding_days=60,
            exit_model="ma60",
        ),
    ]


def run_second_generation(
    cache_dir: Path | None = None,
    output_dir: Path | None = None,
) -> pd.DataFrame:
    bundle = load_public_bundle(cache_dir or default_cache_dir())
    prices = prepare_features(bundle.prices)
    output = output_dir or Path(__file__).resolve().parents[1] / "research" / "results"
    output.mkdir(parents=True, exist_ok=True)
    zero = BacktestConfig(
        commission_rate=0,
        minimum_commission=0,
        transfer_fee_rate=0,
        transfer_fee_rate_before_2022_04_29=0,
        stamp_tax_before_2023_08_28=0,
        stamp_tax_after_2023_08_28=0,
        slippage_bps=0,
    )
    cases = {
        "zero_friction": zero,
        "base": BacktestConfig(),
        "high_10bp_slippage_5bp_commission": BacktestConfig(
            commission_rate=0.0005, slippage_bps=10
        ),
    }
    splits = {
        "train": ("2021-01-01", "2024-12-31"),
        "test_seen_posthoc": ("2025-01-01", "2026-07-31"),
    }
    records = []
    total = len(hypotheses()) * len(cases) * len(splits)
    number = 0
    for spec in hypotheses():
        for cost_case, config in cases.items():
            for split, (start, end) in splits.items():
                number += 1
                print(f"Post-hoc {number}/{total}: {spec.name} {split} {cost_case}", flush=True)
                result = run_backtest(
                    prices, bundle.memberships, bundle.benchmark, spec, start, end, config
                )
                record = _flat_result(result, split)
                record["cost_case"] = cost_case
                record["validation_status"] = "posthoc_test_seen_not_validated"
                records.append(record)
    frame = pd.DataFrame(records)
    frame.to_csv(output / "a_share_second_generation.csv", index=False, encoding="utf-8-sig")
    return frame


def main() -> None:
    frame = run_second_generation()
    columns = ["strategy", "split", "cost_case", "total_return", "max_drawdown", "sharpe", "trades"]
    print(frame[columns].to_string(index=False))


if __name__ == "__main__":
    main()
