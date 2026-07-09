#!/usr/bin/env python3
"""
三个自动交易进程的手动管理工具，不用记PID、不用问Claude。

用法：
    python3 botctl.py status            # 查看三个进程状态 + 最后一条日志
    python3 botctl.py stop [账号|all]    # 停止（默认all，停止全部）
    python3 botctl.py start [账号|all]   # 拉起（默认all）
    python3 botctl.py restart [账号|all] # 重启

账号可选值：ht_7493 / ht_8268 / east_money / all
"""
import subprocess
import sys
import os
import time

DIR = os.path.dirname(os.path.abspath(__file__))

BOTS = {
    'ht_7493': {
        'label': '华泰-7493',
        'match': 'auto_trade.py ht_7493',
        'cmd': ['python3', 'auto_trade.py', 'ht_7493'],
        'console_log': 'auto_trade_ht_7493_console.log',
        'trade_log': 'auto_trade_ht_7493.log',
    },
    'ht_8268': {
        'label': '华泰-8268',
        'match': 'auto_trade.py ht_8268',
        'cmd': ['python3', 'auto_trade.py', 'ht_8268'],
        'console_log': 'auto_trade_ht_8268_console.log',
        'trade_log': 'auto_trade_ht_8268.log',
    },
    'east_money': {
        'label': '东方财富',
        'match': 'stock_auto_trade.py',
        'cmd': ['python3', 'stock_auto_trade.py'],
        'console_log': 'stock_trade_console.log',
        'trade_log': 'stock_trade.log',
    },
}


def _pids(match):
    r = subprocess.run(['pgrep', '-f', match], capture_output=True, text=True)
    return [p for p in r.stdout.strip().split('\n') if p]


def _last_log_line(trade_log):
    path = os.path.join(DIR, trade_log)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
        return lines[-1] if lines else '(日志是空的)'
    except FileNotFoundError:
        return '(日志文件不存在)'


def get_status():
    """结构化的状态列表，dashboard.py 的 /api/bots/status 复用这个"""
    result = []
    for key, b in BOTS.items():
        pids = _pids(b['match'])
        result.append({
            'key': key,
            'label': b['label'],
            'running': bool(pids),
            'pids': pids,
            'last_log': _last_log_line(b['trade_log']),
        })
    return result


def status():
    print(f'{"账号":<10}{"状态":<10}{"PID":<12}最后一条日志')
    for b in get_status():
        state = '✅ 运行中' if b['running'] else '❌ 未运行'
        pid_str = ','.join(b['pids']) if b['pids'] else '-'
        print(f'{b["label"]:<10}{state:<10}{pid_str:<12}{b["last_log"][:90]}')


def stop(name):
    targets = list(BOTS.keys()) if name == 'all' else [name]
    for key in targets:
        b = BOTS[key]
        pids = _pids(b['match'])
        if not pids:
            print(f'{b["label"]}: 没在跑，不用停')
            continue
        for pid in pids:
            subprocess.run(['kill', pid])
        print(f'{b["label"]}: 已停止 (PID {",".join(pids)})')


def start(name):
    targets = list(BOTS.keys()) if name == 'all' else [name]
    for key in targets:
        b = BOTS[key]
        if _pids(b['match']):
            print(f'{b["label"]}: 已经在跑，跳过')
            continue
        console_log_path = os.path.join(DIR, b['console_log'])
        with open(console_log_path, 'a') as f:
            subprocess.Popen(b['cmd'], cwd=DIR, stdout=f, stderr=f,
                              stdin=subprocess.DEVNULL, start_new_session=True)
        print(f'{b["label"]}: 已启动')


def restart(name):
    stop(name)
    time.sleep(2)
    start(name)


if __name__ == '__main__':
    action = sys.argv[1] if len(sys.argv) > 1 else 'status'
    name = sys.argv[2] if len(sys.argv) > 2 else 'all'
    if name != 'all' and name not in BOTS:
        print(f'账号不存在: {name}，可选: {", ".join(BOTS.keys())}, all')
        sys.exit(1)
    if action == 'status':
        status()
    elif action == 'stop':
        stop(name)
    elif action == 'start':
        start(name)
    elif action == 'restart':
        restart(name)
    else:
        print(__doc__)
