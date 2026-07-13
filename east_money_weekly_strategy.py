import json
import time
import requests
import datetime
import sys
import os
from datetime import timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from keys_config import get_key

APIKEY = get_key('dongfang')
APIURL = 'https://mkapi2.dfcfs.com/finskillshub/api/claw/mockTrading'

# 期数配置
CURRENT_PERIOD = 12
PERIOD_START_DATE = '2026-06-15'
PERIOD_END_DATE = '2026-06-18'
INITIAL_CAPITAL = 1000000

# 期数历史记录
PERIOD_HISTORY = {
    11: {'start': '2026-06-08', 'end': '2026-06-12', 'initial': 1000000, 'final': 1037218, 'profit': 37218, 'profit_pct': 3.72},
    12: {'start': PERIOD_START_DATE, 'end': PERIOD_END_DATE, 'initial': INITIAL_CAPITAL, 'final': 0, 'profit': 0, 'profit_pct': 0}
}

ETFS = {
    '510050': '上证50ETF',
    '510300': '沪深300ETF',
    '510500': '中证500ETF',
    '512100': '中证1000ETF',
    '588000': '科创50ETF',
    '512480': '半导体ETF',
    '512760': '芯片ETF',
    '512880': '证券ETF',
    '515180': '银行ETF',
    '512010': '医药ETF',
    '515030': '新能源车ETF',
    '515790': '光伏ETF',
    '512690': '酒ETF',
    '512400': '有色金属ETF',
    '512660': '军工ETF',
    '513050': '中概互联ETF'
}

def log(msg):
    t = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{t}] [东方财富杯] 周策略 {msg}'
    print(line)
    with open('/Users/hetao/stocks_agent/east_money_weekly.log', 'a', encoding='utf-8') as f:
        f.write(line + '\n')

def get_positions():
    try:
        r = requests.post(f'{APIURL}/positions',
            headers={'apikey': APIKEY, 'Content-Type': 'application/json'},
            data='{}', timeout=10)
        if r.status_code == 200:
            return r.json().get('data', {})
    except Exception as e:
        log(f'获取持仓异常: {e}')
    return None

def parse_price(f43):
    if f43 is None or f43 <= 0:
        return 0.0
    if f43 >= 100000:
        return f43 / 1000.0
    elif f43 >= 10000:
        return f43 / 100.0
    elif f43 >= 1000:
        return f43 / 1000.0
    elif f43 >= 100:
        return f43 / 100.0
    else:
        return f43 / 100.0

def get_quote(code):
    try:
        r = requests.get(f'https://push2.eastmoney.com/api/qt/stock/get?secid=1.{code}&fields=f43,f60,f170', timeout=5)
        if r.status_code == 200:
            d = r.json().get('data', {})
            if d and d.get('f43'):
                current = parse_price(d['f43'])
                yesterday = parse_price(d.get('f60', 0))
                pct = d.get('f170', 0) / 100.0 if d.get('f170') else 0
                if current > 0 and 0.1 < current < 1000 and abs(pct) < 30:
                    return {'code': code, 'price': current, 'pct': pct}
    except Exception as e:
        pass
    return None

def buy(code, qty):
    try:
        r = requests.post(f'{APIURL}/trade',
            headers={'apikey': APIKEY, 'Content-Type': 'application/json'},
            json={'type': 'buy', 'stockCode': code, 'quantity': qty, 'useMarketPrice': True},
            timeout=10)
        if r.status_code == 200:
            d = r.json()
            if str(d.get('code')) == '200':
                log(f'✅ 买入成功: {ETFS.get(code,code)} {code} x{qty}')
                return True
            log(f'⚠️ 买入失败: {code} {d.get("message","未知")}')
    except Exception as e:
        log(f'⚠️ 买入异常 {code}: {e}')
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
                log(f'✅ 卖出成功: {ETFS.get(code,code)} {code} x{qty}')
                return True
            log(f'⚠️ 卖出失败: {code} {d.get("message","未知")}')
    except Exception as e:
        log(f'⚠️ 卖出异常 {code}: {e}')
    return False

def calc_qty(cash, price):
    if price <= 0 or cash <= 0:
        return 0
    qty = int(cash / price / 100) * 100
    return qty

def is_monday_open():
    """判断是否为周一开盘时间"""
    now = datetime.datetime.now()
    if now.weekday() != 0:
        return False
    return (now.hour == 9 and now.minute >= 30) or (now.hour > 9 and now.hour < 11)

