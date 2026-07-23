import json
import time
import datetime
import requests
import sys
import os
import re
import botctl
from flask import Flask, render_template, jsonify, request

# 添加路径
sys.path.insert(0, '/Users/hetao/stocks_agent')

# 导入账户配置
from accounts import ACCOUNTS, STRATEGIES, PERIODS, get_accounts_for_dashboard, get_account_with_strategy, ensure_current_period, get_current_period, get_true_initial

app = Flask(__name__)

# ⚠️ API Key 统一从 keys_config.py 读取，不要在这里写死
from keys_config import get_key, get_skill_code

# 东方财富API
MX_APIKEY = get_key('dongfang')
MX_APIURL = 'https://mkapi2.dfcfs.com/finskillshub/api/claw/mockTrading'

# 华泰API（双账户）
HT_APIKEY_7493 = get_key('ht_7493')
HT_APIKEY_8268 = get_key('ht_8268')
HT_APIURL = 'https://ai.zhangle.com/edge/entry/gate'
HT_SKILL_CODE = get_skill_code()
HT_HEADERS = {'apiKey': '', 'Content-Type': 'application/json', 'skillCode': HT_SKILL_CODE}

# ETF列表
ETFS = {
    '510050': '上证50ETF',
    '510300': '沪深300ETF',
    '510500': '中证500ETF',
    '512100': '中证1000ETF',
    '588000': '科创50ETF',
    '512480': '半导体ETF',
    '512760': '芯片ETF',
    '588780': '科创芯片ETF',
    '512880': '证券ETF',
    '515180': '银行ETF',
    '512010': '医药ETF',
    '512170': '医疗ETF',
    '515030': '新能源车ETF',
    '515790': '光伏ETF',
    '516160': '新能源ETF',
    '512690': '酒ETF',
    '512200': '房地产ETF',
    '512400': '有色金属ETF',
    '512990': '有色ETF',
    '512660': '军工ETF',
    '512980': '传媒ETF',
    '513050': '中概互联ETF'
}

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

def get_positions():
    try:
        r = requests.post(f'{MX_APIURL}/positions',
            headers={'apikey': MX_APIKEY, 'Content-Type': 'application/json'},
            data='{}', timeout=10)
        if r.status_code == 200:
            return r.json().get('data', {})
    except:
        pass
    return None

def get_ht_positions(acount_id):
    """获取华泰账户持仓"""
    api_key = HT_APIKEY_7493 if acount_id == '7493' else HT_APIKEY_8268
    headers = {'apiKey': api_key, 'Content-Type': 'application/json', 'skillCode': HT_SKILL_CODE}
    try:
        # 获取余额
        r = requests.post(f'{HT_APIURL}/api/simSkills/getAccountBalance', 
            json={}, headers=headers, timeout=10)
        if r.status_code == 200 and r.json().get('ok'):
            balance = r.json().get('data', {})
            # 获取持仓
            r2 = requests.post(f'{HT_APIURL}/api/simSkills/getPositions',
                json={}, headers=headers, timeout=10)
            positions = []
            if r2.status_code == 200 and r2.json().get('ok'):
                for p in r2.json().get('data', {}).get('positions', []):
                    # 华泰getPositions接口不提供当日涨跌率字段，用当日盈亏/期初市值(市值-当日盈亏)近似算
                    day_profit = p.get('dayProfit', 0)
                    market_value = p.get('marketValue', 0)
                    day_open_value = market_value - day_profit
                    day_pct = (day_profit / day_open_value) * 100 if day_open_value else 0
                    positions.append({
                        'code': p.get('stockCode', ''),
                        'name': p.get('stockName', ''),
                        'count': int(p.get('quantity', 0)),
                        'avail_count': int(p.get('quantity', 0)),
                        'price': p.get('currentPrice', 0),
                        'cost_price': p.get('costPrice', p.get('currentPrice', 0)),
                        'day_pct': day_pct,
                        'day_profit': day_profit,
                        'profit': p.get('profit', 0),
                        'pos_pct': (p.get('currentPrice', 0) * p.get('quantity', 0) / balance.get('totalPositionValue', 1)) * 100 if balance.get('totalPositionValue', 0) > 0 else 0
                    })
            # 华泰getAccountBalance接口的dayProfitPct/totalProfitPct字段本身有bug
            # （分母initialCapital实际返回的是可用资金而非真实初始本金），弃用上游字段，自己用总资产算
            total_assets = balance.get('totalAssets', 0)
            day_profit = balance.get('dayProfit', 0)
            day_open_assets = total_assets - day_profit
            day_profit_pct = (day_profit / day_open_assets) * 100 if day_open_assets else 0
            return {
                'total_assets': total_assets,
                'avail_balance': balance.get('availableBalance', 0),
                'day_profit': day_profit,
                'day_profit_pct': day_profit_pct,
                'positions': positions
            }
    except:
        pass
    return None

