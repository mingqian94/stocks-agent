"""Reproducible public-data research tools for A-share strategies."""

__all__ = ["BacktestConfig", "StrategySpec", "run_backtest"]


def __getattr__(name: str):
    """Preserve the public API without importing NumPy before CLI resource caps."""
    if name in __all__:
        from . import engine

        return getattr(engine, name)
    raise AttributeError(name)
