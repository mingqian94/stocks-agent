"""Frozen Kronos signal adapter for the public-data research engine.

The optional model runtime is deliberately kept outside the execution engine:
predicted candles produce a score, while every fill still uses observed raw
prices and the A-share rules in :mod:`a_share_lab.engine`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import importlib
import json
from pathlib import Path
import random
import sys

from .low_resource import configure_low_resource_environment

# Set caps before importing NumPy/PyTorch-backed libraries.
configure_low_resource_environment()

import numpy as np
import pandas as pd


KRONOS_COLUMNS = ["open", "high", "low", "close", "volume", "amount"]


@dataclass(frozen=True)
class KronosSignalConfig:
    """A fully versioned, resource-bounded inference specification."""

    model_id: str = "NeoQuasar/Kronos-mini"
    tokenizer_id: str = "NeoQuasar/Kronos-Tokenizer-base"
    model_revision: str = "f4e68697d9d5aed55cef5c96aabc3376bcad9f81"
    tokenizer_revision: str = "0e0117387f39004a9016484a186a908917e22426"
    source_revision: str = "67b630e67f6a18c9e9be918d9b4337c960db1e9a"
    lookback: int = 90
    horizon: int = 10
    temperature: float = 1.0
    top_k: int = 1
    top_p: float = 1.0
    sample_count: int = 1
    seed: int = 123
    device: str = "cpu"
    cpu_threads: int = 1


@dataclass(frozen=True)
class CachedSignal:
    score: float
    forecast_close: list[float]


def _input_fingerprint(
    history: pd.DataFrame,
    future_dates,
    config: KronosSignalConfig,
) -> str:
    digest = hashlib.sha256()
    digest.update(pd.util.hash_pandas_object(history, index=True).values.tobytes())
    future_index = pd.DatetimeIndex(pd.to_datetime(future_dates))
    digest.update(future_index.asi8.tobytes())
    digest.update(json.dumps(asdict(config), sort_keys=True).encode("utf-8"))
    return digest.hexdigest()


class KronosSignalCache:
    """Small auditable JSON cache keyed by exact input and model config."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def _path(
        self,
        code: str,
        signal_date: str | pd.Timestamp,
        history: pd.DataFrame,
        future_dates,
        config: KronosSignalConfig,
    ) -> Path:
        safe_code = code.replace(".", "_")
        date = pd.Timestamp(signal_date).date().isoformat()
        fingerprint = _input_fingerprint(history, future_dates, config)
        return self.root / date / f"{safe_code}_{fingerprint}.json"

    def load(
        self,
        code: str,
        signal_date: str | pd.Timestamp,
        history: pd.DataFrame,
        future_dates,
        config: KronosSignalConfig,
    ) -> CachedSignal | None:
        path = self._path(code, signal_date, history, future_dates, config)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return CachedSignal(
            score=float(payload["score"]),
            forecast_close=[float(value) for value in payload["forecast_close"]],
        )

    def save(
        self,
        code: str,
        signal_date: str | pd.Timestamp,
        history: pd.DataFrame,
        future_dates,
        forecast: pd.DataFrame,
        score: float,
        config: KronosSignalConfig,
    ) -> Path:
        path = self._path(code, signal_date, history, future_dates, config)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "code": code,
            "signal_date": pd.Timestamp(signal_date).date().isoformat(),
            "score": float(score),
            "forecast_close": [float(value) for value in forecast["close"]],
            "future_dates": [
                pd.Timestamp(value).isoformat() for value in pd.to_datetime(future_dates)
            ],
            "config": asdict(config),
        }
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8"
        )
        temporary.replace(path)
        return path


class KronosSignalGenerator:
    """Turn a Kronos-compatible predictor into cached cross-sectional scores."""

    def __init__(
        self,
        predictor,
        config: KronosSignalConfig,
        cache: KronosSignalCache,
    ):
        self.predictor = predictor
        self.config = config
        self.cache = cache

    def score_symbol(
        self,
        code: str,
        signal_date: str | pd.Timestamp,
        prices: pd.DataFrame,
        future_dates,
    ) -> float:
        history = build_kronos_input(prices, signal_date, self.config.lookback)
        if len(history) < self.config.lookback:
            raise ValueError(
                f"{code} has {len(history)} rows; {self.config.lookback} required"
            )
        future_index = pd.DatetimeIndex(pd.to_datetime(future_dates))
        if len(future_index) != self.config.horizon:
            raise ValueError(
                f"future_dates has {len(future_index)} rows; {self.config.horizon} required"
            )
        cached = self.cache.load(
            code, signal_date, history, future_index, self.config
        )
        if cached is not None:
            return cached.score
        future_series = pd.Series(future_index)
        forecast = self.predictor.predict(
            df=history.reset_index(drop=True),
            x_timestamp=pd.Series(history.index),
            y_timestamp=future_series,
            pred_len=self.config.horizon,
            T=self.config.temperature,
            top_k=self.config.top_k,
            top_p=self.config.top_p,
            sample_count=self.config.sample_count,
            verbose=False,
        )
        score = forecast_mean_close_score(history, forecast, self.config.horizon)
        self.cache.save(
            code, signal_date, history, future_index, forecast, score, self.config
        )
        return score


