"""
backtest_common.py 的均线信号 + 指标计算单测。用固定的合成价格序列，
不碰 baostock/akshare 网络请求（get_index_data 需要真实网络，不在这里测）。
"""
import pandas as pd
import pytest
from backtest_common import ma_cross_signal, calc_max_drawdown_pct, calc_annualized_return_pct


def make_price_df(prices):
    return pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods=len(prices)),
        'close': prices,
    })


class TestMaCrossSignal:
    def test_uptrend_after_warmup_produces_positive_cumulative_return(self):
        # 前20天横盘让长均线先有数据，之后拉升制造一次真正的金叉，金叉后应该一直持仓吃到涨幅。
        # 注意：如果从第1天就单调上涨，长均线在前20天是NaN，永远等不到一次"从下方穿到上方"
        # 的信号（这是策略本身固有的边界行为，不是这次抽取共用模块引入的）。
        prices = [100.0] * 20 + [100 + i for i in range(1, 40)]
        df = ma_cross_signal(make_price_df(prices), short_period=5, long_period=20)
        assert df['cum_strat'].iloc[-1] > 1.0
        assert df['cum_bh'].iloc[-1] > 1.0

    def test_flat_price_produces_no_return(self):
        prices = [100.0] * 60
        df = ma_cross_signal(make_price_df(prices), short_period=5, long_period=20)
        assert df['cum_strat'].iloc[-1] == pytest.approx(1.0)

    def test_position_is_binary(self):
        prices = [100 + (i % 10) for i in range(60)]
        df = ma_cross_signal(make_price_df(prices), short_period=5, long_period=20)
        assert set(df['position'].dropna().unique()).issubset({0, 1})

    def test_short_ma_crossing_above_long_ma_triggers_buy_signal(self):
        # 前20天横盘，之后急涨，制造一次明确的金叉
        prices = [100.0] * 20 + [100 + i * 2 for i in range(1, 20)]
        df = ma_cross_signal(make_price_df(prices), short_period=5, long_period=20)
        assert (df['signal'] == 1).any()


class TestMaxDrawdown:
    def test_no_drawdown_when_monotonically_increasing(self):
        cum = pd.Series([1.0, 1.1, 1.2, 1.3])
        assert calc_max_drawdown_pct(cum) == pytest.approx(0.0)

    def test_drawdown_from_peak(self):
        # 涨到1.5后跌到1.2，回撤 = (1.2-1.5)/1.5 = -20%
        cum = pd.Series([1.0, 1.5, 1.2])
        assert calc_max_drawdown_pct(cum) == pytest.approx(-20.0)

    def test_recovering_after_drawdown_does_not_hide_it(self):
        cum = pd.Series([1.0, 1.5, 1.2, 1.6])
        assert calc_max_drawdown_pct(cum) == pytest.approx(-20.0)


class TestAnnualizedReturn:
    def test_one_year_return_equals_total_return(self):
        # 正好252个交易日翻倍 -> 年化就是100%
        assert calc_annualized_return_pct(cum_last_value=2.0, num_days=252) == pytest.approx(100.0)

    def test_zero_days_returns_zero(self):
        assert calc_annualized_return_pct(cum_last_value=2.0, num_days=0) == 0.0

    def test_half_year_double_annualizes_above_total_return(self):
        # 126个交易日（半年）翻倍，年化应该远高于100%
        result = calc_annualized_return_pct(cum_last_value=2.0, num_days=126)
        assert result > 100.0
