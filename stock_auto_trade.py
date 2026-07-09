#!/usr/bin/env python3
"""
个股动量策略 - 自动盯盘交易
强势选股 + 集中持仓
"""

import json
import time
import requests
import datetime
import sys
import trade_logger

# ⚠️ API Key 统一从 keys_config.py 读取，不要在这里写死
from accounts import get_current_account
account_info = get_current_account()
APIKEY = account_info.get('api_key', '') if account_info else ''
ACCOUNT_NAME = account_info.get('name', 'Unknown') if account_info else 'Unknown'
AUTO_TRADE = account_info.get('auto_trade', False) if account_info else False

APIURL = 'https://mkapi2.dfcfs.com/finskillshub/api/claw/mockTrading'
LOG_FILE = '/Users/hetao/Documents/stocks/stock_trade.log'

# ========== 策略参数 ==========
# 2026.07.09 调整：第13/14/15期连续三期负收益，落地第13期复盘时写的建议——
# 单票95%仓位改成2只分散、止损从-7%收紧到-5%
MAX_POSITIONS = 2          # 最大持仓2只（原1只，分散降低单票波动）
MAX_POSITION_SIZE = 0.45   # 单只仓位45%（原95%，2只合计90%）
STOP_LOSS = -0.05          # 止损5%（原-7%，收紧）
TAKE_PROFIT = 0.20         # 止盈20%

# 选股条件
MIN_INCREASE = 0.03        # 最小涨幅3%
MAX_INCREASE = 0.12        # 最大涨幅12%
MIN_AMOUNT = 200000000     # 最小成交额2亿


def passes_candidate_filter(pct, amount, min_increase=MIN_INCREASE, max_increase=MAX_INCREASE, min_amount=MIN_AMOUNT):
    """选股条件：涨幅在区间内 + 成交额达标"""
    return min_increase <= pct <= max_increase and amount >= min_amount


def should_stop_loss(profit_pct, stop_loss=STOP_LOSS):
    """profit_pct 是百分数（比如-7.5表示-7.5%），stop_loss 是小数（比如-0.07）。
    round()是因为 -0.07*100 在浮点数里是-7.000000000000001，正好卡在-7.0%的仓位不小心就漏判了"""
    return profit_pct <= round(stop_loss * 100, 6)


def should_take_profit(profit_pct, take_profit=TAKE_PROFIT):
    """profit_pct 是百分数，take_profit 是小数"""
    return profit_pct >= round(take_profit * 100, 6)


def calc_buy_qty(avail_balance, price, position_pct=MAX_POSITION_SIZE):
    """按仓位比例和可用资金算买入数量，整手（100股）"""
    if price <= 0 or avail_balance <= 0:
        return 0
    buy_amount = avail_balance * position_pct
    return int(buy_amount / price / 100) * 100

def log(msg):
    """写日志：先打印到标准输出（nohup会重定向进console日志，作为兜底记录），
    再写文件；写文件失败不应该拖垮整个盯盘进程"""
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{now}] {msg}'
    print(line)
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except OSError as e:
        print(f'[{now}] ⚠️ 写日志文件失败（进程继续运行）: {e}')

def get_positions():
    """获取持仓"""
    try:
        r = requests.post(f'{APIURL}/positions',
            headers={'apikey': APIKEY, 'Content-Type': 'application/json'},
            data='{}', timeout=10)
        if r.status_code == 200:
            return r.json().get('data', {})
    except Exception as e:
        log(f'  ⚠️ 获取持仓异常: {e}')
    return None

def get_stock_candidates():
    """获取符合条件的个股"""
    url = 'https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=50&po=1&np=1&fltt=2&invt=2&fid=f3&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23&fields=f12,f14,f2,f3,f6'
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                data = r.json().get('data', {}).get('diff', [])
                candidates = []
                for item in data:
                    code = item.get('f12', '')
                    name = item.get('f14', '')
                    pct = item.get('f3', 0) / 100 if item.get('f3') else 0
                    amount = item.get('f6', 0) if item.get('f6') else 0
                    price = item.get('f2', 0) if item.get('f2') else 0  # clist接口f2已是元

                    # 筛选条件（pct已是小数形式，直接用小数阈值比较）
                    if passes_candidate_filter(pct, amount):
                        candidates.append({
                            'code': code,
                            'name': name,
                            'pct': pct,
                            'amount': amount,
                            'price': price
                        })
                return candidates
        except Exception as e:
            log(f'  ⚠️ 选股请求失败(第{attempt+1}次): {e}')
            time.sleep(1)
    return []

