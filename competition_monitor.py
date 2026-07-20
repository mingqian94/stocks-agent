#!/usr/bin/env python3
"""
AI量化炒股 - 模拟盘比赛监控系统
监控并记录可参加的模拟盘比赛
"""

import json
import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
COMPETITIONS_FILE = BASE_DIR / "competitions.json"

# ========================================
# 定时搜索配置
# ========================================

# 比赛雷达搜索时间配置
# cron格式: 分钟 小时 日期 月份 星期
# 每周一和周四上午10点搜索新比赛
SEARCH_SCHEDULE = [
    {"hour": 10, "weekday": 0},  # 周一 (0=周一)
    {"hour": 10, "weekday": 3},  # 周四 (3=周四)
]

def should_search_now():
    """检查当前是否是预设的搜索时间"""
    now = datetime.datetime.now()
    hour = now.hour
    weekday = now.weekday()  # 0=周一, 1=周二, ..., 4=周五
    
    for schedule in SEARCH_SCHEDULE:
        if hour == schedule['hour'] and weekday == schedule['weekday']:
            return True
    return False

# ========================================
# 比赛数据库（实时更新）
# ========================================

# 筛选原则：面向公众 + 支持AI自动参与（或有明确AI功能）
COMPETITIONS = {
    "dongfang": {
        "name": "东方财富模拟交易",
        "full_name": "东方财富模拟炒股大赛",
        "platform": "东方财富",
        "type": "模拟盘",
        "market": "A股/ETF",
        "initial_fund": 1000000,
        "start_date": "2026-06-08",
        "end_date": "2026-06-12",
        "status": "进行中",
        "entry": "东方财富App - 金融挑战赛",
        "api_supported": True,
        "ai_mode": "自动交易",
        "priority": 1,
        "notes": "已报名"
    },
    "huatai": {
        "name": "华泰柏瑞杯ETF AI交易巅峰赛",
        "full_name": "华泰柏瑞杯·全国首届ETF AI交易巅峰赛",
        "platform": "华泰证券/华泰柏瑞",
        "type": "模拟盘",
        "market": "ETF",
        "initial_fund": 1000000,
        "start_date": "2026-06-11",
        "end_date": "2026-07-20",
        "status": "即将开始",
        "entry": "涨乐财富通App / AI涨乐App / 活动H5",
        "api_supported": True,
        "ai_mode": "AI Agent自动",
        "priority": 1,
        "notes": "国内首个面向AI智能体的ETF模拟交易赛事，6月5日已开放报名"
    },
    "renji": {
        "name": "人机交易模拟大赛",
        "full_name": "2026人机交易模拟大赛",
        "platform": "未知",
        "type": "模拟盘",
        "market": "A股",
        "initial_fund": 1000000,
        "start_date": "即将启动",
        "end_date": "待定",
        "status": "倒计时",
        "entry": "关注公众号/头条号获取报名通道",
        "api_supported": False,
        "ai_mode": "AI对决模式（手动）",
        "priority": 2,
        "notes": "人脑vs AI同台竞技，百万虚拟资金，真实A股行情"
    },
}

# ========================================
# 搜索关键词库
# ========================================

SEARCH_KEYWORDS = [
    "AI量化炒股模拟比赛",
    "ETF模拟交易大赛",
    "华泰柏瑞杯 AI交易",
    "模拟炒股比赛",
    "人机交易模拟大赛",
    "AI Agent 投资比赛",
    "全国模拟股票大赛",
]

# ========================================
# 函数
# ========================================

