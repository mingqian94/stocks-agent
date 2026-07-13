#!/usr/bin/env python3
"""
东方财富账户：清仓ETF + 切换个股动量策略
执行步骤：
1. 清仓所有ETF持仓
2. 切换策略为个股动量突破
3. 启动新的自动盯盘
"""

import json
import time
import requests
import datetime
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from keys_config import get_key

APIKEY = get_key('dongfang')
APIURL = 'https://mkapi2.dfcfs.com/finskillshub/api/claw/mockTrading'
LOG_FILE = '/Users/hetao/stocks_agent/auto_trade.log'

def log(msg):
    t = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{t}] [东方财富清仓] {msg}'
    print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

def get_positions():
    try:
        r = requests.post(f'{APIURL}/positions',
            headers={'apikey': APIKEY, 'Content-Type': 'application/json'},
            data='{}', timeout=10)
        if r.status_code == 200:
            return r.json().get('data', {})
    except Exception as e:
        log(f'  获取持仓异常: {e}')
    return None

def sell(code, qty):
    try:
        r = requests.post(f'{APIURL}/trade',
            headers={'apikey': APIKEY, 'Content-Type': 'application/json'},
            json={'type': 'sell', 'stockCode': code, 'quantity': qty, 'useMarketPrice': True},
            timeout=10)
        if r.status_code == 200:
            d = r.json()
            if str(d.get('code')) == '200':
                log(f'  卖出成功: {code} x{qty} 委托号: {d.get("data",{}).get("orderID","?")}')
                return True
            log(f'  卖出失败: {code} {d.get("message","未知")}')
        else:
            log(f'  卖出请求失败({r.status_code}): {code}')
    except Exception as e:
        log(f'  卖出异常 {code}: {e}')
    return False

def cancel_all():
    try:
        r = requests.post(f'{APIURL}/cancel',
            headers={'apikey': APIKEY, 'Content-Type': 'application/json'},
            json={'type': 'all'}, timeout=10)
        result = r.json()
        log(f'撤单结果: {result.get("message", "未知")}')
        return True
    except Exception as e:
        log(f'撤单异常: {e}')
    return False

def clear_all_positions():
    """清仓所有持仓"""
    log('=== 开始清仓东方财富账户 ===')
    
    # 先撤单
    cancel_all()
    time.sleep(3)
    
    # 获取持仓
    pos = get_positions()
    if not pos:
        log('无法获取持仓，跳过')
        return False
    
    positions = pos.get('posList', [])
    if not positions:
        log('当前无持仓，无需清仓')
        return True
    
    log(f'持仓数量: {len(positions)}')
    
    # 卖出所有持仓
    all_cleared = True
    for p in positions:
        code = p['secCode']
        name = p['secName']
        count = p['count']
        avail_count = p['availCount']
        
        if avail_count <= 0:
            log(f'  {name}({code}): 可用数量为0，跳过（可能T+1限制）')
            all_cleared = False
            continue
        
        # 卖出可用数量
        sell_qty = (avail_count // 100) * 100
        if sell_qty > 0:
            log(f'  卖出 {name}({code}) {sell_qty}股...')
            if sell(code, sell_qty):
                time.sleep(2)
            else:
                all_cleared = False
        else:
            log(f'  {name}({code}): 可卖数量不足100股，跳过')
    
    # 再次查询持仓
    time.sleep(5)
    pos2 = get_positions()
    if pos2:
        remaining = pos2.get('posList', [])
        if remaining:
            log(f'清仓后仍有 {len(remaining)} 只持仓:')
            for p in remaining:
                log(f'  {p["secName"]}: {p["count"]}股 (可用{p["availCount"]})')
            return False
        else:
            log('清仓完成！当前无持仓')
            return True
    
    return all_cleared

def switch_to_stock_strategy():
    """切换为个股动量策略"""
    log('=== 切换为个股动量突破策略 ===')
    
    # 更新账户配置
    accounts_file = '/Users/hetao/stocks_agent/accounts.py'
    with open(accounts_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 更新东方财富账户策略
    old_strategy = "'strategy': 'etf_momentum'"
    new_strategy = "'strategy': 'stock_momentum'"
    if old_strategy in content:
        content = content.replace(old_strategy, new_strategy)
        with open(accounts_file, 'w', encoding='utf-8') as f:
            f.write(content)
        log('已更新 accounts.py: ETF动量轮动 -> 个股动量突破')
    else:
        log('accounts.py 中未找到 etf_momentum 配置')
    
    # 更新competitions.json
    competitions_file = '/Users/hetao/stocks_agent/competitions.json'
    with open(competitions_file, 'r', encoding='utf-8') as f:
        competitions = json.load(f)
    
    if 'dongfang' in competitions:
        competitions['dongfang']['strategy'] = '个股动量突破'
        competitions['dongfang']['notes'] = '已切换为个股动量突破策略，目标收益10%'
        with open(competitions_file, 'w', encoding='utf-8') as f:
            json.dump(competitions, f, ensure_ascii=False, indent=2)
        log('已更新 competitions.json: 策略切换为个股动量突破')
    
    log('策略切换完成')

if __name__ == '__main__':
    log('🚀 东方财富账户：清仓ETF + 切换个股策略')
    
    # 清仓
    cleared = clear_all_positions()
    
    if cleared:
        # 切换策略
        switch_to_stock_strategy()
        log('✅ 全部完成：清仓 + 策略切换')
    else:
        log('⚠️ 清仓未完成（部分持仓T+1限制），请明天再次执行')
        log('策略暂不切换，等待清仓完成后再切换')
