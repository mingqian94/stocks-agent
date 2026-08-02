"""Reproducible public-data research tools for A-share strategies."""

from .engine import BacktestConfig, StrategySpec, run_backtest

__all__ = ["BacktestConfig", "StrategySpec", "run_backtest"]
