# stocks-agent

面向 A 股的自动交易实验与公开数据策略研究仓库。仓库不包含真实 API Key、账户资金流水或券商私有数据；`a_share_lab` 研究模块不会连接账户或下单。

## 数据从哪里来

本次可复现研究使用 [BaoStock](https://baostock.com/) 0.9.3 免费接口，不是券商 API，也不是交易所授权行情数据库。使用者应同时阅读 BaoStock 的[免责声明](https://baostock.com/disclaimer)。

| 数据 | BaoStock 接口/代码 | 本项目用途 |
|---|---|---|
| 沪深300历史成分股 | `query_hs300_stocks(date)` | 构造点时股票池 |
| 中证500历史成分股 | `query_zz500_stocks(date)` | 与沪深300合并为 CSI800 代理股票池 |
| 股票日线 | `query_history_k_data_plus` | OHLC、前收盘、成交量额、交易状态、`pctChg`、ST 状态 |
| 中证800指数 | `sh.000906` 日线 | 组合基准 |

下载器见 [`a_share_lab/data.py`](a_share_lab/data.py)。执行价格统一使用不复权 OHLC（`adjustflag=3`）；模型和技术指标使用当日可知的 `pctChg` 累乘连续序列，避免把除权缺口直接当成可交易收益。股票池采用半年一次的历史成分股快照，不使用今天的成分股倒推过去。

当前本地研究快照：

- 行情日期：2020-08-14 至 2026-07-31（包含研究期前的指标预热数据）；
- 正式研究期：2021-01-01 至 2026-07-31；
- 1,234 只历史成分股，1,705,559 行日线；
- 15 个沪深300/中证500成分股快照；
- 中证800基准 1,445 行；
- 下载失败股票 0，只保留本地缓存。

完整质量统计见 [`research/results/a_share_data_quality.json`](research/results/a_share_data_quality.json)。

### Git 里有什么、没有什么

- **已提交**：数据下载与回测代码、策略参数、汇总指标、年度结果、成本压力测试和小规模 Kronos 工程 pilot。
- **未提交**：逐股票原始日线、成分股原始缓存、模型权重、Kronos 预测缓存、真实密钥与账户数据。
- 本地原始缓存统一位于 `data/a_share_lab/`，已由 `.gitignore` 排除；可通过下面的命令重新下载。
- `research/results/*.csv` 是回测汇总或小型审计产物，不是原始行情数据。

```powershell
python -m pip install -r requirements-research.txt
python -m a_share_lab.experiments --download
python -m a_share_lab.horizons
python -m a_share_lab.sequoia_x
```

免费接口可能更正历史数据或调整可用性，因此未来重新下载的文件哈希不保证与 2026-08-02 的本地快照完全一致。该数据集也不能消除半年度成分股近似、退市覆盖、盘口排队和分钟成交路径等限制。

## 策略研究

现有研究覆盖原策略、日度排名、突破持有期、市场均线门控、5 日动量、20 日风险调整动量、10 日反转、三个独立重写的 Sequoia-X 规则假设，以及可选的 Kronos K 线预测分数。所有成交仍由统一 A 股引擎处理：收盘后信号、下一开盘、T+1、停牌、一字板、整手、分时代税费、佣金、滑点和成交容量。

- 使用说明：[`a_share_lab/README.md`](a_share_lab/README.md)
- 完整回测结论：[`research/a_share_backtest_report_2026-08-02.md`](research/a_share_backtest_report_2026-08-02.md)
- 多周期结果：[`research/a_share_multi_horizon_report_2026-08-02.md`](research/a_share_multi_horizon_report_2026-08-02.md)
- Kronos 接入与资源验证：[`research/a_share_kronos_implementation_2026-08-02.md`](research/a_share_kronos_implementation_2026-08-02.md)
- Kronos 配对修正与 Sequoia-X 回测：[`research/a_share_kronos_sequoia_x_experiment_2026-10-10.md`](research/a_share_kronos_sequoia_x_experiment_2026-10-10.md)

## Kronos 的使用边界

可选模型来自清华团队开源的 [shiyu-coder/Kronos](https://github.com/shiyu-coder/Kronos)。本仓库没有复制其预训练数据，也没有照搬官方 Qlib 撮合；只按固定 revision 下载最小推理源码和公开权重，把预测结果转换为横截面分数，再交给本项目的 A 股撮合引擎。

当前固定官方配对 `Kronos-mini + Kronos-Tokenizer-2k`，本机只完成 3 股票 × 4 信号日工程验证。该结果用于证明模型、缓存和撮合链路可运行，不构成策略收益或实盘有效性证明。

## 东方财富模拟盘安全模式

`stock_auto_trade.py` 现在默认使用 `shadow`：会生成并记录订单意图，但不会调用东方财富下单接口。仅配置 API Key 不会自动委托。影子/模拟订单记录在 gitignored 的 `paper_order_journal.local.jsonl`，同一策略、股票、方向和原因在同一交易日只允许尝试一次。

显式开启东方财富模拟委托需要同时满足：账户配置允许自动交易、真实 API Key 已配置、当前处于 A 股交易时段、当天已人工确认是交易日、行情快照未过期、账户未触发日亏损/失败次数熔断、单笔买入估值不超过上限。先设置环境变量：

```powershell
$env:EASTMONEY_EXECUTION_MODE = "paper"
$env:EASTMONEY_PAPER_CONFIRM = "SIMULATED_ORDERS_ONLY"
$env:EASTMONEY_MAX_ORDER_VALUE = "500000"
$env:EASTMONEY_MAX_SIGNAL_AGE_SECONDS = "120"
$env:EASTMONEY_MAX_DAILY_LOSS_PCT = "2.0"
$env:EASTMONEY_MAX_FAILED_ORDERS = "2"
```

每个交易日启动前，在确认沪深交易所当天正常开市后，写入当天日期。程序不会自动生成该文件；日期不匹配时一律不下单：

```powershell
Set-Content -LiteralPath .\eastmoney_market_open_date.local -Value (Get-Date -Format 'yyyy-MM-dd')
python stock_auto_trade.py
```

脚本应在 09:35 前启动：第一次 09:25–09:35 的账户快照会把当天开盘总资产写入 `paper_daily_risk.local/YYYY-MM-DD.json`。后续日亏损以当前总资产相对该基线计算，包含已经卖出仓位造成的已实现盈亏；如果当天错过这个初始化窗口且没有已有基线，新买单会保持关闭，卖出风险仓位不受此项限制。

运行期间紧急停止新委托（无需重启进程）：

```powershell
New-Item -ItemType File -Path .\eastmoney_kill_switch.local -Force
```

检查原因并确认可以恢复后，可删除急停文件；删除前程序始终保持拦截：

```powershell
Remove-Item -LiteralPath .\eastmoney_kill_switch.local
```

`EASTMONEY_KILL_SWITCH=1` 也可在启动进程前静态禁用委托；运行后需要动态急停时应使用上述文件。闭市、周末、未人工确认交易日、信号日期不是当天、本次取数超过 120 秒、缺少确认口令、密钥为占位符、账户未开启、当日总资产回撤达到 2% 或当日累计失败达到 2 次时，安全门会在本地拦截，不调用交易接口。未人工确认交易日时，程序连账户和行情查询也不会发起。候选买入必须有东方财富行情源返回的 `f124` 更新时间；新浪备用源只有时分秒、无法确认来源日期，因此只用于影子观察，不会触发 paper 买入。持仓退出使用账户快照的本机接收时间，因为持仓接口不提供行情源时间；该边界会记录在风险说明中。买入受日亏损门控，卖出仍可用于退出风险仓位；失败次数门控对买卖都生效。

并发进程通过 `paper_order_journal.local.jsonl.claims/` 中的原子占位防止重复委托，并以账户级执行锁串行执行“失败计数—提交—记录”，避免多个不同订单并发越过失败熔断。同一策略、股票、方向和原因在同一交易日最多提交一次；即使进程在提交前后崩溃，也会保守地阻止自动重试。订单流水、原子占位、执行锁、日初资产基线、交易日确认和急停文件都只保留在本机且已被 Git 忽略。当前接入的是既有 `daily_breakout_2_fixed` / 个股动量策略；Kronos 与三个 Sequoia-X 假设没有接入模拟盘。

## 风险提示

本项目仅供研究与技术验证，不构成投资建议。回测收益不代表未来收益；任何实盘使用前都需要独立数据审计、前向纸面交易、真实费用/滑点校准和账户级风险控制。
