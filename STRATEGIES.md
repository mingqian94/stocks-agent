# 📊 AI 炒股策略说明

---

## 🎯 项目核心目标

| 项目 | 目标 |
|------|------|
| 核心策略 | 动量轮动 / 个股动量突破 |
| 目标收益 | 年化 8%+ |
| 最大回撤 | -30% 以内 |
| 市场范围 | A股 + ETF（不含港股、美股） |

---

## 🏦 账户配置

| 账户 | 比赛 | 策略 | 目标收益 | 风险等级 | 交易模式 | 状态 |
|------|------|------|----------|----------|----------|------|
| 东方财富 | 东方财富杯 | 个股动量突破 | 10% | 高 | ⚡ 自动交易 | 详见`periods_local.py`（不提交） |
| 华泰-7493 | 华泰证券杯 | ETF动量轮动（稳健型） | 8% | 低 | ⚡ 自动交易 | active |
| 华泰-8268 | 华泰证券杯 | ETF动量轮动（激进型） | 30% | 高 | ⚡ 自动交易 | active |

**配置位置**：`accounts.py`，拆成三张互相独立的表——
- `ACCOUNTS`：账号身份（平台、api_key、绑定的策略），基本不变
- `STRATEGIES`：策略参数，调策略才改
- `PERIODS`：每期比赛的起止/初始/期末资金战绩，东方财富每周一期，跨周时 `ensure_current_period()` 会用实时总资产自动结算上一期、开下一期，不用再手改文件

---

## 📈 历史收益

> 真实的每期战绩数字在 `periods_local.py`（已加入 `.gitignore`，不提交）；这里不再重复维护一份带真实数字的表，避免每次换期都要记得脱敏。下面只是格式示例：

| 期数 | 时间 | 初始资金 | 期末资金 | 收益率 | 策略 |
|------|------|----------|----------|--------|------|
| 第N期 | MM.DD-MM.DD | 100万 | 进行中 | -- | 个股动量突破 |
| 第N-1期 | MM.DD-MM.DD | 100万 | 100万 | **+0.00%** | 个股动量突破 |

> ⚠️ **参赛规则**：东方财富比赛**每周必须有买入交易**才算参赛，否则视为弃权。判定标准是"本周有没有买入"这一个动作——只卖出、只持有都不算，哪怕账户在赚钱。
>
> ⚠️ **这条规则和策略纪律会打架**：`stock_momentum` 策略只有涨幅3-12%、成交额>2亿的候选股才买入，如果一周内一直没有股票满足条件，策略会"正确地"什么都不做——但这样这一周就会被判定弃权。策略的风控纪律和比赛的参赛门槛是两件独立的事，自动交易脚本目前不会替你兜底检查"这周还没买过"，需要人工留意（比如周中/周四check一下`stock_trade.log`有没有买入记录，没有就手动买一笔再决定要不要留仓）。
>
> ⚠️ **曾发生过"裸持仓到期"事故**：三个账号的自动交易脚本在 2026-07-02 14:31 同时因写日志权限错误崩溃，之后一周没有任何脚本重启或调仓（具体期数和收益数字见`periods_local.py`）。已在 `accounts.py`、`auto_trade.py`、`stock_auto_trade.py` 加了写日志失败不崩进程的兜底，并重新拉起了三个进程。

---

## 📌 策略详解

### 1. ETF动量轮动（稳健型）

**账户**：华泰-7493

**逻辑**：监测22只ETF实时涨跌幅，买入动量排名前2且涨幅为正的标的，卖出弱势标的

**参数**：

| 参数 | 值 |
|------|-----|
| 监测ETF数量 | 22只 |
| 持仓上限 | 3只 |
| 每只仓位 | 33.3%（3只满仓，不留现金缓冲——没有补仓策略不需要） |
| 止损线 | -3% |
| 买入条件 | 动量排名前2 + 涨幅>0 |
| 卖出条件 | 不在Top2 且 涨幅<0 |
| 轮询间隔 | **30分钟**（华泰API配额限制） |

**自动操作**：
- 持仓跌-3% → 自动减半仓
- 持仓不在Top2且涨幅<0 → 自动减半仓
- 有可用资金且Top标的符合条件 → 自动买入

**脚本**：`auto_trade.py ht_7493`

---

### 2. ETF动量轮动（激进型）

**账户**：华泰-8268

**逻辑**：监测ETF和行业板块动量，集中持仓高动量标的，追求高收益

**参数**：

| 参数 | 值 |
|------|-----|
| 监测ETF数量 | 22只 |
| 持仓上限 | 2只 |
| 每只仓位 | 50%（2只满仓，不留现金缓冲——没有补仓策略不需要） |
| 止损线 | -5% |
| 买入条件 | 动量排名前2 + 涨幅>0 |
| 卖出条件 | 不在Top2 且 涨幅<0 |
| 轮询间隔 | **30分钟**（华泰API配额限制） |