def get_quote(code):
    try:
        # 判断市场：ETF中5开头是上海，其他是深圳
        if code.startswith('5'):
            secid = f"1.{code}"  # 上海ETF
        else:
            secid = f"0.{code}"  # 深圳ETF

        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Referer': 'https://quote.eastmoney.com/'
        }
        r = requests.get(f'https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=f43,f60,f170', headers=headers, timeout=5)
        if r.status_code == 200:
            d = r.json().get('data', {})
            if d and d.get('f43'):
                current = parse_price(d['f43'])
                yesterday = parse_price(d.get('f60', 0))
                pct = d.get('f170', 0) / 100.0 if d.get('f170') else 0
                if current > 0 and 0.1 < current < 1000 and abs(pct) < 30:
                    return {'code': code, 'name': ETFS.get(code, code), 'price': current, 'yesterday': yesterday, 'pct': pct}
    except:
        pass
    return None

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/api/accounts')
def api_accounts():
    """获取所有账户配置"""
    return jsonify({'success': True, 'accounts': get_accounts_for_dashboard()})

@app.route('/api/configs')
def api_configs():
    """获取账户配置（兼容旧接口）"""
    accounts = get_accounts_for_dashboard()
    configs = {}
    for acc in accounts:
        configs[acc['id']] = {
            'name': acc['name'],
            'platform': acc['platform'],
            'strategy': acc['strategy']['name'],
            'period': acc['period'],
            'initial': acc['initial'],
            'auto_trade': acc['auto_trade']
        }
    return jsonify({'success': True, 'configs': configs})

