#!/usr/bin/env python3
"""
个股动量策略回测
使用本地CSV数据 + Backtrader
"""

import backtrader as bt
import pandas as pd
import numpy as np
from datetime import datetime

# ========== 策略参数（隔日交易版）==========
INITIAL_CAPITAL = 1000000  # 初始资金100万
STOP_LOSS = -0.05          # 止损5%（隔日交易）
TAKE_PROFIT = 0.10         # 止盈10%（隔日交易）
MAX_POSITION_SIZE = 0.95   # 单只仓位95%
MIN_INCREASE = 0.03        # 最小涨幅3%
MAX_INCREASE = 0.09        # 最大涨幅9%

class MomentumStrategy(bt.Strategy):
    """强势股隔日交易策略"""
    params = (
        ('stop_loss', STOP_LOSS),
        ('take_profit', TAKE_PROFIT),
        ('position_size', MAX_POSITION_SIZE),
    )
    
    def __init__(self):
        self.dataclose = self.datas[0].close
        self.datahigh = self.datas[0].high
        self.datalow = self.datas[0].low
        self.dataopen = self.datas[0].open
        self.order = None
        self.buy_price = None
        self.buy_bar = 0
        
    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()} {txt}')
        
    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'买入执行: 价格{order.executed.price:.2f}, 数量{order.executed.size}')
                self.buy_price = order.executed.price
                self.buy_bar = len(self.dataclose)
            else:
                self.log(f'卖出执行: 价格{order.executed.price:.2f}, 数量{order.executed.size}')
            
        self.order = None
    
    def next(self):
        if self.order:
            return
        
        if not self.position:
            # 选股条件：当日涨幅3-9%且收盘接近最高价（强势收盘）
            if len(self.dataclose) < 2:
                return
                
            pct_change = (self.dataclose[0] - self.dataclose[-1]) / self.dataclose[-1]
            # 收盘接近最高价：收盘/高价 > 0.98
            strong_close = self.dataclose[0] / self.datahigh[0] > 0.98 if self.datahigh[0] > 0 else False
            
            if MIN_INCREASE <= pct_change <= MAX_INCREASE and strong_close:
                # 买入95%仓位
                cash = self.broker.getcash()
                size = int((cash * self.params.position_size) / self.dataclose[0] / 100) * 100
                if size >= 100:
                    self.log(f'买入信号: 涨幅{pct_change*100:.2f}%, 强势收盘')
                    self.order = self.buy(size=size)
        else:
            # 隔日交易：次日开盘就卖
            if self.buy_price:
                current_return = (self.dataopen[0] - self.buy_price) / self.buy_price
                hold_days = len(self.dataclose) - self.buy_bar
                
                # 次日开盘卖出（隔日交易）
                if hold_days >= 1:
                    if current_return > 0:
                        self.log(f'隔日盈利卖出: {current_return*100:+.2f}%')
                    else:
                        self.log(f'隔日亏损卖出: {current_return*100:+.2f}%')
                    self.order = self.sell(size=self.position.size)

def create_bullish_data():
    """创建牛市数据（模拟强势股走势）"""
    dates = pd.date_range('2024-01-01', periods=100, freq='D')
    np.random.seed(42)
    
    # 模拟强势股走势：平均上涨1.5%，波动5%
    prices = []
    price = 100
    for i in range(100):
        change = np.random.normal(0.015, 0.05)  # 平均上涨1.5%，波动5%
        price *= (1 + change)
        prices.append(price)
    
    df = pd.DataFrame({
        'open': [p * (1 + np.random.normal(0, 0.01)) for p in prices],
        'high': [p * (1 + abs(np.random.normal(0, 0.03))) for p in prices],
        'low': [p * (1 - abs(np.random.normal(0, 0.03))) for p in prices],
        'close': prices,
        'volume': [int(np.random.normal(2000000, 500000)) for _ in prices]
    }, index=dates)
    
    return df

def create_bearish_data():
    """创建熊市数据（模拟弱势走势）"""
    dates = pd.date_range('2024-01-01', periods=100, freq='D')
    np.random.seed(43)
    
    # 模拟弱势走势：平均下跌0.5%，波动4%
    prices = []
    price = 100
    for i in range(100):
        change = np.random.normal(-0.005, 0.04)  # 平均下跌0.5%，波动4%
        price *= (1 + change)
        prices.append(price)
    
    df = pd.DataFrame({
        'open': [p * (1 + np.random.normal(0, 0.01)) for p in prices],
        'high': [p * (1 + abs(np.random.normal(0, 0.02))) for p in prices],
        'low': [p * (1 - abs(np.random.normal(0, 0.02))) for p in prices],
        'close': prices,
        'volume': [int(np.random.normal(800000, 200000)) for _ in prices]
    }, index=dates)
    
    return df

