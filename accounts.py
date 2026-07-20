# 账户配置表
# ⚠️ 账号密码 / API Key 请在 keys_config.py 中配置，不要写在这里
#
# 三张表分别管理三个独立维度，互不混装：
#   ACCOUNTS  —— 账号身份（平台、api_key、绑定的策略），基本不变
#   STRATEGIES —— 策略定义（选股/止损止盈参数），随策略调优才变
#   PERIODS   —— 比赛周期战绩（每期起止时间、初始/期末资金），每期比赛都会新增一条
import datetime
import re
from keys_config import get_key, is_pending

ACCOUNTS = {
    'ht_7493': {
        'id': 'huatai_7493',
        'name': '华泰-7493',
        'short_name': '华泰-7493',
        'platform': '华泰证券',
        'competition': '华泰证券杯',
        'api_key': get_key('ht_7493'),
        'strategy_id': 'etf_momentum_stable',
        'auto_trade': not is_pending('ht_7493'),
        'status': 'active' if not is_pending('ht_7493') else 'pending_key'
    },
    'ht_8268': {
        'id': 'huatai_8268',
        'name': '华泰-8268',
        'short_name': '华泰-8268',
        'platform': '华泰证券',
        'competition': '华泰证券杯',
        'api_key': get_key('ht_8268'),
        'strategy_id': 'etf_momentum_aggressive',
        'auto_trade': not is_pending('ht_8268'),
        'status': 'active' if not is_pending('ht_8268') else 'pending_key'
    },
    'east_money': {
        'id': 'dongfang',
        'name': '东方财富',
        'short_name': '东方财富',
        'platform': '东方财富模拟交易',
        'competition': '东方财富杯',
        'api_key': get_key('dongfang'),
        'strategy_id': 'stock_momentum',
        'auto_trade': not is_pending('dongfang'),
        'status': 'active' if not is_pending('dongfang') else 'pending_key'
    },
}

# 策略配置表
STRATEGIES = {
    'etf_momentum_stable': {
        'id': 'etf_momentum_stable',
        'name': 'ETF动量轮动（稳健型）',
        'type': 'ETF动量',
        'desc': '监测22只ETF实时涨跌幅，买入动量排名前2且为正的标的，卖出弱势标的',
        'panel': 'etf',
        'stop_loss': -0.03,
        'max_positions': 3,
        'position_size': 0.3333,  # 满仓：3只均分100%，不留现金缓冲（没有补仓策略不需要）
        'target_return': 0.08,
        'risk_level': '低',
        'color': '#00d4ff'
    },
    'etf_momentum_aggressive': {
        'id': 'etf_momentum_aggressive',
        'name': 'ETF动量轮动（激进型）',
        'type': 'ETF动量',
        'desc': '监测ETF和行业板块动量，集中持仓高动量标的，追求高收益',
        'panel': 'etf',
        'stop_loss': -0.05,
        'max_positions': 2,
        'position_size': 0.5,  # 满仓：2只均分100%
        'target_return': 0.30,
        'profit_floor': 0.08,  # 本期收益跌到8%以下就清仓保护，本期不再买入
        'risk_level': '高',
        'color': '#00ff88'
    },
    'stock_momentum': {
        'id': 'stock_momentum',
        'name': '个股动量突破',
        'type': '个股动量',
        'desc': '监测A股实时涨跌幅，买入动量排名前列且符合条件（涨幅3%-12%、成交额>2亿）的强势个股',
        'panel': 'stock',
        'stop_loss': -0.05,
        'take_profit': 0.20,
        'min_increase': 0.03,
        'max_increase': 0.12,
        'min_amount': 200000000,
        'max_positions': 2,
        'position_size': 0.5,  # 满仓：2只均分100%（原1只95%单票）
        'target_return': 0.10,
        'risk_level': '高',
        'color': '#ff4757'
    },
}

# 比赛周期战绩表：每个账号一份按时间排序的列表，最后一条是当前/最新一期。
# final/profit_pct 为 None 表示该期尚未结束。
# 换期时只在这里追加一条（或用 add_period），不用再去改 dashboard.py / accounts.py 其它地方。
# 真实的 PERIODS 数据放在 periods_local.py（已加入 .gitignore，不会被提交），
# git 仓库里只有下面这份脱敏示例——参考 periods_local.example.py 建一份自己的 periods_local.py。
try:
    from periods_local import PERIODS
except ImportError:
    PERIODS = {
        'east_money': [
            {'round': '第1期', 'period': 'MM.DD-MM.DD', 'initial': 1000000, 'final': 1000000, 'profit_pct': 0.00, 'status': 'active'},
        ],
        'ht_7493': [
            {'round': '初赛', 'period': 'YYYY.MM.DD - YYYY.MM.DD', 'initial': 1000000, 'final': None, 'profit_pct': None, 'status': 'active'},
        ],
        'ht_8268': [
            {'round': '初赛', 'period': 'YYYY.MM.DD - YYYY.MM.DD', 'initial': 1000000, 'final': None, 'profit_pct': None, 'status': 'active'},
        ],
    }

CURRENT_ACCOUNT = 'east_money'

def get_current_account():
    """获取当前账户"""
    return ACCOUNTS.get(CURRENT_ACCOUNT)

