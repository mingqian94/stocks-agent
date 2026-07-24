import json
import time
import requests
import datetime
import sys
import os
import trade_logger

# 导入统一配置
from accounts import ACCOUNTS, STRATEGIES, get_account_with_strategy, get_strategy, get_current_period
from keys_config import get_skill_code

# 平台API配置
PLATFORM_CONFIG = {
    'east_money': {
        'name': '东方财富',
        'api_url': 'https://mkapi2.dfcfs.com/finskillshub/api/claw/mockTrading',
        'header_name': 'apikey',
        'quote_url': 'https://push2.eastmoney.com/api/qt/stock/get'
    },
    'ht_7493': {
        'name': '华泰-7493',
        'api_url': 'https://ai.zhangle.com/edge/entry/gate/api/simSkills',
        'header_name': 'apiKey',
        'skill_code': get_skill_code(),
        'quote_url': 'https://ai.zhangle.com/edge/entry/gate/api/simSkills/getQuote'
    },
    'ht_8268': {
        'name': '华泰-8268',
        'api_url': 'https://ai.zhangle.com/edge/entry/gate/api/simSkills',
        'header_name': 'apiKey',
        'skill_code': get_skill_code(),
        'quote_url': 'https://ai.zhangle.com/edge/entry/gate/api/simSkills/getQuote'
    }
}

LOG_DIR = '/Users/hetao/stocks_agent'

ETFS = {
    # === 宽基ETF ===
    '510050': '上证50ETF',
    '510300': '沪深300ETF',
    '510500': '中证500ETF',
    '512100': '中证1000ETF',
    '588000': '科创50ETF',
    # === 科技/半导体 ===
    '512480': '半导体ETF',
    '512760': '芯片ETF',
    '588780': '科创芯片ETF',
    # === 金融 ===
    '512880': '证券ETF',
    '515180': '银行ETF',
    # === 医药 ===
    '512010': '医药ETF',
    '512170': '医疗ETF',
    # === 新能源 ===
    '515030': '新能源车ETF',
    '515790': '光伏ETF',
    '516160': '新能源ETF',
    # === 消费 ===
    '512690': '酒ETF',
    '512200': '房地产ETF',
    # === 周期/资源 ===
    '512400': '有色金属ETF',
    '512990': '有色ETF',
    # === 军工 ===
    '512660': '军工ETF',
    # === 其他 ===
    '512980': '传媒ETF',
    '513050': '中概互联ETF'
}

STOP_LOSS_DAY_PCT = -3.0
MOMENTUM_TOP_N = 3
MIN_BUY_CASH = 50000
MIN_SELL_PCT = -0.5