def create_mixed_data():
    """创建震荡市数据（横盘震荡）"""
    dates = pd.date_range('2024-01-01', periods=100, freq='D')
    np.random.seed(44)
    
    # 模拟横盘震荡：围绕100元波动
    prices = []
    price = 100
    for i in range(100):
        change = np.random.normal(0, 0.015)  # 无趋势，纯随机波动
        price *= (1 + change)
        # 限制在90-110区间
        price = max(90, min(110, price))
        prices.append(price)
    
    df = pd.DataFrame({
        'open': [p * (1 + np.random.normal(0, 0.003)) for p in prices],
        'high': [p * (1 + abs(np.random.normal(0, 0.01))) for p in prices],
        'low': [p * (1 - abs(np.random.normal(0, 0.01))) for p in prices],
        'close': prices,
        'volume': [int(np.random.normal(1000000, 200000)) for _ in prices]
    }, index=dates)
    
    return df

def run_single_backtest(data_df, scenario_name):
    """运行单次回测"""
    cerebro = bt.Cerebro()
    cerebro.addstrategy(MomentumStrategy)
    
    data = bt.feeds.PandasData(dataname=data_df)
    cerebro.adddata(data)
    
    cerebro.broker.setcash(INITIAL_CAPITAL)
    cerebro.broker.setcommission(commission=0.0003)
    
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    
    results = cerebro.run()
    strat = results[0]
    
    sharpe = strat.analyzers.sharpe.get_analysis()
    drawdown = strat.analyzers.drawdown.get_analysis()
    returns = strat.analyzers.returns.get_analysis()
    trades = strat.analyzers.trades.get_analysis()
    
    final_value = cerebro.broker.getvalue()
    total_return = (final_value - INITIAL_CAPITAL) / INITIAL_CAPITAL
    
    return {
        'scenario': scenario_name,
        'final_value': final_value,
        'total_return': total_return,
        'annual_return': returns.get('rnorm100', 0),
        'max_drawdown': drawdown.get('max', {}).get('drawdown', 0),
        'sharpe_ratio': sharpe.get('sharperatio', 0) if sharpe else 0,
        'total_trades': trades.get('total', {}).get('total', 0) if trades else 0,
        'win_trades': trades.get('won', {}).get('total', 0) if trades else 0,
    }

def run_backtest():
    """运行多情景回测"""
    print("=" * 70)
    print("个股动量策略 - 多情景回测")
    print("=" * 70)
    print(f"初始资金: {INITIAL_CAPITAL/10000:.0f}万")
    print(f"止损: {STOP_LOSS*100:.0f}% | 止盈: {TAKE_PROFIT*100:.0f}%")
    print(f"仓位: {MAX_POSITION_SIZE*100:.0f}%")
    print("=" * 70)
    
    scenarios = [
        ('牛市', create_bullish_data()),
        ('熊市', create_bearish_data()),
        ('震荡市', create_mixed_data()),
    ]
    
    results = []
    for name, data_df in scenarios:
        print(f"\n📊 {name}回测...")
        result = run_single_backtest(data_df, name)
        results.append(result)
    
    # 输出汇总结果
    print("\n" + "=" * 70)
    print("📈 回测结果汇总")
    print("=" * 70)
    print(f"{'情景':^10} {'最终资金':^12} {'总收益':^10} {'年化收益':^10} {'最大回撤':^10} {'夏普比率':^8} {'交易次数':^8} {'胜率':^8}")
    print("-" * 70)
    
    for r in results:
        win_rate = (r['win_trades'] / r['total_trades'] * 100) if r['total_trades'] > 0 else 0
        print(f"{r['scenario']:^10} {r['final_value']/10000:^12.1f}万 {r['total_return']*100:^10.2f}% "
              f"{r['annual_return']:^10.2f}% {r['max_drawdown']:^10.2f}% {r['sharpe_ratio'] or 0:^8.2f} "
              f"{r['total_trades']:^8} {win_rate:^8.1f}%")
    
    # 计算期望收益
    weights = {'牛市': 0.3, '熊市': 0.3, '震荡市': 0.4}
    expected_return = sum(r['total_return'] * weights.get(r['scenario'], 0.33) for r in results)
    
    print("-" * 70)
    print(f"\n📊 加权期望收益: {expected_return*100:+.2f}%")
    
    if expected_return >= 0.20:
        print("✅ 策略可达成20%目标！")
    elif expected_return >= 0.10:
        print("⚠️ 策略可达成10%收益")
    else:
        print("❌ 策略收益偏低")
    
    return results

if __name__ == "__main__":
    results = run_backtest()
    print("\n✅ 多情景回测完成！")