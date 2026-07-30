# 比赛周期战绩数据 —— 示例文件
# 复制此文件为 periods_local.py 并填入真实的初始/期末资金、收益率
# periods_local.py 已加入 .gitignore，不会被提交
#
# rank/market_pct/excess_pct 是可选字段（没有就不填，或者填None）：
#   rank        比赛官方排名榜给的名次
#   market_pct  同期沪深300累计涨跌幅（可以用baostock查sh.000300），当参照系
#   excess_pct  profit_pct - market_pct，跑赢/跑输大盘的幅度——2026.07.30复盘发现这个比
#               profit_pct本身更能反映真实排名水平（详见STRATEGIES.md），复盘时建议都填上
PERIODS = {
    'east_money': [
        {'round': '第1期', 'period': 'MM.DD-MM.DD', 'initial': 1000000, 'final': 1000000, 'profit_pct': 0.00, 'status': 'active', 'rank': None, 'market_pct': None, 'excess_pct': None},
    ],
    'ht_7493': [
        {'round': '初赛', 'period': 'YYYY.MM.DD - YYYY.MM.DD', 'initial': 1000000, 'final': None, 'profit_pct': None, 'status': 'active'},
    ],
    'ht_8268': [
        {'round': '初赛', 'period': 'YYYY.MM.DD - YYYY.MM.DD', 'initial': 1000000, 'final': None, 'profit_pct': None, 'status': 'active'},
    ],
}
