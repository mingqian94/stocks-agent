"""Safety gate and local journal for East Money simulated orders.

The default is deliberately shadow-only.  Reaching the broker requires all
independent gates to agree, so merely configuring an API key cannot trade.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Mapping


def _has_real_api_key(api_key: str) -> bool:
    value = api_key.strip()
    return bool(value) and value != "PENDING_USER_INPUT" and not value.startswith("your_")


def _is_a_share_session(now: dt.datetime) -> bool:
    if now.weekday() >= 5:
        return False
    local_time = now.time()
    return (
        dt.time(9, 30) <= local_time <= dt.time(11, 30)
        or dt.time(13, 0) <= local_time < dt.time(15, 0)
    )


@dataclass(frozen=True)
class OrderIntent:
    trade_date: dt.date
    strategy: str
    action: str
    code: str
    quantity: int
    reference_price: float
    reason: str
    observed_at: dt.datetime | None = None

    @property
    def intent_id(self) -> str:
        stable = "|".join(
            (
                self.trade_date.isoformat(),
                self.strategy,
                self.action,
                self.code,
                self.reason,
            )
        )
        return hashlib.sha256(stable.encode("utf-8")).hexdigest()[:20]


@dataclass(frozen=True)
class ExecutionPolicy:
    mode: str
    account_auto_trade: bool
    api_key_configured: bool
    confirmed: bool
    kill_switch: bool
    kill_switch_path: Path | None
    market_open_date_path: Path | None
    max_order_value: float
    max_signal_age_seconds: float
    max_daily_loss_pct: float
    max_failed_orders: int

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str],
        *,
        account_auto_trade: bool,
        api_key: str,
        kill_switch_path: Path | None = None,
        market_open_date_path: Path | None = None,
    ) -> "ExecutionPolicy":
        raw_cap = environment.get("EASTMONEY_MAX_ORDER_VALUE", "500000").strip()
        try:
            max_order_value = max(float(raw_cap), 0.0)
        except ValueError:
            max_order_value = 0.0
        raw_signal_age = environment.get("EASTMONEY_MAX_SIGNAL_AGE_SECONDS", "120").strip()
        try:
            max_signal_age_seconds = max(float(raw_signal_age), 0.0)
        except ValueError:
            max_signal_age_seconds = 0.0
        raw_daily_loss = environment.get("EASTMONEY_MAX_DAILY_LOSS_PCT", "2.0").strip()
        try:
            max_daily_loss_pct = max(float(raw_daily_loss), 0.0)
        except ValueError:
            max_daily_loss_pct = 0.0
        raw_failed_orders = environment.get("EASTMONEY_MAX_FAILED_ORDERS", "2").strip()
        try:
            max_failed_orders = max(int(raw_failed_orders), 0)
        except ValueError:
            max_failed_orders = 0
        return cls(
            mode=environment.get("EASTMONEY_EXECUTION_MODE", "shadow").strip().lower(),
            account_auto_trade=account_auto_trade,
            api_key_configured=_has_real_api_key(api_key),
            confirmed=(
                environment.get("EASTMONEY_PAPER_CONFIRM", "").strip()
                == "SIMULATED_ORDERS_ONLY"
            ),
            kill_switch=environment.get("EASTMONEY_KILL_SWITCH", "").strip().lower()
            in {"1", "true", "yes", "on"},
            kill_switch_path=kill_switch_path,
            market_open_date_path=market_open_date_path,
            max_order_value=max_order_value,
            max_signal_age_seconds=max_signal_age_seconds,
            max_daily_loss_pct=max_daily_loss_pct,
            max_failed_orders=max_failed_orders,
        )


@dataclass(frozen=True)
class ExecutionResult:
    intent_id: str
    status: str
    message: str


def _append_record(path: Path, intent: OrderIntent, status: str, message: str, now: dt.datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    intent_payload = asdict(intent)
    intent_payload["trade_date"] = intent.trade_date.isoformat()
    intent_payload["observed_at"] = (
        intent.observed_at.isoformat(timespec="seconds") if intent.observed_at else None
    )
    record = {
        "recorded_at": now.isoformat(timespec="seconds"),
        "intent_id": intent.intent_id,
        "status": status,
        "message": message,
        "intent": intent_payload,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _already_handled(path: Path, intent_id: str) -> bool:
    if not path.exists():
        return False
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("intent_id") == intent_id and record.get("status") in {
                "shadow", "attempted", "success", "failed"
            }:
                return True
    return False


def _claim_intent(path: Path, intent_id: str, now: dt.datetime) -> bool:
    """Atomically reserve one intent across threads and processes.

    A surviving claim deliberately blocks retries if the process dies after
    claiming but before the broker responds.  For order execution, a missed
    order is safer than an accidental duplicate.
    """
    claim_dir = Path(f"{path}.claims")
    claim_dir.mkdir(parents=True, exist_ok=True)
    claim_path = claim_dir / intent_id
    try:
        descriptor = os.open(
            claim_path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            0o600,
        )
    except FileExistsError:
        return False
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(now.isoformat(timespec="seconds") + "\n")
    return True


def _failed_order_count(path: Path, trade_date: dt.date) -> int:
    if not path.exists():
        return 0
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (
                record.get("status") == "failed"
                and record.get("intent", {}).get("trade_date") == trade_date.isoformat()
            ):
                count += 1
    return count


def _acquire_execution_lock(path: Path, now: dt.datetime, timeout_seconds: float = 2.0) -> Path | None:
    """Serialize the failure-count check and broker submission for one journal."""
    lock_path = Path(f"{path}.execution.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            descriptor = os.open(
                lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
        except FileExistsError:
            if time.monotonic() >= deadline:
                return None
            time.sleep(0.01)
            continue
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(f"pid={os.getpid()} at={now.isoformat(timespec='seconds')}\n")
        return lock_path


def _release_execution_lock(lock_path: Path) -> None:
    try:
        lock_path.unlink()
    except OSError:
        # A leftover lock fails closed on later attempts and requires inspection.
        pass


def execute_intent(
    intent: OrderIntent,
    policy: ExecutionPolicy,
    *,
    journal_path: Path,
    submit: Callable[[], bool],
    now: dt.datetime | None = None,
    account_day_profit_pct: float | None = None,
) -> ExecutionResult:
    """Record an intent or submit it when the explicit safety policy permits."""
    now = now or dt.datetime.now()
    if _already_handled(journal_path, intent.intent_id):
        return ExecutionResult(intent.intent_id, "duplicate", "intent already handled today")

    if policy.mode != "paper":
        try:
            claimed = _claim_intent(journal_path, intent.intent_id, now)
        except OSError:
            return ExecutionResult(
                intent.intent_id,
                "blocked",
                "shadow mode blocked: atomic order claim could not be created",
            )
        if not claimed:
            return ExecutionResult(intent.intent_id, "duplicate", "intent already handled today")
        message = "shadow mode: broker submission disabled"
        _append_record(journal_path, intent, "shadow", message, now)
        return ExecutionResult(intent.intent_id, "shadow", message)

    if not policy.confirmed:
        message = "paper mode blocked: explicit confirmation is missing"
        _append_record(journal_path, intent, "blocked", message, now)
        return ExecutionResult(intent.intent_id, "blocked", message)

    if policy.kill_switch or (
        policy.kill_switch_path is not None and policy.kill_switch_path.exists()
    ):
        message = "paper mode blocked: kill switch is active"
        _append_record(journal_path, intent, "blocked", message, now)
        return ExecutionResult(intent.intent_id, "blocked", message)

    if not policy.account_auto_trade:
        message = "paper mode blocked: account auto-trade opt-in is disabled"
        _append_record(journal_path, intent, "blocked", message, now)
        return ExecutionResult(intent.intent_id, "blocked", message)

    if not policy.api_key_configured:
        message = "paper mode blocked: a real API key is not configured"
        _append_record(journal_path, intent, "blocked", message, now)
        return ExecutionResult(intent.intent_id, "blocked", message)

    if intent.trade_date != now.date() or not _is_a_share_session(now):
        message = "paper mode blocked: outside current A-share market session"
        _append_record(journal_path, intent, "blocked", message, now)
        return ExecutionResult(intent.intent_id, "blocked", message)

    market_open_date = None
    if policy.market_open_date_path is not None:
        try:
            market_open_date = policy.market_open_date_path.read_text(encoding="utf-8").strip()
        except OSError:
            market_open_date = None
    if market_open_date != now.date().isoformat():
        message = "paper mode blocked: today's market-open date is not confirmed"
        _append_record(journal_path, intent, "blocked", message, now)
        return ExecutionResult(intent.intent_id, "blocked", message)

    signal_age = (
        (now - intent.observed_at).total_seconds()
        if intent.observed_at is not None
        else math.inf
    )
    if (
        not math.isfinite(policy.max_signal_age_seconds)
        or signal_age < 0
        or signal_age > policy.max_signal_age_seconds
    ):
        message = "paper mode blocked: missing, future, or stale market observation"
        _append_record(journal_path, intent, "blocked", message, now)
        return ExecutionResult(intent.intent_id, "blocked", message)

    estimated_value = intent.quantity * intent.reference_price
    if (
        intent.action not in {"buy", "sell"}
        or intent.quantity <= 0
        or not math.isfinite(intent.reference_price)
        or intent.reference_price <= 0
        or not math.isfinite(policy.max_order_value)
        or (intent.action == "buy" and estimated_value > policy.max_order_value)
    ):
        message = (
            "paper mode blocked: invalid quantity/price or order value cap exceeded "
            f"({estimated_value:.2f} > {policy.max_order_value:.2f})"
        )
        _append_record(journal_path, intent, "blocked", message, now)
        return ExecutionResult(intent.intent_id, "blocked", message)

    if intent.action == "buy" and (
        not math.isfinite(policy.max_daily_loss_pct)
        or account_day_profit_pct is None
        or not math.isfinite(account_day_profit_pct)
        or account_day_profit_pct <= -policy.max_daily_loss_pct
    ):
        message = "paper mode blocked: daily loss circuit breaker is active"
        _append_record(journal_path, intent, "blocked", message, now)
        return ExecutionResult(intent.intent_id, "blocked", message)

    try:
        execution_lock = _acquire_execution_lock(journal_path, now)
    except OSError:
        execution_lock = None
    if execution_lock is None:
        message = "paper mode blocked: another order execution is active"
        return ExecutionResult(intent.intent_id, "blocked", message)
    try:
        if _already_handled(journal_path, intent.intent_id):
            return ExecutionResult(
                intent.intent_id, "duplicate", "intent already handled today"
            )
        if _failed_order_count(journal_path, intent.trade_date) >= policy.max_failed_orders:
            message = "paper mode blocked: daily failure circuit breaker is active"
            _append_record(journal_path, intent, "blocked", message, now)
            return ExecutionResult(intent.intent_id, "blocked", message)
        try:
            claimed = _claim_intent(journal_path, intent.intent_id, now)
        except OSError:
            message = "paper mode blocked: atomic order claim could not be created"
            _append_record(journal_path, intent, "blocked", message, now)
            return ExecutionResult(intent.intent_id, "blocked", message)
        if not claimed:
            return ExecutionResult(
                intent.intent_id, "duplicate", "intent already handled today"
            )

        _append_record(journal_path, intent, "attempted", "broker submission started", now)
        try:
            submitted = bool(submit())
        except Exception as exc:
            message = f"broker submission raised {type(exc).__name__}"
            _append_record(journal_path, intent, "failed", message, now)
            return ExecutionResult(intent.intent_id, "failed", message)
        status = "success" if submitted else "failed"
        message = "broker submission completed" if submitted else "broker submission failed"
        _append_record(journal_path, intent, status, message, now)
        return ExecutionResult(intent.intent_id, status, message)
    finally:
        _release_execution_lock(execution_lock)