**自动操作**：
- 持仓跌-5% → 自动减半仓
- 持仓不在Top2且涨幅<0 → 自动减半仓
- 有可用资金且Top标的符合条件 → 自动买入
- **收益地板**：本期收益跌到+8%以下 → 立即清仓保护，本期剩余时间不再买入

**脚本**：`auto_trade.py ht_8268`

> ⚠️ **2026-07-09 之前的说明**：这份文档一直是这么写的，但代码里稳健/激进两个账户实际共用同一套`STOP_LOSS_DAY_PCT`/`MOMENTUM_TOP_N`模块常量，`STRATEGIES`字典配的这些参数从未被读取过——也就是说8268实际跑的是跟7493完全一样的风控。已修复：`AutoTrader.__init__`现在真的从`self.strategy`读取`max_positions`/`stop_loss`，8268按这里写的参数集中到Top2、止损放宽到-5%；新增的收益地板也是这次一起加的。

---

### 3. 个股动量突破

**账户**：东方财富

**逻辑**：监测A股实时涨跌幅，买入动量排名前列的强势个股，止损-5%，止盈+8%

**参数**（2026-07-09调整，落地第13期复盘时写的建议——见下方说明）：

| 参数 | 值 |
|------|-----|
| 最小涨幅 | 3% |
| 最大涨幅 | 12% |
| 最小成交额 | 2亿 |
| 持仓上限 | 2只 |
| 每只仓位 | 50%（2只满仓，不留现金缓冲——没有补仓策略不需要） |
| 止损线 | -5% |
| 止盈线 | +8%（原20%，2026-07-20调整，见下方说明） |
| 持仓数量 | 最多2只（原1只满仓，分散降低波动） |
| 轮询间隔 | 3分钟 |

**选股条件**：
1. 涨幅在 3%~12% 之间（排除涨幅过小或涨停）
2. 成交额 > 2亿（排除流动性差的标的）
3. 选取动量最强的最多2只买入，补满空缺持仓位

**自动操作**：
- 持仓跌-5% → 自动止损
- 持仓涨+8% → 自动止盈
- 持仓不满2只且有资金且有符合条件的股 → 自动买入

**脚本**：`stock_auto_trade.py`

**注意事项**：
- 最多持仓2只个股，不再单票满仓
- 个股策略只能持有个股，不持ETF
- **T+1制度，对应代码逻辑**（`stock_auto_trade.py`的`check_and_trade()`）：
  - 当日买入的股票，broker返回的持仓里`availCount`（可卖数量）为0，要到下一交易日才变成可卖数量
  - 止损/止盈判断（`should_stop_loss`/`should_take_profit`，line 257/260）不看`avail`，哪怕`avail=0`也会照常判断、照常打印"触发止损/止盈"日志——这是有意的，让人能看到信号，不是漏判
  - 但实际执行卖出前有硬性门槛`if AUTO_TRADE and h['avail'] > 0`（line 261-262、265-266），`avail=0`时这一行直接跳过，不会真的调用`sell()`——这就是T+1在代码里唯一真正"卡住"下单的地方
  - 同一个信号会在T+1解冻前的每一轮（3分钟一次）反复打印，直到`avail`变为可卖数量、真正执行卖出为止

> ⚠️ **2026-07-09 调整说明**：第13/14/15期连续三期负收益，其中第13期复盘（见`strategy_log.md`）当时就写过"单票集中持仓在震荡市回撤大"、"考虑分散持仓2-3只"、"止损线可考虑收紧至-5%"——但一直没有真的改参数。这次落地：止损-7%→-5%，单票95%→最多2只各45%。
>
> ⚠️ **2026-07-20 调整说明**：+20%止盈全历史几乎从未真正触发过（止损49次:止盈1次），拿真实买入记录回测过，2笔（300040/600722）在+20%规则下始终未落袋、换成+8%能提前锁定收益——改成+8%。"收紧涨幅带3%-12%→3%-8%"这个思路也讨论过，但需要对全市场做逐日历史扫描才能验证，暂缓。

---

## 🔌 可用API接口

### 东方财富模拟交易API

| 接口 | 说明 |
|------|------|
| `https://mkapi2.dfcfs.com/finskillshub/api/claw/mockTrading/positions` | 获取持仓 |

**认证**：`apikey`（小写）+ API Key

**注意**：`/account` 端点返回302，需用 `/positions` 获取资产

### 华泰证券模拟交易API

