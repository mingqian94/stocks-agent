"""
把每一笔成交（不管是自动交易脚本下的单，还是手动操作）都记一行进 strategy_log.md，
放在文件末尾一张自动追加的表里，跟前面手写的复盘叙述分开，互不干扰。
写日志失败不应该影响交易本身，所以这里只打印警告，不抛异常。
"""
import datetime
import os
import fcntl

_DIR = os.path.dirname(os.path.abspath(__file__))
STRATEGY_LOG = os.path.join(_DIR, 'strategy_log.local.md')

_SECTION_HEADER = '## 📒 全部买卖记录（自动追加，手动/自动交易成交后都会写这里，最新在最上面）'
_TABLE_HEAD = '| 时间 | 账户 | 操作 | 标的 | 数量 | 价格 | 来源 | 委托号 |'
_TABLE_SEP = '|------|------|------|------|------|------|------|--------|'


def record_trade(account, action, code, name='', qty=0, price=None, order_id=None, source='自动'):
    """成交后调用。account: 账户名（如"东方财富"）；action: 'buy'/'sell'；source: '自动'/'手动'。
    三个交易进程可能几乎同时成交，用 flock 独占锁把"读整个文件→插入一行→写回"这段序列化，
    避免两个进程互相用旧内容覆盖对方刚写的那一行。"""
    try:
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        action_label = '买入' if action == 'buy' else '卖出'
        price_str = f'{price:.2f}' if isinstance(price, (int, float)) else '--'
        target = f'{code} {name}'.strip()
        row = f'| {now} | {account} | {action_label} | {target} | {qty} | {price_str} | {source} | {order_id or "--"} |'

        if not os.path.exists(STRATEGY_LOG):
            open(STRATEGY_LOG, 'a', encoding='utf-8').close()

        with open(STRATEGY_LOG, 'r+', encoding='utf-8') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                content = f.read()
                if _TABLE_SEP in content:
                    content = content.replace(_TABLE_SEP, _TABLE_SEP + '\n' + row, 1)
                else:
                    content = content.rstrip('\n') + '\n\n---\n\n' + _SECTION_HEADER + '\n\n' + _TABLE_HEAD + '\n' + _TABLE_SEP + '\n' + row + '\n'
                f.seek(0)
                f.write(content)
                f.truncate()
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except Exception as e:
        print(f'⚠️ 写strategy_log.md交易记录失败: {e}')