class AutoTrader:
    def __init__(self, account_key):
        self.account_key = account_key
        self.account = ACCOUNTS.get(account_key)
        if not self.account:
            raise ValueError(f'账户不存在: {account_key}')

        self.platform = self.account.get('platform', '')
        self.account_id = self.account.get('id', '')

        # 根据账户ID匹配平台配置
        if 'huatai_7493' in self.account_id or account_key == 'ht_7493':
            self.platform_cfg = PLATFORM_CONFIG['ht_7493']
        elif 'huatai_8268' in self.account_id or account_key == 'ht_8268':
            self.platform_cfg = PLATFORM_CONFIG['ht_8268']
        else:
            self.platform_cfg = PLATFORM_CONFIG['east_money']

        self.api_url = self.platform_cfg['api_url']
        self.header_name = self.platform_cfg['header_name']
        self.api_key = self.account.get('api_key', '')

        self.strategy_id = self.account.get('strategy_id', '')
        self.strategy = STRATEGIES.get(self.strategy_id, {})
        self.auto_trade = self.account.get('auto_trade', False)

        # 2026.07.09 之前这几个是全账户共用的模块常量，稳健/激进两个账户跑的是同一套风控，
        # STRATEGIES里配的stop_loss/max_positions只是文档展示，代码没真正读过。现在按账户读：
        self.momentum_top_n = self.strategy.get('max_positions', MOMENTUM_TOP_N)
        self.stop_loss_day_pct = self.strategy.get('stop_loss', STOP_LOSS_DAY_PCT / 100) * 100
        self.profit_floor = self.strategy.get('profit_floor')  # None表示没配地板，不做保护

        self.log_file = f'{LOG_DIR}/auto_trade_{account_key}.log'

    def get_headers(self):
        headers = {'Content-Type': 'application/json'}
        headers[self.header_name] = self.api_key
        if 'skill_code' in self.platform_cfg:
            headers['skillCode'] = self.platform_cfg['skill_code']
        return headers

    def log(self, msg):
        t = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        account_name = self.account.get('name', 'Unknown')
        competition = self.account.get('competition', 'Unknown')
        line = f'[{t}] [{competition}] [{account_name}] {msg}'
        # 先打印到标准输出（nohup会重定向进console日志，作为兜底记录），
        # 再写文件；写文件失败不应该拖垮整个盯盘进程
        print(line)
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(line + '\n')
        except OSError as e:
            print(f'[{t}] ⚠️ 写日志文件失败（进程继续运行）: {e}')

    def get_positions(self):
        try:
            if self.platform_cfg == PLATFORM_CONFIG['east_money']:
                r = requests.post(f'{self.api_url}/positions',
                    headers=self.get_headers(),
                    data='{}', timeout=10)
            else:
                # 华泰：先取账户余额，再取持仓（getPositions不返回 totalAssets/availBalance）
                bal = self.get_balance() or {}
                r = requests.post(f'{self.api_url}/getPositions',
                    headers=self.get_headers(), json={}, timeout=10)

            if r.status_code == 200:
                d = r.json()
                if self.platform_cfg == PLATFORM_CONFIG['east_money']:
                    if str(d.get('code', '')) == '200':
                        return d.get('data', {})
                else:
                    if d.get('ok'):
                        data = d.get('data', {})
                        # 华泰API字段统一转换为标准字段
                        std_positions = []
                        for p in data.get('positions', []):
                            std_positions.append({
                                'secCode': p.get('stockCode', ''),
                                'secName': p.get('stockName', ''),
                                # 华泰接口返回的是float（如199100.0），submitOrder的quantity按整数解析，
                                # 传"199100.0"会被Java端NumberFormatException拒收(500)，这里转成int
                                'count': int(p.get('quantity', 0)),
                                'availCount': int(p.get('availableQuantity', 0)),
                                'costPrice': p.get('costPrice', 0),
                                'price': p.get('currentPrice', 0),
                                'dayProfit': p.get('dayProfit', 0),
                                'profitPct': p.get('profitPct', 0),
                                'posPct': p.get('positionPct', 0)
                            })
                        return {
                            'totalAssets': bal.get('totalAssets', 0),
                            'availBalance': bal.get('availBalance', 0),
                            'posList': std_positions
                        }
        except Exception as e:
            self.log(f'  ⚠️ 获取持仓异常: {e}')
        return None

    def get_balance(self):
        try:
            if self.platform_cfg == PLATFORM_CONFIG['east_money']:
                r = requests.post(f'{self.api_url}/account',
                    headers=self.get_headers(),
                    json={'action': 'getAccountBalance', 'data': {}}, timeout=10)
            else:
                r = requests.post(f'{self.api_url}/getAccountBalance',
                    headers=self.get_headers(), json={}, timeout=10)

            if r.status_code == 200:
                d = r.json()
                if self.platform_cfg == PLATFORM_CONFIG['east_money']:
                    if str(d.get('code', '')) == '200':
                        return d.get('data', {})
                else:
                    if d.get('ok'):
                        data = d.get('data', {})
                        # 华泰字段统一：availableBalance -> availBalance
                        return {
                            'totalAssets': data.get('totalAssets', 0),
                            'availBalance': data.get('availableBalance', 0),
                            'dayProfit': data.get('dayProfit', 0)
                        }
        except Exception as e:
            self.log(f'  ⚠️ 获取余额异常: {e}')
        return None

    def get_quote(self, code):
        try:
            if self.platform_cfg == PLATFORM_CONFIG['east_money']:
                secid = f"1.{code}" if code.startswith('5') else f"0.{code}"
                r = requests.get(f'{self.platform_cfg["quote_url"]}?secid={secid}&fields=f43,f60,f170', timeout=5)
                if r.status_code == 200:
                    d = r.json().get('data', {})
                    if d and d.get('f43'):
                        price = self.parse_price(d['f43'])
                        yesterday = self.parse_price(d.get('f60', 0))
                        pct = d.get('f170', 0) / 100.0 if d.get('f170') else 0
                        if price > 0 and 0.1 < price < 1000 and abs(pct) < 30:
                            return {'code': code, 'price': price, 'yesterday': yesterday, 'pct': pct}
            else:
                # 华泰接口
                exchange = 'SH' if code.startswith('5') or code.startswith('6') else 'SZ'
                r = requests.post(f'{self.platform_cfg["quote_url"]}',
                    headers=self.get_headers(),
                    json={'stockCode': code, 'exchange': exchange}, timeout=5)
                if r.status_code == 200 and r.json().get('ok'):
                    d = r.json().get('data', {})
                    price = d.get('currentPrice', 0)
                    pct = d.get('change', 0) or 0
                    if price > 0:
                        return {'code': code, 'price': price, 'pct': pct}
        except:
            pass
        return None

    def parse_price(self, f43):
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

    def _get_position_count(self, code):
        """查某只股票当前持仓数量，查不到持仓数据返回None（跟"持仓0股"区分开）"""
        pos_data = self.get_positions()
        if not pos_data:
            return None
        for p in pos_data.get('posList', []):
            if p.get('secCode') == code:
                return p.get('count', 0)
        return 0

    def verify_position_change(self, code, baseline_count, qty, direction, retries=8, delay=5):
        """broker说下单成功了，不代表真的成交了——下单前记一次持仓基线，
        下单后隔几秒重新查，确认股数真的按预期方向变化，而不是只信下单接口的同步响应。
        留10%容差应对部分成交/委托数量取整误差。
        2026.07.24：东方财富模拟盘实测碰到过持仓更新延迟超过12秒的情况，窗口改成8次×5秒(40秒)。"""
        for attempt in range(retries):
            time.sleep(delay)
            cur = self._get_position_count(code)
            if cur is None:
                continue
            if direction == 'buy' and cur >= baseline_count + qty * 0.9:
                return True
            if direction == 'sell' and cur <= baseline_count - qty * 0.9:
                return True
        return False

    def buy(self, code, qty, price=None):
        baseline = self._get_position_count(code)
        try:
            if price is None:
                q = self.get_quote(code)
                price = q['price'] if q else 0
            if price <= 0:
                self.log(f'  ⚠️ 买入 {code} 无法获取价格，跳过')
                return False

            if self.platform_cfg == PLATFORM_CONFIG['east_money']:
                r = requests.post(f'{self.api_url}/trade',
                    headers=self.get_headers(),
                    json={'action': 'buy', 'data': {'stockCode': code, 'quantity': qty, 'price': price}}, timeout=10)
            else:
                exchange = 'SH' if code.startswith('5') or code.startswith('6') else 'SZ'
                r = requests.post(f'{self.api_url}/submitOrder',
                    headers=self.get_headers(),
                    json={'direction': 'buy', 'stockCode': code, 'quantity': int(qty), 'exchange': exchange, 'price': price}, timeout=10)

            if r.status_code == 200:
                d = r.json()
                ok = str(d.get('code')) == '200' if self.platform_cfg == PLATFORM_CONFIG['east_money'] else d.get('ok')
                if ok:
                    order_id = d.get('data', {}).get('orderID', '?')
                    if baseline is not None and not self.verify_position_change(code, baseline, qty, 'buy'):
                        self.log(f'  🚨 二次核实失败: {code} broker说买入成功，但隔几秒重新查持仓股数没有相应增加，可能没真的成交，不记为成功交易')
                        return False
                    self.log(f'  ✅ 买入成功: {ETFS.get(code, code)} {code} x{qty} @{price:.3f} 委托号: {order_id}（已核实持仓变化）')
                    trade_logger.record_trade(self.account.get('name', ''), 'buy', code, ETFS.get(code, ''), qty, price, order_id)
                    return True
                if self.platform_cfg == PLATFORM_CONFIG['east_money']:
                    self.log(f'  ⚠️ 买入失败: {code} {d.get("message", "未知")}')
                else:
                    err = d.get('error', {})
                    self.log(f'  ⚠️ 买入失败: {code} {err.get("message", str(err)) or d}')
            else:
                self.log(f'  ⚠️ 买入请求失败({r.status_code}): {code} | {r.text[:500]}')
        except Exception as e:
            self.log(f'  ⚠️ 买入异常 {code}: {e}')
        return False

    def sell(self, code, qty, price=None):
        baseline = self._get_position_count(code)
        try:
            if price is None:
                q = self.get_quote(code)
                price = q['price'] if q else 0
            if price <= 0:
                self.log(f'  ⚠️ 卖出 {code} 无法获取价格，跳过')
                return False

            if self.platform_cfg == PLATFORM_CONFIG['east_money']:
                r = requests.post(f'{self.api_url}/trade',
                    headers=self.get_headers(),
                    json={'action': 'sell', 'data': {'stockCode': code, 'quantity': qty, 'price': price}}, timeout=10)
            else:
                exchange = 'SH' if code.startswith('5') or code.startswith('6') else 'SZ'
                r = requests.post(f'{self.api_url}/submitOrder',
                    headers=self.get_headers(),
                    json={'direction': 'sell', 'stockCode': code, 'quantity': int(qty), 'exchange': exchange, 'price': price}, timeout=10)

            if r.status_code == 200:
                d = r.json()
                ok = str(d.get('code')) == '200' if self.platform_cfg == PLATFORM_CONFIG['east_money'] else d.get('ok')
                if ok:
                    order_id = d.get('data', {}).get('orderID', '?')
                    if baseline is not None and not self.verify_position_change(code, baseline, qty, 'sell'):
                        self.log(f'  🚨 二次核实失败: {code} broker说卖出成功，但隔几秒重新查持仓股数没有相应减少，可能没真的成交，不记为成功交易')
                        return False
                    self.log(f'  ✅ 卖出成功: {ETFS.get(code, code)} {code} x{qty} @{price:.3f} 委托号: {order_id}（已核实持仓变化）')
                    trade_logger.record_trade(self.account.get('name', ''), 'sell', code, ETFS.get(code, ''), qty, price, order_id)
                    return True
                if self.platform_cfg == PLATFORM_CONFIG['east_money']:
                    self.log(f'  ⚠️ 卖出失败: {code} {d.get("message", "未知")}')
                else:
                    err = d.get('error', {})
                    self.log(f'  ⚠️ 卖出失败: {code} {err.get("message", str(err)) or d}')
            else:
                self.log(f'  ⚠️ 卖出请求失败({r.status_code}): {code} | {r.text[:500]}')
        except Exception as e:
            self.log(f'  ⚠️ 卖出异常 {code}: {e}')
        return False

    def calc_qty(self, cash, price):
        if price <= 0 or cash <= 0:
            return 0
        qty = int(cash / price / 100) * 100
        return qty

    def check_and_trade(self):
        self.log(f'========= 自动盯盘启动 =========')
        self.log(f'  模式: {"⚡ 自动交易模式" if self.auto_trade else "🔔 提醒模式"}')
        self.log(f'  平台: {self.platform}')
        self.log(f'  策略: {self.strategy.get("name", "未设置")}')

        pos = self.get_positions()
        if not pos:
            self.log('❌ 无法获取持仓，跳过本轮')
            return

        # 统一字段：get_positions已统一为 posList 格式
        total_assets = pos.get('totalAssets', 0)
        avail_balance = pos.get('availBalance', 0)
        # 东方财富/华泰都已经是 posList
        if 'posList' in pos:
            positions = pos['posList']
        else:
            positions = pos.get('positions', [])

        # 华泰平台：获取每个持仓的今日涨跌幅（通过getQuote）
        is_ht = self.platform_cfg != PLATFORM_CONFIG['east_money']

        self.log(f'总资产: {total_assets:.0f}元 | 可用: {avail_balance:.0f}元')
        self.log(f'持仓数量: {len(positions)}')

        # 收益地板保护：本期收益跌到地板以下就清仓，本期剩余时间不再冒险
        if self.profit_floor is not None:
            period = get_current_period(self.account_key)
            initial = period.get('initial') if period else None
            if initial:
                period_profit_pct = (total_assets - initial) / initial
                if period_profit_pct <= self.profit_floor:
                    self.log(f'🛑 触发收益地板保护: 本期收益{period_profit_pct*100:+.2f}% <= 地板{self.profit_floor*100:.0f}%，清仓保护，本期不再买入')
                    if self.auto_trade:
                        for p in positions:
                            code = p.get('secCode') or p.get('stockCode') or p.get('code')
                            name = p.get('secName') or p.get('stockName') or p.get('name')
                            avail_count = p.get('availCount', 0)
                            price = p.get('price', 0) or 0
                            if avail_count > 0 and price > 0:
                                self.sell(code, avail_count, price=price)
                                time.sleep(2)
                    self.log('========= 本轮结束（地板保护） =========\n')
                    return

        pos_map = {}
        pos_pct_map = {}
        alert_messages = []
        for p in positions:
            code = p.get('secCode') or p.get('stockCode') or p.get('code')
            name = p.get('secName') or p.get('stockName') or p.get('name')
            count = p.get('count', 0)
            avail_count = p.get('availCount', 0)
            price = p.get('price', 0) or 0
            profit_pct = p.get('profitPct', 0) or 0

            # 东方财富有dayProfitPct，华泰没有需要通过getQuote计算
            if 'dayProfitPct' in p:
                day_pct = p.get('dayProfitPct', 0) or 0
            else:
                # 华泰：从 getQuote 拿涨跌幅
                q = self.get_quote(code)
                if q and 'pct' in q:
                    day_pct = q['pct']
                else:
                    # 兜底：用 costPrice 估算
                    day_pct = 0

            pos_pct = p.get('posPct', 0) or 0

            self.log(f'  {name}({code}): {count}股(可用{avail_count}) 现价{price:.3f} 今日{day_pct:.2f}% 累计盈亏{profit_pct:.2f}% 占比{pos_pct:.1f}%')
            pos_map[code] = p
            pos_pct_map[code] = day_pct
            p['_day_pct'] = day_pct  # 缓存

            if day_pct <= self.stop_loss_day_pct:
                alert_msg = f'🚨 【止损提醒】{name}({code}) 今日跌幅{day_pct:.2f}%，建议减半仓！'
                self.log(f'  {alert_msg}')
                alert_messages.append(alert_msg)
                if self.auto_trade and avail_count > 0:
                    sell_qty = avail_count // 2
                    sell_qty = sell_qty // 100 * 100
                    if sell_qty > 0:
                        self.log(f'  → 自动减仓 {sell_qty} 股')
                        self.sell(code, sell_qty, price=price)
                        time.sleep(2)

        self.log(f'\n--- 行情监测 ---')
        quotes = {}
        for code in ETFS:
            q = self.get_quote(code)
            if q:
                quotes[code] = q
                self.log(f'  {ETFS[code]}({code}) 价格:{q["price"]:.3f} 涨跌幅:{q["pct"]:.2f}%')
            elif code in pos_pct_map:
                p = pos_map[code]
                if 'priceDec' in p:
                    price = p['price'] / (10**p['priceDec'])
                else:
                    price = p.get('price', 0) or 0
                pct = pos_pct_map[code]
                self.log(f'  {ETFS[code]}({code}) 价格:{price:.3f} 涨跌幅:{pct:.2f}% (持仓数据)')
                quotes[code] = {'code': code, 'price': price, 'pct': pct}

        sorted_etfs = sorted(quotes.items(), key=lambda x: x[1]['pct'], reverse=True)
        if sorted_etfs:
            top_list = [(ETFS.get(c, c), f'{q["pct"]:.2f}%') for c, q in sorted_etfs]
            self.log(f'📊 动量排名: {top_list}')

            top_codes = [c for c, q in sorted_etfs[:self.momentum_top_n] if q['pct'] > 0]
            if top_codes:
                self.log(f'\n--- 交易建议 ---')
                self.log(f'  🌟 推荐买入: {[ETFS.get(c, c) for c in top_codes]}')

                current_pos_codes = set(pos_map.keys())
                held_not_top = current_pos_codes - set(top_codes)
                for weak_code in held_not_top:
                    if weak_code in pos_map:
                        p = pos_map[weak_code]
                        avail_count = p.get('availCount', 0)
                        day_pct = p.get('_day_pct', 0) or 0
                        price = p.get('price', 0) or 0
                        if avail_count > 0 and day_pct < MIN_SELL_PCT and price > 0:
                            alert_msg = f'🔄 【减仓提醒】{ETFS.get(weak_code, weak_code)}({weak_code}) 今日{day_pct:.2f}%，不在动量Top{len(top_codes)}，建议减半仓！'
                            self.log(f'  {alert_msg}')
                            alert_messages.append(alert_msg)
                            if self.auto_trade:
                                sell_qty = avail_count // 2
                                sell_qty = sell_qty // 100 * 100
                                if sell_qty > 0:
                                    self.log(f'  → 自动卖出 {sell_qty} 股')
                                    self.sell(weak_code, sell_qty, price=price)
                                    time.sleep(3)

                pos2 = self.get_positions()
                if pos2:
                    # 字段已统一，不需要除1000
                    avail_balance2 = pos2.get('availBalance', 0)

                    if avail_balance2 >= MIN_BUY_CASH:
                        # 满仓投入，不留现金缓冲——没有补仓/加仓策略，不需要预留资金摊低成本
                        per_target = avail_balance2 / len(top_codes)
                        self.log(f'  💰 可用{avail_balance2:.0f}元，每只计划{per_target:.0f}元')
                        for code in top_codes:
                            q = quotes.get(code)
                            if not q:
                                continue
                            price = q['price']
                            if price <= 0:
                                continue
                            qty = self.calc_qty(per_target, price)
                            if qty >= 100:
                                alert_msg = f'➕ 【买入提醒】建议买入 {ETFS.get(code, code)}({code}) {qty}股 @{price:.3f} (约{qty*price:.0f}元)'
                                self.log(f'  {alert_msg}')
                                alert_messages.append(alert_msg)
                                if self.auto_trade:
                                    self.log(f'  → 自动买入')
                                    self.buy(code, qty, price=price)
                                    time.sleep(3)
                    else:
                        self.log(f'  💤 可用资金{avail_balance2:.0f}元，不足买入')
            else:
                self.log(f'  💤 无正收益标的，观望')

        if alert_messages:
            self.log(f'\n📣 ======== 重要提醒 ========')
            for msg in alert_messages:
                self.log(f'    {msg}')
            self.log('=============================\n')

        self.log('========= 本轮结束 =========\n')


