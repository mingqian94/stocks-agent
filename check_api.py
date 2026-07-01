import requests, os, json

APIKEY = os.environ.get('MX_APIKEY', '')
APIURL = 'https://mkapi2.dfcfs.com/finskillshub/api/claw/mockTrading'

print(f"APIKEY: {APIKEY[:10]}...")
print()

r = requests.get(f'{APIURL}/positions', headers={'apikey': APIKEY}, timeout=10)
print(f"状态码: {r.status_code}")
print(f"原始响应前500字符:")
print(r.text[:500])

try:
    data = r.json()
    print()
    print(f"JSON结构 keys: {data.keys()}")
    if 'data' in data:
        d = data['data']
        print(f"data类型: {type(d)}")
        if isinstance(d, dict):
            print(f"data keys: {list(d.keys())[:20]}")
        else:
            print(f"data内容前300字: {str(d)[:300]}")
except:
    print("不是JSON")
