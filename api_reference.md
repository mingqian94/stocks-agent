# 📊 AI 炒股策略日志

---

## 🎯 项目核心目标

| 项目 | 目标 |
|------|------|
| 核心策略 | 动量轮动 / 个股动量突破 |
| 目标收益 | 年化 8%+ |
| 最大回撤 | -30% 以内 |
| 市场范围 | A股 + ETF（不含港股、美股） |

## 🏦 账户配置与交易模式

| 账户 | 比赛 | 策略 | 目标收益 | 风险等级 | 交易模式 | 状态 |
|------|------|------|----------|----------|----------|------|
| 东方财富 | 东方财富杯 | 个股动量突破 | 10% | 高 | ⚡ 自动交易 | active |
| 华泰-7493 | 华泰证券杯 | ETF动量轮动（稳健型） | 8% | 低 | ⚡ 自动交易 | active |
| 华泰-8268 | 华泰证券杯 | ETF动量轮动（激进型） | 30% | 高 | ⚡ 自动交易 | active |
| 北师大中银杯 | 北师大中银杯 | 手动操作 | -- | -- | 🔔 手动模式 | pending |

**交易模式说明**：
- ⚡ **自动交易**：系统每3分钟自动检查行情，触发买入/卖出条件时自动下单
- 🔔 **手动模式**：系统仅生成交易提醒和策略建议，需用户手动确认后下单

**配置位置**：
- 账户基础配置：`accounts.py`（`auto_trade`字段控制）
- 前端展示：`dashboard.py` → `CONFIGS`（`auto_trade`字段）
- 自动交易脚本：`auto_trade.py`（运行时读取当前账户`auto_trade`值）

---

## 🔌 可用API接口汇总

### 1. 东方财富模拟交易API

**用途**：东方财富杯模拟交易账户

| 接口 | 方法 | 说明 |
|------|------|------|
| `https://mkapi2.dfcfs.com/finskillshub/api/claw/mockTrading` | POST | 模拟交易主接口 |

**认证方式**：
```python
headers = {
    'mx-api-key': 'mkt_heJbQPgu8rPWGeTnEcx479Si1TLyOOLa9ikQuKEN6N8',
    'Content-Type': 'application/json'
}
```

**支持操作**：
- `getAccountBalance` - 获取账户余额
- `getPositions` - 获取持仓
- `buy` - 买入
- `sell` - 卖出
- `getOrders` - 获取委托单

**示例**：
```python
data = {
    "action": "getAccountBalance",
    "data": {}
}
r = requests.post(url, headers=headers, json=data)
```

---

### 2. 华泰证券模拟交易API

**用途**：华泰证券杯模拟交易账户

| 接口 | 方法 | 说明 |
|------|------|------|
| `https://ai.zhangle.com/edge/entry/gate/api/simSkills/*` | POST | 模拟交易主接口 |

**认证方式**：
```python
headers = {
    'apiKey': 'ht_qabM0qimkZj86qF3h6Xr118Le88ByCZ5Mu1PDWPws',  # 7493账户
    # 或 'ht_033MHA9CvnXcZyanwx7qkU4AmLdyv8eIuTtrDOIoX',  # 8268账户
    'Content-Type': 'application/json',
    'skillCode': 'mx_1778741794549'
}
```

**支持操作**：
- `/api/simSkills/getAccountBalance` - 获取账户余额
- `/api/simSkills/getPositions` - 获取持仓
- `/api/simSkills/buy` - 买入
- `/api/simSkills/sell` - 卖出
- `/api/simSkills/getOrders` - 获取委托单
- `/api/simSkills/getQuote` - 获取行情（需传exchange参数）

**行情接口示例**：
```python
data = {
    'stockCode': '510050',
    'exchange': 'SH'  # SH=上海, SZ=深圳, BJ=北京
}
r = requests.post(url, json=data, headers=headers)
```

---

### 3. 腾讯行情API

**用途**：批量获取A股/ETF实时行情（公开接口，无需认证）

| 接口 | 方法 | 说明 |
|------|------|------|
| `http://qt.gtimg.cn/q=` | GET | 批量行情查询 |

