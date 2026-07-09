"""
ETF动量轮动策略（auto_trade.py）里跟网络无关的纯计算逻辑单测。
AutoTrader.__init__ 只读 accounts.py/keys_config.py 里已经加载好的配置，不发请求，
可以直接实例化来测 calc_qty。
"""
import pytest
import auto_trade


@pytest.fixture
def trader():
    return auto_trade.AutoTrader('ht_7493')


class TestCalcQty:
    def test_position_size_calculation(self, trader):
        # 10万现金，股价10元 -> 10000股，整手
        assert trader.calc_qty(cash=100_000, price=10.0) == 10000

    def test_rounds_down_to_whole_lots(self, trader):
        # 3万现金，股价13.7元 -> 2189.78股，取整到手(100)应该是2100股
        qty = trader.calc_qty(cash=30_000, price=13.7)
        assert qty == 2100
        assert qty % 100 == 0

    def test_zero_price_returns_zero(self, trader):
        assert trader.calc_qty(cash=100_000, price=0) == 0

    def test_zero_cash_returns_zero(self, trader):
        assert trader.calc_qty(cash=0, price=10.0) == 0

    def test_negative_cash_returns_zero(self, trader):
        assert trader.calc_qty(cash=-100, price=10.0) == 0

    def test_insufficient_cash_for_one_lot_returns_zero(self, trader):
        # 股价100元，只有5000元现金，连1手(100股=1万元)都买不了
        assert trader.calc_qty(cash=5000, price=100.0) == 0


class TestAccountBinding:
    def test_ht_7493_binds_stable_strategy(self, trader):
        assert trader.strategy_id == 'etf_momentum_stable'

    def test_ht_8268_binds_aggressive_strategy(self):
        t = auto_trade.AutoTrader('ht_8268')
        assert t.strategy_id == 'etf_momentum_aggressive'

    def test_unknown_account_raises(self):
        with pytest.raises(ValueError):
            auto_trade.AutoTrader('not_a_real_account')
