"""
记录真实成交摩擦（跟研究报告a_share_lab的建议对应）：信号价、用的是市价单还是限价单重试、
失败次数、实际成交均价（买入能从broker持仓接口拿到真实costPrice；卖出这个API拿不到精确成交价，
用限价单价格或决策价做近似，note里注明）。只记本地，不进git——这是真实账户的交易细节。
"""
import csv
import os
import datetime
import fcntl

_DIR = os.path.dirname(os.path.abspath(__file__))
FRICTION_LOG = os.path.join(_DIR, 'friction_log.local.csv')

_HEADER = ['time', 'account', 'action', 'code', 'name', 'decision_price', 'order_type',
           'limit_price', 'fail_count_before', 'result', 'actual_fill_price', 'slippage', 'note']


def record_friction(account, action, code, name, decision_price, order_type, limit_price,
                     fail_count_before, result, actual_fill_price=None, note=''):
    """记一行真实摩擦数据。action: 'buy'/'sell'；order_type: 'market'/'limit'；
    result: 'success'/'failed'。actual_fill_price为None时slippage留空，不瞎算。"""
    try:
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        slippage = ''
        if actual_fill_price is not None and decision_price:
            slippage = round(actual_fill_price - decision_price, 4)
        row = [now, account, action, code, name, decision_price, order_type,
               limit_price or '', fail_count_before, result, actual_fill_price or '', slippage, note]

        file_exists = os.path.exists(FRICTION_LOG)
        with open(FRICTION_LOG, 'a', newline='', encoding='utf-8') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(_HEADER)
                writer.writerow(row)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except OSError as e:
        print(f'⚠️ 写摩擦日志失败（不影响交易本身）: {e}')