@app.route('/api/positions/<game>')
def api_positions(game):
    # 兼容旧的game名称
    game_key_map = {
        'dongfang': 'east_money',
        'huatai_7493': 'ht_7493',
        'huatai_8268': 'ht_8268'
    }
    account_key = game_key_map.get(game, game)

    # 获取账户和策略配置
    acc = get_account_with_strategy(account_key)
    if not acc:
        return jsonify({'success': False, 'message': '账户不存在'})

    config = {
        'platform': acc['platform'],
        'strategy': acc['strategy']['name'],
        'period': acc['period'],
        'initial': acc.get('initial', 1000000),
        'auto_trade': acc.get('auto_trade', False)
    }

    # 华泰账户
    if account_key in ['ht_7493', 'ht_8268']:
        account_id = '7493' if account_key == 'ht_7493' else '8268'
        ht_data = get_ht_positions(account_id)
        if ht_data:
            total_assets = ht_data.get('total_assets', 0)
            avail_balance = ht_data.get('avail_balance', 0)
            initial = config.get('initial', 1000000)
            total_profit = total_assets - initial
            profit_pct = (total_profit / initial) * 100
            
            # 获取基准
            benchmark_day_pct = 0.0
            try:
                r = requests.get('https://push2.eastmoney.com/api/qt/stock/get?secid=1.510300&fields=f43,f60,f170', timeout=5)
                if r.status_code == 200:
                    d = r.json().get('data', {})
                    benchmark_day_pct = (d.get('f170', 0) or 0) / 100.0
            except:
                pass
            
            return jsonify({
                'success': True,
                'config': config,
                'strategy': acc['strategy'],
                'total_assets': total_assets,
                'avail_balance': avail_balance,
                'initial': initial,
                'profit': total_profit,
                'profit_pct': profit_pct,
                # 华泰没有滚动分期，本期收益就是总收益
                'since_inception_profit': total_profit,
                'since_inception_profit_pct': profit_pct,
                'day_profit': ht_data.get('day_profit', 0),
                'day_profit_pct': ht_data.get('day_profit_pct', 0),
                'benchmark_day_pct': benchmark_day_pct,
                'positions': ht_data.get('positions', [])
            })
        return jsonify({'success': False, 'config': config, 'strategy': acc['strategy']})
    
    # 东方财富 - 使用真实API数据
    pos = get_positions()
    if pos:
        total_assets = pos.get('totalAssets', 0) / 1000
        avail_balance = pos.get('availBalance', 0) / 1000
        # 东方财富杯每周一期：跨周时用当前实时总资产自动结算上一期、开启新一期
        ensure_current_period(account_key, live_total_assets=total_assets)
        current_period = get_current_period(account_key)
        config['round'] = current_period.get('round', config.get('round', ''))
        config['period'] = current_period.get('period', config.get('period', ''))
        config['initial'] = current_period.get('initial', config.get('initial', 1000000))
        initial = config['initial']
        total_profit = total_assets - initial
        profit_pct = (total_profit / initial) * 100
        
        positions = []
        for p in pos.get('posList', []):
            code = p['secCode']
            name = p['secName']
            count = p['count']
            avail_count = p['availCount']
            price = p['price'] / (10**p['priceDec'])
            cost_price = p.get('costPrice', price)
            cost_price_dec = p.get('costPriceDec', p.get('priceDec', 0))
            cost_price = cost_price / (10**cost_price_dec) if cost_price else price
            day_pct = p.get('dayProfitPct', 0)
            day_profit = p.get('dayProfit', 0) / 1000
            profit = p.get('profit', 0) / 1000
            pos_pct = p.get('posPct', 0)
            cost_amount = count * cost_price
            positions.append({
                'code': code,
                'name': name,
                'count': count,
                'avail_count': avail_count,
                'price': price,
                'cost_price': cost_price,
                'cost_amount': cost_amount,
                'day_pct': day_pct,
                'day_profit': day_profit,
                'profit': profit,
                'pos_pct': pos_pct
            })
        # 获取今日基准（沪深300）
        benchmark_day_pct = 0.0
        try:
            r = requests.get('https://push2.eastmoney.com/api/qt/stock/get?secid=1.510300&fields=f43,f170', timeout=5)
            if r.status_code == 200:
                d = r.json().get('data', {})
                benchmark_day_pct = (d.get('f170', 0) or 0) / 100.0
        except:
            pass
        
        # 计算今日收益
        day_profit = sum(p.get('dayProfit', 0) for p in pos.get('posList', [])) / 1000
        day_profit_pct = (day_profit / total_assets) * 100 if total_assets > 0 else 0

        # 总收益：相对最初本金（第一期的initial），跟"本期收益"（相对当前这一期的起点）是两个数字，
        # 东方财富每周滚动一期，容易把本期收益误当成总收益看
        true_initial = get_true_initial(account_key)
        since_inception_profit = total_assets - true_initial
        since_inception_profit_pct = (since_inception_profit / true_initial) * 100

        return jsonify({
            'success': True,
            'config': config,
            'strategy': acc['strategy'],
            'total_assets': total_assets,
            'avail_balance': avail_balance,
            'initial': initial,
            'profit': total_profit,
            'profit_pct': profit_pct,
            'since_inception_profit': since_inception_profit,
            'since_inception_profit_pct': since_inception_profit_pct,
            'day_profit': day_profit,
            'day_profit_pct': day_profit_pct,
            'benchmark_day_pct': benchmark_day_pct,
            'positions': positions
        })
    return jsonify({'success': False, 'config': config, 'strategy': acc.get('strategy', {})})

