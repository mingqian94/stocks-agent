# Kronos 与 Sequoia-X：A 股研究项目接入评估

**评估日期：2026-10-10**  
**目标仓库：`stocks-agent` / `a_share_lab`**  
**证据边界：只采用官方 GitHub、官方模型卡、论文页和仓库源码。未把 Star 数、README 自述或示例回测当作收益有效性证明。**

> **执行更新**：本报告提出的 P0 与 P1 已于同日完成。Kronos 已改为官方 `mini + Tokenizer-2k` 配对并重跑 3×4 pilot；三个 Sequoia-X 规则已独立重写并完成五窗口回测。实际结果见 [`a_share_kronos_sequoia_x_experiment_2026-10-10.md`](a_share_kronos_sequoia_x_experiment_2026-10-10.md)。

## 结论先行

| 项目 | 它是什么 | 对本项目的价值 | 接入判断 |
|---|---|---|---|
| **Kronos** | 金融 K 线 tokenizer + 自回归 Transformer，输出未来 OHLCVA 路径 | 可作为与传统动量/突破不同的连续预测因子 | **保留研究接入，但先修正当前模型/Tokenizer 配对；不要进模拟盘或实盘** |
| **Sequoia-X** | A 股日线规则扫描器 + 本地 SQLite + 飞书通知；不是 AI 模型，也没有模型权重 | 其中 `HighTightFlag`、120 日 RPS、均线放量等规则可变成低算力对照因子 | **不整体引入、不复制源码；独立重写少数规则到现有回测引擎** |

最合适的组合不是让两套项目替换现有系统，而是：

1. 继续让本项目的 `a_share_lab` 负责点时股票池、下一开盘成交、T+1、涨跌停、停牌、成本、滑点与容量；
2. 把 Kronos 作为一个可冻结版本的**连续分数**；
3. 把 Sequoia-X 中少数规则重写为**候选过滤器/传统因子基线**；
4. 分别做单因子和增量贡献检验，不能只看组合后的收益。

## 一、项目身份与活跃度

### 1. Kronos