| 接口 | 说明 |
|------|------|
| `/api/simSkills/getPositions` | 获取持仓 |
| `/api/simSkills/getAccountBalance` | 获取余额 |
| `/api/simSkills/submitOrder` | 买卖下单 |
| `/api/simSkills/getQuote` | 获取行情 |

**认证**：`apiKey` + `skillCode`（从 `keys_config.py` 读取）

**⚠️ 配额限制**：华泰API每日配额有限，两个账户共用配额池，建议轮询间隔≥30分钟

### 腾讯行情API（推荐）

| 接口 | 说明 |
|------|------|
| `http://qt.gtimg.cn/q=sh510050,sz159915` | 批量行情，无频率限制 |

---

## 🚀 快速启动

```bash
# 启动监控面板
python3 dashboard.py

# 启动ETF自动交易（华泰，30分钟轮询）
nohup python3 auto_trade.py ht_7493 >> auto_trade_ht_7493.log 2>&1 &
nohup python3 auto_trade.py ht_8268 >> auto_trade_ht_8268.log 2>&1 &

# 启动个股自动交易（东方财富，3分钟轮询）
nohup python3 stock_auto_trade.py >> stock_trade.log 2>&1 &
```

## 🕹️ 手动查看/停止/启动交易进程

不想每次都靠Claude或者记PID，两个入口都能看到三个进程的实时状态并操作：

**命令行**（不依赖dashboard是否在跑）：
```bash
python3 botctl.py status            # 查看状态
python3 botctl.py stop [账号|all]    # 停止，账号: ht_7493 / ht_8268 / east_money
python3 botctl.py start [账号|all]
python3 botctl.py restart [账号|all]
```

**网页**：dashboard 首页顶部有一张"🤖 Bot Status"卡片，实时显示三个进程是否在跑、PID、最后一条日志，每个都有停止/启动/重启按钮（背后调的是 `/api/bots/status`、`/api/bots/<stop|start|restart>`，跟命令行工具是同一套逻辑）。

**开机自动拉起（launchd）**：仓库搬到`~/stocks_agent`之后launchd真的能用了，`launchd/`目录下三个plist（`com.stocks.stockautotrade`、`com.stocks.autotrade.ht7493`、`com.stocks.autotrade.ht8268`）已经装到`~/Library/LaunchAgents/`并启用，配了`RunAtLoad`+`KeepAlive`——开机或者进程意外退出都会自动重新拉起，不用再手动`nohup`。装/卸载：
```bash
# 装
cp launchd/com.stocks.*.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.stocks.stockautotrade.plist
launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.stocks.autotrade.ht7493.plist
launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.stocks.autotrade.ht8268.plist

# 卸载（比如要手动调试的时候）
launchctl bootout gui/501/com.stocks.stockautotrade
```
`botctl.py stop`能停掉进程，但如果对应的launchd job还在，`KeepAlive`会在30秒内把它拉回来——想彻底停要么`launchctl bootout`，要么先接受"停了会自动重启"这个事实。

---

## 📁 项目文件结构

```
stocks/
├── accounts.py          # 账户和策略配置表
├── keys_config.py       # API Key统一配置
├── dashboard.py         # Flask监控面板
├── templates/
│   └── dashboard.html   # 前端页面
├── auto_trade.py       # ETF动量轮动自动交易
├── stock_auto_trade.py # 个股动量突破自动交易
├── STRATEGIES.md       # 策略说明文档
├── strategy_log.md     # 交易日志（历史记录）
└── api_reference.md    # API接口详细文档
```

---

## ⚠️ 已知问题

