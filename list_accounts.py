from accounts import list_accounts

accounts = list_accounts()
print('📋 所有账户列表')
print('=' * 60)
for aid, info in accounts.items():
    status_icon = {
        'active': '✅',
        'pending': '⏳',
        'completed': '🏁'
    }.get(info['status'], '❓')
    name = info['name']
    competition = info['competition']
    period = info['period']
    strategy = info['strategy']
    target = info['target_return'] * 100
    risk = info['risk_level']
    status = info['status']
    print(f'{status_icon} {name}')
    print(f'   比赛: {competition}')
    print(f'   周期: {period}')
    print(f'   策略: {strategy}')
    print(f'   目标: {target:.0f}% | 风险: {risk}')
    print(f'   状态: {status}')
    print()