**使用方式**：
```python
# 批量查询多个股票
codes = 'sh510050,sh510300,sz159915'  # sh=上海, sz=深圳
url = f'http://qt.gtimg.cn/q={codes}'
r = requests.get(url)

# 解析返回数据（~分隔）
lines = r.text.strip().split('\n')
for line in lines:
    parts = line.split('~')
    code = parts[2]      # 代码
    name = parts[1]      # 名称
    price = parts[3]     # 现价
    pct = parts[32]      # 涨跌幅
```

**优点**：
- 一次请求可查询多个股票
- 无频率限制
- 响应速度快

---

### 4. 东方财富行情API

**用途**：获取A股/ETF实时行情（公开接口，有频率限制）

| 接口 | 方法 | 说明 |
|------|------|------|
| `https://push2.eastmoney.com/api/qt/stock/get` | GET | 单个股票行情 |
| `https://push2.eastmoney.com/api/qt/clist/get` | GET | 股票列表行情 |

**使用方式**：
```python
# 单个股票
secid = '1.510050'  # 1=上海, 0=深圳
url = f'https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=f43,f60,f170'
headers = {
    'User-Agent': 'Mozilla/5.0',
    'Referer': 'https://quote.eastmoney.com/'
}
r = requests.get(url, headers=headers)

# 股票列表（涨幅榜）
url = 'https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=50&po=1&np=1&fltt=2&invt=2&fid=f3&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23&fields=f12,f14,f2,f3,f6'
```

**注意**：
- 需要添加User-Agent和Referer头
- 频繁请求会被限制，建议使用腾讯行情接口

---

## 📁 项目文件结构

```
/Users/hetao/Documents/stocks/
├── accounts.py              # 账户和策略配置表
├── dashboard.py             # Flask监控面板
├── templates/
│   └── dashboard.html       # 前端页面
├── auto_trade.py            # ETF动量轮动自动交易脚本
├── stock_auto_trade.py      # 个股动量突破自动交易脚本
├── strategy_log.md          # 策略日志文档
├── api_reference.md         # API接口文档（本文件）
├── period_data.json         # 期数数据
├── select-stock/            # 华泰选股工具
├── watchlist-management/    # 华泰自选股管理工具
└── strategies/              # 策略模块
```

---

## 🚀 快速启动

### 启动监控面板
```bash
cd /Users/hetao/Documents/stocks
python3 dashboard.py
# 访问 http://localhost:5000/
```

### 启动自动交易（ETF策略）
```bash
nohup python3 auto_trade.py >> auto_trade.log 2>&1 &
```

### 启动自动交易（个股策略）
```bash
nohup python3 stock_auto_trade.py >> stock_trade.log 2>&1 &
```

---

## 📊 策略说明

### ETF动量轮动策略

**适用账户**：华泰-7493（稳健型）、华泰-8268（激进型）

**策略逻辑**：
1. 每3分钟获取22只ETF实时涨跌幅
2. 买入动量排名前2且涨幅为正的ETF
3. 持仓不在Top2且跌幅<-0.5%时，减半仓换强势标的
4. 止损：单只ETF当日跌幅≥3%时提醒减仓

**ETF池**：
- 宽基(5)：上证50、沪深300、中证500、中证1000、科创50
- 科技(3)：半导体、芯片、科创芯片
- 金融(2)：证券、银行
- 医药(2)：医药、医疗
- 新能源(3)：新能源车、光伏、新能源
- 消费(2)：酒、房地产
- 周期(2)：有色金属、有色
- 军工传媒(3)：军工、传媒、中概互联

---

### 个股动量突破策略

**适用账户**：东方财富

**策略逻辑**：
1. 每3分钟扫描A股涨幅榜
2. 筛选条件：涨幅3%-12%，成交额>2亿
3. 买入符合条件的个股（最大持仓1只，仓位95%）
4. 止损：-7%
5. 止盈：+20%

**风险等级**：高（集中持仓单只个股）

---

## 📝 更新日志

### 2026-06-16
- ✅ 新增个股动量突破策略
- ✅ 东方财富账户切换为个股策略
- ✅ 华泰账户使用华泰行情接口
- ✅ 整理API接口文档
- ✅ 修复Dashboard显示bug

### 2026-06-15
- ✅ 创建accounts.py统一配置管理
- ✅ Dashboard根据账户动态渲染策略面板
- ✅ 华泰双账户支持

### 2026-06-11
- ✅ 华泰证券杯开赛
- ✅ 启动ETF动量轮动策略

### 2026-06-08
- ✅ 东方财富杯开赛
- ✅ 项目初始化
