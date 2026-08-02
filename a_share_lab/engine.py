"""Daily A-share portfolio backtester with explicit execution assumptions.

This is a research engine, not a broker emulator.  Signals are calculated at
the close and orders are submitted at the next trading day's open.  Daily OHLC
data is then used to model fixed stops/targets for positions that are already
T+1 sellable.  Conservative one-price limit and suspension checks prevent the
engine from assuming fills that were unlikely to be available.
"""

from __future__ import annotations

from bisect import bisect_right
from collections import Counter
from dataclasses import dataclass
import math
from typing import Literal

import numpy as np
import pandas as pd


EntryModel = Literal[
    "daily_breakout", "daily_rank", "momentum_5d", "risk_adjusted_20d", "reversal_10d",
    "external_score",
]
ExitModel = Literal["fixed_only", "ma20", "ma60", "momentum_5d"]
MarketGate = Literal["none", "ma20", "ma60"]


@dataclass(frozen=True)
class BacktestConfig:
    initial_capital: float = 1_000_000.0
    commission_rate: float = 0.0003
    minimum_commission: float = 5.0
    commission_includes_regulatory_fees: bool = True
    regulatory_fee_rate: float = 0.00002
    exchange_handling_fee_rate: float = 0.0000341
    transfer_fee_rate: float = 0.00001
    transfer_fee_rate_before_2022_04_29: float = 0.00002
    stamp_tax_before_2023_08_28: float = 0.001
    stamp_tax_after_2023_08_28: float = 0.0005
    slippage_bps: float = 5.0
    lot_size: int = 100
    investable_fraction: float = 0.98
    maximum_participation_rate: float = 0.0025


@dataclass(frozen=True)
class StrategySpec:
    name: str
    entry_model: EntryModel
    max_positions: int
    stop_loss: float
    take_profit: float | None
    max_holding_days: int | None
    exit_model: ExitModel = "fixed_only"
    minimum_amount: float = 200_000_000.0
    minimum_history: int = 65
    minimum_daily_return: float = 0.03
    maximum_daily_return: float = 0.08
    require_previous_day_up: bool = True
    minimum_return_5d: float = 0.05
    maximum_return_5d: float = 0.20
    minimum_return_20d: float = 0.08
    maximum_return_20d: float = 0.40
    minimum_return_10d: float = -0.30
    maximum_return_10d: float = -0.08
    minimum_external_score: float = 0.0
    exclude_limit_touch: bool = False
    market_gate: MarketGate = "none"


@dataclass
class Position:
    code: str
    shares: int
    entry_price: float
    entry_date: pd.Timestamp
    entry_fee: float
    entry_gap: float
    last_price: float
    holding_days: int = 0


class MembershipResolver:
    def __init__(self, memberships: pd.DataFrame):
        snapshots = memberships.copy()
        snapshots["snapshot_date"] = pd.to_datetime(snapshots["snapshot_date"])
        grouped = snapshots.groupby("snapshot_date")["code"].apply(lambda values: frozenset(values))
        self.dates = list(grouped.index.sort_values())
        self.members = {date: grouped.loc[date] for date in self.dates}

    def on(self, date: pd.Timestamp) -> frozenset[str]:
        index = bisect_right(self.dates, pd.Timestamp(date)) - 1
        return self.members[self.dates[index]] if index >= 0 else frozenset()


