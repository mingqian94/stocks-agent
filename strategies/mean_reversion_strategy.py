#!/usr/bin/env python3
"""
ETF均值回归策略
原理：买入跌幅较大的ETF，等待反弹
适合：市场震荡期，抄底反弹
"""

import requests
import json
from datetime import datetime

# ========== 策略参数 ==========
ETFS = {
    '510300': '沪深300ETF', '510500': '中证500ETF', '512100': '中证1000ETF',
    '159915': '创业板ETF', '588000': '科创50ETF', '512480': '半导体ETF',
    '512760': '芯片ETF', '512690': '酒ETF', '512980': '传媒ETF',
    '515790': '光伏ETF', '516160': '新能源ETF', '512400': '有色金属ETF'
}

MIN_DROP = -0.03    # 最小跌幅3%
MAX_DROP = -0.10    # 最大跌幅10%（排除暴跌）
STOP_LOSS = -0.05   # 止损5%
TAKE_PROFIT = 0.05  # 止盈5%
MAX_POSITIONS = 3   # 最大持仓3只
POSITION_SIZE = 0.30 # 每只30%

def get_etf_quotes():
    """获取ETF行情"""
    quotes = []
    for code in ETFS:
        try:
            secid = f"1.{code}" if code.startswith('5') else f"0.{code}"
            url = f"https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=f43,f60,f170,f44,f45,f46"
            r = requests.get(url, timeout=5)
            d = r.json().get('data', {})
            if d:
                pct = (d.get('f170', 0) or 0) / 100
                price = d.get('f43', 0) or 0
                if price > 0:
                    quotes.append({
                        'code': code,
                        'name': ETFS[code],
                        'price': price / 100 if price > 1000 else price,
                        'pct': pct,
                    })
        except:
            continue
    return quotes

def select_oversold(quotes):
    """选出超跌ETF"""
    candidates = []
    for q in quotes:
        pct = q.get('pct', 0)
        # 跌幅在3%-10%之间
        if pct >= MIN_DROP and pct <= MAX_DROP:
            candidates.append({
                'code': q['code'],
                'name': q['name'],
                'price': q['price'],
                'pct': pct,
                'drop_score': abs(pct) * 100,  # 跌幅越大得分越高
            })
    
    # 按跌幅排序（跌幅越大优先）
    candidates.sort(key=lambda x: x['drop_score'], reverse=True)
    return candidates[:MAX_POSITIONS]

def run_strategy():
    """运行策略"""
    print("=" * 60)
    print("ETF均值回归策略")
    print("=" * 60)
    print(f"选股条件: 跌幅{MIN_DROP*100}% ~ {MAX_DROP*100}%")
    print(f"止盈: {TAKE_PROFIT*100}% | 止损: {STOP_LOSS*100}%")
    print("=" * 60)
    
    quotes = get_etf_quotes()
    print(f"\n📊 ETF行情获取: {len(quotes)}只")
    
    # 按涨幅排序
    quotes.sort(key=lambda x: x['pct'], reverse=True)
    print("\n📈 今日涨幅排名:")
    for i, q in enumerate(quotes[:5]):
        print(f"   {i+1}. {q['name']}: {q['pct']*100:+.2f}%")
    
    # 选出超跌ETF
    oversold = select_oversold(quotes)
    
    if oversold:
        print("\n🎯 超跌ETF推荐（抄底机会）:")
        for i, s in enumerate(oversold):
            print(f"   {i+1}. {s['name']}({s['code']})")
            print(f"      跌幅: {s['pct']*100:.2f}%")
            print(f"      建议: 等反弹5%卖出")
    else:
        print("\n⚠️ 今日无超跌ETF（跌幅<3%或>10%）")
        print("   建议: 观望，等待回调机会")
    
    return {
        'quotes': quotes,
        'oversold': oversold,
        'signal': '买入超跌' if oversold else '观望',
    }

if __name__ == "__main__":
    run_strategy()