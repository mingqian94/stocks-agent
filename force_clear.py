#!/usr/bin/env python3
"""
撤销所有待成交委托并重新卖出
"""

import requests
import json
import time
import sys
import os
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from keys_config import get_key

APIKEY = get_key('dongfang')
APIURL = 'https://mkapi2.dfcfs.com/finskillshub/api/claw/mockTrading'

def get_positions():
    """获取持仓"""
    try:
        r = requests.post(f'{APIURL}/positions',
            headers={'apikey': APIKEY, 'Content-Type': 'application/json'},
            data='{}', timeout=10)
        if r.status_code == 200:
            return r.json().get('data', {})
    except Exception as e:
        print(f'获取持仓异常: {e}')
    return None

def cancel_all_orders():
    """撤销所有待成交委托"""
    try:
        # 东方财富API撤销所有委托
        r = requests.post(f'{APIURL}/cancelAll',
            headers={'apikey': APIKEY, 'Content-Type': 'application/json'},
            json={},
            timeout=10)
        if r.status_code == 200:
            d = r.json()
            print(f'撤销所有委托: {d}')
            return str(d.get('code')) == '200'
    except Exception as e:
        print(f'撤销异常: {e}')
    return False

def sell_stock(code, qty):
    """卖出"""
    try:
        r = requests.post(f'{APIURL}/trade',
            headers={'apikey': APIKEY, 'Content-Type': 'application/json'},
            json={'type': 'sell', 'stockCode': code, 'quantity': qty, 'useMarketPrice': True},
            timeout=10)
        if r.status_code == 200:
            d = r.json()
            if str(d.get('code')) == '200':
                print(f'✅ 卖出成功: {code} x{qty}')
                return True
            print(f'⚠️ 卖出失败: {d.get("message")}')
        return False
    except Exception as e:
        print(f'⚠️ 卖出异常: {e}')
        return False

def main():
    print('='*60)
    print(f'清仓脚本 - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('='*60)

    # 1. 尝试撤销所有委托
    print('\n1. 撤销所有待成交委托...')
    cancel_all_orders()
    time.sleep(2)

    # 2. 获取持仓
    print('\n2. 检查持仓...')
    pos_data = get_positions()
    if not pos_data:
        print('无法获取持仓')
        return

    pos_list = pos_data.get('posList', [])
    active_positions = [p for p in pos_list if p.get('count', 0) > 0]

    if not active_positions:
        print('✅ 持仓已清空')
        return

    print(f'仍有 {len(active_positions)} 只持仓:')
    for pos in active_positions:
        code = pos['secCode']
        name = pos.get('secName', '')
        count = pos['count']
        avail = pos.get('availCount', 0)
        print(f'  {code} {name}: {count}股(可用{avail})')

    # 3. 尝试卖出
    print('\n3. 尝试卖出...')
    for pos in active_positions:
        code = pos['secCode']
        count = pos['count']
        avail = pos.get('availCount', 0)

        if avail > 0:
            sell_stock(code, avail)
        else:
            print(f'  ⚠️ {code} 可用数量仍为0，等待委托成交')

        time.sleep(0.5)

    # 4. 最终状态
    time.sleep(2)
    pos_data = get_positions()
    if pos_data:
        print('\n最终状态:')
        print(f'  总资产: {pos_data.get("totalAssets", 0)/10000:.2f}万')
        print(f'  可用资金: {pos_data.get("availBalance", 0)/10000:.2f}万')
        active = [p for p in pos_data.get('posList', []) if p.get('count', 0) > 0]
        print(f'  持仓: {len(active)}只')

if __name__ == '__main__':
    main()
