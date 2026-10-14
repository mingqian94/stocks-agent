import datetime as dt
import threading
from concurrent.futures import ThreadPoolExecutor

from paper_execution import ExecutionPolicy, OrderIntent, execute_intent


def test_default_policy_records_shadow_intent_without_submitting(tmp_path):
    policy = ExecutionPolicy.from_environment(
        {}, account_auto_trade=True, api_key="configured-key"
    )
    intent = OrderIntent(
        trade_date=dt.date(2026, 10, 12),
        strategy="daily_breakout_2_fixed",
        action="buy",
        code="600000",
        quantity=100,
        reference_price=10.0,
        reason="entry",
        observed_at=dt.datetime(2026, 10, 12, 10, 0),
    )
    calls = []

    result = execute_intent(
        intent,
        policy,
        journal_path=tmp_path / "orders.jsonl",
        submit=lambda: calls.append("submitted") or True,
        now=dt.datetime(2026, 10, 12, 10, 0),
    )

    assert result.status == "shadow"
    assert calls == []
    assert "shadow" in (tmp_path / "orders.jsonl").read_text(encoding="utf-8")


def test_repeated_shadow_intent_is_journaled_only_once(tmp_path):
    policy = ExecutionPolicy.from_environment(
        {}, account_auto_trade=True, api_key="configured-key"
    )
    intent = OrderIntent(
        trade_date=dt.date(2026, 10, 12),
        strategy="daily_breakout_2_fixed",
        action="buy",
        code="600000",
        quantity=100,
        reference_price=10.0,
        reason="entry",
        observed_at=dt.datetime(2026, 10, 12, 10, 0),
    )
    journal = tmp_path / "orders.jsonl"

    execute_intent(
        intent,
        policy,
        journal_path=journal,
        submit=lambda: True,
        now=dt.datetime(2026, 10, 12, 10, 0),
    )
    repeated = execute_intent(
        intent,
        policy,
        journal_path=journal,
        submit=lambda: True,
        now=dt.datetime(2026, 10, 12, 10, 3),
    )

    assert repeated.status == "duplicate"
    assert len(journal.read_text(encoding="utf-8").splitlines()) == 1


def test_paper_mode_requires_explicit_confirmation(tmp_path):
    policy = ExecutionPolicy.from_environment(
        {"EASTMONEY_EXECUTION_MODE": "paper"},
        account_auto_trade=True,
        api_key="configured-key",
    )
    intent = OrderIntent(
        trade_date=dt.date(2026, 10, 12),
        strategy="daily_breakout_2_fixed",
        action="buy",
        code="600000",
        quantity=100,
        reference_price=10.0,
        reason="entry",
    )
    calls = []

    result = execute_intent(
        intent,
        policy,
        journal_path=tmp_path / "orders.jsonl",
        submit=lambda: calls.append("submitted") or True,
        now=dt.datetime(2026, 10, 12, 10, 0),
    )

    assert result.status == "blocked"
    assert "confirmation" in result.message
    assert calls == []


def test_confirmed_paper_intent_submits_only_once_per_day(tmp_path):
    market_open_date = tmp_path / "market-open-date"
    market_open_date.write_text("2026-10-12", encoding="utf-8")
    policy = ExecutionPolicy.from_environment(
        {
            "EASTMONEY_EXECUTION_MODE": "paper",
            "EASTMONEY_PAPER_CONFIRM": "SIMULATED_ORDERS_ONLY",
        },
        account_auto_trade=True,
        api_key="configured-key",
        market_open_date_path=market_open_date,
    )
    intent = OrderIntent(
        trade_date=dt.date(2026, 10, 12),
        strategy="daily_breakout_2_fixed",
        action="buy",
        code="600000",
        quantity=100,
        reference_price=10.0,
        reason="entry",
        observed_at=dt.datetime(2026, 10, 12, 10, 0),
    )
    calls = []
    journal = tmp_path / "orders.jsonl"

    first = execute_intent(
        intent,
        policy,
        journal_path=journal,
        submit=lambda: calls.append("submitted") or True,
        now=dt.datetime(2026, 10, 12, 10, 0),
        account_day_profit_pct=0.0,
    )
    duplicate = execute_intent(
        intent,
        policy,
        journal_path=journal,
        submit=lambda: calls.append("submitted") or True,
        now=dt.datetime(2026, 10, 12, 10, 3),
    )

    assert first.status == "success"
    assert duplicate.status == "duplicate"
    assert calls == ["submitted"]