@app.route('/api/quotes')
def api_quotes():
    """批量获取ETF行情 - 使用腾讯行情接口"""
    try:
        # 腾讯行情接口：http://qt.gtimg.cn/q=sh510050,sz159915
        codes_list = []
        for code in ETFS.keys():
            if code.startswith('5') or code.startswith('6'):
                codes_list.append(f"sh{code}")
            else:
                codes_list.append(f"sz{code}")

        codes_str = ','.join(codes_list)
        url = f'http://qt.gtimg.cn/q={codes_str}'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        r = requests.get(url, headers=headers, timeout=10)

        quotes = []
        if r.status_code == 200:
            lines = r.text.strip().split('\n')
            for line in lines:
                if '~' not in line:
                    continue
                parts = line.split('~')
                if len(parts) >= 35:
                    code = parts[2]  # 代码
                    name = parts[1]  # 名称
                    price = float(parts[3])  # 现价
                    pct = float(parts[32])  # 涨跌幅

                    if price > 0 and 0.1 < price < 1000 and abs(pct) < 30:
                        quotes.append({
                            'code': code,
                            'name': name or ETFS.get(code, code),
                            'price': price,
                            'pct': pct
                        })

        quotes.sort(key=lambda x: x['pct'], reverse=True)
        return jsonify({'success': True, 'quotes': quotes})
    except Exception as e:
        return jsonify({'success': False, 'quotes': [], 'error': str(e)})


def get_ht_quote(code, api_key):
    """使用华泰接口获取单个ETF行情"""
    try:
        exchange = 'SH' if code.startswith('5') or code.startswith('6') else 'SZ'
        headers = {'apiKey': api_key, 'Content-Type': 'application/json', 'skillCode': HT_SKILL_CODE}
        url = f'{HT_APIURL}/api/simSkills/getQuote'
        data = {'stockCode': code, 'exchange': exchange}
        r = requests.post(url, json=data, headers=headers, timeout=5)
        if r.status_code == 200 and r.json().get('ok'):
            d = r.json().get('data', {})
            price = d.get('currentPrice', 0)
            pct = d.get('change', 0) or 0  # 华泰返回的是change字段
            if price > 0:
                return {
                    'code': code,
                    'name': d.get('stockName') or ETFS.get(code, code),
                    'price': price,
                    'pct': pct
                }
    except:
        pass
    return None


@app.route('/api/quotes_ht/<account_id>')
def api_quotes_ht(account_id):
    """华泰账户专用行情接口"""
    try:
        api_key = HT_APIKEY_7493 if account_id == '7493' else HT_APIKEY_8268
        quotes = []
        for code in ETFS.keys():
            q = get_ht_quote(code, api_key)
            if q:
                quotes.append(q)
        quotes.sort(key=lambda x: x['pct'], reverse=True)
        return jsonify({'success': True, 'quotes': quotes})
    except Exception as e:
        return jsonify({'success': False, 'quotes': [], 'error': str(e)})

