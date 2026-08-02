import pandas as pd
import pytest

from a_share_lab.engine import (
    BacktestConfig,
    StrategySpec,
    _stamp_tax,
    _buy_blocked,
    _lot_size,
    _quantity_step,
    _tick_price,
    _transfer_fee,
    prepare_features,
    run_backtest,
    select_candidates,
)
from a_share_lab.horizons import all_frozen_specs, trailing_windows


def _row(date, code, open_, high, low, close, preclose, amount=500_000_000):
    return {
        "date": pd.Timestamp(date),
        "code": code,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "preclose": preclose,
        "volume": 1_000_000,
        "amount": amount,
        "turn": 3.0,
        "tradestatus": 1,
        "pctChg": (close / preclose - 1) * 100,
        "isST": 0,
    }


def _benchmark(dates):
    return pd.DataFrame(
        {
            "date": pd.to_datetime(dates),
            "close": [100.0 + index for index in range(len(dates))],
        }
    )


def _memberships(codes):
    return pd.DataFrame(
        {
            "snapshot_date": [pd.Timestamp("2023-12-31")] * len(codes),
            "code": codes,
        }
    )


def test_daily_breakout_uses_previous_day_confirmation():
    prices = pd.DataFrame(
        [
            _row("2024-01-01", "sh.600000", 100, 102, 99, 101, 100),
            _row("2024-01-02", "sh.600000", 101, 107, 101, 106.05, 101),
        ]
    )
    features = prepare_features(prices)
    spec = StrategySpec(
        name="test",
        entry_model="daily_breakout",
        max_positions=2,
        stop_loss=-0.05,
        take_profit=0.08,
        max_holding_days=None,
        minimum_history=1,
    )
    selected = select_candidates(features[features["date"] == pd.Timestamp("2024-01-02")], spec)
    assert selected["code"].tolist() == ["sh.600000"]


def test_t_plus_one_prevents_same_day_stop_exit():
    dates = ["2024-01-01", "2024-01-02", "2024-01-03"]
    prices = pd.DataFrame(
        [
            _row(dates[0], "sh.600000", 100, 106, 99, 105, 100),  # signal
            _row(dates[1], "sh.600000", 100, 101, 90, 96, 105),   # buy; same-day stop ignored
            _row(dates[2], "sh.600000", 96, 97, 89, 90, 96),      # T+1 stop can execute
        ]
    )
    spec = StrategySpec(
        name="t1",
        entry_model="daily_breakout",
        max_positions=1,
        stop_loss=-0.05,
        take_profit=None,
        max_holding_days=None,
        minimum_history=1,
        require_previous_day_up=False,
    )
    result = run_backtest(
        prices,
        _memberships(["sh.600000"]),
        _benchmark(dates),
        spec,
        dates[0],
        dates[-1],
    )
    assert len(result["trades"]) == 1
    trade = result["trades"].iloc[0]
    assert trade["entry_date"] == pd.Timestamp("2024-01-02")
    assert trade["exit_date"] == pd.Timestamp("2024-01-03")
    assert trade["reason"] in {"stop", "stop_gap"}


def test_later_slot_targets_total_equity_not_remaining_cash():
    dates = ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"]
    rows = [
        _row(dates[0], "sh.600000", 10, 10.6, 9.9, 10.5, 10),
        _row(dates[0], "sh.600001", 10, 10.1, 9.9, 10.0, 10),
        _row(dates[1], "sh.600000", 10, 10.2, 9.9, 10.1, 10.5),
        _row(dates[1], "sh.600001", 10, 10.6, 9.9, 10.5, 10),
        _row(dates[2], "sh.600000", 10, 10.2, 9.9, 10.1, 10.1),
        _row(dates[2], "sh.600001", 10, 10.2, 9.9, 10.1, 10.5),
        _row(dates[3], "sh.600000", 10, 10.2, 9.9, 10.1, 10.1),
        _row(dates[3], "sh.600001", 10, 10.2, 9.9, 10.1, 10.1),
    ]
    spec = StrategySpec(
        name="sizing",
        entry_model="daily_breakout",
        max_positions=2,
        stop_loss=-0.50,
        take_profit=None,
        max_holding_days=None,
        minimum_history=1,
        require_previous_day_up=False,
    )
    result = run_backtest(
        pd.DataFrame(rows),
        _memberships(["sh.600000", "sh.600001"]),
        _benchmark(dates),
        spec,
        dates[0],
        dates[-1],
    )
    open_positions = result["open_positions"].set_index("code")
    assert (
        open_positions.loc["sh.600001", "shares"]
        * open_positions.loc["sh.600001", "entry_price"]
        > 400_000
    )


def test_stamp_tax_changes_on_2023_reduction_date():
    config = BacktestConfig()
    assert _stamp_tax(pd.Timestamp("2023-08-27"), config) == pytest.approx(0.001)
    assert _stamp_tax(pd.Timestamp("2023-08-28"), config) == pytest.approx(0.0005)
    assert _transfer_fee(pd.Timestamp("2022-04-28"), config) == pytest.approx(0.00002)
    assert _transfer_fee(pd.Timestamp("2022-04-29"), config) == pytest.approx(0.00001)