def test_kill_switch_blocks_confirmed_paper_order(tmp_path):
    policy = ExecutionPolicy.from_environment(
        {
            "EASTMONEY_EXECUTION_MODE": "paper",
            "EASTMONEY_PAPER_CONFIRM": "SIMULATED_ORDERS_ONLY",
            "EASTMONEY_KILL_SWITCH": "1",
        },
        account_auto_trade=True,
        api_key="configured-key",
    )
    intent = OrderIntent(
        trade_date=dt.date(2026, 10, 12),
        strategy="daily_breakout_2_fixed",
        action="sell",
        code="600000",
        quantity=100,
        reference_price=10.0,
        reason="stop_loss",
    )
    calls = []

    result = execute_intent(
        intent,
        policy,
        journal_path=tmp_path / "orders.jsonl",
        submit=lambda: calls.append("submitted") or True,
        now=dt.datetime(2026, 10, 12, 10, 0),
    )

    assert result.status == "blocked"
    assert "kill switch" in result.message
    assert calls == []


def test_kill_switch_file_stops_an_already_running_policy(tmp_path):
    kill_switch = tmp_path / "kill-switch"
    policy = ExecutionPolicy.from_environment(
        {
            "EASTMONEY_EXECUTION_MODE": "paper",
            "EASTMONEY_PAPER_CONFIRM": "SIMULATED_ORDERS_ONLY",
        },
        account_auto_trade=True,
        api_key="configured-key",
        kill_switch_path=kill_switch,
    )
    kill_switch.touch()
    intent = OrderIntent(
        trade_date=dt.date(2026, 10, 12),
        strategy="daily_breakout_2_fixed",
        action="sell",
        code="600000",
        quantity=100,
        reference_price=10.0,
        reason="stop_loss",
    )
    calls = []

    result = execute_intent(
        intent,
        policy,
        journal_path=tmp_path / "orders.jsonl",
        submit=lambda: calls.append("submitted") or True,
        now=dt.datetime(2026, 10, 12, 10, 0),
    )

    assert result.status == "blocked"
    assert "kill switch" in result.message
    assert calls == []


def test_paper_order_requires_account_opt_in_and_real_api_key(tmp_path):
    environment = {
        "EASTMONEY_EXECUTION_MODE": "paper",
        "EASTMONEY_PAPER_CONFIRM": "SIMULATED_ORDERS_ONLY",
    }
    intent = OrderIntent(
        trade_date=dt.date(2026, 10, 12),
        strategy="daily_breakout_2_fixed",
        action="buy",
        code="600000",
        quantity=100,
        reference_price=10.0,
        reason="entry",
    )
    calls = []

    without_account_opt_in = execute_intent(
        intent,
        ExecutionPolicy.from_environment(
            environment, account_auto_trade=False, api_key="configured-key"
        ),
        journal_path=tmp_path / "account-off.jsonl",
        submit=lambda: calls.append("submitted") or True,
        now=dt.datetime(2026, 10, 12, 10, 0),
    )
    without_key = execute_intent(
        intent,
        ExecutionPolicy.from_environment(
            environment, account_auto_trade=True, api_key="PENDING_USER_INPUT"
        ),
        journal_path=tmp_path / "key-missing.jsonl",
        submit=lambda: calls.append("submitted") or True,
        now=dt.datetime(2026, 10, 12, 10, 0),
    )

    assert without_account_opt_in.status == "blocked"
    assert "account" in without_account_opt_in.message
    assert without_key.status == "blocked"
    assert "API key" in without_key.message
    assert calls == []


