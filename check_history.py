#!/usr/bin/env python3
"""
查询交易记录
"""

import requests
import json
import sys
import os
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from keys_config import get_key

APIKEY = get_key('dongfang')
APIURL = 'https://mkapi2.dfcfs.com/finskillshub/api/claw/mockTrading'

def get_trade_history():
    """获取交易记录"""
    try:
        # 尝试不同的接口
        urls = [
            f'{APIURL}/history',
            f'{APIURL}/trades',
            f'{APIURL}/records',
            f'{APIURL}/deal',
        ]

        for url in urls:
            try:
                r = requests.get(url, headers={'apikey': APIKEY}, timeout=10)
                print(f'{url}: status={r.status_code}')
                if r.status_code == 200:
                    print(r.text[:500])
                print()
            except Exception as e:
                print(f'{url}: {e}\n')
    except Exception as e:
        print(f'异常: {e}')

def get_position_detail():
    """获取持仓详情"""
    try:
        r = requests.post(f'{APIURL}/positions',
            headers={'apikey': APIKEY, 'Content-Type': 'application/json'},
            data='{}', timeout=10)
        if r.status_code == 200:
            data = r.json()
            print('持仓详情:')
            print(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f'异常: {e}')

if __name__ == '__main__':
    print('='*60)
    print('查询交易记录')
    print('='*60)
    get_trade_history()
    print('\n' + '='*60)
    print('持仓详情')
    print('='*60)
    get_position_detail()
