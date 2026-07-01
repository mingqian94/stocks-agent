#!/usr/bin/env python3
"""
东方财富账户：个股动量突破策略自动盯盘
策略逻辑：
1. 选股：当日涨幅3-12%、成交额>2000万、价格3-200元
2. 持仓：最多1只，单票仓位95%
3. 止损：-7% 止盈：+20%
4. 检查频率：每3分钟
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
LOG_FILE = '/Users/hetao/Documents/stocks/auto_trade.log'

# 策略参数
STOP_LOSS_PCT = -7.0       # 止损 -7%
TAKE_PROFIT_PCT = 20.0     # 止盈 +20%
MAX_POSITIONS = 1          # 最大持仓1只
MAX_POSITION_SIZE = 0.95   # 单只仓位95%
MIN_INCREASE = 3.0         # 最小涨幅3%
MAX_INCREASE = 12.0        # 最大涨幅12%
MIN_AMOUNT = 20000000      # 最小成交额2000万
MIN_PRICE = 3.0            # 最低价格3元
MAX_PRICE = 200.0          # 最高价格200元

# 个股池（可通过AKShare动态获取，这里先定义关注列表）
STOCK_POOL = []  # 动态获取

def log(msg):
    t = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{t}] [东方财富-个股动量] {msg}'
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

def get_stock_quote(code):
    """获取个股行情"""
    try:
        # 判断市场 0=深圳, 1=上海
        mkt = '0' if code.startswith(('0', '3')) else '1'
        r = requests.get(
            f'https://push2.eastmoney.com/api/qt/stock/get?secid={mkt}.{code}&fields=f43,f44,f45,f46,f47,f48,f60,f170',
            timeout=5
        )
        if r.status_code == 200:
            d = r.json().get('data', {})
            if d and d.get('f43'):
                # f43=最新价, f44=最高价, f45=最低价, f46=开盘价, f47=成交量, f48=成交额, f60=昨收, f170=涨跌幅
                current = d['f43'] / 100.0 if d['f43'] else 0
                high = d.get('f44', 0) / 100.0 if d.get('f44') else 0
                low = d.get('f45', 0) / 100.0 if d.get('f45') else 0
                open_price = d.get('f46', 0) / 100.0 if d.get('f46') else 0
                volume = d.get('f47', 0)  # 手
                amount = d.get('f48', 0)  # 元
                yesterday = d.get('f60', 0) / 100.0 if d.get('f60') else 0
                pct = d.get('f170', 0) / 100.0 if d.get('f170') else 0
                
                if current > 0 and yesterday > 0:
                    return {
                        'code': code,
                        'price': current,
                        'high': high,
                        'low': low,
                        'open': open_price,
                        'volume': volume,
                        'amount': amount,
                        'yesterday': yesterday,
                        'pct': pct
                    }
    except Exception as e:
        pass
    return None

def get_top_stocks():
    """获取涨幅榜前列个股"""
    try:
        # 使用东方财富涨幅榜API
        url = 'https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=50&po=1&np=1&fltt=2&invt=2&fid=f12&fs=m:0+t:6,m:0+t:13,m:1+t:2,m:1+t:23&fields=f12,f14,f2,f3,f5,f6,f7,f8,f9,f10,f13,f15,f16,f17,f18,f20,f21,f22,f23,f24,f25,f26,f27,f28,f29,f30,f31,f32,f33,f34,f35,f36,f37,f38,f39,f40,f41,f42,f43,f44,f45,f46,f47,f48,f49,f50,f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65,f66,f67,f68,f69,f70,f71,f72,f73,f74,f75,f76,f77,f78,f79,f80,f81,f82,f83,f84,f85,f86,f87,f88,f89,f90,f91,f92,f93,f94,f95,f96,f97,f98,f99,f100'
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            stocks = []
            if data.get('data') and data['data'].get('diff'):
                for item in data['data']['diff']:
                    code = item.get('f12', '')
                    name = item.get('f14', '')
                    price = item.get('f2', 0) / 100.0 if item.get('f2') else 0
                    pct = item.get('f3', 0) / 100.0 if item.get('f3') else 0
                    amount = item.get('f6', 0)  # 成交额
                    volume = item.get('f5', 0)  # 成交量
                    
                    # 筛选条件
                    if (MIN_INCREASE <= pct <= MAX_INCREASE and
                        price >= MIN_PRICE and price <= MAX_PRICE and
                        amount >= MIN_AMOUNT):
                        stocks.append({
                            'code': code,
                            'name': name,
                            'price': price,
                            'pct': pct,
                            'amount': amount,
                            'volume': volume
                        })
            
            # 按涨幅排序
            stocks.sort(key=lambda x: x['pct'], reverse=True)
            return stocks[:10]  # 返回Top10
    except Exception as e:
        log(f'获取涨幅榜异常: {e}')
    return []

def buy(code, qty):
    try:
        r = requests.post(f'{APIURL}/trade',
            headers={'apikey': APIKEY, 'Content-Type': 'application/json'},
            json={'type': 'buy', 'stockCode': code, 'quantity': qty, 'useMarketPrice': True},
            timeout=10)
        if r.status_code == 200:
            d = r.json()
            if str(d.get('code')) == '200':
                log(f'  买入成功: {code} x{qty} 委托号: {d.get("data",{}).get("orderID","?")}')
                return True
            log(f'  买入失败: {code} {d.get("message","未知")}')
        else:
            log(f'  买入请求失败({r.status_code}): {code}')
    except Exception as e:
        log(f'  买入异常 {code}: {e}')
    return False

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

def calc_qty(cash, price):
    if price <= 0 or cash <= 0:
        return 0
    qty = int(cash / price / 100) * 100
    return qty

def check_and_trade():
    log('========= 个股动量策略盯盘启动 =========')
    
    pos = get_positions()
    if not pos:
        log('无法获取持仓，跳过本轮')
        return
    
    total_assets = pos.get('totalAssets', 0) / 1000
    avail_balance = pos.get('availBalance', 0) / 1000
    log(f'总资产: {total_assets:.0f}元 | 可用: {avail_balance:.0f}元')
    
    positions = pos.get('posList', [])
    log(f'持仓数量: {len(positions)}')
    
    # 检查现有持仓
    for p in positions:
        code = p['secCode']
        name = p['secName']
        count = p['count']
        avail_count = p['availCount']
        price = p['price'] / (10**p['priceDec'])
        day_pct = p['dayProfitPct']
        profit_pct = p['profitPct']
        cost = p['costPrice'] / (10**p['costPriceDec'])
        
        log(f'  持仓: {name}({code}) {count}股 成本{cost:.2f} 现价{price:.2f} 盈亏{profit_pct:.2f}%')
        
        # 止损检查
        if profit_pct <= STOP_LOSS_PCT:
            log(f'  🚨 止损触发！{name} 盈亏{profit_pct:.2f}% <= {STOP_LOSS_PCT}%')
            if avail_count > 0:
                sell_qty = (avail_count // 100) * 100
                if sell_qty > 0:
                    log(f'  → 卖出全部 {sell_qty}股')
                    sell(code, sell_qty)
            return
        
        # 止盈检查
        if profit_pct >= TAKE_PROFIT_PCT:
            log(f'  🎯 止盈触发！{name} 盈亏{profit_pct:.2f}% >= {TAKE_PROFIT_PCT}%')
            if avail_count > 0:
                sell_qty = (avail_count // 100) * 100
                if sell_qty > 0:
                    log(f'  → 卖出全部 {sell_qty}股')
                    sell(code, sell_qty)
            return
    
    # 如果有持仓，不再买入新股票
    if len(positions) >= MAX_POSITIONS:
        log(f'  已持有{len(positions)}只股票，达到上限{MAX_POSITIONS}只，不再买入')
        log('========= 本轮结束 =========\n')
        return
    
    # 选股
    log('\n--- 选股 ---')
    top_stocks = get_top_stocks()
    if not top_stocks:
        log('  无符合条件的个股')
        log('========= 本轮结束 =========\n')
        return
    
    log(f'  符合条件的个股: {len(top_stocks)}只')
    for i, s in enumerate(top_stocks[:5]):
        log(f'  {i+1}. {s["name"]}({s["code"]}) 涨幅{s["pct"]:.2f}% 价格{s["price"]:.2f} 成交额{s["amount"]/10000:.0f}万')
    
    # 买入Top1
    if top_stocks and avail_balance > 50000:
        target = top_stocks[0]
        target_code = target['code']
        target_name = target['name']
        target_price = target['price']
        
        # 计算买入数量（95%仓位）
        target_cash = total_assets * MAX_POSITION_SIZE
        if target_cash > avail_balance:
            target_cash = avail_balance
        
        qty = calc_qty(target_cash, target_price)
        if qty >= 100:
            log(f'\n  ➕ 买入 {target_name}({target_code}) {qty}股 @ {target_price:.2f} (约{qty*target_price:.0f}元)')
            buy(target_code, qty)
        else:
            log(f'  计算买入数量不足100股，跳过')
    else:
        log(f'  可用资金{avail_balance:.0f}元不足或没有符合条件的股票')
    
    log('========= 本轮结束 =========\n')

if __name__ == '__main__':
    log(f'🚀 个股动量策略盯盘启动 | PID:{os.getpid()}')
    log(f'   规则: 涨幅{MIN_INCREASE}%-{MAX_INCREASE}% | 止损{STOP_LOSS_PCT}% | 止盈{TAKE_PROFIT_PCT}% | 每3分钟检查')
    
    while True:
        now = datetime.datetime.now()
        hour = now.hour
        minute = now.minute
        weekday = now.weekday()
        
        is_trading = False
        if weekday >= 5:
            pass
        elif hour == 9 and minute >= 30:
            is_trading = True
        elif hour == 10 or hour == 11:
            is_trading = True
        elif hour == 13 or hour == 14:
            is_trading = True
        elif hour == 15 and minute == 0:
            is_trading = True
        
        if is_trading:
            try:
                check_and_trade()
            except Exception as e:
                log(f'异常: {e}')
        else:
            weekd_cn = ['一','二','三','四','五','六','日'][weekday]
            log(f'非交易时间 {now.strftime("%Y-%m-%d %H:%M:%S")} (周{weekd_cn})，等待中...')
        
        time.sleep(180)
