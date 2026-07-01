import backtrader as bt
import datetime
import pandas as pd

# 创建测试数据
dates = pd.date_range('2020-01-01', periods=100, freq='D')
prices = pd.DataFrame({
    'open': [100 + i * 0.5 for i in range(100)],
    'high': [102 + i * 0.5 for i in range(100)],
    'low': [98 + i * 0.5 for i in range(100)],
    'close': [101 + i * 0.5 for i in range(100)],
    'volume': [1000000 for _ in range(100)]
}, index=dates)

class TestStrategy(bt.Strategy):
    def __init__(self):
        self.dataclose = self.datas[0].close
        
    def next(self):
        if not self.position:
            if self.dataclose[0] < self.dataclose[-1]:
                self.buy()
        else:
            if self.dataclose[0] > self.dataclose[-1]:
                self.sell()

# 创建Cerebro引擎
cerebro = bt.Cerebro()
cerebro.addstrategy(TestStrategy)

# 使用PandasData
data = bt.feeds.PandasData(dataname=prices)
cerebro.adddata(data)

# 设置初始资金
cerebro.broker.setcash(100000.0)

print(f'初始资金: {cerebro.broker.getvalue():.2f}')
cerebro.run()
print(f'最终资金: {cerebro.broker.getvalue():.2f}')
print('Backtrader 本地数据测试成功！')