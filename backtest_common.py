"""
backtest_full.py / backtest_aggressive.py / backtest_conservative.py / backtest.py
共用的数据获取和指标计算函数。

backtest.py 用 akshare 拿ETF数据，stock_momentum_backtest.py 用 Backtrader + 合成数据，
这两个数据来源跟这里的 baostock 指数数据不是一回事，没有为了"统一"硬凑到一起。
"""
import pandas as pd
import baostock as bs


def get_index_data(code, name, start_date="2016-01-01", end_date="2026-06-07"):
    """用baostock获取指数历史数据。调用前需要自己 bs.login()（跟原来三份脚本的用法一致，
    这个模块不在import时偷偷登录，免得只用 ma_cross_signal 的 backtest.py 也被迫连一次baostock）"""
    try:
        rs = bs.query_history_k_data_plus(
            code,
            "date,open,high,low,close,volume",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="2"
        )

        if rs.error_code != "0":
            return None

        data_list = []
        while rs.error_code == "0" and rs.next():
            data_list.append(rs.get_row_data())

        if not data_list:
            return None

        df = pd.DataFrame(data_list, columns=rs.fields)
        df["date"] = pd.to_datetime(df["date"])

        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        return df.dropna().sort_values("date").reset_index(drop=True)

    except Exception:
        return None


def ma_cross_signal(df, short_period=5, long_period=20):
    """
    短期/长期均线金叉死叉信号：短均线上穿长均线买入持有，下穿卖出空仓。
    返回带 position/daily_return/strategy_return/cum_bh/cum_strat 列的 df。
    """
    df = df.copy()

    df["ma_short"] = df["close"].rolling(short_period).mean()
    df["ma_long"] = df["close"].rolling(long_period).mean()

    df["signal"] = 0
    df.loc[(df["ma_short"] > df["ma_long"]) & (df["ma_short"].shift(1) <= df["ma_long"].shift(1)), "signal"] = 1
    df.loc[(df["ma_short"] < df["ma_long"]) & (df["ma_short"].shift(1) >= df["ma_long"].shift(1)), "signal"] = -1

    df["position"] = df["signal"].replace(-1, 0).cumsum().clip(lower=0)
    df["position"] = (df["position"] > 0).astype(int)

    df["daily_return"] = df["close"].pct_change()
    df["strategy_return"] = df["position"].shift(1) * df["daily_return"]

    df["cum_bh"] = (1 + df["daily_return"]).cumprod()
    df["cum_strat"] = (1 + df["strategy_return"]).cumprod()

    return df


def calc_max_drawdown_pct(cum_series):
    """给一条累计收益序列（1.0起点），算最大回撤，返回百分数（负数）"""
    rolling_max = cum_series.cummax()
    drawdown = (cum_series - rolling_max) / rolling_max
    return drawdown.min() * 100


def calc_annualized_return_pct(cum_last_value, num_days, trading_days_per_year=252):
    """把累计收益终值（1.0起点）换算成年化收益率百分数"""
    years = num_days / trading_days_per_year
    if years <= 0:
        return 0.0
    return (cum_last_value ** (1 / years) - 1) * 100