def weekly_rebalance():
    """每周一开盘调仓"""
    log('========= 周度调仓开始 =========')
    
    pos = get_positions()
    if not pos:
        log('❌ 无法获取持仓')
        return
    
    total_assets = pos.get('totalAssets', 0) / 1000
    avail_balance = pos.get('availBalance', 0) / 1000
    log(f'当前总资产: {total_assets:.0f}元 | 可用: {avail_balance:.0f}元')
    
    positions = pos.get('posList', [])
    log(f'当前持仓数量: {len(positions)}')
    
    current_pos = {p['secCode']: p for p in positions}
    
    log('\n--- 收集行情数据 ---')
    quotes = {}
    for code in ETFS:
        q = get_quote(code)
        if q:
            quotes[code] = q
            log(f'  {ETFS[code]}({code}) {q["pct"]:+.2f}%')
    
    if not quotes:
        log('❌ 无法获取行情数据')
        return
    
    log('\n--- 周度策略: 动量Top3配置 ---')
    sorted_etfs = sorted(quotes.items(), key=lambda x: x[1]['pct'], reverse=True)
    top3 = [(code, data) for code, data in sorted_etfs[:3] if data['pct'] > 0]
    
    if top3:
        top_names = [f"{ETFS.get(c, c)}({c}) {d['pct']:+.2f}%" for c, d in top3]
        log(f'  本周强势标的: {", ".join(top_names)}')
        
        log('\n--- 清仓非强势标的 ---')
        for code, p in current_pos.items():
            if code not in [c for c, d in top3]:
                avail_count = p['availCount']
                if avail_count > 0:
                    log(f'  卖出非强势: {ETFS.get(code, code)} {avail_count}股')
                    sell(code, avail_count)
                    time.sleep(2)
        
        time.sleep(3)
        pos = get_positions()
        if pos:
            avail_balance = pos.get('availBalance', 0) / 1000
            log(f'\n--- 建仓强势标的 ---')
            log(f'  可用资金: {avail_balance:.0f}元')
            
            if avail_balance >= 10000:
                per_target = avail_balance / len(top3) * 0.95
                log(f'  每只计划: {per_target:.0f}元')
                
                for code, data in top3:
                    price = data['price']
                    qty = calc_qty(per_target, price)
                    if qty >= 100:
                        log(f'  买入 {ETFS.get(code, code)} {qty}股 @{price:.3f}')
                        buy(code, qty)
                        time.sleep(3)
            else:
                log('  可用资金不足1万元，跳过建仓')
    else:
        log('  无正收益标的，保持观望')
    
    log('========= 周度调仓结束 =========')

def weekly_summary():
    """周复盘"""
    log('========= 周度复盘开始 =========')
    
    log(f'📅 第{CURRENT_PERIOD}期: {PERIOD_START_DATE} ~ {PERIOD_END_DATE}')
    
    pos = get_positions()
    if pos:
        total_assets = pos.get('totalAssets', 0) / 1000
        profit = total_assets - INITIAL_CAPITAL
        profit_pct = (profit / INITIAL_CAPITAL) * 100
        
        log(f'💰 期末总资产: {total_assets:.0f}元')
        log(f'📈 本期收益: {profit:+.0f}元 ({profit_pct:+.2f}%)')
        
        positions = pos.get('posList', [])
        log(f'📦 当前持仓: {len(positions)}只')
        
        for p in positions:
            code = p['secCode']
            name = p['secName']
            count = p['count']
            price = p['price'] / (10**p['priceDec'])
            day_pct = p['dayProfitPct']
            profit = p['profit'] / 1000
            log(f'  {name}({code}): {count}股 现价{price:.3f} 今日{day_pct:+.2f}% 盈亏{profit:+.0f}元')
        
        PERIOD_HISTORY[CURRENT_PERIOD]['final'] = total_assets
        PERIOD_HISTORY[CURRENT_PERIOD]['profit'] = profit
        PERIOD_HISTORY[CURRENT_PERIOD]['profit_pct'] = profit_pct
        
        log('\n📊 历史期数收益统计:')
        total_profit = 0
        total_pct = 0
        for period in sorted(PERIOD_HISTORY.keys()):
            ph = PERIOD_HISTORY[period]
            total_profit += ph['profit']
            total_pct += ph['profit_pct']
            log(f'  第{period}期: {ph["profit"]:+.0f}元 ({ph["profit_pct"]:+.2f}%)')
        log(f'  累计收益: {total_profit:+.0f}元')
    
    log('========= 周度复盘结束 =========')
    
    save_period_data()

def save_period_data():
    """保存期数数据到文件"""
    data = {
        'current_period': CURRENT_PERIOD,
        'period_history': PERIOD_HISTORY
    }
    with open('/Users/hetao/stocks_agent/period_data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log('✅ 期数数据已保存')

def main():
    log(f'🚀 东方财富杯周策略启动')
    log(f'   规则: 每周一开盘调仓 | 周五收盘复盘')
    
    while True:
        now = datetime.datetime.now()
        weekday = now.weekday()
        hour = now.hour
        minute = now.minute
        
        if weekday == 0 and hour == 9 and minute >= 30 and minute <= 35:
            weekly_rebalance()
        
        if weekday == 4 and hour == 14 and minute >= 55:
            weekly_summary()
        
        time.sleep(60)

if __name__ == '__main__':
    main()