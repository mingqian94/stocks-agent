#!/usr/bin/env python3
"""
AKShare数据获取模块
使用curl方式获取数据（绕过Python requests连接问题）
"""

import subprocess
import json
import pandas as pd

def get_stock_list():
    """获取A股实时行情"""
    try:
        cmd = [
            'curl', '-s',
            'https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=5000&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f3&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23&fields=f2,f3,f4,f5,f6,f12,f14,f15,f16,f17,f18,f20,f21',
            '-H', 'User-Agent: Mozilla/5.0'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        data = json.loads(result.stdout)
        
        stocks = []
        for item in data.get('data', {}).get('diff', []):
            if item.get('f12'):
                stocks.append({
                    'code': str(item.get('f12', '')),
                    'name': item.get('f14', ''),
                    'price': item.get('f2', 0) or 0,
                    'pct': (item.get('f3', 0) or 0) / 100,
                    'change': item.get('f4', 0) or 0,
                    'volume': item.get('f5', 0) or 0,
                    'amount': item.get('f6', 0) or 0,
                    'high': item.get('f15', 0) or 0,
                    'low': item.get('f16', 0) or 0,
                    'open': item.get('f17', 0) or 0,
                    'prev_close': item.get('f18', 0) or 0,
                    'market_cap': (item.get('f20', 0) or 0) / 10000,
                    'circulating_cap': (item.get('f21', 0) or 0) / 10000,
                })
        return pd.DataFrame(stocks)
    except Exception as e:
        print(f"获取股票列表失败: {e}")
        return pd.DataFrame()

def get_stock_hist(code, days=30):
    """获取个股历史数据"""
    try:
        secid = f"0.{code}" if code.startswith('0') or code.startswith('3') else f"1.{code}"
        cmd = [
            'curl', '-s',
            f'https://push2his.eastmoney.com/api/qt/stock/kline/get?secid={secid}&fields1=f1,f2,f3,f4,f5&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=1&lmt={days}',
            '-H', 'User-Agent: Mozilla/5.0'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        data = json.loads(result.stdout)
        
        klines = data.get('data', {}).get('klines', [])
        records = []
        for kline in klines:
            parts = kline.split(',')
            records.append({
                'date': parts[0],
                'open': float(parts[1]),
                'close': float(parts[2]),
                'high': float(parts[3]),
                'low': float(parts[4]),
                'volume': int(parts[5]),
                'amount': float(parts[6]),
                'amplitude': float(parts[7]),
                'pct': float(parts[8]),
                'change': float(parts[9]),
                'turnover': float(parts[10]) if len(parts) > 10 else 0,
            })
        return pd.DataFrame(records)
    except Exception as e:
        print(f"获取历史数据失败: {e}")
        return pd.DataFrame()

if __name__ == "__main__":
    print("=== AKShare数据获取测试 ===")
    
    print("\n1. 获取A股实时行情...")
    df = get_stock_list()
    print(f"获取到 {len(df)} 只股票")
    if not df.empty:
        print(df[['code', 'name', 'price', 'pct']].head(10))
    
    print("\n2. 获取个股历史数据...")
    hist = get_stock_hist('000001', days=5)
    print(f"获取到 {len(hist)} 条记录")
    if not hist.empty:
        print(hist)