"""
东方财富个股动量策略（stock_auto_trade.py）的纯计算逻辑单测。
不碰网络：选股、止损止盈、仓位计算都是不依赖 requests 的纯函数。
"""
import datetime as dt
from unittest.mock import patch

from paper_execution import ExecutionPolicy
import stock_auto_trade as sat


class TestCandidateFilter:
    def test_within_range_and_enough_volume_passes(self):
        assert sat.passes_candidate_filter(pct=0.05, amount=3_00000000) is True

    def test_excludes_low_pct(self):
        assert sat.passes_candidate_filter(pct=0.01, amount=3_00000000) is False

    def test_excludes_too_high_pct_near_limit_up(self):
        assert sat.passes_candidate_filter(pct=0.15, amount=3_00000000) is False

    def test_excludes_low_volume(self):
        assert sat.passes_candidate_filter(pct=0.05, amount=1_00000000) is False

    def test_boundaries_are_inclusive(self):
        assert sat.passes_candidate_filter(pct=sat.MIN_INCREASE, amount=sat.MIN_AMOUNT) is True
        assert sat.passes_candidate_filter(pct=sat.MAX_INCREASE, amount=sat.MIN_AMOUNT) is True


class TestStopLossTakeProfit:
    # 用 sat.STOP_LOSS/sat.TAKE_PROFIT 而不是硬编码-7%/20%，
    # 这样以后再调参数（比如这次从-7%改到-5%）测试不用跟着改
    def test_stop_loss_triggers_at_threshold(self):
        threshold_pct = sat.STOP_LOSS * 100
        assert sat.should_stop_loss(threshold_pct) is True

    def test_stop_loss_triggers_below_threshold(self):
        assert sat.should_stop_loss(sat.STOP_LOSS * 100 - 2.5) is True

    def test_stop_loss_does_not_trigger_above_threshold(self):
        assert sat.should_stop_loss(sat.STOP_LOSS * 100 + 0.1) is False

    def test_take_profit_triggers_at_threshold(self):
        assert sat.should_take_profit(sat.TAKE_PROFIT * 100) is True

    def test_take_profit_does_not_trigger_below_threshold(self):
        assert sat.should_take_profit(sat.TAKE_PROFIT * 100 - 0.1) is False

    def test_stop_loss_and_take_profit_are_mutually_exclusive_in_practice(self):
        # 正常盈亏不会同时触发，止损止盈之间应该有一段"什么都不做"的区间
        midpoint = (sat.STOP_LOSS * 100 + sat.TAKE_PROFIT * 100) / 2
        for pct in (midpoint, 0.0):
            assert sat.should_stop_loss(pct) is False
            assert sat.should_take_profit(pct) is False


class TestPositionSizeCalculation:
    def test_position_size_calculation(self):
        # 10万可用资金，指定90%仓位，股价10元 -> 9万仓位 / 10元 = 9000股，按手（100股）取整
        qty = sat.calc_buy_qty(avail_balance=100_000, price=10.0, position_pct=0.9)
        assert qty == 9000

    def test_rounds_down_to_whole_lots(self):
        # 3万资金90%仓位=27000元，股价13.7元 -> 1970.8股，取整到手(100)应该是1900股
        qty = sat.calc_buy_qty(avail_balance=30_000, price=13.7, position_pct=0.9)
        assert qty == 1900
        assert qty % 100 == 0

    def test_default_position_size_matches_current_strategy_param(self):
        # 用默认 position_pct（即 sat.MAX_POSITION_SIZE）算一遍，跟显式传参数的结果对得上
        qty_default = sat.calc_buy_qty(avail_balance=100_000, price=10.0)
        qty_explicit = sat.calc_buy_qty(avail_balance=100_000, price=10.0, position_pct=sat.MAX_POSITION_SIZE)
        assert qty_default == qty_explicit

    def test_zero_price_returns_zero(self):
        assert sat.calc_buy_qty(avail_balance=100_000, price=0) == 0

    def test_zero_balance_returns_zero(self):
        assert sat.calc_buy_qty(avail_balance=0, price=10.0) == 0

    def test_negative_price_returns_zero(self):
        assert sat.calc_buy_qty(avail_balance=100_000, price=-5) == 0


