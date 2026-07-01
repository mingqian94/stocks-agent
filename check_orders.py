#!/usr/bin/env python3
"""
监控东方财富账户委托状态
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
                return True
        return False
    except:
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
                return True
            print(f'卖出失败: {d.get("message")}')
        return False
    except Exception as e:
        print(f'卖出异常: {e}')
        return False

def main():
    print('='*60)
    print(f'监控时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('='*60)

    # 1. 获取持仓
    pos_data = get_positions()
    if pos_data:
        total_assets = pos_data.get('totalAssets', 0) / 10000
        avail_balance = pos_data.get('availBalance', 0) / 10000
        pos_list = pos_data.get('posList', [])

        print(f'\n资产状态:')
        print(f'  总资产: {total_assets:.2f}万')
        print(f'  可用资金: {avail_balance:.2f}万')

        # 只显示有持仓的
        active_positions = [p for p in pos_list if p.get('count', 0) > 0]
        if active_positions:
            print(f'\n持仓明细:')
            for pos in active_positions:
                code = pos['secCode']
                name = pos.get('secName', '')
                count = pos['count']
                avail = pos.get('availCount', 0)
                profit_pct = pos.get('profitPct', 0)
                print(f'  {code} {name}: {count}股(可用{avail}) 盈亏{profit_pct:+.2f}%')
        else:
            print('\n✅ 持仓已清空')

    # 2. 获取委托
    orders = get_orders()
    if orders:
        # 按状态分类
        status_map = {
            0: '待成交',
            1: '部分成交',
            2: '已报',
            3: '已成交',
            4: '已撤销',
            5: '废单'
        }

        pending = [o for o in orders if o.get('entrustStatus') in [0, 1, 2]]
        filled = [o for o in orders if o.get('entrustStatus') == 3]
        cancelled = [o for o in orders if o.get('entrustStatus') == 4]

        print(f'\n委托统计:')
        print(f'  待成交: {len(pending)}笔')
        print(f'  已成交: {len(filled)}笔')
        print(f'  已撤销: {len(cancelled)}笔')

        if pending:
            print(f'\n待成交委托:')
            for o in pending:
                status = status_map.get(o.get('entrustStatus'), '未知')
                print(f'  {o["stockCode"]} {o["stockName"]}: {o["entrustType"]} {o["entrustCount"]}股 @ {o["entrustPrice"]} ({status})')

        # 显示最近的已成交委托
        if filled:
            print(f'\n最近已成交委托:')
            for o in filled[-5:]:
                print(f'  {o["stockCode"]} {o["stockName"]}: {o["entrustType"]} {o["entrustCount"]}股 @ {o["entrustPrice"]}')
    else:
        print('\n无委托记录')

    # 3. 如果有待成交的卖出委托，可以选择撤销
    if orders:
        pending_sells = [o for o in orders if o.get('entrustStatus') in [0, 1, 2] and o.get('entrustType') == '卖出']
        if pending_sells:
            print(f'\n⚠️ 有{len(pending_sells)}笔卖出委托待成交')
            print('这些委托锁定了持仓，导致可用数量为0')
            print('选项:')
            print('  1. 等待成交（可能需要时间）')
            print('  2. 撤销后重新以市价卖出')

if __name__ == '__main__':
    main()