| 问题 | 状态 | 解决方案 |
|------|------|----------|
| 华泰API配额耗尽 | 已缓解 | 轮询间隔改为30分钟 |
| Dashboard期数显示顺序 | ✅ 已修复 | 最新期数在前 |
| 个股数据toFixed报错 | ✅ 已修复 | 增加类型检查 |
| 东方财富某期初始资金算错 | ✅ 已修正 | 已用上一期期末资金带入修正（具体数字见`periods_local.py`） |
| 三个自动交易脚本7/2同时崩溃（写日志时PermissionError） | ✅ 已缓解 | log()写文件失败改为捕获异常打印警告，不再拖垮整个进程；已重新拉起 |
| 崩溃/重启电脑后没有进程自动拉起来，可能再裸持仓 | ✅ 已修复 | 仓库搬出`~/Documents`后launchd真的能用了，三个交易进程都配成了`RunAtLoad+KeepAlive`的LaunchAgent，开机/崩溃后会自动拉起，不用再手动`nohup` |
| `~/Documents`受TCC保护，launchd/cron等非交互进程访问不了，是7/2崩溃和launchd守护失败的共同根因 | ✅ 已修复 | 2026-07-13 把整个仓库搬到`~/stocks_agent`（不受TCC保护），代码里所有硬编码的`/Users/hetao/Documents/stocks`路径同步改掉；实测确认launchd现在能正常读写仓库文件 |
| 每周换期要手改accounts.py+dashboard.py+文档多处 | ✅ 已修复 | `accounts.py` 拆出 `PERIODS` 表，`ensure_current_period()` 跨周自动结算/开新期 |
| Dashboard手动买卖按钮（`/api/trade`）引用未定义的`APIURL`/`APIKEY`，点击必报错 | ✅ 已修复 | 手动下单不是这个项目要的（靠自动交易脚本），按钮/弹窗/接口整套删掉了，不是留着不修 |
| 东方财富策略选股纪律可能导致某周零买入，被判定弃权（策略风控 vs 参赛规则打架） | 🔴 未解决 | 无自动兜底检查，需人工每周留意`stock_trade.log`有没有买入记录；曾有一期就是人工手动补的一笔买入 |
| 交易记录只在各账号自己的原始日志里，`strategy_log.md`没有统一的成交记录 | ✅ 已修复 | 新增`trade_logger.py`，`auto_trade.py`/`stock_auto_trade.py`的`buy()`/`sell()`成交后都会调用，统一写进`strategy_log.md`末尾的记录表，手动交易调用同样的函数也会记 |
| `trade_logger.record_trade()`读写整个文件没加锁，三个进程几乎同时成交可能互相覆盖丢一行 | ✅ 已修复 | 加了`flock`独占锁，20并发写压测过，一行不丢 |
| 折线图降采样可能丢最后一个真实数据点，右端比实际滞后 | ✅ 已修复 | 采样后强制把最后一个点换回真实值 |
| `backtest.py`/`backtest_full.py`/`backtest_aggressive.py`/`backtest_conservative.py`重复了baostock数据获取和年化/回撤计算逻辑 | ✅ 已修复 | 抽成`backtest_common.py`（`get_index_data`/`ma_cross_signal`/`calc_max_drawdown_pct`/`calc_annualized_return_pct`），4个文件改成调用它；数值验证跟原实现完全一致才替换 |
| 根目录一堆一次性调试脚本（`debug2.py`/`debug_api.py`/`check_api.py`/`check_orders.py`）没人清理，其中`check_orders.py`的`/entrust`接口还是坏的 | ✅ 已修复 | 确认无引用后删除 |
| 止损止盈、选股、仓位计算等核心策略逻辑没有回归测试 | ✅ 已修复 | 抽出纯函数（`should_stop_loss`/`should_take_profit`/`passes_candidate_filter`/`calc_buy_qty`/`AutoTrader.calc_qty`），`tests/`下35个pytest单测全绿；顺带测出`should_stop_loss`有个浮点数精度bug（`-0.07*100`不是精确的`-7.0`，导致刚好-7.0%不触发止损），已修复 |
| 稳健/激进两个华泰账户代码里实际共用同一套风控（`STOP_LOSS_DAY_PCT`/`MOMENTUM_TOP_N`模块常量），`STRATEGIES`字典配的参数从未被读取 | ✅ 已修复 | `AutoTrader.__init__`改成从`self.strategy`读取，8268真正Top2/-5%止损；新增8%收益地板保护 |
| `accounts.py`的`STRATEGIES['stock_momentum']`还是止损-7%/单只95%/1只的旧值，跟`stock_auto_trade.py`实际用的常量不一致，dashboard显示的策略参数是过期的 | ✅ 已修复 | 同步成-5%/2只/每只50%，跟代码常量对齐 |
| 三个策略的仓位公式都留了10%现金缓冲（`*0.9`），但没有补仓/加仓策略，不需要预留资金摊低成本 | ✅ 已修复 | 改成满仓：`stock_auto_trade.py`单只仓位0.45→0.5，`auto_trade.py`的`*0.9`去掉；`STRATEGIES`字典的`position_size`同步更新 |
| 华泰两个账户的卖出（止损/减仓/收益地板保护）从7月初起一直失败，风控形同虚设，`~/stocks_agent`两个账户裸持仓到初赛结束（7.20复盘时发现） | ✅ 已修复 | 根因：华泰`getPositions`返回的`quantity`/`availableQuantity`是float（如`199100.0`），直接透传进`submitOrder`请求体，服务端Java按整数解析`NumberFormatException`拒收(500)；买入之所以一直没事是因为买入数量是本地算出来的int。修复：持仓归一化时转`int`，`submitOrder`里也强制`int(qty)`做双保险；顺带把失败时的完整响应体记进日志方便下次排查。修复当天验证：8268重启后成功清仓3只（此前0次成功卖出记录） |