def prepare_features(prices: pd.DataFrame) -> pd.DataFrame:
    """Create lag-safe close-of-day features for all supported strategies."""
    frame = prices.copy().sort_values(["code", "date"])
    frame["date"] = pd.to_datetime(frame["date"])
    numeric = [
        "open", "high", "low", "close", "preclose", "volume", "amount", "turn",
        "tradestatus", "pctChg", "isST",
    ]
    for column in numeric:
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    grouped = frame.groupby("code", group_keys=False)
    raw_return = np.where(
        frame["preclose"] > 0, frame["close"] / frame["preclose"] - 1.0, np.nan
    )
    # pctChg uses the exchange's point-in-time reference price and therefore
    # avoids treating an ex-right price gap as an investable loss.  Raw OHLC
    # remains untouched for execution and cash accounting.
    frame["daily_return"] = frame["pctChg"] / 100.0
    frame["daily_return"] = frame["daily_return"].where(frame["daily_return"].notna(), raw_return)
    frame["previous_day_return"] = grouped["daily_return"].shift(1)
    frame["signal_price"] = (1.0 + frame["daily_return"].fillna(0.0)).groupby(frame["code"]).cumprod()
    growth_board = frame["code"].str.startswith(("sh.688", "sz.300", "sz.301"))
    frame["limit_pct"] = np.where(growth_board, 0.20, 0.10)
    frame["limit_reference"] = np.where(
        (1.0 + frame["daily_return"] > 0) & frame["daily_return"].notna(),
        frame["close"] / (1.0 + frame["daily_return"]),
        frame["preclose"],
    )
    frame["upper_limit"] = frame["limit_reference"] * (1.0 + frame["limit_pct"])
    frame["touched_upper_limit"] = frame["high"] >= frame["upper_limit"] - 0.011
    frame["one_price_upper_limit"] = (
        frame["touched_upper_limit"]
        & (frame["low"] >= frame["upper_limit"] - 0.011)
    )
    signal_grouped = frame.groupby("code", group_keys=False)["signal_price"]
    for window in (5, 10, 20, 60):
        frame[f"return_{window}d"] = signal_grouped.pct_change(window, fill_method=None)
    frame["ma20"] = signal_grouped.transform(lambda values: values.rolling(20).mean())
    frame["ma60"] = signal_grouped.transform(lambda values: values.rolling(60).mean())
    frame["volatility20"] = grouped["daily_return"].transform(lambda values: values.rolling(20).std())
    frame["amount20"] = grouped["amount"].transform(lambda values: values.rolling(20).mean())
    frame["amount20_lag1"] = grouped["amount"].transform(
        lambda values: values.rolling(20).mean().shift(1)
    )
    frame["history_days"] = grouped.cumcount() + 1
    return frame.replace([np.inf, -np.inf], np.nan)


def select_candidates(day: pd.DataFrame, spec: StrategySpec) -> pd.DataFrame:
    """Rank eligible candidates using only features known at this close."""
    eligible = day[
        (day["tradestatus"] == 1)
        & (day["volume"] > 0)
        & (day["isST"] == 0)
        & (day["history_days"] >= spec.minimum_history)
        & (day["amount"] >= spec.minimum_amount)
    ].copy()
    if eligible.empty:
        return eligible.assign(score=pd.Series(dtype=float))

    if spec.entry_model == "daily_breakout":
        mask = eligible["daily_return"].between(
            spec.minimum_daily_return, spec.maximum_daily_return, inclusive="both"
        )
        if spec.require_previous_day_up:
            mask &= eligible["previous_day_return"] > 0
        eligible = eligible[mask]
        eligible["score"] = eligible["daily_return"]
    elif spec.entry_model == "daily_rank":
        mask = eligible["daily_return"].between(0.0, eligible["limit_pct"] + 0.001, inclusive="both")
        if spec.exclude_limit_touch:
            mask &= ~eligible["touched_upper_limit"]
        eligible = eligible[mask]
        eligible["score"] = eligible["daily_return"]
    elif spec.entry_model == "momentum_5d":
        mask = (
            eligible["daily_return"].between(-0.02, spec.maximum_daily_return, inclusive="both")
            & eligible["return_5d"].between(
                spec.minimum_return_5d, spec.maximum_return_5d, inclusive="both"
            )
            & (eligible["signal_price"] > eligible["ma20"])
        )
        eligible = eligible[mask]
        eligible["score"] = eligible["return_5d"]
    elif spec.entry_model == "risk_adjusted_20d":
        mask = (
            eligible["daily_return"].between(-0.03, 0.05, inclusive="both")
            & eligible["return_20d"].between(
                spec.minimum_return_20d, spec.maximum_return_20d, inclusive="both"
            )
            & (eligible["signal_price"] > eligible["ma20"])
            & (eligible["ma20"] > eligible["ma60"])
            & (eligible["amount20"] >= spec.minimum_amount)
            & (eligible["volatility20"] > 0)
        )
        eligible = eligible[mask]
        eligible["score"] = eligible["return_20d"] / eligible["volatility20"]
    elif spec.entry_model == "reversal_10d":
        mask = (
            eligible["daily_return"].between(-0.03, 0.03, inclusive="both")
            & eligible["return_10d"].between(
                spec.minimum_return_10d, spec.maximum_return_10d, inclusive="both"
            )
            & (eligible["signal_price"] < eligible["ma20"])
            & (eligible["amount20"] >= spec.minimum_amount)
        )
        eligible = eligible[mask]
        eligible["score"] = -eligible["return_10d"]
    elif spec.entry_model == "external_score":
        if "external_score" not in eligible:
            return eligible.iloc[0:0].assign(score=pd.Series(dtype=float))
        mask = eligible["external_score"].notna() & (
            eligible["external_score"] >= spec.minimum_external_score
        )
        eligible = eligible[mask]
        eligible["score"] = eligible["external_score"]
    else:
        raise ValueError(f"Unsupported entry model: {spec.entry_model}")
    return eligible.sort_values(["score", "amount"], ascending=[False, False])


