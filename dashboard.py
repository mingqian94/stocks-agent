import json
import time
import requests
import sys
import os
import re
from flask import Flask, render_template, jsonify

# 添加路径
sys.path.insert(0, '/Users/hetao/Documents/stocks')

# 导入账户配置
from accounts import ACCOUNTS, STRATEGIES, get_accounts_for_dashboard, get_account_with_strategy

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
                    positions.append({
                        'code': p.get('stockCode', ''),
                        'name': p.get('stockName', ''),
                        'count': int(p.get('quantity', 0)),
                        'avail_count': int(p.get('quantity', 0)),
                        'price': p.get('currentPrice', 0),
                        'cost_price': p.get('avgCostPrice', p.get('currentPrice', 0)),
                        'day_pct': p.get('dayProfitPct', 0) * 100 if p.get('dayProfitPct') else 0,
                        'day_profit': p.get('dayProfit', 0),
                        'profit': p.get('profit', 0),
                        'pos_pct': (p.get('currentPrice', 0) * p.get('quantity', 0) / balance.get('totalPositionValue', 1)) * 100 if balance.get('totalPositionValue', 0) > 0 else 0
                    })
            return {
                'total_assets': balance.get('totalAssets', 0),
                'avail_balance': balance.get('availableBalance', 0),
                'day_profit': balance.get('dayProfit', 0),
                'day_profit_pct': balance.get('dayProfitPct', 0) * 100 if balance.get('dayProfitPct') else 0,
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
        initial = config.get('initial', 1000000)
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
        
        return jsonify({
            'success': True,
            'config': config,
            'strategy': acc['strategy'],
            'total_assets': total_assets,
            'avail_balance': avail_balance,
            'initial': initial,
            'profit': total_profit,
            'profit_pct': profit_pct,
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
            sys.path.insert(0, '/Users/hetao/Documents/stocks')
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
        with open('/Users/hetao/Documents/stocks/auto_trade.log', 'r', encoding='utf-8') as f:
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
        with open('/Users/hetao/Documents/stocks/stock_trade.log', 'r', encoding='utf-8') as f:
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
    """获取指定账户的期数数据（从accounts配置读取）"""
    try:
        accounts_data = get_accounts_for_dashboard()
        account = None
        for acc in accounts_data:
            if acc['id'] == game:
                account = acc
                break

        if not account:
            return jsonify({'success': False, 'message': '账户不存在'})

        # 从accounts配置（PERIODS表）生成期数信息
        round_name = account.get('round', account['competition'])
        period = account.get('period', '')
        initial = account.get('initial', 1000000)

        # 获取当前资产
        total_assets = initial
        avail_balance = initial

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
                        total_assets = float(d.get('totalAssets', initial)) / 1000
                        avail_balance = float(d.get('availBalance', initial)) / 1000
            elif game.startswith('huatai'):
                api_key = HT_APIKEY_7493 if game == 'huatai_7493' else HT_APIKEY_8268
                headers = {'apiKey': api_key, 'Content-Type': 'application/json', 'skillCode': HT_SKILL_CODE}
                r = requests.post(f'{HT_APIURL}/api/simSkills/getAccountBalance',
                    json={}, headers=headers, timeout=5)
                if r.status_code == 200:
                    result = r.json()
                    if result.get('ok'):
                        d = result.get('data', {})
                        total_assets = float(d.get('totalAssets', initial))
                        avail_balance = float(d.get('availableAmount', initial))
        except:
            pass

        # 东方财富第13期：初始资金=第12期结束时带入
        if game == 'dongfang':
            initial = 1073000

        profit = total_assets - initial
        profit_pct = round(profit / initial * 100, 2) if initial > 0 else 0

        # 第14期（当前）
        # 东方财富第14期初始资金 = 第13期结束带入（硬编码，防止accounts模块缓存）
        effective_initial = 999000 if game == 'dongfang' else initial
        current_round = {
            'round': round_name,
            'period': period,
            'initial': effective_initial,
            'total_assets': total_assets,
            'avail_balance': avail_balance,
            'profit': total_assets - effective_initial,
            'profit_pct': round((total_assets - effective_initial) / effective_initial * 100, 2),
            'competition': account.get('competition', ''),
            'platform': account.get('platform', ''),
            'status': account.get('status', 'active')
        }

        # 东方财富多期历史（最新在前）
        rounds = []
        # 第14期（当前）
        rounds.append(current_round)
        # 第13期（历史，6.22-6.26）
        if game == 'dongfang':
            rounds.append({
                'round': '第13期',
                'period': '2026.06.22 - 2026.06.26',
                'initial': 1073000,
                'total_assets': 999000,
                'avail_balance': 0,
                'profit': -74000,
                'profit_pct': -6.90,
                'competition': '东方财富杯',
                'platform': '东方财富模拟交易',
                'status': 'ended'
            })
        # 第12期（历史，6.15-6.18）
        if game == 'dongfang':
            rounds.append({
                'round': '第12期',
                'period': '2026.06.15 - 2026.06.18',
                'initial': 1033000,
                'total_assets': 1073000,
                'avail_balance': 0,
                'profit': 40000,
                'profit_pct': 3.87,
                'competition': '东方财富杯',
                'platform': '东方财富模拟交易',
                'status': 'ended'
            })
        # 第11期（历史数据）
        if game == 'dongfang':
            rounds.append({
                'round': '第11期',
                'period': '2026.06.08 - 2026.06.12',
                'initial': 1000000,
                'total_assets': 1033000,
                'avail_balance': 0,
                'profit': 33000,
                'profit_pct': 3.30,
                'competition': '东方财富杯',
                'platform': '东方财富模拟交易',
                'status': 'ended'
            })

        data = {
            'round': round_name,
            'period': period,
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

@app.route('/api/trade', methods=['POST'])
def api_trade():
    from flask import request
    data = request.json
    action = data.get('action')
    code = data.get('code')
    qty = data.get('quantity')
    
    try:
        if action == 'buy':
            r = requests.post(f'{APIURL}/trade',
                headers={'apikey': APIKEY, 'Content-Type': 'application/json'},
                json={'type': 'buy', 'stockCode': code, 'quantity': qty, 'useMarketPrice': True},
                timeout=10)
        elif action == 'sell':
            r = requests.post(f'{APIURL}/trade',
                headers={'apikey': APIKEY, 'Content-Type': 'application/json'},
                json={'type': 'sell', 'stockCode': code, 'quantity': qty, 'useMarketPrice': True},
                timeout=10)
        else:
            return jsonify({'success': False, 'message': '无效操作'})
        
        if r.status_code == 200:
            d = r.json()
            if str(d.get('code')) == '200':
                return jsonify({'success': True, 'data': d.get('data', {})})
            return jsonify({'success': False, 'message': d.get('message', '未知错误')})
        return jsonify({'success': False, 'message': f'HTTP {r.status_code}'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