@app.route('/api/signal/<game>')
def api_signal(game):
    """策略信号 - 根据账户类型返回不同信号"""
    # 获取账户配置
    accounts_data = get_accounts_for_dashboard()
    account = None
    for acc in accounts_data:
        if acc['id'] == game:
            account = acc
            break

    if not account:
        return jsonify({'success': False, 'signal': '未知账户', 'signal_type': 'info'})

    strategy = account.get('strategy', {})
    panel_type = strategy.get('panel', 'etf')

    # 个股策略信号
    if panel_type == 'stock':
        try:
            # 获取符合条件的个股
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Referer': 'https://quote.eastmoney.com/'
            }
            url = 'https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=50&po=1&np=1&fltt=2&invt=2&fid=f3&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23&fields=f12,f14,f2,f3,f6,f10'
            r = requests.get(url, headers=headers, timeout=5)
            if r.status_code == 200:
                data = r.json().get('data', {}).get('diff', [])
                candidates = []
                for item in data:
                    pct = (item.get('f3', 0)) / 100.0
                    amount = item.get('f6', 0)
                    if 0.03 <= pct <= 0.12 and amount >= 200000000:
                        candidates.append({
                            'code': item.get('f12'),
                            'name': item.get('f14'),
                            'pct': pct,
                            'amount': amount
                        })
                candidates.sort(key=lambda x: x['pct'], reverse=True)

                if len(candidates) >= 1:
                    top = candidates[0]
                    signal = f'买入 {top["name"]} +{top["pct"]*100:.1f}%'
                    signal_type = 'success'
                else:
                    signal = '等待时机（涨幅榜暂无符合条件的个股）'
                    signal_type = 'info'

                return jsonify({
                    'success': True,
                    'signal': signal,
                    'signal_type': signal_type,
                    'panel': 'stock',
                    'candidates_count': len(candidates)
                })
        except:
            pass

        return jsonify({
            'success': True,
            'signal': '观望（扫描中...）',
            'signal_type': 'info',
            'panel': 'stock'
        })

    # ETF策略信号（原有逻辑）
    quotes = []
    for code in ETFS:
        q = get_quote(code)
        if q:
            quotes.append(q)
    quotes.sort(key=lambda x: x['pct'], reverse=True)

    signal = '观望'
    signal_type = 'info'
    if len(quotes) >= 2:
        top1 = quotes[0]
        top2 = quotes[1]
        if top1['pct'] > 0 and top2['pct'] > 0:
            signal = f'买入 {top1["name"]} + {top2["name"]}'
            signal_type = 'success'
        elif top1['pct'] < -2:
            signal = '⚠️ 止损警戒'
            signal_type = 'danger'
        elif quotes[0]['pct'] > 0:
            signal = f'关注 {top1["name"]}'
            signal_type = 'warning'

    return jsonify({
        'success': True,
        'signal': signal,
        'signal_type': signal_type,
        'panel': 'etf',
        'top': quotes[0] if quotes else None
    })

@app.route('/api/strategies')
def api_strategies():
    """获取策略列表"""
    return jsonify({'success': True, 'strategies': STRATEGIES})

@app.route('/api/strategy/<strategy_id>')
def api_strategy(strategy_id):
    """运行指定策略"""
    if strategy_id == 'mean_reversion':
        try:
            import mean_reversion_strategy
            result = mean_reversion_strategy.run_strategy()
            return jsonify({'success': True, 'strategy': 'ETF均值回归', 'result': result})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    elif strategy_id == 'sector_rotation':
        try:
            import sector_rotation_strategy
            result = sector_rotation_strategy.run_strategy()
            return jsonify({'success': True, 'strategy': '板块轮动', 'result': result})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    elif strategy_id == 'stock_momentum':
        try:
            sys.path.insert(0, '/Users/hetao/stocks_agent')
            import stock_auto_trade
            result = stock_auto_trade.run_strategy()
            return jsonify({'success': True, 'strategy': '个股动量突破', 'result': result})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    else:
        return jsonify({'success': False, 'error': '策略不存在'})

@app.route('/api/logs')
def api_logs():
    try:
        with open('/Users/hetao/stocks_agent/auto_trade.log', 'r', encoding='utf-8') as f:
            lines = f.readlines()[-100:]
            return jsonify({'success': True, 'logs': lines})
    except:
        return jsonify({'success': False, 'logs': []})

@app.route('/api/stock_candidates')
def api_stock_candidates():
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
                    price = item.get('f2', 0) if item.get('f2') else 0

                    if 0.03 <= pct <= 0.12 and amount >= 200000000:
                        candidates.append({
                            'code': code,
                            'name': name,
                            'day_pct': pct * 100,
                            'amount': amount,
                            'price': price
                        })

                return jsonify({
                    'success': True,
                    'candidates': candidates,
                    'total': len(candidates),
                    'params': {
                        'min_increase': 3,
                        'max_increase': 12,
                        'min_amount': 200000000
                    }
                })
        except Exception as e:
            if attempt == 2:
                return jsonify({'success': False, 'error': str(e), 'candidates': []})
            time.sleep(1)
    return jsonify({'success': False, 'error': '请求失败3次', 'candidates': []})