def test_confirmed_paper_order_never_calls_broker_while_market_is_closed(tmp_path):
    policy = ExecutionPolicy.from_environment(
        {
            "EASTMONEY_EXECUTION_MODE": "paper",
            "EASTMONEY_PAPER_CONFIRM": "SIMULATED_ORDERS_ONLY",
        },
        account_auto_trade=True,
        api_key="configured-key",
    )
    intent = OrderIntent(
        trade_date=dt.date(2026, 10, 11),
        strategy="daily_breakout_2_fixed",
        action="buy",
        code="600000",
        quantity=100,
        reference_price=10.0,
        reason="entry",
    )
    calls = []

    result = execute_intent(
        intent,
        policy,
        journal_path=tmp_path / "orders.jsonl",
        submit=lambda: calls.append("submitted") or True,
        now=dt.datetime(2026, 10, 11, 10, 0),  # Sunday
    )

    assert result.status == "blocked"
    assert "market session" in result.message
    assert calls == []


def test_paper_order_requires_today_market_open_confirmation(tmp_path):
    market_open_date = tmp_path / "market-open-date"
    policy = ExecutionPolicy.from_environment(
        {
            "EASTMONEY_EXECUTION_MODE": "paper",
            "EASTMONEY_PAPER_CONFIRM": "SIMULATED_ORDERS_ONLY",
        },
        account_auto_trade=True,
        api_key="configured-key",
        market_open_date_path=market_open_date,
    )
    intent = OrderIntent(
        trade_date=dt.date(2026, 10, 12),
        strategy="daily_breakout_2_fixed",
        action="buy",
        code="600000",
        quantity=100,
        reference_price=10.0,
        reason="entry",
    )
    calls = []

    result = execute_intent(
        intent,
        policy,
        journal_path=tmp_path / "orders.jsonl",
        submit=lambda: calls.append("submitted") or True,
        now=dt.datetime(2026, 10, 12, 10, 0),
    )

    assert result.status == "blocked"
    assert "market-open date" in result.message
    assert calls == []


def test_stale_market_observation_fails_closed(tmp_path):
    market_open_date = tmp_path / "market-open-date"
    market_open_date.write_text("2026-10-12", encoding="utf-8")
    policy = ExecutionPolicy.from_environment(
        {
            "EASTMONEY_EXECUTION_MODE": "paper",
            "EASTMONEY_PAPER_CONFIRM": "SIMULATED_ORDERS_ONLY",
            "EASTMONEY_MAX_SIGNAL_AGE_SECONDS": "120",
        },
        account_auto_trade=True,
        api_key="configured-key",
        market_open_date_path=market_open_date,
    )
    intent = OrderIntent(
        trade_date=dt.date(2026, 10, 12),
        strategy="daily_breakout_2_fixed",
        action="buy",
        code="600000",
        quantity=100,
        reference_price=10.0,
        reason="entry",
        observed_at=dt.datetime(2026, 10, 12, 9, 55),
    )
    calls = []

    result = execute_intent(
        intent,
        policy,
        journal_path=tmp_path / "orders.jsonl",
        submit=lambda: calls.append("submitted") or True,
        now=dt.datetime(2026, 10, 12, 10, 0),
    )

    assert result.status == "blocked"
    assert "stale market observation" in result.message
    assert calls == []


def test_daily_loss_circuit_breaker_blocks_new_buys(tmp_path):
    market_open_date = tmp_path / "market-open-date"
    market_open_date.write_text("2026-10-12", encoding="utf-8")
    policy = ExecutionPolicy.from_environment(
        {
            "EASTMONEY_EXECUTION_MODE": "paper",
            "EASTMONEY_PAPER_CONFIRM": "SIMULATED_ORDERS_ONLY",
            "EASTMONEY_MAX_DAILY_LOSS_PCT": "2.0",
        },
        account_auto_trade=True,
        api_key="configured-key",
        market_open_date_path=market_open_date,
    )
    intent = OrderIntent(
        trade_date=dt.date(2026, 10, 12),
        strategy="daily_breakout_2_fixed",
        action="buy",
        code="600000",
        quantity=100,
        reference_price=10.0,
        reason="entry",
        observed_at=dt.datetime(2026, 10, 12, 10, 0),
    )
    calls = []

    result = execute_intent(
        intent,
        policy,
        journal_path=tmp_path / "orders.jsonl",
        submit=lambda: calls.append("submitted") or True,
        now=dt.datetime(2026, 10, 12, 10, 0),
        account_day_profit_pct=-2.5,
    )

    assert result.status == "blocked"
    assert "daily loss circuit breaker" in result.message
    assert calls == []