def run_account(account_key):
    """运行单个账户的自动盯盘"""
    try:
        trader = AutoTrader(account_key)
        trader.log(f'🚀 自动盯盘脚本启动 | 账户: {trader.account.get("name")} | 平台: {trader.platform}')

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
                    trader.check_and_trade()
                except Exception as e:
                    trader.log(f'❌ 异常: {e}')
            else:
                weekd_cn = ['一','二','三','四','五','六','日'][weekday]
                trader.log(f'非交易时间 {now.strftime("%Y-%m-%d %H:%M:%S")} (周{weekd_cn})，等待中...')

            # 华泰账户每30分钟轮一次，其他账户3分钟
            sleep_interval = 1800 if 'huatai' in trader.account_id else 180
            time.sleep(sleep_interval)
    except Exception as e:
        print(f'❌ 账户 {account_key} 启动失败: {e}')


if __name__ == '__main__':
    # 启动所有启用自动交易的账户
    active_accounts = [k for k, v in ACCOUNTS.items() if v.get('auto_trade') and v.get('status') == 'active']

    if len(sys.argv) > 1:
        # 指定特定账户
        account_key = sys.argv[1]
        if account_key in ACCOUNTS:
            run_account(account_key)
        else:
            print(f'❌ 账户不存在: {account_key}')
            print(f'可用账户: {list(ACCOUNTS.keys())}')
    else:
        # 启动所有ETF策略账户
        if not active_accounts:
            print('❌ 没有启用自动交易的账户')
            sys.exit(1)

        print(f'🚀 准备启动 {len(active_accounts)} 个ETF策略账户: {active_accounts}')

        # 在子进程中启动每个账户
        for acc_key in active_accounts:
            if ACCOUNTS[acc_key].get('strategy_id') != 'stock_momentum':
                pid = os.fork()
                if pid == 0:
                    run_account(acc_key)
                    sys.exit(0)
                else:
                    print(f'   启动 {acc_key} (PID: {pid})')

        # 主进程等待
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            print('退出')
