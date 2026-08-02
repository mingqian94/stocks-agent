"""Focused cost and exit-reason attribution after the frozen first-pass grid."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .data import default_cache_dir, load_public_bundle
from .engine import BacktestConfig, prepare_features, run_backtest
from .experiments import _flat_result, strategy_presets


SELECTED = (
    "daily_breakout_2_fixed",
    "daily_breakout_2_time2",
    "daily_breakout_2_time5_market_ma60",
    "risk_adjusted20_4_ma20",
)


def run_followup(
    cache_dir: Path | None = None,
    output_dir: Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    bundle = load_public_bundle(cache_dir or default_cache_dir())
    prices = prepare_features(bundle.prices)
    specs = {spec.name: spec for spec in strategy_presets() if spec.name in SELECTED}
    output = output_dir or Path(__file__).resolve().parents[1] / "research" / "results"
    output.mkdir(parents=True, exist_ok=True)

    zero_friction = BacktestConfig(
        commission_rate=0.0,
        minimum_commission=0.0,
        transfer_fee_rate=0.0,
        transfer_fee_rate_before_2022_04_29=0.0,
        stamp_tax_before_2023_08_28=0.0,
        stamp_tax_after_2023_08_28=0.0,
        slippage_bps=0.0,
    )
    cost_cases = {
        "zero_friction": zero_friction,
        "base": BacktestConfig(),
        "high_10bp_slippage_5bp_commission": BacktestConfig(
            commission_rate=0.0005, slippage_bps=10.0
        ),
    }
    splits = {
        "train": ("2021-01-01", "2024-12-31"),
        "test": ("2025-01-01", "2026-07-31"),
    }
    sensitivity_records: list[dict] = []
    exit_records: list[dict] = []
    total = len(specs) * len(cost_cases) * len(splits)
    number = 0
    for strategy_name, spec in specs.items():
        for cost_case, config in cost_cases.items():
            for split, (start_date, end_date) in splits.items():
                number += 1
                print(f"Follow-up {number}/{total}: {strategy_name} {split} {cost_case}", flush=True)
                result = run_backtest(
                    prices,
                    bundle.memberships,
                    bundle.benchmark,
                    spec,
                    start_date,
                    end_date,
                    config,
                )
                record = _flat_result(result, split)
                record["cost_case"] = cost_case
                sensitivity_records.append(record)
                if cost_case == "base" and not result["trades"].empty:
                    grouped = result["trades"].groupby("reason")
                    for reason, trades in grouped:
                        exit_records.append(
                            {
                                "strategy": strategy_name,
                                "split": split,
                                "reason": reason,
                                "trades": int(len(trades)),
                                "win_rate": float((trades["net_pnl"] > 0).mean()),
                                "average_net_return": float(trades["net_return"].mean()),
                                "total_net_pnl": float(trades["net_pnl"].sum()),
                            }
                        )

    sensitivity = pd.DataFrame(sensitivity_records)
    exits = pd.DataFrame(exit_records)
    sensitivity.to_csv(
        output / "a_share_followup_cost_sensitivity.csv", index=False, encoding="utf-8-sig"
    )
    exits.to_csv(output / "a_share_exit_reasons.csv", index=False, encoding="utf-8-sig")
    return sensitivity, exits


def main() -> None:
    sensitivity, _ = run_followup()
    columns = [
        "strategy", "split", "cost_case", "total_return", "max_drawdown", "sharpe", "trades"
    ]
    print(sensitivity[columns].to_string(index=False))


if __name__ == "__main__":
    main()