@app.route('/api/stock_strategy_status')
def api_stock_strategy_status():
    """获取个股策略运行状态"""
    try:
        # 检查进程是否运行
        import subprocess
        result = subprocess.run(['pgrep', '-f', 'stock_auto_trade.py'], capture_output=True, text=True)
        is_running = bool(result.stdout.strip())

        # 读取stock_trade.log最后几行
        with open('/Users/hetao/stocks_agent/stock_trade.log', 'r', encoding='utf-8') as f:
            lines = f.readlines()[-30:]

        # 解析最新状态
        status = {
            'running': is_running,
            'last_check': '',
            'total_assets': 0,
            'avail_balance': 0,
            'positions': [],
            'message': ''
        }

        # 简单解析：从最后往前找
        for line in lines:
            # 时间戳
            if re.match(r'\[2026-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]', line):
                status['last_check'] = line[1:20]
            # 总资产
            if '总资产:' in line:
                match = re.search(r'总资产:\s*([\d.]+)万', line)
                if match:
                    status['total_assets'] = float(match.group(1))
            # 可用资金
            if '可用资金:' in line:
                match = re.search(r'可用资金:\s*([\d.]+)万', line)
                if match:
                    status['avail_balance'] = float(match.group(1))
            # 持仓
            if '持仓:' in line and '盈亏' in line:
                match = re.search(r'持仓:\s*(\d+)\s+(\S+)\s+(\d+)股\s+盈亏([+-][\d.]+)%', line)
                if match:
                    status['positions'].append({
                        'code': match.group(1),
                        'name': match.group(2),
                        'count': int(match.group(3)),
                        'profit_pct': float(match.group(4))
                    })

        return jsonify({'success': True, 'status': status})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/periods/<game>')
def api_periods_game(game):
    """获取指定账户的期数数据 —— 历史全部来自 accounts.PERIODS，不再硬编码某一期的数字"""
    try:
        game_to_account_key = {'dongfang': 'east_money', 'huatai_7493': 'ht_7493', 'huatai_8268': 'ht_8268'}
        account_key = game_to_account_key.get(game)
        account = get_account_with_strategy(account_key) if account_key else None
        if not account:
            return jsonify({'success': False, 'message': '账户不存在'})

        # 获取当前资产（实时）
        total_assets = account.get('initial', 1000000)
        avail_balance = total_assets
        try:
            if game == 'dongfang':
                # 注意：/account 端点返回302，改用 /positions 获取资产
                r = requests.post(f'{MX_APIURL}/positions',
                    headers={'apikey': MX_APIKEY, 'Content-Type': 'application/json'},
                    data='{}',
                    timeout=5)
                if r.status_code == 200:
                    result = r.json()
                    if str(result.get('code', '')) == '200' or result.get('code') == 200:
                        d = result.get('data', {})
                        # 东方财富API返回元，除1000转为千元（与前端单位一致）
                        total_assets = float(d.get('totalAssets', total_assets)) / 1000
                        avail_balance = float(d.get('availBalance', avail_balance)) / 1000
            elif game.startswith('huatai'):
                api_key = HT_APIKEY_7493 if game == 'huatai_7493' else HT_APIKEY_8268
                headers = {'apiKey': api_key, 'Content-Type': 'application/json', 'skillCode': HT_SKILL_CODE}
                r = requests.post(f'{HT_APIURL}/api/simSkills/getAccountBalance',
                    json={}, headers=headers, timeout=5)
                if r.status_code == 200:
                    result = r.json()
                    if result.get('ok'):
                        d = result.get('data', {})
                        total_assets = float(d.get('totalAssets', total_assets))
                        avail_balance = float(d.get('availableAmount', avail_balance))
        except:
            pass

        # 东方财富杯每周一期：跨周时自动结算上一期、开新一期
        if account_key in ('east_money',):
            ensure_current_period(account_key, live_total_assets=total_assets)
            account = get_account_with_strategy(account_key)

        initial = account.get('initial', 1000000)
        profit = total_assets - initial
        profit_pct = round(profit / initial * 100, 2) if initial > 0 else 0

        # 历史 + 当前周期（最新在前），全部来自 PERIODS 表
        account_periods = PERIODS.get(account_key, [])
        rounds = []
        for i, p in enumerate(reversed(account_periods)):
            is_current = (i == 0)
            rounds.append({
                'round': p['round'],
                'period': p['period'],
                'initial': p['initial'],
                'total_assets': total_assets if is_current else p.get('final', p['initial']),
                'avail_balance': avail_balance if is_current else 0,
                'profit': profit if is_current else (p.get('final', p['initial']) - p['initial']),
                'profit_pct': profit_pct if is_current else (p.get('profit_pct') or 0),
                'competition': account.get('competition', ''),
                'platform': account.get('platform', ''),
                'status': 'active' if is_current else 'ended'
            })

        data = {
            'round': account.get('round', ''),
            'period': account.get('period', ''),
            'initial': initial,
            'total_assets': total_assets,
            'avail_balance': avail_balance,
            'profit': profit,
            'profit_pct': profit_pct,
            'competition': account.get('competition', ''),
            'platform': account.get('platform', ''),
            'status': account.get('status', 'active'),
            'rounds': rounds  # 多期历史数据
        }

        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/bots/status')
