"""Safety gate and local journal for East Money simulated orders.

The default is deliberately shadow-only.  Reaching the broker requires all
independent gates to agree, so merely configuring an API key cannot trade.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
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
    max_order_value: float

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str],
        *,
        account_auto_trade: bool,
        api_key: str,
    ) -> "ExecutionPolicy":
        raw_cap = environment.get("EASTMONEY_MAX_ORDER_VALUE", "500000").strip()
        try:
            max_order_value = max(float(raw_cap), 0.0)
        except ValueError:
            max_order_value = 0.0
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
            max_order_value=max_order_value,
        )


@dataclass(frozen=True)
class ExecutionResult:
    intent_id: str
    status: str
    message: str


def _append_record(path: Path, intent: OrderIntent, status: str, message: str, now: dt.datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "recorded_at": now.isoformat(timespec="seconds"),
        "intent_id": intent.intent_id,
        "status": status,
        "message": message,
        "intent": {**asdict(intent), "trade_date": intent.trade_date.isoformat()},
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


def execute_intent(
    intent: OrderIntent,
    policy: ExecutionPolicy,
    *,
    journal_path: Path,
    submit: Callable[[], bool],
    now: dt.datetime | None = None,
) -> ExecutionResult:
    """Record an intent or submit it when the explicit safety policy permits."""
    now = now or dt.datetime.now()
    if _already_handled(journal_path, intent.intent_id):
        return ExecutionResult(intent.intent_id, "duplicate", "intent already handled today")

    if policy.mode != "paper":
        message = "shadow mode: broker submission disabled"
        _append_record(journal_path, intent, "shadow", message, now)
        return ExecutionResult(intent.intent_id, "shadow", message)

    if not policy.confirmed:
        message = "paper mode blocked: explicit confirmation is missing"
        _append_record(journal_path, intent, "blocked", message, now)
        return ExecutionResult(intent.intent_id, "blocked", message)

    if policy.kill_switch:
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

    estimated_value = intent.quantity * intent.reference_price
    if (
        intent.action not in {"buy", "sell"}
        or intent.quantity <= 0
        or intent.reference_price <= 0
        or (intent.action == "buy" and estimated_value > policy.max_order_value)
    ):
        message = (
            "paper mode blocked: invalid quantity/price or order value cap exceeded "
            f"({estimated_value:.2f} > {policy.max_order_value:.2f})"
        )
        _append_record(journal_path, intent, "blocked", message, now)
        return ExecutionResult(intent.intent_id, "blocked", message)

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
