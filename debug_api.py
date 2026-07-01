import requests, os, json

APIKEY = os.environ.get('MX_APIKEY', '')
APIURL = 'https://mkapi2.dfcfs.com/finskillshub/api/claw/mockTrading'

r = requests.post(f'{APIURL}/positions',
    headers={'apikey': APIKEY, 'Content-Type': 'application/json'},
    data='{}', timeout=10)

print(f"状态码: {r.status_code}")
data = r.json()
print(f"返回代码: {data.get('code')}")
print(f"返回消息: {data.get('message')}")
print(f"success: {data.get('success')}")

d = data.get('data', {})
print(f"data类型: {type(d)}")

if isinstance(d, dict):
    print(f"\ndata keys: {list(d.keys())}")
    print(f"\ntotalAssets: {d.get('totalAssets')} (元/1000 = {d.get('totalAssets', 0)/1000:.2f}元")
    print(f"availBalance: {d.get('availBalance')}")
    print(f"totalAssets/1000: {d.get('totalAssets', 0)/1000:.2f}元")
    
    pos_list = d.get('posList', [])
    print(f"\n持仓数: {len(pos_list)}")
    for p in pos_list:
        print(f"  字段: {list(p.keys())}")
        print(f"  {p.get('secName', p.get('stockName'))}({p.get('secCode', p.get('stockCode'))}")
        print(f"    count={p.get('count')} price={p.get('price')} priceDec={p.get('priceDec')}")
        print(f"    dayProfitPct={p.get('dayProfitPct')} dayProfitAmt={p.get('dayProfitAmt')}")
        print(f"    profit={p.get('profit')} posPct={p.get('posPct')}")
        print(f"    avgCost={p.get('avgCost')} costPrice={p.get('costPrice')}")
else:
    print(f"不是dict: {str(d)[:300]}")
