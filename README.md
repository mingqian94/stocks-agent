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
```

免费接口可能更正历史数据或调整可用性，因此未来重新下载的文件哈希不保证与 2026-08-02 的本地快照完全一致。该数据集也不能消除半年度成分股近似、退市覆盖、盘口排队和分钟成交路径等限制。

## 策略研究

现有研究覆盖原策略、日度排名、突破持有期、市场均线门控、5 日动量、20 日风险调整动量、10 日反转，以及可选的 Kronos K 线预测分数。所有成交仍由统一 A 股引擎处理：收盘后信号、下一开盘、T+1、停牌、一字板、整手、分时代税费、佣金、滑点和成交容量。

- 使用说明：[`a_share_lab/README.md`](a_share_lab/README.md)
- 完整回测结论：[`research/a_share_backtest_report_2026-08-02.md`](research/a_share_backtest_report_2026-08-02.md)
- 多周期结果：[`research/a_share_multi_horizon_report_2026-08-02.md`](research/a_share_multi_horizon_report_2026-08-02.md)
- Kronos 接入与资源验证：[`research/a_share_kronos_implementation_2026-08-02.md`](research/a_share_kronos_implementation_2026-08-02.md)

## Kronos 的使用边界

可选模型来自清华团队开源的 [shiyu-coder/Kronos](https://github.com/shiyu-coder/Kronos)。本仓库没有复制其预训练数据，也没有照搬官方 Qlib 撮合；只按固定 revision 下载最小推理源码和公开权重，把预测结果转换为横截面分数，再交给本项目的 A 股撮合引擎。

当前本机只完成 `Kronos-mini` 的 3 股票 × 4 信号日工程验证。该结果用于证明模型、缓存和撮合链路可运行，不构成策略收益或实盘有效性证明。

## 风险提示

本项目仅供研究与技术验证，不构成投资建议。回测收益不代表未来收益；任何实盘使用前都需要独立数据审计、前向纸面交易、真实费用/滑点校准和账户级风险控制。
