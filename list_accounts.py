from accounts import get_accounts_for_dashboard

accounts = get_accounts_for_dashboard()
print('📋 所有账户列表')
print('=' * 60)
for info in accounts:
    status_icon = {
        'active': '✅',
        'pending': '⏳',
        'completed': '🏁'
    }.get(info['status'], '❓')
    name = info['name']
    competition = info['competition']
    round_name = info['round']
    period = info['period']
    strategy = info['strategy']['name']
    target = (info['strategy']['target_return'] or 0) * 100
    risk = info['strategy']['risk_level']
    status = info['status']
    print(f'{status_icon} {name}')
    print(f'   比赛: {competition} ({round_name})')
    print(f'   周期: {period}')
    print(f'   策略: {strategy}')
    print(f'   目标: {target:.0f}% | 风险: {risk}')
    print(f'   状态: {status}')
    print()