def _price_limit(code: str) -> float:
    # Research universe excludes ST names and Beijing listings.  Since the
    # sample starts after the ChiNext registration reform, 300/301 and STAR
    # names use the broad 20% band; main-board names use 10%.
    if code.startswith("sh.688") or code.startswith("sz.300") or code.startswith("sz.301"):
        return 0.20
    return 0.10


def _lot_size(code: str, config: BacktestConfig) -> int:
    return 200 if code.startswith("sh.688") else config.lot_size


def _quantity_step(code: str, config: BacktestConfig) -> int:
    # STAR orders have a 200-share minimum but may increase one share at a time.
    return 1 if code.startswith("sh.688") else config.lot_size


def _tick_price(price: float, side: str) -> float:
    """Round modeled fills adversely to the A-share RMB 0.01 tick."""
    cents = float(price) * 100.0
    rounded = math.ceil(cents - 1e-9) if side == "buy" else math.floor(cents + 1e-9)
    return max(rounded / 100.0, 0.01)


def _limit_reference(row: pd.Series) -> float:
    daily_return = row.get("daily_return", np.nan)
    close = row.get("close", np.nan)
    if pd.notna(daily_return) and pd.notna(close) and 1.0 + float(daily_return) > 0:
        return float(close) / (1.0 + float(daily_return))
    return float(row["preclose"])


def _buy_blocked(row: pd.Series) -> bool:
    reference = _limit_reference(row)
    if row["tradestatus"] != 1 or row["volume"] <= 0 or reference <= 0:
        return True
    upper = reference * (1.0 + _price_limit(str(row["code"])))
    return row["low"] >= upper - 0.011


def _sell_blocked(row: pd.Series) -> bool:
    reference = _limit_reference(row)
    if row["tradestatus"] != 1 or row["volume"] <= 0 or reference <= 0:
        return True
    lower = reference * (1.0 - _price_limit(str(row["code"])))
    return row["high"] <= lower + 0.011


def _stamp_tax(date: pd.Timestamp, config: BacktestConfig) -> float:
    if pd.Timestamp(date) < pd.Timestamp("2023-08-28"):
        return config.stamp_tax_before_2023_08_28
    return config.stamp_tax_after_2023_08_28


def _transfer_fee(date: pd.Timestamp, config: BacktestConfig) -> float:
    if pd.Timestamp(date) < pd.Timestamp("2022-04-29"):
        return config.transfer_fee_rate_before_2022_04_29
    return config.transfer_fee_rate