def test_non_finite_daily_loss_limit_fails_closed(tmp_path):
    market_open_date = tmp_path / "market-open-date"
    market_open_date.write_text("2026-10-12", encoding="utf-8")
    policy = ExecutionPolicy.from_environment(
        {
            "EASTMONEY_EXECUTION_MODE": "paper",
            "EASTMONEY_PAPER_CONFIRM": "SIMULATED_ORDERS_ONLY",
            "EASTMONEY_MAX_DAILY_LOSS_PCT": "nan",
        },
        account_auto_trade=True,
        api_key="configured-key",
        market_open_date_path=market_open_date,
    )
    intent = OrderIntent(
        trade_date=dt.date(2026, 10, 12),
        strategy="daily_breakout_2_fixed",
        action="buy",
        code="600000",
        quantity=100,
        reference_price=10.0,
        reason="entry",
        observed_at=dt.datetime(2026, 10, 12, 10, 0),
    )
    calls = []

    result = execute_intent(
        intent,
        policy,
        journal_path=tmp_path / "orders.jsonl",
        submit=lambda: calls.append("submitted") or True,
        now=dt.datetime(2026, 10, 12, 10, 0),
        account_day_profit_pct=0.0,
    )

    assert result.status == "blocked"
    assert "daily loss circuit breaker" in result.message
    assert calls == []


def test_daily_failure_circuit_breaker_stops_further_orders(tmp_path):
    market_open_date = tmp_path / "market-open-date"
    market_open_date.write_text("2026-10-12", encoding="utf-8")
    policy = ExecutionPolicy.from_environment(
        {
            "EASTMONEY_EXECUTION_MODE": "paper",
            "EASTMONEY_PAPER_CONFIRM": "SIMULATED_ORDERS_ONLY",
            "EASTMONEY_MAX_FAILED_ORDERS": "2",
        },
        account_auto_trade=True,
        api_key="configured-key",
        market_open_date_path=market_open_date,
    )
    journal = tmp_path / "orders.jsonl"
    calls = []

    results = []
    for index, code in enumerate(("600000", "600001", "600002")):
        intent = OrderIntent(
            trade_date=dt.date(2026, 10, 12),
            strategy="daily_breakout_2_fixed",
            action="sell",
            code=code,
            quantity=100,
            reference_price=10.0,
            reason="stop_loss",
            observed_at=dt.datetime(2026, 10, 12, 10, index),
        )
        results.append(
            execute_intent(
                intent,
                policy,
                journal_path=journal,
                submit=lambda: calls.append("submitted") or False,
                now=dt.datetime(2026, 10, 12, 10, index),
                account_day_profit_pct=0.0,
            )
        )

    assert [result.status for result in results] == ["failed", "failed", "blocked"]
    assert "failure circuit breaker" in results[-1].message
    assert calls == ["submitted", "submitted"]


def test_concurrent_workers_claim_an_intent_atomically(tmp_path):
    market_open_date = tmp_path / "market-open-date"
    market_open_date.write_text("2026-10-12", encoding="utf-8")
    policy = ExecutionPolicy.from_environment(
        {
            "EASTMONEY_EXECUTION_MODE": "paper",
            "EASTMONEY_PAPER_CONFIRM": "SIMULATED_ORDERS_ONLY",
        },
        account_auto_trade=True,
        api_key="configured-key",
        market_open_date_path=market_open_date,
    )
    intent = OrderIntent(
        trade_date=dt.date(2026, 10, 12),
        strategy="daily_breakout_2_fixed",
        action="sell",
        code="600000",
        quantity=100,
        reference_price=10.0,
        reason="stop_loss",
        observed_at=dt.datetime(2026, 10, 12, 10, 0),
    )
    journal = tmp_path / "orders.jsonl"
    start = threading.Barrier(8)
    calls = []

    def worker():
        start.wait()
        return execute_intent(
            intent,
            policy,
            journal_path=journal,
            submit=lambda: calls.append("submitted") or True,
            now=dt.datetime(2026, 10, 12, 10, 0),
            account_day_profit_pct=0.0,
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: worker(), range(8)))

    assert sum(result.status == "success" for result in results) == 1
    assert sum(result.status == "duplicate" for result in results) == 7
    assert calls == ["submitted"]