- 官方项目是 [`shiyu-coder/Kronos`](https://github.com/shiyu-coder/Kronos)，论文为 [Kronos: A Foundation Model for the Language of Financial Markets](https://ojs.aaai.org/index.php/AAAI/article/view/39730)，已收录于 AAAI 2026。
- 截至本次核查，默认分支最新提交仍为 2026-04-13 的 [`67b630e`](https://github.com/shiyu-coder/Kronos/commit/67b630e67f6a18c9e9be918d9b4337c960db1e9a)，与本项目已经固定的源码提交相同；[仓库仍没有正式 Release](https://github.com/shiyu-coder/Kronos/releases)。因此，自 2026-08-02 本项目首次接入后，**没有新的官方源码版本需要升级**。
- GitHub 官方仓库元数据在 2026-10-10 附近显示约 4 万 Star、6 千余 Fork；这些只说明关注度，不说明可交易性。[实时仓库元数据](https://api.github.com/repos/shiyu-coder/Kronos)。
- `Kronos-mini` 的最新模型仓库提交仍为 `f4e6869`，官方配套 `Kronos-Tokenizer-2k` 最新提交为 `26966d0`，现均已由本项目固定。[mini 提交历史](https://huggingface.co/NeoQuasar/Kronos-mini/commits/main)；[2k tokenizer 提交历史](https://huggingface.co/NeoQuasar/Kronos-Tokenizer-2k/commits/main)。

### 2. Sequoia-X：准确身份

本报告中的 Sequoia-X 是 [`sngyai/Sequoia-X`](https://github.com/sngyai/Sequoia-X)，仓库自述为“A 股量化选股系统 V2”。搜索中还能找到若干同名二次仓库；在用户没有提供链接的情况下，本报告选择关注度、历史和提交数均明显更高的 `sngyai` 仓库作为上游。它与同名的分布式计算/机器学习研究项目无关，也不是类似 Kronos 的基础模型。

- 官方 README 定位是：用 BaoStock 更新 A 股日 K、本地 SQLite 存储、收盘后运行规则策略并推送飞书。[README](https://github.com/sngyai/Sequoia-X/blob/master/README.md)
- 默认分支最新提交为 2026-05-09 的 [`444c0db69ff36b46ef2b22ab265051d60c16029d`](https://github.com/sngyai/Sequoia-X/commit/444c0db69ff36b46ef2b22ab265051d60c16029d)，此后约五个月没有代码提交；仓库累计 202 次提交，当前 GitHub 页面约 8 千 Star、1.6 千 Fork。[提交历史](https://github.com/sngyai/Sequoia-X/commits/master/)；[仓库首页](https://github.com/sngyai/Sequoia-X)
- [`pyproject.toml`](https://github.com/sngyai/Sequoia-X/blob/master/pyproject.toml) 声明版本 `2.0.0`，但[没有正式 Release](https://github.com/sngyai/Sequoia-X/releases)，只有一个指向旧代码的 [`v1.0-legacy` 标签](https://github.com/sngyai/Sequoia-X/tags)。所以“V2”是源码内版本号，不是可审计的发布包。
- 根目录只有源码、测试、README、`pyproject.toml` 等，**没有论文、模型卡、训练流程或模型权重**。[仓库文件列表](https://github.com/sngyai/Sequoia-X)

## 二、Kronos：已有接入、当前缺口与新增价值

### 已经借鉴并实现的部分

本项目已有实现见 [`a_share_kronos_implementation_2026-08-02.md`](a_share_kronos_implementation_2026-08-02.md) 和 [`kronos_signal.py`](../a_share_lab/kronos_signal.py)：

- 固定官方源码提交、模型 revision、Tokenizer revision，并校验下载源码哈希；
- 用 90 个交易日历史预测未来 10 日，按未来 10 日预测收盘均值相对当前收盘构造横截面分数；
- 用点时可知的连续信号价构造模型输入，但把真实未复权价格留给撮合；
- 预测结果只作为收盘后分数，成交仍走下一开盘、T+1、真实涨跌停、停牌、整手、税费、滑点和容量模型；
- CPU 单线程、缓存、失败记录、覆盖率审计和小规模 pilot 均已具备。

这些边界是正确的。Kronos 官方自己也说明其 A 股 Qlib 流程只是演示，并非生产级量化系统，生产使用仍需组合约束、风险中性、动态仓位、交易成本、滑点与冲击建模。[官方 A 股微调与免责声明](https://github.com/shiyu-coder/Kronos/blob/master/README.md#-finetuning-on-your-own-data-a-share-market-example)

### 必须先修正：当前 mini / Tokenizer 不是官方配对

本项目当前配置是：

- `NeoQuasar/Kronos-mini`
- `NeoQuasar/Kronos-Tokenizer-base`

但官方 Model Zoo 明确列出：

- `Kronos-mini`（4.1M 参数、2048 context）应配 [`Kronos-Tokenizer-2k`](https://huggingface.co/NeoQuasar/Kronos-Tokenizer-2k)；
- `Kronos-small`（24.7M 参数、512 context）和 `Kronos-base` 应配 `Kronos-Tokenizer-base`。[官方模型表](https://github.com/shiyu-coder/Kronos/blob/master/README.md#-model-zoo)

两种 tokenizer 的配置也并不相同：2k tokenizer 的 `group_size=5`，base tokenizer 的 `group_size=4`。[Tokenizer-2k 配置](https://huggingface.co/NeoQuasar/Kronos-Tokenizer-2k/raw/main/config.json)；[Tokenizer-base 配置](https://huggingface.co/NeoQuasar/Kronos-Tokenizer-base/raw/main/config.json)

官方唯一回归测试固定的是 `Kronos-small@901c26c` + `Tokenizer-base@0e011738`，不是 mini + base。[官方回归测试](https://github.com/shiyu-coder/Kronos/blob/master/tests/test_kronos_regression.py)

因此，现有 3 股票 × 4 日期 pilot 只能证明“不报错且链路能跑”，**不能证明使用了官方认可的模型语义配对**。此前本来也没有把 pilot 当收益证据，所以历史结论无需撤回，但其 12 个分数不应进入后续性能比较。

建议二选一：

1. **旧电脑优先：`mini + Tokenizer-2k`**，固定 2k tokenizer 的当前 revision，重跑单票回归和 3×4 pilot；
2. **更强机器的正式实验：`small + Tokenizer-base`**，直接复用官方回归测试配对和 revision，再生成冻结分数。

### 当前版本没有带来新的模型能力

截至 2026-10-10，上游源码和本项目已固定的 mini/base-tokenizer 模型仓库都没有更新。现在值得做的不是“升级新版”，而是：

- 改正官方配对；
- 用不重叠时期生成足够覆盖率的冻结分数；
- 先看横截面 RankIC、分位数组合单调性和预测稳定性，再看扣费收益；
- 对比 `Kronos-only`、传统因子-only、Kronos + 传统过滤器三组，衡量增量，而不是只看总收益。

### 输入、输出、算力和许可

| 项目 | 核验结果 |
|---|---|
| 输入 | 历史 DataFrame 至少含 `open/high/low/close`，`volume/amount` 可选；还需历史和未来时间戳。[官方预测接口](https://github.com/shiyu-coder/Kronos/blob/master/README.md#-making-forecasts) |
| 输出 | 未来 `open/high/low/close/volume/amount` 路径；本项目应继续只从中提取信号，不把预测价当成交价。 |
| 公开权重 | mini、small、base 已公开；large（499.2M）仍未公开。[Model Zoo](https://github.com/shiyu-coder/Kronos/blob/master/README.md#-model-zoo) |
| 推理依赖 | Python 3.10+、PyTorch 2+、einops、Hugging Face Hub、safetensors 等。[requirements.txt](https://github.com/shiyu-coder/Kronos/blob/master/requirements.txt) |
| 训练资源 | 官方 tokenizer 和 predictor 微调脚本使用 `torchrun` 多 GPU，默认每卡 batch 50、30 epoch；不适合这台旧电脑常规运行。[微调说明](https://github.com/shiyu-coder/Kronos/blob/master/README.md#step-3-run-the-finetuning)；[训练配置](https://github.com/shiyu-coder/Kronos/blob/master/finetune/config.py) |
| 商用许可 | 代码有完整 MIT LICENSE，公开模型卡也标 MIT；一般允许商用、修改与再分发，但必须保留版权和许可文本，且无担保。[代码 LICENSE](https://github.com/shiyu-coder/Kronos/blob/master/LICENSE)；[mini 模型卡](https://huggingface.co/NeoQuasar/Kronos-mini) |

MIT 覆盖开源代码/已发布权重，不自动替第三方行情数据授权，也不保证预测结果适合交易。Kronos 的 120 亿 K 线预训练语料没有公开下载，本项目不应声称拥有或复现其预训练数据。[模型卡的数据规模说明](https://huggingface.co/NeoQuasar/Kronos-mini)

## 三、Sequoia-X：能借什么，不能直接用什么

### 数据、输入与输出

- 数据引擎用 BaoStock `query_history_k_data_plus` 拉 `date/open/high/low/close/volume/amount`，参数 `adjustflag="1"`（后复权），落地 SQLite `stock_daily`。[数据引擎](https://github.com/sngyai/Sequoia-X/blob/master/sequoia_x/data/engine.py)
- 初次回填用当前 `query_stock_basic` 返回的“仍在上市”股票，后续策略遍历本地代码列表；源码没有历史成分股快照或历史上市状态。因此它适合**今天收盘后的扫描**，不能直接作为无生存者偏差的历史股票池。[股票列表实现](https://github.com/sngyai/Sequoia-X/blob/master/sequoia_x/data/engine.py#L317-L348)
- 策略接口只返回 `list[str]` 股票代码，主流程把命中列表发到飞书；没有持仓状态、退出规则、资金曲线、成本、成交约束或绩效指标。[策略基类](https://github.com/sngyai/Sequoia-X/blob/master/sequoia_x/strategy/base.py)；[主程序](https://github.com/sngyai/Sequoia-X/blob/master/main.py)
- 因此它的输出是**筛选命中**，不是收益预测、目标仓位或交易指令，更不是已验证 alpha。

### 依赖、资源与权重

- Python `>=3.10`；运行依赖只有 `akshare`、`baostock`、`pandas`、`pydantic-settings`、`python-dotenv`、`rich`、`requests`，没有 PyTorch、GPU 或模型下载。[pyproject.toml](https://github.com/sngyai/Sequoia-X/blob/master/pyproject.toml)
- 没有模型，自然也没有公开权重、训练资源或推理显存要求。
- 日常同步源码最多启动 8 个进程。对于本项目所用旧电脑，不应照搬；若借其数据更新思路，应固定 1–2 worker 或继续使用本项目已有的可续传 BaoStock 缓存。[多进程实现](https://github.com/sngyai/Sequoia-X/blob/master/sequoia_x/data/engine.py#L151-L158)
- 官方 README 声称全市场首次回填约 12 分钟、日常 2–3 分钟，这只是作者环境下的自述，不能当成本机性能保证。[README](https://github.com/sngyai/Sequoia-X/blob/master/README.md#两种运行模式)

### 许可证：公开可看，不等于可放心复制商用

README 末尾写了“MIT”，但仓库根目录没有 `LICENSE` 文件，GitHub 页面也没有识别出的许可证条目。[根目录文件列表](https://github.com/sngyai/Sequoia-X)；[README 许可证段](https://github.com/sngyai/Sequoia-X/blob/master/README.md#许可证--license)

这比 Kronos 的完整 MIT LICENSE 模糊。**在上游补充完整许可证文本或作者书面确认前，不建议复制 Sequoia-X 源码进入公开或商业产品。** 本项目可以基于公开描述独立实现常见的技术分析规则，并保留来源记录；若未来要直接拷贝实现，应先解决许可证问题。

### 七类规则的适配度

README 只列六类 K 线策略，但 `main.py` 实际还注册了 `PrivatePlacementStrategy`，合计七类。[主程序策略列表](https://github.com/sngyai/Sequoia-X/blob/master/main.py#L49-L65)

| 规则 | 与本项目重合度 | 价值判断 | 建议 |
|---|---:|---|---|
| `TurtleTrade`：20 日新高 + 成交额过亿 + 阳线/上涨 | 高 | 本项目已有 `daily_breakout`；新增点只是流动性与阳线过滤 | 不另起策略，做两个过滤条件的 ablation |
| `MaVolume`：MA5 上穿 MA20 + 量 > 20 日均量 1.5 倍 | 中 | 简单、低算力、与现有 20 日风险调整动量不完全相同 | **第二优先级重写并回测** |
| `HighTightFlag`：40 日涨幅 >60%、10 日收敛、高位、缩量 | 低 | 当前策略库没有这一形态，增量最大 | **第一优先级重写并回测** |
| `RpsBreakout`：120 日收益横截面前 10%，且接近 120 日高点 | 中 | 是更长周期横截面动量，可与现有 20 日风险调整动量互补 | **第一优先级重写；改名 `rps120_near_high`** |
| `LimitUpShakeout`：昨日约 10% 涨停、今日放量阴线且不破昨收 | 低 | A 股特有事件形态，但官方固定 9.5% 阈值不覆盖 ST、创业板、科创板及历史制度 | 第三优先级，只能复用本项目历史涨跌停规则 |
| `UptrendLimitDown`：MA20>MA60 后放量约 10% 跌停 | 低 | 逆势接跌停，尾部与流动性风险高 | 最后测试，小仓位独立组，不与突破策略混选 |
| `PrivatePlacement`：近 7 日定增公告 | 无 | 使用 AkShare 当前接口；没有点时历史公告库，容易形成回测时点污染 | 暂不纳入回测，可单独做观察提醒 |

上述规则条件可在官方源码直接核验：[TurtleTrade](https://github.com/sngyai/Sequoia-X/blob/master/sequoia_x/strategy/turtle_trade.py)、[MaVolume](https://github.com/sngyai/Sequoia-X/blob/master/sequoia_x/strategy/ma_volume.py)、[HighTightFlag](https://github.com/sngyai/Sequoia-X/blob/master/sequoia_x/strategy/high_tight_flag.py)、[RpsBreakout](https://github.com/sngyai/Sequoia-X/blob/master/sequoia_x/strategy/rps_breakout.py)、[涨停洗盘](https://github.com/sngyai/Sequoia-X/blob/master/sequoia_x/strategy/limit_up_shakeout.py)、[上升趋势跌停](https://github.com/sngyai/Sequoia-X/blob/master/sequoia_x/strategy/uptrend_limit_down.py)、[定增公告](https://github.com/sngyai/Sequoia-X/blob/master/sequoia_x/strategy/private_placement.py)。

两个重要修正：

1. 官方 `RpsBreakout` 的滚动最高价包含当日，且条件是收盘不低于最高价的 90%，实质是“接近高点”，不是严格突破；移植时应按含义命名，避免标签误导。
2. 官方两个涨跌停策略都用固定 `1.095/0.905`，本项目不能照搬。应调用已有按日期、板块和 ST 状态计算的真实涨跌停约束。

## 四、建议的低资源验证路线

### P0：先修 Kronos 配对，不扩样本

1. `mini + Tokenizer-2k` 固定 revision；
2. 增加测试，拒绝非官方模型/Tokenizer 配对；
3. 重跑单票与 3 股票 × 4 日期工程 pilot，旧缓存换命名空间，不能混用；
4. 只有输出可复现、覆盖率 100% 后，再到强机器生成大样本冻结分数。

这一步仍可在旧电脑单线程完成，不做全 CSI800 逐日推理。

### P1：只重写三个 Sequoia-X 假设

按优先顺序：

1. `high_tight_flag_40_10`
2. `rps120_near_high`
3. `ma5_cross_ma20_volume15`

实现方式：只增加 `a_share_lab` 的滞后安全特征和 `StrategySpec`，不引入 Sequoia-X 包、SQLite、飞书或 8 进程数据层。特征一次预计算，多窗口复用，符合旧电脑的 CPU/内存限制。

### P2：统一验证

- 继续使用 1 个月、3 个月、6 个月、1 年、3 年窗口，但短窗口只作为行为检查；
- 另保留至少两个不重叠的样本外阶段，参数不能按五个窗口赢家回调；
- 每个信号先报告覆盖率、换手、持仓数、RankIC/分位数组合，再报告收益、回撤和成本压力；
- 对照组至少包括现有 `daily_breakout_2_fixed`、`risk_adjusted20`、等权与 CSI800；
- Sequoia-X 规则必须用本项目点时 CSI300+CSI500 成分、连续信号价、未复权成交价和真实 A 股限制；
- 通过门槛应是：多个不重叠时期都有方向一致的增量，扣费后仍有效，且不是少数交易贡献全部收益。

### P3：最后才测试组合

推荐两种组合，不做大网格搜索：

1. **传统过滤 + Kronos 排名**：先用 `rps120_near_high` 或 `high_tight_flag` 形成候选集，再以 Kronos 分数排序；
2. **Kronos 与传统因子线性混合**：各自横截面标准化后固定 50/50 权重，和单因子对照。

如果组合提升但 Kronos 单因子没有 RankIC/分位单调性，不应把提升归因于 Kronos。

## 五、最终判断

### Kronos

**能用，但目前只适合作为研究因子。** 本项目已经把最难的版本固定、缓存审计和 A 股撮合边界搭好了；上游没有新版价值。当前最高优先级不是扩大回测，而是修正 `mini + Tokenizer-base` 的非官方配对。修正后，在强机器完成冻结分数和不重叠样本验证之前，不进入 `stock_auto_trade.py`、模拟盘或实盘。

### Sequoia-X

**能借策略想法，不能直接当回测框架或交易系统接入。** 它的优势是规则简单、A 股日线原生、零 GPU；弱点是没有资金/成交/退出回测，没有点时历史股票池，涨跌停规则过度简化，许可证文件也缺失。最值得独立重写的是 `HighTightFlag` 与 120 日 RPS，均线放量作为低成本补充；其数据层、通知层和回测假设都不应移植。

一句话：**Kronos 留作“预测分数”，Sequoia-X 留作“规则假设库”，交易与验证仍由本项目自己的 A 股引擎负责。**

## 主要一手资料

- [Kronos 官方仓库](https://github.com/shiyu-coder/Kronos)
- [Kronos AAAI 2026 论文页](https://ojs.aaai.org/index.php/AAAI/article/view/39730)
- [Kronos 官方 Model Zoo / A 股微调说明](https://github.com/shiyu-coder/Kronos/blob/master/README.md)
- [Kronos 官方回归测试](https://github.com/shiyu-coder/Kronos/blob/master/tests/test_kronos_regression.py)
- [Kronos-mini 模型卡](https://huggingface.co/NeoQuasar/Kronos-mini)
- [Kronos-Tokenizer-2k 模型卡](https://huggingface.co/NeoQuasar/Kronos-Tokenizer-2k)
- [Kronos MIT LICENSE](https://github.com/shiyu-coder/Kronos/blob/master/LICENSE)
- [Sequoia-X 官方仓库](https://github.com/sngyai/Sequoia-X)
- [Sequoia-X README](https://github.com/sngyai/Sequoia-X/blob/master/README.md)
- [Sequoia-X 数据引擎](https://github.com/sngyai/Sequoia-X/blob/master/sequoia_x/data/engine.py)
- [Sequoia-X 策略目录](https://github.com/sngyai/Sequoia-X/tree/master/sequoia_x/strategy)
- [Sequoia-X 依赖声明](https://github.com/sngyai/Sequoia-X/blob/master/pyproject.toml)
