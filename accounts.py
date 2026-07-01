# 账户配置表
# ⚠️ 账号密码 / API Key 请在 keys_config.py 中配置，不要写在这里
from keys_config import get_key, is_pending

ACCOUNTS = {
    'ht_7493': {
        'id': 'huatai_7493',
        'name': '华泰-7493',
        'short_name': '华泰-7493',
        'platform': '华泰证券',
        'competition': '华泰证券杯',
        'round': '初赛',
        'period': '2026.06.11 - 2026.07.20',
        'initial': 1000000,
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
        'round': '初赛',
        'period': '2026.06.11 - 2026.07.20',
        'initial': 1000000,
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
        'round': '第13期',
        'period': '2026.06.22 - 2026.06.26',
        'initial': 1073000,  # 第12期结束时带入（收益率+3.87%）
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
        'position_size': 0.30,
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
        'position_size': 0.45,
        'target_return': 0.30,
        'risk_level': '高',
        'color': '#00ff88'
    },
    'stock_momentum': {
        'id': 'stock_momentum',
        'name': '个股动量突破',
        'type': '个股动量',
        'desc': '监测A股实时涨跌幅，买入动量排名前列且符合条件（涨幅3%-12%、成交额>2亿）的强势个股',
        'panel': 'stock',
        'stop_loss': -0.07,
        'take_profit': 0.20,
        'min_increase': 0.03,
        'max_increase': 0.12,
        'min_amount': 200000000,
        'max_positions': 1,
        'position_size': 0.95,
        'target_return': 0.10,
        'risk_level': '高',
        'color': '#ff4757'
    },
    'manual': {
        'id': 'manual',
        'name': '手动操作',
        'type': '手动',
        'desc': '手动操作，待开赛后启用',
        'panel': 'etf',
        'target_return': 0,
        'risk_level': '未知',
        'color': '#ffb74d'
    },
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

def get_account_with_strategy(account_id):
    """获取账户及其策略配置"""
    account = ACCOUNTS.get(account_id)
    if account:
        strategy_id = account.get('strategy_id')
        strategy = STRATEGIES.get(strategy_id, {})
        return {**account, 'strategy': strategy}
    return None

def list_accounts():
    """列出所有账户"""
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
        result.append({
            'id': acc['id'],
            'key': key,
            'name': acc['name'],
            'short_name': acc.get('short_name', acc['name']),
            'platform': acc['platform'],
            'competition': acc['competition'],
            'round': acc.get('round', ''),
            'period': acc['period'],
            'initial': acc.get('initial', 1000000),
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
