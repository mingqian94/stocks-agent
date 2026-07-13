import os
import subprocess
import time

ACCOUNTS = ['ht_7493', 'ht_8268']

def start_trade(account_id):
    env = os.environ.copy()
    env['CURRENT_ACCOUNT'] = account_id
    
    log_file = f'/Users/hetao/stocks_agent/auto_trade_{account_id}.log'
    
    process = subprocess.Popen(
        ['python3', 'auto_trade.py'],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd='/Users/hetao/stocks_agent'
    )
    
    return process, log_file

if __name__ == '__main__':
    processes = []
    
    for account in ACCOUNTS:
        print(f'启动账户: {account}')
        proc, log_file = start_trade(account)
        processes.append((account, proc, log_file))
        time.sleep(2)
    
    print(f'\n已启动 {len(processes)} 个账户盯盘')
    print('按 Ctrl+C 停止所有进程')
    
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print('\n正在停止所有进程...')
        for account, proc, _ in processes:
            proc.terminate()
            print(f'已停止: {account}')