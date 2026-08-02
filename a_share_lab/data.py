"""BaoStock data acquisition and point-in-time universe helpers.

The cache is deliberately local-only (``data/a_share_lab`` is gitignored).
All strategy signals are built later from observations available on or before
the signal date; this module only downloads and normalises public daily data.
"""

from __future__ import annotations

import json
import hashlib
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd


PRICE_FIELDS = (
    "date,code,open,high,low,close,preclose,volume,amount,turn,"
    "tradestatus,pctChg,isST,adjustflag"
)
NUMERIC_PRICE_COLUMNS = [
    "open",
    "high",
    "low",
    "close",
    "preclose",
    "volume",
    "amount",
    "turn",
    "pctChg",
]


@dataclass(frozen=True)
class PublicDataBundle:
    prices: pd.DataFrame
    memberships: pd.DataFrame
    benchmark: pd.DataFrame


def default_cache_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "a_share_lab"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _semiannual_anchors(start_date: str, end_date: str) -> list[pd.Timestamp]:
    """Return coarse point-in-time index snapshots without current-universe bias."""
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    years = range(start.year - 1, end.year + 1)
    anchors = {
        pd.Timestamp(year=year, month=6, day=30) for year in years
    } | {
        pd.Timestamp(year=year, month=12, day=31) for year in years
    }
    anchors.add(start)
    anchors.add(end)
    return sorted(day for day in anchors if start - pd.Timedelta(days=370) <= day <= end)


def _query_rows(result) -> list[list[str]]:
    rows: list[list[str]] = []
    while result.error_code == "0" and result.next():
        rows.append(result.get_row_data())
    if result.error_code != "0":
        raise RuntimeError(f"BaoStock query failed: {result.error_code} {result.error_msg}")
    return rows


def _query_with_retry(bs, query_factory, attempts: int = 5) -> list[list[str]]:
    """Run a BaoStock query and transparently recover expired sessions."""
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return _query_rows(query_factory())
        except RuntimeError as error:
            last_error = error
            if attempt == attempts - 1:
                break
            # BaoStock sessions can expire during a long constituent+price run.
            # A fresh login is cheap and lets the per-symbol cache resume safely.
            try:
                bs.logout()
            except Exception:
                pass
            time.sleep(min(2 ** attempt, 8))
            login = bs.login()
            if login.error_code != "0":
                last_error = RuntimeError(
                    f"BaoStock relogin failed: {login.error_code} {login.error_msg}"
                )
    raise last_error or RuntimeError("BaoStock query failed without an error message")


