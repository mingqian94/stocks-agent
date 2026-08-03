"""Regime-based position sizing experiment (2026-08-03, post-report follow-up).

`research/a_share_backtest_report_2026-08-02.md` only tested market strength
as a binary trade/no-trade gate (`market_gate="ma20"/"ma60"`), which did not
help. This script tests a different, previously-untried idea: instead of a
binary switch, scale new-buy position size down when the CSI800 benchmark is
below its own MA60 ("market_ma60_tiered" in engine.py), applied to the two
strategies this project actually cares about:

- ``daily_breakout_2_fixed``: the exact spec currently live in
  ``stock_auto_trade.py`` (3%-8% band + prior-day confirm + -5%/+8% fixed exits).
- ``risk_adjusted20_4_ma20``: the strategy currently under forward paper
  observation (``shadow_momentum_20d.py``).

Same train/test protocol as the first round (2021-01-01..2024-12-31 train,
2025-01-01..2026-07-31 test, pre-declared, not re-tuned after seeing test
results) so this is directly comparable to the frozen report numbers. Writes
to ``research/results/a_share_regime_sizing_2026-08-03.csv`` — a new file, the
original frozen ``a_share_strategy_summary.csv`` is not touched or overwritten.

Run:
    python -m a_share_lab.regime_sizing
"""
from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

import pandas as pd

from .data import default_cache_dir, load_public_bundle
from .engine import BacktestConfig, StrategySpec, prepare_features, run_backtest

TRAIN_START = "2021-01-01"
TRAIN_END = "2024-12-31"
TEST_START = "2025-01-01"
TEST_END = "2026-07-31"

BASE_SPECS = [
    StrategySpec(
        name="daily_breakout_2_fixed",
        entry_model="daily_breakout",
        max_positions=2,
        stop_loss=-0.05,
        take_profit=0.08,
        max_holding_days=None,
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
]


def _flat_result(result: dict, split: str) -> dict:
    row = {"strategy": result["strategy"], "split": split}
    row.update(result["metrics"])
    row["benchmark_total_return"] = result["benchmark_metrics"].get("total_return")
    row["benchmark_max_drawdown"] = result["benchmark_metrics"].get("max_drawdown")
    return row


def run_experiment(cache_dir: Path | None = None, output_dir: Path | None = None) -> pd.DataFrame:
    cache_dir = cache_dir or default_cache_dir()
    output_dir = output_dir or Path(__file__).resolve().parents[1] / "research" / "results"
    output_dir.mkdir(parents=True, exist_ok=True)

    bundle = load_public_bundle(cache_dir)
    prepared_prices = prepare_features(bundle.prices)
    config = BacktestConfig()

    specs: list[StrategySpec] = []
    for base in BASE_SPECS:
        specs.append(replace(base, name=f"{base.name}_baseline"))
        specs.append(
            replace(base, name=f"{base.name}_regime_sized", position_scaling="market_ma60_tiered")
        )

    records: list[dict] = []
    for spec in specs:
        for split, start, end in (("train", TRAIN_START, TRAIN_END), ("test", TEST_START, TEST_END)):
            result = run_backtest(
                prepared_prices, bundle.memberships, bundle.benchmark, spec,
                start_date=start, end_date=end, config=config,
            )
            records.append(_flat_result(result, split))

    summary = pd.DataFrame(records)
    summary.to_csv(output_dir / "a_share_regime_sizing_2026-08-03.csv", index=False, encoding="utf-8-sig")
    (output_dir / "a_share_regime_sizing_specs_2026-08-03.json").write_text(
        json.dumps([asdict(spec) for spec in specs], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


if __name__ == "__main__":
    result = run_experiment()
    cols = ["strategy", "split", "total_return", "max_drawdown", "sharpe", "trades", "win_rate"]
    print(result[cols].to_string(index=False))