def load_official_predictor(
    source_dir: str | Path,
    config: KronosSignalConfig,
):
    """Load the pinned official runtime with strict local resource caps."""
    source = Path(source_dir).resolve()
    if not (source / "model" / "__init__.py").exists():
        raise FileNotFoundError(
            f"Kronos source not found at {source}; expected model/__init__.py"
        )
    if config.device != "cpu":
        raise ValueError("this research runner only permits device='cpu'")
    if config.cpu_threads != 1:
        raise ValueError("this low-resource runner requires cpu_threads=1")

    configure_low_resource_environment(config.cpu_threads)
    try:
        import torch
    except ImportError as error:
        raise RuntimeError(
            "Kronos runtime is optional; install requirements-kronos.txt first"
        ) from error

    torch.set_num_threads(config.cpu_threads)
    if torch.get_num_interop_threads() != config.cpu_threads:
        try:
            torch.set_num_interop_threads(config.cpu_threads)
        except RuntimeError as error:
            raise RuntimeError(
                "PyTorch interop threads were initialized before the resource cap"
            ) from error
    random.seed(config.seed)
    np.random.seed(config.seed)
    torch.manual_seed(config.seed)
    source_text = str(source)
    if source_text not in sys.path:
        sys.path.insert(0, source_text)
    from .kronos_setup import verify_runtime_source

    verify_runtime_source(source)
    existing_model_module = sys.modules.get("model")
    expected_init = (source / "model" / "__init__.py").resolve()
    if existing_model_module is not None:
        existing_path = Path(getattr(existing_model_module, "__file__", "")).resolve()
        if existing_path != expected_init:
            raise RuntimeError(
                f"refusing previously imported model module from {existing_path}"
            )
    model_module = importlib.import_module("model")
    imported_path = Path(model_module.__file__).resolve()
    if imported_path != expected_init:
        raise RuntimeError(f"Kronos imported from unexpected path: {imported_path}")
    Kronos = model_module.Kronos
    KronosPredictor = model_module.KronosPredictor
    KronosTokenizer = model_module.KronosTokenizer

    tokenizer = KronosTokenizer.from_pretrained(
        config.tokenizer_id, revision=config.tokenizer_revision
    )
    model = Kronos.from_pretrained(config.model_id, revision=config.model_revision)
    tokenizer.eval()
    model.eval()
    return KronosPredictor(
        model,
        tokenizer,
        device=config.device,
        max_context=min(512, config.lookback),
    )


def build_kronos_input(
    prices: pd.DataFrame,
    signal_date: str | pd.Timestamp,
    lookback: int = 90,
) -> pd.DataFrame:
    """Build a point-in-time continuous K-line window for one symbol.

    Raw OHLC is scaled so the close equals ``signal_price``, which is already
    constructed from point-in-time daily returns.  Volume and amount retain
    their observed values.  Rows after ``signal_date`` are never included.
    """
    required = {"date", "signal_price", *KRONOS_COLUMNS}
    missing = sorted(required - set(prices.columns))
    if missing:
        raise ValueError(f"Kronos input is missing columns: {', '.join(missing)}")
    if lookback <= 0:
        raise ValueError("lookback must be positive")

    cutoff = pd.Timestamp(signal_date)
    window = prices.loc[pd.to_datetime(prices["date"]) <= cutoff].copy()
    window = window.sort_values("date").tail(lookback)
    scale = window["signal_price"] / window["close"]
    for column in ("open", "high", "low", "close"):
        window[column] = window[column] * scale
    return window.set_index("date")[KRONOS_COLUMNS]


def forecast_mean_close_score(
    history: pd.DataFrame,
    forecast: pd.DataFrame,
    horizon: int = 10,
) -> float:
    """Score a forecast using the paper's mean-future-close formula."""
    if horizon <= 0:
        raise ValueError("horizon must be positive")
    if history.empty or "close" not in history:
        raise ValueError("history must contain at least one close")
    if forecast.empty or "close" not in forecast:
        raise ValueError("forecast must contain at least one close")
    future_close = pd.to_numeric(forecast["close"], errors="coerce").head(horizon)
    if len(future_close) < horizon or future_close.isna().any():
        raise ValueError(f"forecast must contain {horizon} valid closes")
    current_close = float(history["close"].iloc[-1])
    if current_close <= 0:
        raise ValueError("current close must be positive")
    return float(future_close.mean() / current_close - 1.0)
