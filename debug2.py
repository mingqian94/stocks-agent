import requests, json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from keys_config import get_key

APIKEY = get_key('dongfang')
APIURL = 'https://mkapi2.dfcfs.com/finskillshub/api/claw/mockTrading'

r = requests.post(f'{APIURL}/positions',
    headers={'apikey': APIKEY, 'Content-Type': 'application/json'},
    data='{}', timeout=10)

data = r.json()
print(f"status_code: {r.status_code}")
print(f"code: {data.get('code')}")
print(f"message: {data.get('message')}")
print(f"success: {data.get('success')}")

d = data.get('data', {})
if not d:
    print("data为空，尝试用json字段")
    d = data.get('data') if isinstance(data.get('data'), dict) else {}

print(f"\ndata类型: {type(d)}")
if isinstance(d, dict) and d:
    print(f"data keys: {list(d.keys())}")
    print(f"totalAssets={d.get('totalAssets')}")
    print(f"availBalance={d.get('availBalance')}")
    pos_list = d.get('posList', [])
    print(f"持仓数: {len(pos_list)}")
    for p in pos_list:
        print(f"  字段: {list(p.keys())}")
        print(f"  {p.get('secName')}({p.get('secCode')}): {p.get('count')}股 price={p.get('price')} priceDec={p.get('priceDec')}")
        print(f"    dayProfitPct={p.get('dayProfitPct')} dayProfitAmt={p.get('dayProfitAmt')} profit={p.get('profit')}")
        print(f"    avgCost={p.get('avgCost')} costPrice={p.get('costPrice')}")
else:
    print(f"data空或非dict，完整响应: {json.dumps(data, ensure_ascii=False)[:500]}")
