#!/usr/bin/env python3
"""
清仓东方财富账户的所有ETF持仓
"""

import requests
import json
import time
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from keys_config import get_key

# 东方财富账户配置
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

def get_orders():
    """获取委托"""
    try:
        r = requests.get(f'{APIURL}/entrust',
            headers={'apikey': APIKEY},
            timeout=10)
        if r.status_code == 200:
            return r.json().get('data', [])
    except Exception as e:
        print(f'获取委托异常: {e}')
    return []

def cancel_order(order_id):
    """撤销委托"""
    try:
        r = requests.post(f'{APIURL}/cancel',
            headers={'apikey': APIKEY, 'Content-Type': 'application/json'},
            json={'entrustId': order_id},
            timeout=10)
        if r.status_code == 200:
            d = r.json()
            if str(d.get('code')) == '200':
                print(f'  ✅ 撤销成功: {order_id}')
                return True
            print(f'  ⚠️ 撤销失败: {d.get("message")}')
        else:
            print(f'  ⚠️ 撤销请求失败({r.status_code})')
    except Exception as e:
        print(f'  ⚠️ 撤销异常: {e}')
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
                print(f'  ✅ 卖出成功: {code} x{qty}')
                return True
            print(f'  ⚠️ 卖出失败: {d.get("message")}')
        else:
            print(f'  ⚠️ 卖出请求失败({r.status_code})')
    except Exception as e:
        print(f'  ⚠️ 卖出异常: {e}')
    return False

def main():
    print('='*60)
    print('清仓东方财富账户ETF持仓')
    print('='*60)

    # 1. 获取持仓
    pos_data = get_positions()
    if not pos_data:
        print('无法获取持仓')
        return

    total_assets = pos_data.get('totalAssets', 0) / 10000
    avail_balance = pos_data.get('availBalance', 0) / 10000
    pos_list = pos_data.get('posList', [])

    print(f'总资产: {total_assets:.2f}万')
    print(f'可用资金: {avail_balance:.2f}万')
    print(f'持仓数量: {len(pos_list)}')

    if not pos_list:
        print('持仓已清空')
        return

    # 2. 显示持仓
    print('\n持仓明细:')
    for pos in pos_list:
        code = pos['secCode']
        name = pos.get('secName', '')
        count = pos['count']
        avail = pos.get('availCount', 0)
        print(f'  {code} {name}: 持仓{count}股, 可用{avail}股')

    # 3. 检查待成交委托
    orders = get_orders()
    pending_orders = [o for o in orders if o.get('entrustStatus') in [0, 1, 2]]

    if pending_orders:
        print(f'\n待成交委托: {len(pending_orders)}笔')
        for o in pending_orders:
            print(f'  {o["stockCode"]} {o["stockName"]}: {o["entrustType"]} {o["entrustCount"]}股 @ {o["entrustPrice"]}')

        # 撤销所有待成交委托
        print('\n撤销待成交委托...')
        for o in pending_orders:
            cancel_order(o['entrustId'])
            time.sleep(0.5)

        # 等待撤销生效
        print('等待3秒...')
        time.sleep(3)

        # 重新获取持仓
        pos_data = get_positions()
        if pos_data:
            pos_list = pos_data.get('posList', [])

    # 4. 卖出所有持仓
    print('\n卖出所有持仓...')
    for pos in pos_list:
        if pos.get('count', 0) > 0:
            code = pos['secCode']
            count = pos['count']
            avail = pos.get('availCount', 0)

            if avail > 0:
                sell_stock(code, avail)
            else:
                print(f'  ⚠️ {code} 可用数量为0，无法卖出')

            time.sleep(0.5)

    # 5. 最终状态
    time.sleep(2)
    pos_data = get_positions()
    if pos_data:
        print('\n最终状态:')
        print(f'  总资产: {pos_data.get("totalAssets", 0)/10000:.2f}万')
        print(f'  可用资金: {pos_data.get("availBalance", 0)/10000:.2f}万')
        print(f'  持仓: {len(pos_data.get("posList", []))}只')

if __name__ == '__main__':
    main()
