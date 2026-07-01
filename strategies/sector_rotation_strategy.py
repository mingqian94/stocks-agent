#!/usr/bin/env python3
"""
板块轮动策略
原理：追踪热点板块，买入板块龙头
适合：结构性行情，板块轮动明显
"""

import requests
import json
from datetime import datetime

# ========== 策略参数 ==========
SECTOR_THRESHOLD = 0.02   # 板块涨幅阈值2%
MAX_POSITIONS = 3         # 最大持仓3只
POSITION_SIZE = 0.25      # 每只25%
STOP_LOSS = -0.05         # 止损5%
TAKE_PROFIT = 0.10        # 止盈10%

# 板块代码映射
SECTORS = {
    'BK0477': '半导体', 'BK0428': '芯片', 'BK0493': '光伏',
    'BK0429': '锂电池', 'BK0430': '新能源车', 'BK0431': '白酒',
    'BK0432': '医药', 'BK0433': '银行', 'BK0434': '券商',
    'BK0435': '房地产', 'BK0436': '钢铁', 'BK0437': '煤炭',
    'BK0438': '有色金属', 'BK0439': '化工', 'BK0440': '建材',
    'BK0441': '机械', 'BK0442': '电力', 'BK0443': '通信',
    'BK0444': '计算机', 'BK0445': '传媒', 'BK0446': '军工'
}

def get_sector_quotes():
    """获取板块行情"""
    quotes = []
    for code, name in SECTORS.items():
        try:
            url = f"https://push2.eastmoney.com/api/qt/clist/get"
            params = {
                "pn": 1, "pz": 1,
                "fs": f"b:{code}",
                "fields": "f1,f2,f3,f4,f5,f6,f12,f14"
            }
            r = requests.get(url, params=params, timeout=5)
            d = r.json().get('data', {}).get('diff', [])
            if d:
                item = d[0]
                pct = (item.get('f3', 0) or 0) / 100
                quotes.append({
                    'code': code,
                    'name': name,
                    'pct': pct,
                })
        except:
            continue
    return quotes

def get_sector_leaders(sector_code):
    """获取板块龙头股"""
    try:
        url = f"https://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": 1, "pz": 10,
            "fs": f"b:{sector_code}+f:!50",
            "fields": "f1,f2,f3,f4,f5,f6,f12,f14,f15,f16"
        }
        r = requests.get(url, params=params, timeout=10)
        d = r.json().get('data', {}).get('diff', [])
        
        leaders = []
        for item in d[:3]:
            pct = (item.get('f3', 0) or 0) / 100
            price = item.get('f2', 0) or 0
            if price > 0 and pct > 0:
                leaders.append({
                    'code': item.get('f12', ''),
                    'name': item.get('f14', ''),
                    'price': price,
                    'pct': pct,
                })
        return leaders
    except:
        return []

def run_strategy():
    """运行策略"""
    print("=" * 60)
    print("板块轮动策略")
    print("=" * 60)
    print(f"板块涨幅阈值: {SECTOR_THRESHOLD*100}%")
    print(f"止盈: {TAKE_PROFIT*100}% | 止损: {STOP_LOSS*100}%")
    print("=" * 60)
    
    # 获取板块行情
    sectors = get_sector_quotes()
    print(f"\n📊 板块行情获取: {len(sectors)}个")
    
    # 按涨幅排序
    sectors.sort(key=lambda x: x['pct'], reverse=True)
    
    print("\n📈 今日板块涨幅Top5:")
    for i, s in enumerate(sectors[:5]):
        print(f"   {i+1}. {s['name']}: {s['pct']*100:+.2f}%")
    
    # 选出热点板块
    hot_sectors = [s for s in sectors if s['pct'] >= SECTOR_THRESHOLD]
    
    if hot_sectors:
        print(f"\n🔥 热点板块（涨幅>{SECTOR_THRESHOLD*100}%）:")
        for s in hot_sectors[:3]:
            print(f"   {s['name']}: {s['pct']*100:+.2f}%")
            
            # 获取板块龙头
            leaders = get_sector_leaders(s['code'])
            if leaders:
                print(f"   龙头股:")
                for l in leaders:
                    print(f"      - {l['name']}({l['code']}): {l['pct']*100:+.2f}%")
    else:
        print("\n⚠️ 今日无热点板块（涨幅<2%）")
        print("   建议: 观望，等待板块轮动机会")
    
    return {
        'sectors': sectors,
        'hot_sectors': hot_sectors,
        'signal': '买入龙头' if hot_sectors else '观望',
    }

if __name__ == "__main__":
    run_strategy()