import datetime as dt

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
    policy = ExecutionPolicy.from_environment(
        {
            "EASTMONEY_EXECUTION_MODE": "paper",
            "EASTMONEY_PAPER_CONFIRM": "SIMULATED_ORDERS_ONLY",
        },
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
    journal = tmp_path / "orders.jsonl"

    first = execute_intent(
        intent,
        policy,
        journal_path=journal,
        submit=lambda: calls.append("submitted") or True,
        now=dt.datetime(2026, 10, 12, 10, 0),
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


def test_order_value_cap_blocks_oversized_simulated_order(tmp_path):
    policy = ExecutionPolicy.from_environment(
        {
            "EASTMONEY_EXECUTION_MODE": "paper",
            "EASTMONEY_PAPER_CONFIRM": "SIMULATED_ORDERS_ONLY",
            "EASTMONEY_MAX_ORDER_VALUE": "100000",
        },
        account_auto_trade=True,
        api_key="configured-key",
    )
    intent = OrderIntent(
        trade_date=dt.date(2026, 10, 12),
        strategy="daily_breakout_2_fixed",
        action="buy",
        code="600000",
        quantity=20_000,
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
    assert "order value cap" in result.message
    assert calls == []