class TestDailyLossCalculation:
    def test_calculates_pct_from_persisted_opening_assets(self):
        snapshot = {"totalAssets": 980_000}

        assert sat.calculate_account_day_profit_pct(snapshot, 1_000_000) == -2.0

    def test_missing_or_invalid_account_snapshot_fails_closed(self):
        assert sat.calculate_account_day_profit_pct({}, 100_000) is None
        assert sat.calculate_account_day_profit_pct({"totalAssets": 100_000}, None) is None

    def test_opening_assets_are_initialized_only_near_market_open(self, tmp_path):
        snapshot = {"totalAssets": 1_000_000}
        risk_dir = tmp_path / "risk"

        opening = sat.load_or_initialize_opening_assets(
            snapshot,
            dt.datetime(2026, 10, 12, 9, 30),
            risk_dir,
        )
        later = sat.load_or_initialize_opening_assets(
            {"totalAssets": 970_000},
            dt.datetime(2026, 10, 12, 14, 0),
            risk_dir,
        )

        assert opening == 1_000_000
        assert later == 1_000_000
        assert sat.calculate_account_day_profit_pct({"totalAssets": 970_000}, later) == -3.0

    def test_late_start_without_opening_snapshot_blocks_new_buys(self, tmp_path):
        assert sat.load_or_initialize_opening_assets(
            {"totalAssets": 1_000_000},
            dt.datetime(2026, 10, 12, 10, 0),
            tmp_path / "risk",
        ) is None


def test_eastmoney_source_timestamp_is_preferred_to_receive_time():
    received_at = dt.datetime(2026, 10, 12, 10, 0)
    source_at = dt.datetime(2026, 10, 12, 9, 55)

    assert sat.eastmoney_observed_at(
        {"f124": int(source_at.timestamp())}, received_at
    ) == source_at
    assert sat.eastmoney_observed_at({}, received_at) is None


def test_check_skips_all_account_calls_until_market_day_is_armed(tmp_path):
    with (
        patch.object(sat, "MARKET_OPEN_DATE_FILE", tmp_path / "missing-market-date"),
        patch.object(sat, "get_positions") as get_positions,
        patch.object(sat, "log"),
    ):
        sat.check_and_trade()

    get_positions.assert_not_called()


class TestPaperExecutionRouting:
    def test_shadow_route_records_plan_without_calling_broker(self, tmp_path):
        policy = ExecutionPolicy.from_environment(
            {}, account_auto_trade=True, api_key="configured-key"
        )

        with patch.object(sat, "buy") as broker_buy:
            result = sat.route_simulated_order(
                "buy",
                "600000",
                100,
                name="浦发银行",
                price=10.0,
                reason="entry",
                policy=policy,
                journal_path=tmp_path / "orders.jsonl",
                now=dt.datetime(2026, 10, 12, 10, 0),
            )

        assert result.status == "shadow"
        broker_buy.assert_not_called()

    def test_confirmed_paper_route_calls_existing_eastmoney_buy(self, tmp_path):
        now = dt.datetime(2026, 10, 12, 10, 0)
        market_open_date = tmp_path / "market-open-date"
        market_open_date.write_text(now.date().isoformat(), encoding="utf-8")
        policy = ExecutionPolicy.from_environment(
            {
                "EASTMONEY_EXECUTION_MODE": "paper",
                "EASTMONEY_PAPER_CONFIRM": "SIMULATED_ORDERS_ONLY",
            },
            account_auto_trade=True,
            api_key="configured-key",
            market_open_date_path=market_open_date,
        )

        with patch.object(sat, "buy", return_value=True) as broker_buy:
            result = sat.route_simulated_order(
                "buy",
                "600000",
                100,
                name="浦发银行",
                price=10.0,
                reason="entry",
                policy=policy,
                journal_path=tmp_path / "orders.jsonl",
                now=now,
                observed_at=now,
                account_day_profit_pct=0.0,
            )

        assert result.status == "success"
        broker_buy.assert_called_once_with(
            "600000", 100, "浦发银行", 10.0, source="模拟盘"
        )
