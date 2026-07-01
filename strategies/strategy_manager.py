#!/usr/bin/env python3
"""
策略管理器
统一管理所有策略，提供API接口
"""

import os
import sys
import json
from datetime import datetime

# 策略模块路径
STRATEGY_PATH = os.path.dirname(os.path.abspath(__file__))

# ========== 策略注册表 ==========
STRATEGIES = {
    'etf_momentum': {
        'name': 'ETF动量轮动',
        'file': 'etf_momentum_strategy.py',  # 使用auto_trade.py的逻辑
        'type': '趋势类',
        'risk': '低',
        'target': '8-15%',
        'status': 'active',
    },
    'stock_momentum': {
        'name': '个股动量突破',
        'file': '../stock_auto_trade.py',
        'type': '趋势类',
        'risk': '高',
        'target': '20-40%',
        'status': 'active',
    },
    'mean_reversion': {
        'name': 'ETF均值回归',
        'file': 'mean_reversion_strategy.py',
        'type': '均值回归',
        'risk': '中',
        'target': '10-20%',
        'status': 'ready',
    },
    'sector_rotation': {
        'name': '板块轮动',
        'file': 'sector_rotation_strategy.py',
        'type': '事件驱动',
        'risk': '中',
        'target': '15-25%',
        'status': 'ready',
    },
}

def get_strategy_list():
    """获取策略列表"""
    return STRATEGIES

def run_strategy(strategy_id):
    """运行指定策略"""
    if strategy_id not in STRATEGIES:
        return {'error': f'策略 {strategy_id} 不存在'}
    
    strategy = STRATEGIES[strategy_id]
    strategy_file = os.path.join(STRATEGY_PATH, strategy['file'])
    
    if not os.path.exists(strategy_file):
        return {'error': f'策略文件不存在: {strategy_file}'}
    
    # 动态导入并执行
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(strategy_id, strategy_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        if hasattr(module, 'run_strategy'):
            result = module.run_strategy()
            return {
                'success': True,
                'strategy': strategy['name'],
                'result': result,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
        else:
            return {'error': f'策略模块缺少 run_strategy 函数'}
    except Exception as e:
        return {'error': f'策略执行失败: {str(e)}'}

def get_all_signals():
    """获取所有策略信号"""
    signals = {}
    for strategy_id in STRATEGIES:
        try:
            result = run_strategy(strategy_id)
            if result.get('success'):
                signals[strategy_id] = {
                    'name': STRATEGIES[strategy_id]['name'],
                    'signal': result['result'].get('signal', '观望'),
                    'timestamp': result['timestamp'],
                }
        except:
            signals[strategy_id] = {
                'name': STRATEGIES[strategy_id]['name'],
                'signal': '执行失败',
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
    return signals

def compare_strategies():
    """对比各策略表现"""
    print("=" * 60)
    print("策略对比分析")
    print("=" * 60)
    
    for sid, s in STRATEGIES.items():
        print(f"\n{s['name']} ({sid}):")
        print(f"   类型: {s['type']}")
        print(f"   风险: {s['risk']}")
        print(f"   目标: {s['target']}")
        print(f"   状态: {s['status']}")
    
    print("\n" + "=" * 60)
    print("推荐组合")
    print("=" * 60)
    print("短期冲刺: 个股动量突破 + 板块轮动")
    print("中期稳健: ETF动量轮动 + ETF均值回归")
    print("长期持有: ETF动量轮动 (主策略)")

if __name__ == "__main__":
    # 测试所有策略
    print("策略管理器测试")
    print("=" * 60)
    
    for sid in STRATEGIES:
        print(f"\n运行策略: {STRATEGIES[sid]['name']}")
        result = run_strategy(sid)
        if result.get('success'):
            print(f"   信号: {result['result'].get('signal', 'N/A')}")
        else:
            print(f"   错误: {result.get('error', '未知错误')}")
    
    print("\n" + "=" * 60)
    compare_strategies()