def get_quote(code):
    """获取个股行情"""
    try:
        # 判断市场代码
        market = '1' if code.startswith(('6', '5')) else '0'
        url = f'https://push2.eastmoney.com/api/qt/stock/get?secid={market}.{code}&fields=f43,f60,f170'
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            d = r.json().get('data', {})
            if d and d.get('f43'):
                current = d['f43'] / 1000
                pct = d.get('f170', 0) / 100
                return {'code': code, 'price': current, 'pct': pct}
    except:
        pass
    return None

def buy(code, qty, name='', price=None, source='自动'):
    """买入"""
    try:
        r = requests.post(f'{APIURL}/trade',
            headers={'apikey': APIKEY, 'Content-Type': 'application/json'},
            json={'type': 'buy', 'stockCode': code, 'quantity': qty, 'useMarketPrice': True},
            timeout=10)
        if r.status_code == 200:
            d = r.json()
            if str(d.get('code')) == '200':
                order_id = d.get('data', {}).get('orderID', '?')
                log(f'  ✅ 买入成功: {code} x{qty} 委托号: {order_id}')
                trade_logger.record_trade(ACCOUNT_NAME, 'buy', code, name, qty, price, order_id, source)
                return True
            log(f'  ⚠️ 买入失败: {code} {d.get("message","未知")}')
        else:
            log(f'  ⚠️ 买入请求失败({r.status_code}): {code}')
    except Exception as e:
        log(f'  ⚠️ 买入异常 {code}: {e}')
    return False

def sell(code, qty, name='', price=None, source='自动'):
    """卖出"""
    try:
        r = requests.post(f'{APIURL}/trade',
            headers={'apikey': APIKEY, 'Content-Type': 'application/json'},
            json={'type': 'sell', 'stockCode': code, 'quantity': qty, 'useMarketPrice': True},
            timeout=10)
        if r.status_code == 200:
            d = r.json()
            if str(d.get('code')) == '200':
                order_id = d.get('data', {}).get('orderID', '?')
                log(f'  ✅ 卖出成功: {code} x{qty} 委托号: {order_id}')
                trade_logger.record_trade(ACCOUNT_NAME, 'sell', code, name, qty, price, order_id, source)
                return True
            log(f'  ⚠️ 卖出失败: {code} {d.get("message","未知")}')
        else:
            log(f'  ⚠️ 卖出请求失败({r.status_code}): {code}')
    except Exception as e:
        log(f'  ⚠️ 卖出异常 {code}: {e}')
    return False

