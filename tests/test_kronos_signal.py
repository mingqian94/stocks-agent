import pandas as pd
import pytest

from a_share_lab.data import load_public_subset
from a_share_lab.kronos_experiment import validate_resource_budget
from a_share_lab.kronos_setup import verify_runtime_source
from a_share_lab.kronos_signal import (
    KronosSignalGenerator,
    KronosSignalCache,
    KronosSignalConfig,
    build_kronos_input,
    forecast_mean_close_score,
)


def test_build_kronos_input_uses_only_history_and_rescales_raw_ohlc():
    prices = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-07-01", "2026-07-02", "2026-07-03"]),
            "open": [9.0, 19.0, 29.0],
            "high": [11.0, 21.0, 31.0],
            "low": [8.0, 18.0, 28.0],
            "close": [10.0, 20.0, 30.0],
            "volume": [100.0, 200.0, 300.0],
            "amount": [1_000.0, 4_000.0, 9_000.0],
            "signal_price": [1.0, 1.05, 1.10],
        }
    )

    result = build_kronos_input(prices, signal_date="2026-07-02", lookback=2)

    assert list(result.index) == list(pd.to_datetime(["2026-07-01", "2026-07-02"]))
    assert list(result.columns) == ["open", "high", "low", "close", "volume", "amount"]
    assert result.loc[pd.Timestamp("2026-07-01"), "open"] == 0.9
    assert result.loc[pd.Timestamp("2026-07-02"), "close"] == 1.05
    assert result.loc[pd.Timestamp("2026-07-02"), "volume"] == 200.0


def test_forecast_score_matches_the_frozen_paper_formula():
    history = pd.DataFrame({"close": [100.0]}, index=pd.to_datetime(["2026-07-01"]))
    forecast = pd.DataFrame(
        {"close": [101.0, 103.0, 200.0]},
        index=pd.to_datetime(["2026-07-02", "2026-07-03", "2026-07-04"]),
    )

    score = forecast_mean_close_score(history, forecast, horizon=2)

    assert score == pytest.approx(0.02)


def test_signal_cache_round_trip_is_bound_to_input_and_model_config(tmp_path):
    history = pd.DataFrame(
        {"open": [0.9], "high": [1.1], "low": [0.8], "close": [1.0],
         "volume": [100.0], "amount": [1_000.0]},
        index=pd.to_datetime(["2026-07-01"]),
    )
    forecast = pd.DataFrame(
        {"close": [1.01, 1.03]}, index=pd.to_datetime(["2026-07-02", "2026-07-03"])
    )
    cache = KronosSignalCache(tmp_path)
    config = KronosSignalConfig(horizon=2)
    future_dates = pd.to_datetime(["2026-07-02", "2026-07-03"])

    assert cache.load("sh.600000", "2026-07-01", history, future_dates, config) is None
    cache.save("sh.600000", "2026-07-01", history, future_dates, forecast, 0.02, config)

    loaded = cache.load("sh.600000", "2026-07-01", history, future_dates, config)
    assert loaded is not None
    assert loaded.score == pytest.approx(0.02)
    assert loaded.forecast_close == [1.01, 1.03]

    changed = history.copy()
    changed.loc[:, "close"] = 1.1
    assert cache.load("sh.600000", "2026-07-01", changed, future_dates, config) is None
    changed_calendar = pd.to_datetime(["2026-07-02", "2026-07-06"])
    assert cache.load("sh.600000", "2026-07-01", history, changed_calendar, config) is None


def test_generator_uses_frozen_predictor_parameters_and_reuses_cache(tmp_path):
    class FakePredictor:
        def __init__(self):
            self.calls = []

        def predict(self, **kwargs):
            assert hasattr(kwargs["y_timestamp"], "dt")
            self.calls.append(kwargs)
            return pd.DataFrame(
                {"close": [1.01, 1.03]}, index=pd.DatetimeIndex(kwargs["y_timestamp"])
            )

    prices = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-06-30", "2026-07-01"]),
            "open": [0.9, 0.95], "high": [1.1, 1.05], "low": [0.8, 0.9],
            "close": [1.0, 1.0], "volume": [100.0, 110.0],
            "amount": [1_000.0, 1_100.0], "signal_price": [1.0, 1.0],
        }
    )
    predictor = FakePredictor()
    config = KronosSignalConfig(lookback=2, horizon=2)
    generator = KronosSignalGenerator(predictor, config, KronosSignalCache(tmp_path))
    future_dates = pd.to_datetime(["2026-07-02", "2026-07-03"])

    first = generator.score_symbol("sh.600000", "2026-07-01", prices, future_dates)
    second = generator.score_symbol("sh.600000", "2026-07-01", prices, future_dates)

    assert first == pytest.approx(0.02)
    assert second == first
    assert len(predictor.calls) == 1
    assert predictor.calls[0]["sample_count"] == 1
    assert predictor.calls[0]["top_k"] == 1


def test_public_subset_loader_reads_only_requested_symbol_files(tmp_path):
    prices_dir = tmp_path / "prices"
    prices_dir.mkdir()
    pd.DataFrame(
        {"snapshot_date": ["2026-06-30", "2026-06-30"],
         "code": ["sh.600000", "sh.600001"]}
    ).to_csv(tmp_path / "memberships.csv.gz", index=False, compression="gzip")
    pd.DataFrame(
        {"date": ["2026-07-01"], "close": [100.0]}
    ).to_csv(tmp_path / "benchmark_csi800.csv.gz", index=False, compression="gzip")
    for code in ("sh.600000", "sh.600001"):
        pd.DataFrame({"date": ["2026-07-01"], "code": [code], "close": [10.0]}).to_csv(
            prices_dir / f"{code.replace('.', '_')}.csv.gz", index=False, compression="gzip"
        )

    bundle = load_public_subset(["sh.600001"], tmp_path)

    assert list(bundle.prices["code"]) == ["sh.600001"]
    assert set(bundle.memberships["code"]) == {"sh.600000", "sh.600001"}


def test_default_resource_budget_blocks_accidental_large_model_runs():
    validate_resource_budget(["sh.600000"] * 3, max_signal_dates=4)
    with pytest.raises(ValueError, match="20 symbols"):
        validate_resource_budget([f"sh.{index:06d}" for index in range(21)], 1)
    with pytest.raises(ValueError, match="20 signal dates"):
        validate_resource_budget(["sh.600000"], 21)
    validate_resource_budget(
        [f"sh.{index:06d}" for index in range(21)], 21, allow_large_run=True
    )


def test_runtime_source_verification_rejects_local_modifications(tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    for name in ("__init__.py", "kronos.py", "module.py"):
        (model_dir / name).write_text("modified", encoding="utf-8")

    with pytest.raises(RuntimeError, match="source hash mismatch"):
        verify_runtime_source(tmp_path)