def save_competitions():
    """保存比赛数据库到JSON文件"""
    with open(COMPETITIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(COMPETITIONS, f, ensure_ascii=False, indent=2)
    print(f"✅ 比赛数据库已保存: {COMPETITIONS_FILE}")

def load_competitions():
    """从JSON文件加载比赛数据库"""
    if COMPETITIONS_FILE.exists():
        with open(COMPETITIONS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        COMPETITIONS.update(data)
        print(f"✅ 已加载 {len(data)} 个比赛")
    else:
        print(f"ℹ️  {COMPETITIONS_FILE} 不存在，使用默认数据")

def add_competition(key, **kwargs):
    """添加新比赛"""
    COMPETITIONS[key] = kwargs
    save_competitions()
    print(f"✅ 已添加比赛: {kwargs.get('name', key)}")

def show_competitions():
    """显示所有比赛"""
    print("\n" + "="*70)
    print("📊 AI量化炒股 - 模拟盘比赛总览")
    print("="*70)
    
    # 按优先级排序
    sorted_items = sorted(COMPETITIONS.items(), key=lambda x: x[1].get('priority', 99))
    
    for i, (key, comp) in enumerate(sorted_items, 1):
        status_icon = "🟢" if comp['status'] == "进行中" else ("🟡" if "即将" in comp['status'] else "🔵")
        
        print(f"\n{status_icon} [{i}] {comp['name']} (优先级: {comp['priority']})")
        print(f"    平台: {comp['platform']}")
        print(f"    类型: {comp['type']} | 市场: {comp['market']}")
        print(f"    初始资金: {comp['initial_fund']:,.0f}元")
        print(f"    时间: {comp['start_date']} ~ {comp['end_date']}")
        print(f"    状态: {comp['status']}")
        print(f"    AI模式: {comp['ai_mode']}")
        if comp.get('api_supported'):
            print(f"    自动化: ✅ 支持API自动交易")
        else:
            print(f"    自动化: ⚠️ 需手动")
        print(f"    入口: {comp['entry']}")
        if comp.get('notes'):
            print(f"    备注: {comp['notes']}")
    
    print(f"\n共 {len(COMPETITIONS)} 个比赛")
    print("="*70)

def show_active_competitions():
    """显示正在进行中或即将开始的比赛"""
    today = datetime.date.today()
    print("\n" + "="*70)
    print(f"🎯 当前关注的比赛 ({today.strftime('%Y-%m-%d')})")
    print("="*70)
    
    active = [(k, v) for k, v in COMPETITIONS.items() 
              if v['status'] in ['进行中', '即将开始', '可报名']]
    
    active.sort(key=lambda x: x[1].get('priority', 99))
    
    for key, comp in active:
        status_icon = "🟢" if comp['status'] == "进行中" else "🟡"
        fund_wan = comp['initial_fund'] / 10000
        
        print(f"\n{status_icon} {comp['name']}")
        print(f"    📅 {comp['start_date']} ~ {comp['end_date']}")
        print(f"    💰 {fund_wan:.0f}万 | {comp['market']} | {comp['ai_mode']}")
        if comp.get('notes'):
            print(f"    📝 {comp['notes']}")
    
    print(f"\n共 {len(active)} 个活跃比赛")
    print("="*70)

def get_upcoming_competitions():
    """获取即将开始的比赛（30天内）"""
    today = datetime.date.today()
    upcoming = []
    
    for key, comp in COMPETITIONS.items():
        if comp['status'] in ['即将开始', '待开始', '可报名']:
            try:
                start = datetime.datetime.strptime(comp['start_date'], '%Y-%m-%d').date()
                days_left = (start - today).days
                if 0 <= days_left <= 30:
                    upcoming.append((key, comp, days_left))
            except:
                pass
    
    if upcoming:
        upcoming.sort(key=lambda x: x[2])
        print(f"\n⏰ 30天内即将开始的比赛:")
        for key, comp, days in upcoming:
            print(f"  • {comp['name']}: {days}天后开始 ({comp['start_date']})")
    else:
        print(f"\nℹ️  30天内暂无新比赛")

def generate_markdown():
    """生成比赛汇总Markdown文档"""
    md_file = BASE_DIR / "competitions_summary.local.md"  # 含真实收益数据，不提交（见.gitignore）
    
    lines = []
    lines.append("# 📊 AI量化炒股 - 模拟盘比赛汇总")
    lines.append("")
    lines.append(f"_更新时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_")
    lines.append("")
    
    # 比赛总览表
    lines.append("## 🏆 比赛总览")
    lines.append("")
    lines.append("| 比赛 | 平台 | 类型 | 市场 | 初始资金 | 时间 | 状态 | AI模式 |")
    lines.append("|------|------|------|------|----------|------|------|--------|")
    
    sorted_items = sorted(COMPETITIONS.items(), key=lambda x: x[1].get('priority', 99))
    for key, comp in sorted_items:
        lines.append(f"| {comp['name']} | {comp['platform']} | {comp['type']} | {comp['market']} | {comp['initial_fund']:,}元 | {comp['start_date']}~{comp['end_date']} | {comp['status']} | {comp['ai_mode']} |")
    
    lines.append("")
    
    # 详细信息
    lines.append("## 📋 详细信息")
    for key, comp in sorted_items:
        lines.append("")
        lines.append(f"### {comp['name']}")
        lines.append(f"- **全称**: {comp['full_name']}")
        lines.append(f"- **平台**: {comp['platform']}")
        lines.append(f"- **类型**: {comp['type']}")
        lines.append(f"- **市场**: {comp['market']}")
        lines.append(f"- **初始资金**: {comp['initial_fund']:,}元")
        lines.append(f"- **时间**: {comp['start_date']} ~ {comp['end_date']}")
        lines.append(f"- **状态**: {comp['status']}")
        lines.append(f"- **参赛入口**: {comp['entry']}")
        lines.append(f"- **AI模式**: {comp['ai_mode']}")
        lines.append(f"- **支持自动交易**: {'✅ 是' if comp.get('api_supported') else '⚠️ 需手动'}")
        if comp.get('notes'):
            lines.append(f"- **备注**: {comp['notes']}")
    
    # 搜索关键词
    lines.append("")
    lines.append("## 🔍 搜索关键词")
    lines.append("")
    for kw in SEARCH_KEYWORDS:
        lines.append(f"- {kw}")
    
    content = '\n'.join(lines)
    
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ Markdown文档已生成: {md_file}")
    return md_file

# ========================================
# 主程序
# ========================================

if __name__ == '__main__':
    import sys
    
    # 加载已有数据
    load_competitions()
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == 'list':
            show_competitions()
        elif cmd == 'active':
            show_active_competitions()
            get_upcoming_competitions()
        elif cmd == 'md':
            generate_markdown()
        elif cmd == 'save':
            save_competitions()
        else:
            print(f"❌ 未知命令: {cmd}")
            print("可用命令: list / active / md / save")
    else:
        # 默认：显示活跃比赛 + 提醒
        show_active_competitions()
        get_upcoming_competitions()
        
        # 生成最新Markdown
        generate_markdown()
        
        # 保存数据
        save_competitions()
