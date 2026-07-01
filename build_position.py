#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""东方财富模拟组合快速建仓脚本"""

import os
import json
import subprocess

MX_APIKEY = os.environ.get('MX_APIKEY', '')
MX_API_URL = 'https://mkapi2.dfcfs.com/finskillshub'

def trade(stock_code, quantity):
    """执行买入操作"""
    payload = {
        'type': 'buy',
        'stockCode': stock_code,
        'quantity': quantity,
        'useMarketPrice': True,
    }
    url = f"{MX_API_URL}/api/claw/mockTrading/trade"
    
    cmd = [
        'curl', '-s', '-X', 'POST', url,
        '-H', f'apikey: {MX_APIKEY}',
        '-H', 'Content-Type: application/json; charset=UTF-8',
        '-d', json.dumps(payload)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            print(f"[ERROR] curl failed: {result.stderr}")
            return None
        return json.loads(result.stdout)
    except Exception as e:
        print(f"[ERROR] API request failed: {e}")
        return None

def get_positions():
    """获取持仓"""
    url = f"{MX_API_URL}/api/claw/mockTrading/positions"
    cmd = [
        'curl', '-s', '-X', 'POST', url,
        '-H', f'apikey: {MX_APIKEY}',
        '-H', 'Content-Type: application/json',
        '-d', '{"moneyUnit": 1}'
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return json.loads(result.stdout) if result.returncode == 0 else None
    except Exception as e:
        print(f"[ERROR] get positions failed: {e}")
        return None

def main():
    print("="*50)
    print("🏁 开始东方财富模拟组合建仓")
    print("="*50)
    
    if not MX_APIKEY:
        print("[ERROR] MX_APIKEY 未配置")
        return
    
    # 建仓计划
    positions = [
        {'code': '510300', 'name': '沪深300ETF', 'qty': 60000},  # 30万左右，市价约5元
        {'code': '159915', 'name': '创业板ETF', 'qty': 100000}, # 25万左右，市价约2.5元
        {'code': '588000', 'name': '科创50ETF', 'qty': 130000}, # 20万左右，市价约1.5元
        {'code': '510500', 'name': '中证500ETF', 'qty': 30000},  # 25万左右，市价约8.5元
    ]
    
    for pos in positions:
        print(f"\n👉 买入 {pos['name']} ({pos['code']}) 数量: {pos['qty']}")
        result = trade(pos['code'], pos['qty'])
        
        if result:
            code = result.get('code')
            if code in ['0', 0, '200', 200]:
                order_id = result.get('data', {}).get('orderId', '')
                print(f"   ✅ 委托成功！单号: {order_id}")
            else:
                msg = result.get('message', '未知错误')
                print(f"   ❌ 委托失败: {msg}")
        else:
            print(f"   ❌ 请求失败")
    
    print("\n" + "="*50)
    print("📊 查询最终持仓情况...")
    print("="*50)
    
    pos_result = get_positions()
    if pos_result:
        print(json.dumps(pos_result, ensure_ascii=False, indent=2))
    
    print("\n🎉 建仓完成！")
    print("周末我们复盘，优化策略！")

if __name__ == '__main__':
    main()

