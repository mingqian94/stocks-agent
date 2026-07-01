import sys
import time
sys.path.insert(0, '/Users/hetao/Documents/stocks')
from auto_trade import *

print('=== 执行动量轮动调仓操作 ===')
print('当前时间:', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
print()

pos = get_positions()
if not pos:
    print('❌ 无法获取持仓')
    sys.exit(1)

total_assets = pos.get('totalAssets', 0) / 1000
avail_balance = pos.get('availBalance', 0) / 1000
print(f'总资产: {total_assets:.0f}元 | 可用: {avail_balance:.0f}元')

pos_map = {}
for p in pos.get('posList', []):
    code = p['secCode']
    pos_map[code] = {
        'price': p['price'] / (10**p['priceDec']),
        'count': p['count']
    }

print()
print('--- 买入强势标的 ---')
top_codes = ['512480', '588000']
per_target = avail_balance / len(top_codes) * 0.9
print(f'每只目标买入: {per_target:.0f}元')

for code in top_codes:
    if code in pos_map:
        price = pos_map[code]['price']
        qty = calc_qty(per_target, price)
        if qty >= 100:
            name = ETFS[code]
            print(f'买入 {name}({code}): {qty}股 @{price:.3f}')
            buy(code, qty)
            time.sleep(3)

print()
print('--- 调仓完成 ---')

pos2 = get_positions()
print()
print('📊 调仓后持仓')
total_assets2 = pos2.get('totalAssets', 0) / 1000
avail_balance2 = pos2.get('availBalance', 0) / 1000
print(f'总资产: {total_assets2:.0f}元 | 可用: {avail_balance2:.0f}元')
print()
for p in pos2.get('posList', []):
    code = p['secCode']
    name = p['secName']
    count = p['count']
    price = p['price'] / (10**p['priceDec'])
    profit = p['profit'] / 1000
    pos_pct = p.get('posPct', 0)
    print(f'  {name}({code}): {count}股 现价{price:.3f} 盈亏{profit:.0f}元 占比{pos_pct:.1f}%')