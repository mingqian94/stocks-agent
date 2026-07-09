"""
ETF动量轮动策略（auto_trade.py）里跟网络无关的纯计算逻辑单测。
AutoTrader.__init__ 只读 accounts.py/keys_config.py 里已经加载好的配置，不发请求，
可以直接实例化来测 calc_qty。
"""
from unittest.mock import patch
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


class TestPerAccountRiskParams:
    """2026.07.09之前稳健/激进两个账户实际用的是同一套模块常量（同样的止损、同样的持仓集中度），
    STRATEGIES里配的参数从来没被读过。这几个测试确认现在是真的按账户分开了。"""

    def test_stable_account_uses_top3_momentum(self, trader):
        assert trader.momentum_top_n == 3

    def test_aggressive_account_uses_top2_momentum(self):
        t = auto_trade.AutoTrader('ht_8268')
        assert t.momentum_top_n == 2

    def test_stable_account_stop_loss_is_tighter(self, trader):
        assert trader.stop_loss_day_pct == pytest.approx(-3.0)

    def test_aggressive_account_stop_loss_is_looser(self):
        t = auto_trade.AutoTrader('ht_8268')
        assert t.stop_loss_day_pct == pytest.approx(-5.0)

    def test_stable_account_has_no_profit_floor(self, trader):
        assert trader.profit_floor is None

    def test_aggressive_account_has_8pct_profit_floor(self):
        t = auto_trade.AutoTrader('ht_8268')
        assert t.profit_floor == pytest.approx(0.08)


class TestProfitFloorCircuitBreaker:
    """本期收益跌到地板以下要清仓保护、本期不再买入——mock掉网络请求，只验证触发行为"""

    def _fake_period(self, initial=1_000_000):
        return {'round': '初赛', 'period': '测试期', 'initial': initial, 'final': None, 'profit_pct': None, 'status': 'active'}

    def test_sells_everything_when_below_floor(self):
        t = auto_trade.AutoTrader('ht_8268')
        t.auto_trade = True
        fake_positions = {
            'totalAssets': 1_070_000,  # (1070000-1000000)/1000000 = 7% < 8%地板
            'availBalance': 50_000,
            'posList': [
                {'secCode': '512480', 'secName': '半导体ETF', 'availCount': 1000, 'price': 2.0},
                {'secCode': '588000', 'secName': '科创50ETF', 'availCount': 500, 'price': 3.0},
            ]
        }
        with patch.object(t, 'get_positions', return_value=fake_positions), \
             patch('auto_trade.get_current_period', return_value=self._fake_period()), \
             patch.object(t, 'sell') as mock_sell, \
             patch('time.sleep'):
            t.check_and_trade()

        assert mock_sell.call_count == 2
        sold_codes = {call.args[0] for call in mock_sell.call_args_list}
        assert sold_codes == {'512480', '588000'}

    def test_does_not_sell_when_above_floor(self):
        t = auto_trade.AutoTrader('ht_8268')
        t.auto_trade = True
        fake_positions = {
            'totalAssets': 1_200_000,  # 20% > 8%地板，不应该触发
            'availBalance': 50_000,
            'posList': [{'secCode': '512480', 'secName': '半导体ETF', 'availCount': 1000, 'price': 2.0}]
        }
        with patch.object(t, 'get_positions', return_value=fake_positions), \
             patch('auto_trade.get_current_period', return_value=self._fake_period()), \
             patch.object(t, 'sell') as mock_sell, \
             patch.object(t, 'get_quote', return_value=None), \
             patch('time.sleep'):
            t.check_and_trade()

        mock_sell.assert_not_called()

    def test_stable_account_has_no_floor_to_trigger(self):
        # ht_7493 没配profit_floor，哪怕跌到负收益也不应该走地板保护那条分支
        t = auto_trade.AutoTrader('ht_7493')
        t.auto_trade = True
        fake_positions = {
            'totalAssets': 800_000,  # -20%，如果错误地继承了地板逻辑会被清仓
            'availBalance': 50_000,
            'posList': [{'secCode': '512480', 'secName': '半导体ETF', 'availCount': 1000, 'price': 2.0}]
        }
        with patch.object(t, 'get_positions', return_value=fake_positions), \
             patch('auto_trade.get_current_period', return_value=self._fake_period()), \
             patch.object(t, 'sell') as mock_sell, \
             patch.object(t, 'get_quote', return_value=None), \
             patch('time.sleep'):
            t.check_and_trade()

        # 没配地板，止损判断留给逐票的-3%当日跌幅逻辑，不会因为地板保护整体清仓
        assert mock_sell.call_count == 0