def get_account(account_id):
    """获取指定账户"""
    return ACCOUNTS.get(account_id)

def get_strategy(strategy_id):
    """获取指定策略"""
    return STRATEGIES.get(strategy_id)

def get_current_period(account_id):
    """获取账号当前（最新）一期的周期战绩，没有记录时返回空字典"""
    periods = PERIODS.get(account_id, [])
    return periods[-1] if periods else {}

def add_period(account_id, round_name, period_str, initial, final=None, profit_pct=None, status='active'):
    """比赛换期时调用：追加一条新的周期记录，取代手改 accounts.py 多处字段"""
    if PERIODS.get(account_id):
        PERIODS[account_id][-1]['status'] = 'done'
    PERIODS.setdefault(account_id, []).append({
        'round': round_name,
        'period': period_str,
        'initial': initial,
        'final': final,
        'profit_pct': profit_pct,
        'status': status
    })

# 每周滚动一期的账号（东方财富杯规则：每周一期）；华泰是初赛长周期，不在这里滚动
WEEKLY_ROLLING_ACCOUNTS = {'east_money'}

def _week_bounds(d):
    """d 所在自然周的周一/周五日期"""
    monday = d - datetime.timedelta(days=d.weekday())
    friday = monday + datetime.timedelta(days=4)
    return monday, friday

def _fmt_period(monday, friday):
    return f"{monday.month}.{monday.day}-{friday.month}.{friday.day}"

def _next_round_name(last_round):
    m = re.search(r'\d+', last_round or '')
    return f'第{int(m.group()) + 1}期' if m else '第1期'

def ensure_current_period(account_id, live_total_assets=None):
    """
    检查该账号是否已经跨入新的一周；如果是，自动结算上一期（final/profit_pct 用
    live_total_assets 回填）并追加新一期（initial 沿用同一个数字，因为账户资金是连续的，
    只是按周分段记录战绩）。只对 WEEKLY_ROLLING_ACCOUNTS 里的账号生效，其余账号原样返回
    当前周期，不做任何滚动。建议在每次拿到账户实时总资产的地方调用（比如 dashboard 的
    positions 接口），这样换周当天第一次访问就会自动结算，不用手改 accounts.py。
    """
    if account_id not in WEEKLY_ROLLING_ACCOUNTS:
        return get_current_period(account_id)

    monday, friday = _week_bounds(datetime.date.today())
    current_period_str = _fmt_period(monday, friday)

    periods = PERIODS.get(account_id, [])
    if periods and periods[-1]['period'] == current_period_str:
        return periods[-1]

    if not periods:
        return get_current_period(account_id)

    prev = periods[-1]
    if live_total_assets is not None:
        prev['final'] = live_total_assets
        prev['profit_pct'] = round((live_total_assets - prev['initial']) / prev['initial'] * 100, 2)
    prev['status'] = 'done'

    initial = live_total_assets if live_total_assets is not None else prev.get('final') or prev['initial']
    add_period(account_id, _next_round_name(prev['round']), current_period_str, initial, status='active')
    return get_current_period(account_id)

def get_account_with_strategy(account_id):
    """获取账户 + 策略 + 当前周期战绩"""
    account = ACCOUNTS.get(account_id)
    if not account:
        return None
    strategy_id = account.get('strategy_id')
    strategy = STRATEGIES.get(strategy_id, {})
    period = get_current_period(account_id)
    return {
        **account,
        'strategy': strategy,
        'round': period.get('round', ''),
        'period': period.get('period', ''),
        'initial': period.get('initial', 1000000),
    }

def list_accounts():
    """列出所有账户（原始身份信息，不含周期战绩）"""
    return ACCOUNTS

def list_strategies():
    """列出所有策略"""
    return STRATEGIES

def get_accounts_for_dashboard():
    """获取Dashboard需要的账户列表"""
    result = []
    for key, acc in ACCOUNTS.items():
        strategy_id = acc.get('strategy_id')
        strategy = STRATEGIES.get(strategy_id, {})
        period = get_current_period(key)
        result.append({
            'id': acc['id'],
            'key': key,
            'name': acc['name'],
            'short_name': acc.get('short_name', acc['name']),
            'platform': acc['platform'],
            'competition': acc['competition'],
            'round': period.get('round', ''),
            'period': period.get('period', ''),
            'initial': period.get('initial', 1000000),
            'auto_trade': acc.get('auto_trade', False),
            'status': acc.get('status', 'active'),
            'strategy': {
                'id': strategy.get('id'),
                'name': strategy.get('name'),
                'type': strategy.get('type'),
                'desc': strategy.get('desc'),
                'panel': strategy.get('panel'),
                'stop_loss': strategy.get('stop_loss'),
                'take_profit': strategy.get('take_profit'),
                'min_increase': strategy.get('min_increase'),
                'max_increase': strategy.get('max_increase'),
                'min_amount': strategy.get('min_amount'),
                'max_positions': strategy.get('max_positions'),
                'position_size': strategy.get('position_size'),
                'target_return': strategy.get('target_return'),
                'risk_level': strategy.get('risk_level'),
                'color': strategy.get('color')
            }
        })
    return result