def _transaction_fee(amount: float, side: str, date: pd.Timestamp, config: BacktestConfig) -> float:
    commission = max(config.minimum_commission, amount * config.commission_rate)
    fee = commission + amount * _transfer_fee(date, config)
    if not config.commission_includes_regulatory_fees:
        fee += amount * (config.regulatory_fee_rate + config.exchange_handling_fee_rate)
    if side == "sell":
        fee += amount * _stamp_tax(date, config)
    return fee


def _max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    return float((equity / equity.cummax() - 1.0).min())


def _metrics(
    equity_curve: pd.DataFrame,
    trades: pd.DataFrame,
    initial_capital: float,
    turnover_notional: float,
) -> dict[str, float | int]:
    if equity_curve.empty:
        return {}
    equity = equity_curve.set_index("date")["equity"]
    returns = equity.pct_change().dropna()
    years = max(len(returns) / 252.0, 1.0 / 252.0)
    total_return = equity.iloc[-1] / initial_capital - 1.0
    annual_return = (equity.iloc[-1] / initial_capital) ** (1.0 / years) - 1.0
    volatility = returns.std(ddof=0) * np.sqrt(252) if len(returns) else 0.0
    sharpe = returns.mean() / returns.std(ddof=0) * np.sqrt(252) if returns.std(ddof=0) > 0 else 0.0
    downside = returns[returns < 0].std(ddof=0)
    sortino = returns.mean() / downside * np.sqrt(252) if downside and downside > 0 else 0.0
    drawdown = _max_drawdown(equity)
    winners = trades[trades["net_pnl"] > 0] if not trades.empty else trades
    losers = trades[trades["net_pnl"] < 0] if not trades.empty else trades
    gross_profit = winners["net_pnl"].sum() if not winners.empty else 0.0
    gross_loss = -losers["net_pnl"].sum() if not losers.empty else 0.0
    return {
        "total_return": float(total_return),
        "annual_return": float(annual_return),
        "annual_volatility": float(volatility),
        "max_drawdown": drawdown,
        "sharpe": float(sharpe),
        "sortino": float(sortino),
        "calmar": float(annual_return / abs(drawdown)) if drawdown < 0 else 0.0,
        "trades": int(len(trades)),
        "win_rate": float(len(winners) / len(trades)) if len(trades) else 0.0,
        "profit_factor": float(gross_profit / gross_loss) if gross_loss > 0 else 0.0,
        "average_trade_return": float(trades["net_return"].mean()) if len(trades) else 0.0,
        "average_holding_days": float(trades["holding_days"].mean()) if len(trades) else 0.0,
        "average_entry_gap": float(trades["entry_gap"].mean()) if len(trades) else 0.0,
        "turnover": float(turnover_notional / equity.mean()),
        "average_exposure": float(equity_curve["exposure"].mean()),
        "final_equity": float(equity.iloc[-1]),
    }


