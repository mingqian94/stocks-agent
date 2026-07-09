"""
东方财富个股动量策略（stock_auto_trade.py）的纯计算逻辑单测。
不碰网络：选股、止损止盈、仓位计算都是不依赖 requests 的纯函数。
"""
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
    def test_stop_loss_triggers_at_threshold(self):
        assert sat.should_stop_loss(-7.0) is True

    def test_stop_loss_triggers_below_threshold(self):
        assert sat.should_stop_loss(-9.5) is True

    def test_stop_loss_does_not_trigger_above_threshold(self):
        assert sat.should_stop_loss(-6.9) is False

    def test_take_profit_triggers_at_threshold(self):
        assert sat.should_take_profit(20.0) is True

    def test_take_profit_does_not_trigger_below_threshold(self):
        assert sat.should_take_profit(19.9) is False

    def test_stop_loss_and_take_profit_are_mutually_exclusive_in_practice(self):
        # 正常盈亏不会同时触发，止损止盈之间应该有一段"什么都不做"的区间
        for pct in (-5.0, 0.0, 5.0, 10.0):
            assert sat.should_stop_loss(pct) is False
            assert sat.should_take_profit(pct) is False


class TestPositionSizeCalculation:
    def test_position_size_calculation(self):
        # 10万可用资金，95%仓位，股价10元 -> 9.5万仓位 / 10元 = 9500股，按手（100股）取整
        qty = sat.calc_buy_qty(avail_balance=100_000, price=10.0)
        assert qty == 9500

    def test_rounds_down_to_whole_lots(self):
        # 3万资金95%仓位=28500元，股价13.7元 -> 2080.29股，取整到手(100)应该是2000股
        qty = sat.calc_buy_qty(avail_balance=30_000, price=13.7)
        assert qty == 2000
        assert qty % 100 == 0

    def test_zero_price_returns_zero(self):
        assert sat.calc_buy_qty(avail_balance=100_000, price=0) == 0

    def test_zero_balance_returns_zero(self):
        assert sat.calc_buy_qty(avail_balance=0, price=10.0) == 0

    def test_negative_price_returns_zero(self):
        assert sat.calc_buy_qty(avail_balance=100_000, price=-5) == 0
