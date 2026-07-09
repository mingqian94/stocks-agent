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