def check_and_trade():
    """检查并交易"""
    log(f'\n{"="*60}')
    log(f'📊 {ACCOUNT_NAME} 个股动量策略检查')
    log(f'  模式: {"⚡ 自动交易模式" if AUTO_TRADE else "🔔 提醒模式"}')
    log(f'{"="*60}')

    # 获取持仓
    pos_data = get_positions()
    if not pos_data:
        log('  ⚠️ 无法获取持仓')
        return

    # 东方财富API返回的单位：totalAssets/availBalance 是"分"级别（除以1000 = 元）
    total_assets = pos_data.get('totalAssets', 0) / 1000
    avail_balance = pos_data.get('availBalance', 0) / 1000
    pos_list = pos_data.get('posList', [])

    log(f'  总资产: {total_assets:.0f}元')
    log(f'  可用资金: {avail_balance:.0f}元')

    # 检查持仓
    holdings = []
    for pos in pos_list:
        if pos.get('count', 0) > 0:
            code = pos['secCode']
            count = pos['count']
            avail = pos.get('availCount', 0)
            cost = pos.get('costPrice', 0) / 1000
            current = pos.get('price', 0) / 1000
            profit_pct = pos.get('profitPct', 0)
            holdings.append({
                'code': code,
                'name': pos.get('secName', ''),
                'count': count,
                'avail': avail,
                'cost': cost,
                'current': current,
                'profit_pct': profit_pct
            })
            log(f'  持仓: {code} {pos.get("secName","")} {count}股 盈亏{profit_pct:+.2f}%')

    # ====== 启动时清仓不符合策略的ETF（个股策略只能持有个股）======
    etf_codes = {'510050','510300','510500','512100','588000','512480','512760','588780',
                 '512880','515180','512010','512170','515030','515790','516160','512690',
                 '512200','512400','512990','512660','512980','513050','159915'}
    etf_to_clear = [h for h in holdings if h['code'] in etf_codes]
    if etf_to_clear:
        for h in etf_to_clear:
            if h['avail'] > 0:
                log(f'  🚨 检测到ETF持仓（个股策略不符）: {h["code"]} {h["name"]} {h["avail"]}股可用')
                if AUTO_TRADE:
                    log(f'  → 自动清仓ETF: {h["code"]}')
                    sell(h['code'], h['avail'], h['name'], h['current'])
                    time.sleep(2)
            else:
                log(f'  ⏸️ ETF {h["code"]} {h["name"]} 持有{h["count"]}股但可用0（T+1冻结，等待明日清仓）')
        # 重新读取持仓
        pos_data2 = get_positions()
        if pos_data2:
            pos_list = pos_data2.get('posList', [])
            avail_balance = pos_data2.get('availBalance', 0) / 1000
            holdings = []
            for pos in pos_list:
                if pos.get('count', 0) > 0:
                    holdings.append({
                        'code': pos['secCode'],
                        'name': pos.get('secName', ''),
                        'count': pos['count'],
                        'avail': pos.get('availCount', 0),
                        'cost': pos.get('costPrice', 0) / 1000,
                        'current': pos.get('price', 0) / 1000,
                        'profit_pct': pos.get('profitPct', 0)
                    })

    # 计算"活跃持仓"：剔除T+1冻结的ETF（不可交易）
    active_holdings = [h for h in holdings if not (h['code'] in etf_codes and h['avail'] == 0)]

    # 止损止盈检查（只对活跃持仓）
    for h in active_holdings:
        if should_stop_loss(h['profit_pct']):
            log(f'  🚨 触发止损: {h["code"]} {h["profit_pct"]:+.2f}%')
            if AUTO_TRADE and h['avail'] > 0:
                sell(h['code'], h['avail'], h['name'], h['current'])
        elif should_take_profit(h['profit_pct']):
            log(f'  🎉 触发止盈: {h["code"]} {h["profit_pct"]:+.2f}%')
            if AUTO_TRADE and h['avail'] > 0:
                sell(h['code'], h['avail'], h['name'], h['current'])

    # 如果没有活跃持仓或未满，寻找买入机会（可以补满到 MAX_POSITIONS 只）
    open_slots = MAX_POSITIONS - len(active_holdings)
    if open_slots > 0 and avail_balance >= 50000:
        log('  🔍 寻找买入机会...')
        candidates = get_stock_candidates()

        if candidates:
            log(f'  发现 {len(candidates)} 只符合条件的个股')
            for c in candidates[:5]:
                log(f'    {c["code"]} {c["name"]} +{c["pct"]*100:.2f}% 成交额{c["amount"]/100000000:.1f}亿')

            held_codes = {h['code'] for h in active_holdings}
            new_picks = [c for c in candidates if c['code'] not in held_codes][:open_slots]

            # 每只按 MAX_POSITION_SIZE 用同一份可用资金算仓位（不是买完一只再扣减），
            # 这样MAX_POSITIONS只加起来正好是 MAX_POSITIONS * MAX_POSITION_SIZE 的总仓位
            for best in new_picks:
                buy_qty = calc_buy_qty(avail_balance, best['price'])
                if buy_qty >= 100:
                    log(f'  💡 建议买入: {best["code"]} {best["name"]} x{buy_qty}')
                    if AUTO_TRADE:
                        buy(best['code'], buy_qty, best['name'], best['price'])
                        time.sleep(2)
        else:
            log('  暂无符合条件的个股')

    log(f'  下次检查: 3分钟后')

def main():
    """主函数"""
    log('='*60)
    log(f'🚀 个股动量策略启动')
    log(f'  账户: {ACCOUNT_NAME}')
    log(f'  自动交易: {"是" if AUTO_TRADE else "否"}')
    log(f'  策略参数: 涨幅{MIN_INCREASE*100:.0f}%-{MAX_INCREASE*100:.0f}% 成交额>{MIN_AMOUNT/100000000:.0f}亿')
    log(f'  止损{STOP_LOSS*100:.0f}% 止盈{TAKE_PROFIT*100:.0f}%')
    log('='*60)

    while True:
        try:
            now = datetime.datetime.now()
            # 只在交易时间运行
            if now.weekday() < 5:  # 周一到周五
                hour = now.hour
                minute = now.minute
                # 9:30-11:30, 13:00-15:00
                is_trading_time = (
                    (hour == 9 and minute >= 30) or  # 9:30-9:59
                    (hour == 10) or                   # 10:00-10:59
                    (hour == 11 and minute <= 30) or # 11:00-11:30
                    (hour == 13) or                  # 13:00-13:59
                    (hour == 14)                     # 14:00-14:59
                )
                if is_trading_time:
                    check_and_trade()
                else:
                    log(f'  ⏸️ 非交易时间 {now.strftime("%H:%M")}')
            else:
                log(f'  ⏸️ 周末休市')

            time.sleep(180)  # 3分钟检查一次
        except KeyboardInterrupt:
            log('  👋 用户中断')
            break
        except Exception as e:
            log(f'  ⚠️ 异常: {e}')
            time.sleep(60)

if __name__ == '__main__':
    main()