def test_concurrent_failures_cannot_overshoot_daily_failure_limit(tmp_path):
    market_open_date = tmp_path / "market-open-date"
    market_open_date.write_text("2026-10-12", encoding="utf-8")
    policy = ExecutionPolicy.from_environment(
        {
            "EASTMONEY_EXECUTION_MODE": "paper",
            "EASTMONEY_PAPER_CONFIRM": "SIMULATED_ORDERS_ONLY",
            "EASTMONEY_MAX_FAILED_ORDERS": "2",
        },
        account_auto_trade=True,
        api_key="configured-key",
        market_open_date_path=market_open_date,
    )
    journal = tmp_path / "orders.jsonl"
    start = threading.Barrier(4)
    calls = []

    def worker(index):
        intent = OrderIntent(
            trade_date=dt.date(2026, 10, 12),
            strategy="daily_breakout_2_fixed",
            action="sell",
            code=f"60000{index}",
            quantity=100,
            reference_price=10.0,
            reason="stop_loss",
            observed_at=dt.datetime(2026, 10, 12, 10, 0),
        )
        start.wait()
        return execute_intent(
            intent,
            policy,
            journal_path=journal,
            submit=lambda: calls.append(index) or False,
            now=dt.datetime(2026, 10, 12, 10, 0),
            account_day_profit_pct=0.0,
        )

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(worker, range(4)))

    assert sum(result.status == "failed" for result in results) == 2
    assert sum(result.status == "blocked" for result in results) == 2
    assert len(calls) == 2


def test_order_value_cap_blocks_oversized_simulated_order(tmp_path):
    market_open_date = tmp_path / "market-open-date"
    market_open_date.write_text("2026-10-12", encoding="utf-8")
    policy = ExecutionPolicy.from_environment(
        {
            "EASTMONEY_EXECUTION_MODE": "paper",
            "EASTMONEY_PAPER_CONFIRM": "SIMULATED_ORDERS_ONLY",
            "EASTMONEY_MAX_ORDER_VALUE": "100000",
        },
        account_auto_trade=True,
        api_key="configured-key",
        market_open_date_path=market_open_date,
    )
    intent = OrderIntent(
        trade_date=dt.date(2026, 10, 12),
        strategy="daily_breakout_2_fixed",
        action="buy",
        code="600000",
        quantity=20_000,
        reference_price=10.0,
        reason="entry",
        observed_at=dt.datetime(2026, 10, 12, 10, 0),
    )
    calls = []

    result = execute_intent(
        intent,
        policy,
        journal_path=tmp_path / "orders.jsonl",
        submit=lambda: calls.append("submitted") or True,
        now=dt.datetime(2026, 10, 12, 10, 0),
    )

    assert result.status == "blocked"
    assert "order value cap" in result.message
    assert calls == []


def test_non_finite_price_fails_closed(tmp_path):
    market_open_date = tmp_path / "market-open-date"
    market_open_date.write_text("2026-10-12", encoding="utf-8")
    policy = ExecutionPolicy.from_environment(
        {
            "EASTMONEY_EXECUTION_MODE": "paper",
            "EASTMONEY_PAPER_CONFIRM": "SIMULATED_ORDERS_ONLY",
        },
        account_auto_trade=True,
        api_key="configured-key",
        market_open_date_path=market_open_date,
    )
    intent = OrderIntent(
        trade_date=dt.date(2026, 10, 12),
        strategy="daily_breakout_2_fixed",
        action="buy",
        code="600000",
        quantity=100,
        reference_price=float("nan"),
        reason="entry",
        observed_at=dt.datetime(2026, 10, 12, 10, 0),
    )
    calls = []

    result = execute_intent(
        intent,
        policy,
        journal_path=tmp_path / "orders.jsonl",
        submit=lambda: calls.append("submitted") or True,
        now=dt.datetime(2026, 10, 12, 10, 0),
    )

    assert result.status == "blocked"
    assert "invalid quantity/price" in result.message
    assert calls == []