def api_bots_status():
    """三个自动交易进程是否在跑 + 最后一条日志"""
    try:
        return jsonify({'success': True, 'bots': botctl.get_status()})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/bots/<action>', methods=['POST'])
def api_bots_action(action):
    """手动停止/启动/重启自动交易进程。action: stop/start/restart，body: {"name": "ht_7493"|"ht_8268"|"east_money"|"all"}"""
    if action not in ('stop', 'start', 'restart'):
        return jsonify({'success': False, 'message': f'不支持的操作: {action}'})
    name = (request.json or {}).get('name', 'all')
    if name != 'all' and name not in botctl.BOTS:
        return jsonify({'success': False, 'message': f'账号不存在: {name}'})
    try:
        getattr(botctl, action)(name)
        return jsonify({'success': True, 'bots': botctl.get_status()})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

NAV_LOG_MAP = {
    'dongfang': 'stock_trade.log',
    'huatai_7493': 'auto_trade_ht_7493.log',
    'huatai_8268': 'auto_trade_ht_8268.log',
}
NAV_LINE_RE = re.compile(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\].*总资产[:：]\s*([\d.]+)元')

@app.route('/api/nav_history/<game>')
def api_nav_history(game):
    """从交易日志里解析总资产快照，给收益分析的折线图用。range: day/week/month/all"""
    try:
        range_key = request.args.get('range', 'all')
        log_file = NAV_LOG_MAP.get(game)
        if not log_file:
            return jsonify({'success': False, 'message': '账户不存在'})

        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), log_file)
        points = []
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    m = NAV_LINE_RE.search(line)
                    if m:
                        points.append({'time': m.group(1), 'total_assets': float(m.group(2))})

        if range_key != 'all' and points:
            latest = datetime.datetime.strptime(points[-1]['time'], '%Y-%m-%d %H:%M:%S')
            cutoff = {
                'day': latest - datetime.timedelta(hours=24),
                'week': latest - datetime.timedelta(days=7),
                'month': latest - datetime.timedelta(days=30),
            }.get(range_key)
            if cutoff:
                points = [p for p in points
                          if datetime.datetime.strptime(p['time'], '%Y-%m-%d %H:%M:%S') >= cutoff]

        # 降采样，避免几千个点糊在一起；强制保留最后一个点，不然图表右端会比实际数据旧
        if len(points) > 200:
            step = len(points) // 200
            sampled = points[::step]
            if sampled[-1] != points[-1]:
                sampled[-1] = points[-1]
            points = sampled

        return jsonify({'success': True, 'points': points})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