def run_backtest(
    prices: pd.DataFrame,
    memberships: pd.DataFrame,
    benchmark: pd.DataFrame,
    spec: StrategySpec,
    start_date: str,
    end_date: str,
    config: BacktestConfig | None = None,
) -> dict:
    """Run one strategy specification and return metrics plus audit tables."""
    config = config or BacktestConfig()
    required_features = {
        "signal_price", "return_5d", "return_10d", "return_20d", "ma20", "ma60", "history_days"
    }
    features = prices.copy() if required_features.issubset(prices.columns) else prepare_features(prices)
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    features = features[(features["date"] <= end)].copy()
    trade_dates = sorted(features.loc[features["date"].between(start, end), "date"].unique())
    by_date = {pd.Timestamp(date): day.set_index("code", drop=False) for date, day in features.groupby("date")}
    resolver = MembershipResolver(memberships)
    benchmark_features = benchmark.copy().sort_values("date")
    benchmark_features["ma20"] = benchmark_features["close"].rolling(20).mean()
    benchmark_features["ma60"] = benchmark_features["close"].rolling(60).mean()
    benchmark_by_date = benchmark_features.set_index("date")

    cash = config.initial_capital
    positions: dict[str, Position] = {}
    pending_buys: list[str] = []
    pending_exits: dict[str, str] = {}
    trade_records: list[dict] = []
    equity_records: list[dict] = []
    equal_weight_returns: list[dict] = []
    turnover_notional = 0.0
    execution_audit: Counter[str] = Counter()
    slippage = config.slippage_bps / 10_000.0

    def mark_price(code: str, day_rows: pd.DataFrame, field: str = "close") -> float:
        if code in day_rows.index and pd.notna(day_rows.at[code, field]):
            return float(day_rows.at[code, field])
        return positions[code].last_price

    def portfolio_value(day_rows: pd.DataFrame, field: str) -> float:
        return cash + sum(position.shares * mark_price(code, day_rows, field) for code, position in positions.items())

    def sell(code: str, raw_price: float, date: pd.Timestamp, reason: str) -> bool:
        nonlocal cash, turnover_notional
        position = positions[code]
        price = _tick_price(float(raw_price) * (1.0 - slippage), "sell")
        amount = position.shares * price
        fee = _transaction_fee(amount, "sell", date, config)
        cash += amount - fee
        cost_basis = position.shares * position.entry_price + position.entry_fee
        net_pnl = amount - fee - cost_basis
        trade_records.append(
            {
                "code": code,
                "entry_date": position.entry_date,
                "exit_date": date,
                "entry_price": position.entry_price,
                "exit_price": price,
                "shares": position.shares,
                "holding_days": position.holding_days,
                "reason": reason,
                "net_pnl": net_pnl,
                "net_return": net_pnl / cost_basis if cost_basis > 0 else 0.0,
                "entry_gap": position.entry_gap,
            }
        )
        turnover_notional += amount
        del positions[code]
        pending_exits.pop(code, None)
        return True

    for date in trade_dates:
        date = pd.Timestamp(date)
        day_rows = by_date[date]
        membership_today = resolver.on(date)
        member_codes = membership_today.intersection(day_rows.index)
        if member_codes:
            member_rows = day_rows.loc[list(member_codes)]
            valid_returns = member_rows.loc[
                (member_rows["tradestatus"] == 1) & member_rows["daily_return"].notna(),
                "daily_return",
            ]
            equal_weight_returns.append(
                {"date": date, "return": float(valid_returns.mean()) if len(valid_returns) else 0.0}
            )

        # Decisions made at the prior close execute at today's open.  Sells go
        # first so replacement buys use released cash and target total equity.
        for code, reason in list(pending_exits.items()):
            if code not in positions:
                continue
            execution_audit["sell_attempts"] += 1
            if code not in day_rows.index:
                execution_audit["sell_missing_bar"] += 1
                continue
            row = day_rows.loc[code]
            if not _sell_blocked(row):
                sell(code, float(row["open"]), date, reason)
            elif row["tradestatus"] != 1 or row["volume"] <= 0:
                execution_audit["sell_blocked_suspension"] += 1
            else:
                execution_audit["sell_blocked_limit"] += 1

        equity_open = portfolio_value(day_rows, "open")
        target_value = equity_open * config.investable_fraction / spec.max_positions
        for code in list(pending_buys):
            execution_audit["buy_attempts"] += 1
            if code in positions:
                continue
            if len(positions) >= spec.max_positions:
                execution_audit["buy_blocked_capacity"] += 1
                continue
            if code not in day_rows.index:
                execution_audit["buy_missing_bar"] += 1
                continue
            row = day_rows.loc[code]
            if _buy_blocked(row) or row["isST"] == 1:
                if row["tradestatus"] != 1 or row["volume"] <= 0:
                    execution_audit["buy_blocked_suspension"] += 1
                elif row["isST"] == 1:
                    execution_audit["buy_blocked_st"] += 1
                else:
                    execution_audit["buy_blocked_limit"] += 1
                continue
            price = _tick_price(float(row["open"]) * (1.0 + slippage), "buy")
            capacity = (
                float(row["amount20_lag1"]) * config.maximum_participation_rate
                if pd.notna(row.get("amount20_lag1", np.nan))
                else target_value
            )
            if capacity < target_value:
                execution_audit["buy_capacity_limited"] += 1
            budget = min(
                target_value,
                cash / (1.0 + config.commission_rate + _transfer_fee(date, config)),
                capacity,
            )
            lot_size = _lot_size(code, config)
            quantity_step = _quantity_step(code, config)
            shares = int(budget / price / quantity_step) * quantity_step
            if shares < lot_size:
                continue
            amount = shares * price
            fee = _transaction_fee(amount, "buy", date, config)
            if amount + fee > cash:
                shares -= quantity_step
                amount = shares * price
                fee = _transaction_fee(amount, "buy", date, config) if shares > 0 else 0.0
            if shares < lot_size or amount + fee > cash:
                execution_audit["buy_blocked_cash"] += 1
                continue
            cash -= amount + fee
            turnover_notional += amount
            positions[code] = Position(
                code=code,
                shares=shares,
                entry_price=price,
                entry_date=date,
                entry_fee=fee,
                entry_gap=float(row["open"] / row["preclose"] - 1.0) if row["preclose"] > 0 else 0.0,
                last_price=float(row["close"]),
            )
        pending_buys = []

        # Intraday fixed exits apply only after T+1.  If both stop and target
        # appear inside one daily bar, choose the stop first (conservative path).
        for code, position in list(positions.items()):
            if code not in day_rows.index:
                continue
            row = day_rows.loc[code]
            position.last_price = float(row["close"])
            stop_price = position.entry_price * (1.0 + spec.stop_loss)
            target_price = (
                position.entry_price * (1.0 + spec.take_profit)
                if spec.take_profit is not None
                else None
            )
            if position.entry_date >= date:
                if float(row["low"]) <= stop_price:
                    execution_audit["t1_stop_triggered"] += 1
                if target_price is not None and float(row["high"]) >= target_price:
                    execution_audit["t1_target_triggered"] += 1
                continue
            if _sell_blocked(row):
                if float(row["low"]) <= stop_price:
                    execution_audit["intraday_stop_blocked"] += 1
                continue
            exit_price = None
            reason = ""
            if float(row["open"]) <= stop_price:
                exit_price, reason = float(row["open"]), "stop_gap"
            elif target_price is not None and float(row["open"]) >= target_price:
                exit_price, reason = float(row["open"]), "target_gap"
            elif float(row["low"]) <= stop_price:
                exit_price, reason = stop_price, "stop"
            elif target_price is not None and float(row["high"]) >= target_price:
                exit_price, reason = target_price, "target"
            if exit_price is not None:
                sell(code, exit_price, date, reason)

        # Mark the portfolio after all fills.
        for code, position in positions.items():
            if code in day_rows.index and pd.notna(day_rows.at[code, "close"]):
                position.last_price = float(day_rows.at[code, "close"])
                if int(day_rows.at[code, "tradestatus"]) == 1:
                    position.holding_days += 1
        equity = portfolio_value(day_rows, "close")
        gross = sum(position.shares * position.last_price for position in positions.values())
        equity_records.append(
            {
                "date": date,
                "equity": equity,
                "cash": cash,
                "positions": len(positions),
                "exposure": gross / equity if equity > 0 else 0.0,
            }
        )

        # Close-of-day exits to be attempted next open.
        membership = membership_today
        for code, position in positions.items():
            reason = None
            row = day_rows.loc[code] if code in day_rows.index else None
            if code not in membership:
                reason = "left_universe"
            elif spec.max_holding_days is not None and position.holding_days >= spec.max_holding_days:
                reason = "time_exit"
            elif row is not None and spec.exit_model == "ma20" and row["signal_price"] < row["ma20"]:
                reason = "ma20_exit"
            elif row is not None and spec.exit_model == "ma60" and row["signal_price"] < row["ma60"]:
                reason = "ma60_exit"
            elif row is not None and spec.exit_model == "momentum_5d" and row["return_5d"] <= 0:
                reason = "momentum_exit"
            if reason:
                pending_exits[code] = reason

        # Build tomorrow's orders from today's observable close.  Scheduled
        # exits free slots, but a blocked sell tomorrow will safely prevent an
        # over-capacity buy because execution rechecks len(positions).
        active_after_exits = len(positions) - len(pending_exits)
        slots = max(spec.max_positions - active_after_exits, 0)
        market_allows_entry = True
        if spec.market_gate != "none":
            if date not in benchmark_by_date.index:
                market_allows_entry = False
            else:
                market_row = benchmark_by_date.loc[date]
                market_allows_entry = bool(
                    pd.notna(market_row[spec.market_gate])
                    and market_row["close"] > market_row[spec.market_gate]
                )
        if slots and market_allows_entry:
            eligible_codes = membership.intersection(day_rows.index)
            candidates = select_candidates(day_rows.loc[list(eligible_codes)], spec)
            excluded = set(positions) | set(pending_buys)
            pending_buys = [code for code in candidates["code"] if code not in excluded][:slots]
        elif slots and not market_allows_entry:
            execution_audit["market_gate_blocked_days"] += 1

    # Terminal performance is mark-to-market.  Forcing a final-close sale would
    # invent liquidity, add a non-strategy trade and can violate T+1 for a name
    # bought on the last day.  Keep the open-position table for audit instead.
    execution_audit["open_positions_at_end"] = len(positions)
    open_positions = pd.DataFrame(
        [
            {
                "code": position.code,
                "shares": position.shares,
                "entry_date": position.entry_date,
                "entry_price": position.entry_price,
                "last_price": position.last_price,
                "holding_days": position.holding_days,
                "unrealized_return": position.last_price / position.entry_price - 1.0,
            }
            for position in positions.values()
        ]
    )

    equity_curve = pd.DataFrame(equity_records)
    trades = pd.DataFrame(trade_records)
    metrics = _metrics(equity_curve, trades, config.initial_capital, turnover_notional)

    equal_weight_curve = pd.DataFrame(equal_weight_returns)
    if not equal_weight_curve.empty:
        equal_weight_curve["equity"] = (
            (1.0 + equal_weight_curve["return"]).cumprod() * config.initial_capital
        )
        equal_weight_metrics = {
            "total_return": float(equal_weight_curve["equity"].iloc[-1] / config.initial_capital - 1.0),
            "max_drawdown": _max_drawdown(equal_weight_curve["equity"]),
        }
    else:
        equal_weight_metrics = {}

    benchmark_slice = benchmark[benchmark["date"].between(start, end)].copy().sort_values("date")
    if not benchmark_slice.empty:
        benchmark_slice["equity"] = (
            benchmark_slice["close"] / benchmark_slice["close"].iloc[0] * config.initial_capital
        )
        benchmark_metrics = {
            "total_return": float(benchmark_slice["equity"].iloc[-1] / config.initial_capital - 1.0),
            "max_drawdown": _max_drawdown(benchmark_slice["equity"]),
        }
    else:
        benchmark_metrics = {}
    return {
        "strategy": spec.name,
        "start_date": start_date,
        "end_date": end_date,
        "metrics": metrics,
        "benchmark_metrics": benchmark_metrics,
        "equal_weight_metrics": equal_weight_metrics,
        "execution_audit": dict(execution_audit),
        "equity_curve": equity_curve,
        "trades": trades,
        "open_positions": open_positions,
    }
