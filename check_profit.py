import requests, os

APIKEY = os.environ.get('MX_APIKEY', '')
APIURL = 'https://mkapi2.dfcfs.com/finskillshub/api/claw/mockTrading'

r = requests.get(f'{APIURL}/positions', headers={'apikey': APIKEY}, timeout=10)
data = r.json()

pos = data.get('data', {}) if isinstance(data.get('data'), dict) else {}
total_assets = pos.get('totalAssets', 0) / 1000
avail_balance = pos.get('availBalance', 0) / 1000
initial = 1000000
total_profit = total_assets - initial
profit_pct = (total_profit / initial) * 100

print(f"总资产: {total_assets:.2f} 元")
print(f"可用资金: {avail_balance:.2f} 元")
print(f"累计收益: {total_profit:.2f} 元 ({profit_pct:.2f}%)")
print(f"初始资金: {initial} 元")
print()

day_profit_total = 0
for p in pos.get('posList', []):
    code = p.get('stockCode', '')
    name = p.get('stockName', '')
    day_pct = p.get('dayProfitPct', 0)
    day_profit = p.get('dayProfitAmt', 0) / 1000
    day_profit_total += day_profit
    print(f"{name}({code}): 今日涨跌 {day_pct:.2f}%, 今日盈亏 {day_profit:.2f}元")

day_profit_pct = (day_profit_total / initial) * 100
print()
print(f"今日总盈亏: {day_profit_total:.2f} 元 ({day_profit_pct:.2f}%)")

r2 = requests.get('https://push2.eastmoney.com/api/qt/stock/get?secid=1.510300&fields=f43,f170', timeout=5)
d = r2.json().get('data', {})
benchmark = (d.get('f170', 0) or 0) / 100.0
print(f"沪深300ETF今日: {benchmark:.2f}%")
print(f"跑赢基准: {day_profit_pct - benchmark:.2f}%")