def fetch_memberships(bs, start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch historical CSI 300/500 membership snapshots.

    BaoStock returns the latest valid constituent snapshot on or before the
    requested calendar date.  We retain the requested date as ``snapshot_date``
    so the engine can use only a snapshot already observable at that time.
    """
    records: list[dict[str, str]] = []
    queries = (
        ("CSI300", bs.query_hs300_stocks),
        ("CSI500", bs.query_zz500_stocks),
    )
    for anchor in _semiannual_anchors(start_date, end_date):
        requested = anchor.strftime("%Y-%m-%d")
        for index_name, query in queries:
            rows = _query_with_retry(bs, lambda query=query, requested=requested: query(requested))
            for update_date, code, name in rows:
                records.append(
                    {
                        "snapshot_date": requested,
                        "source_update_date": update_date,
                        "index_name": index_name,
                        "code": code,
                        "name": name,
                    }
                )
    frame = pd.DataFrame.from_records(records)
    if frame.empty:
        raise RuntimeError("BaoStock returned no historical index constituents")
    frame["snapshot_date"] = pd.to_datetime(frame["snapshot_date"])
    return frame.drop_duplicates(["snapshot_date", "index_name", "code"]).sort_values(
        ["snapshot_date", "index_name", "code"]
    )


def _normalise_price_frame(rows: list[list[str]], fields: Iterable[str]) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=list(fields))
    if frame.empty:
        return frame
    frame["date"] = pd.to_datetime(frame["date"])
    for column in NUMERIC_PRICE_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["tradestatus"] = pd.to_numeric(frame["tradestatus"], errors="coerce").fillna(0).astype(int)
    frame["isST"] = pd.to_numeric(frame["isST"], errors="coerce").fillna(0).astype(int)
    frame["adjustflag"] = pd.to_numeric(frame["adjustflag"], errors="coerce").fillna(0).astype(int)
    return frame.sort_values("date").drop_duplicates(["date", "code"])


def fetch_symbol_history(bs, code: str, start_date: str, end_date: str) -> pd.DataFrame:
    rows = _query_with_retry(
        bs,
        lambda: bs.query_history_k_data_plus(
            code,
            PRICE_FIELDS,
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            # Actual, unadjusted OHLC is required for fills, price limits and
            # cash accounting.  pctChg later forms the corporate-action-safe
            # signal series without pretending adjusted prices were tradable.
            adjustflag="3",
        ),
    )
    return _normalise_price_frame(rows, PRICE_FIELDS.split(","))


def fetch_benchmark(bs, start_date: str, end_date: str, code: str = "sh.000906") -> pd.DataFrame:
    fields = ["date", "code", "open", "high", "low", "close", "preclose", "volume", "amount"]
    rows = _query_with_retry(
        bs,
        lambda: bs.query_history_k_data_plus(
            code,
            ",".join(fields),
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="3",
        ),
    )
    frame = pd.DataFrame(rows, columns=fields)
    if frame.empty:
        raise RuntimeError(f"BaoStock returned no benchmark data for {code}")
    frame["date"] = pd.to_datetime(frame["date"])
    for column in ["open", "high", "low", "close", "preclose", "volume", "amount"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.sort_values("date")


def download_public_bundle(
    start_date: str,
    end_date: str,
    cache_dir: Path | None = None,
    refresh: bool = False,
) -> PublicDataBundle:
    """Download or resume a public CSI 300+500 research bundle."""
    import baostock as bs

    cache = Path(cache_dir or default_cache_dir())
    prices_dir = cache / "prices"
    prices_dir.mkdir(parents=True, exist_ok=True)
    membership_path = cache / "memberships.csv.gz"
    benchmark_path = cache / "benchmark_csi800.csv.gz"
    metadata_path = cache / "metadata.json"
    manifest_path = cache / "manifest.csv"

    login = bs.login()
    if login.error_code != "0":
        raise RuntimeError(f"BaoStock login failed: {login.error_code} {login.error_msg}")
    try:
        if refresh or not membership_path.exists():
            memberships = fetch_memberships(bs, start_date, end_date)
            memberships.to_csv(membership_path, index=False, compression="gzip")
        else:
            memberships = pd.read_csv(membership_path, parse_dates=["snapshot_date"])

        warmup_start = (pd.Timestamp(start_date) - pd.Timedelta(days=140)).strftime("%Y-%m-%d")
        codes = sorted(memberships["code"].unique())
        frames: list[pd.DataFrame] = []
        failures: list[dict[str, str]] = []
        manifest_records: list[dict[str, object]] = []
        total = len(codes)
        for number, code in enumerate(codes, start=1):
            symbol_path = prices_dir / f"{code.replace('.', '_')}.csv.gz"
            needs_fetch = refresh or not symbol_path.exists()
            if not needs_fetch:
                try:
                    cached_header = pd.read_csv(symbol_path, nrows=1)
                    needs_fetch = (
                        "adjustflag" not in cached_header.columns
                        or cached_header.empty
                        or int(cached_header["adjustflag"].iloc[0]) != 3
                    )
                except Exception:
                    needs_fetch = True
            if needs_fetch:
                try:
                    frame = fetch_symbol_history(bs, code, warmup_start, end_date)
                    if not frame.empty:
                        frame.to_csv(symbol_path, index=False, compression="gzip")
                    else:
                        failures.append({"code": code, "error": "empty history"})
                except Exception as error:
                    failures.append({"code": code, "error": str(error)})
                    print(f"BaoStock failed {code}: {error}", flush=True)
            if symbol_path.exists():
                frame = pd.read_csv(symbol_path, parse_dates=["date"])
                frames.append(frame)
                manifest_records.append(
                    {
                        "code": code,
                        "rows": len(frame),
                        "min_date": frame["date"].min().date().isoformat() if not frame.empty else "",
                        "max_date": frame["date"].max().date().isoformat() if not frame.empty else "",
                        "adjustflag": int(frame["adjustflag"].iloc[0]) if "adjustflag" in frame and not frame.empty else 0,
                        "sha256": _sha256(symbol_path),
                    }
                )
            if number == 1 or number % 50 == 0 or number == total:
                print(f"BaoStock prices: {number}/{total}", flush=True)

        if refresh or not benchmark_path.exists():
            benchmark = fetch_benchmark(bs, warmup_start, end_date)
            benchmark.to_csv(benchmark_path, index=False, compression="gzip")
        else:
            benchmark = pd.read_csv(benchmark_path, parse_dates=["date"])
    finally:
        bs.logout()

    if not frames:
        raise RuntimeError("No stock histories were downloaded")
    prices = pd.concat(frames, ignore_index=True).drop_duplicates(["date", "code"])
    pd.DataFrame(manifest_records).to_csv(manifest_path, index=False, encoding="utf-8-sig")
    metadata_path.write_text(
        json.dumps(
            {
                "start_date": start_date,
                "end_date": end_date,
                "symbols": int(prices["code"].nunique()),
                "rows": int(len(prices)),
                "source": "BaoStock 0.9.3",
                "execution_prices": "unadjusted OHLC (adjustflag=3)",
                "signal_prices": "compounded point-in-time pctChg",
                "universe": "historical CSI300 + CSI500 snapshots",
                "failed_symbols": failures,
                "membership_sha256": _sha256(membership_path),
                "benchmark_sha256": _sha256(benchmark_path),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return PublicDataBundle(prices=prices, memberships=memberships, benchmark=benchmark)


def load_public_bundle(cache_dir: Path | None = None) -> PublicDataBundle:
    cache = Path(cache_dir or default_cache_dir())
    membership_path = cache / "memberships.csv.gz"
    benchmark_path = cache / "benchmark_csi800.csv.gz"
    price_paths = sorted((cache / "prices").glob("*.csv.gz"))
    if not membership_path.exists() or not benchmark_path.exists() or not price_paths:
        raise FileNotFoundError("Public cache is incomplete; run the downloader first")
    memberships = pd.read_csv(membership_path, parse_dates=["snapshot_date"])
    benchmark = pd.read_csv(benchmark_path, parse_dates=["date"])
    prices = pd.concat(
        (pd.read_csv(path, parse_dates=["date"]) for path in price_paths),
        ignore_index=True,
    ).drop_duplicates(["date", "code"])
    return PublicDataBundle(prices=prices, memberships=memberships, benchmark=benchmark)


def load_public_subset(
    codes: Iterable[str],
    cache_dir: Path | None = None,
) -> PublicDataBundle:
    """Load selected symbol files without materialising the full price cache."""
    requested = list(dict.fromkeys(codes))
    if not requested:
        raise ValueError("at least one symbol code is required")
    cache = Path(cache_dir or default_cache_dir())
    membership_path = cache / "memberships.csv.gz"
    benchmark_path = cache / "benchmark_csi800.csv.gz"
    price_paths = [cache / "prices" / f"{code.replace('.', '_')}.csv.gz" for code in requested]
    missing = [path.name for path in price_paths if not path.exists()]
    if not membership_path.exists() or not benchmark_path.exists() or missing:
        detail = f"; missing symbols: {', '.join(missing)}" if missing else ""
        raise FileNotFoundError(f"Public cache subset is incomplete{detail}")
    memberships = pd.read_csv(membership_path, parse_dates=["snapshot_date"])
    benchmark = pd.read_csv(benchmark_path, parse_dates=["date"])
    prices = pd.concat(
        (pd.read_csv(path, parse_dates=["date"]) for path in price_paths),
        ignore_index=True,
    ).drop_duplicates(["date", "code"])
    return PublicDataBundle(prices=prices, memberships=memberships, benchmark=benchmark)