def test_signal_return_uses_point_in_time_pct_change_not_raw_ex_right_gap():
    row = _row("2024-01-02", "sh.600000", 9, 9.2, 8.9, 9, 10)
    row["pctChg"] = 0.0  # exchange reference was adjusted for a corporate action
    features = prepare_features(pd.DataFrame([row]))
    assert features.iloc[0]["daily_return"] == pytest.approx(0.0)
    assert features.iloc[0]["close"] == pytest.approx(9.0)  # execution price remains raw


def test_star_market_uses_200_share_minimum_lot():
    config = BacktestConfig(lot_size=100)
    assert _lot_size("sh.688001", config) == 200
    assert _lot_size("sh.600000", config) == 100
    assert _quantity_step("sh.688001", config) == 1
    assert _quantity_step("sh.600000", config) == 100


def test_fill_prices_round_adversely_to_one_cent_tick():
    assert _tick_price(10.001, "buy") == pytest.approx(10.01)
    assert _tick_price(10.009, "sell") == pytest.approx(10.00)


def test_one_price_limit_up_is_not_assumed_buyable():
    row = pd.Series(_row("2024-01-02", "sh.600000", 11, 11, 11, 11, 10))
    row["daily_return"] = 0.10
    assert _buy_blocked(row) is True


def test_same_bar_stop_and_target_uses_conservative_stop_path():
    dates = ["2024-01-01", "2024-01-02", "2024-01-03"]
    prices = pd.DataFrame(
        [
            _row(dates[0], "sh.600000", 100, 106, 99, 105, 100),
            _row(dates[1], "sh.600000", 100, 102, 98, 100, 105),
            _row(dates[2], "sh.600000", 100, 110, 90, 100, 100),
        ]
    )
    spec = StrategySpec(
        name="path",
        entry_model="daily_breakout",
        max_positions=1,
        stop_loss=-0.05,
        take_profit=0.05,
        max_holding_days=None,
        minimum_history=1,
        require_previous_day_up=False,
    )
    result = run_backtest(
        prices, _memberships(["sh.600000"]), _benchmark(dates), spec, dates[0], dates[-1]
    )
    assert result["trades"].iloc[0]["reason"] == "stop"


def test_final_blocked_position_remains_in_terminal_equity():
    dates = ["2024-01-01", "2024-01-02", "2024-01-03"]
    prices = pd.DataFrame(
        [
            _row(dates[0], "sh.600000", 100, 106, 99, 105, 100),
            _row(dates[1], "sh.600000", 100, 101, 99, 100, 105),
            _row(dates[2], "sh.600000", 90, 90, 90, 90, 100),
        ]
    )
    spec = StrategySpec(
        name="blocked_end",
        entry_model="daily_breakout",
        max_positions=1,
        stop_loss=-0.05,
        take_profit=None,
        max_holding_days=None,
        minimum_history=1,
        require_previous_day_up=False,
    )
    result = run_backtest(
        prices, _memberships(["sh.600000"]), _benchmark(dates), spec, dates[0], dates[-1]
    )
    terminal = result["equity_curve"].iloc[-1]
    assert terminal["positions"] == 1
    assert terminal["equity"] > terminal["cash"]
    assert result["execution_audit"]["open_positions_at_end"] == 1


def test_trailing_windows_are_inclusive_calendar_periods():
    assert trailing_windows("2026-07-31") == {
        "1_month": "2026-07-01",
        "3_months": "2026-05-01",
        "6_months": "2026-02-01",
        "1_year": "2025-08-01",
        "3_years": "2023-08-01",
    }


def test_horizon_runner_keeps_all_frozen_strategy_origins():
    specs = all_frozen_specs()
    assert len(specs) == 21
    assert specs[0][1] == "existing_git"
    assert sum(origin == "first_pass_new" for _, origin in specs) == 16
    assert sum(origin == "posthoc_new" for _, origin in specs) == 4


def test_external_scores_rank_at_close_and_fill_the_winner_next_open():
    dates = ["2024-01-01", "2024-01-02", "2024-01-03"]
    rows = []
    for date in dates:
        rows.extend(
            [
                _row(date, "sh.600000", 10, 10.5, 9.5, 10, 10),
                _row(date, "sh.600001", 20, 21, 19, 20, 20),
            ]
        )
    prices = pd.DataFrame(rows)
    prices["external_score"] = float("nan")
    prices.loc[
        (prices["date"] == pd.Timestamp(dates[0])) & (prices["code"] == "sh.600000"),
        "external_score",
    ] = 0.05
    prices.loc[
        (prices["date"] == pd.Timestamp(dates[0])) & (prices["code"] == "sh.600001"),
        "external_score",
    ] = 0.10
    spec = StrategySpec(
        name="external",
        entry_model="external_score",
        max_positions=1,
        stop_loss=-0.50,
        take_profit=None,
        max_holding_days=None,
        minimum_history=1,
        minimum_external_score=0.0,
    )

    result = run_backtest(
        prices,
        _memberships(["sh.600000", "sh.600001"]),
        _benchmark(dates),
        spec,
        dates[0],
        dates[-1],
    )

    assert list(result["open_positions"]["code"]) == ["sh.600001"]
    assert result["open_positions"].iloc[0]["entry_date"] == pd.Timestamp(dates[1])
