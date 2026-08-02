# 微信文章项目核查：Kronos 金融 K 线基础模型

> 核查日期：2026-08-02（Asia/Shanghai）  
> 原文：[《GitHub 3.5万 Star，清华团队做了一个读 A 股 K 线的大模型》](https://mp.weixin.qq.com/s/LKHQW9rn8GMFDZsl6i0P8Q)，公众号“极客之家”。  
> 结论适用于本次所见官方仓库 `master` 分支提交 `67b630e`、官方模型卡和论文。本文是技术研究，不构成投资建议。

## 结论先行

文章介绍的项目是清华大学团队的 **Kronos**，官方仓库为 [`shiyu-coder/Kronos`](https://github.com/shiyu-coder/Kronos)，论文已正式发表于 AAAI 2026。项目不是聊天式“炒股 Agent”，也不是可直接实盘的 A 股策略，而是一个把 OHLCV/成交额 K 线离散化后自回归预测未来 K 线的时序基础模型。[AAAI 论文页](https://ojs.aaai.org/index.php/AAAI/article/view/39730)列出的七位作者均来自清华大学交叉信息研究院或自动化系；[论文摘要](https://arxiv.org/abs/2508.02739)和[仓库 README](https://github.com/shiyu-coder/Kronos/blob/master/README.md)共同说明了模型定位。

对本仓库最值得借鉴的只有一层：**把 Kronos 当作新的、可冻结版本的横截面预测信号生成器，继续交给现有 `a_share_lab` 做下一开盘成交、T+1、涨跌停、税费、滑点和容量回测。** 不建议搬入它的 Qlib 回测器，更不能用预测出来的未来 OHLC 当成真实成交路径。

现阶段不建议先微调。应该先用公开的 `Kronos-small` 做零样本实验，固定 90 日回看、10 日预测和论文信号公式，验证它在本项目 1 个月、3 个月、6 个月、1 年、3 年窗口中能否在真实成本前后都增加信息。若零样本毛信号都不稳定，微调只会放大算力投入和过拟合风险。

## 1. 项目身份与作者

- 项目名称：**Kronos: A Foundation Model for the Language of Financial Markets**。
- 官方代码：[`shiyu-coder/Kronos`](https://github.com/shiyu-coder/Kronos)。仓库所有者显示为 `shiyu-coder`，许可证文件署名 `ShiYu`。[仓库元数据 API](https://api.github.com/repos/shiyu-coder/Kronos)；[LICENSE](https://github.com/shiyu-coder/Kronos/blob/master/LICENSE)。
- 正式论文：Yu Shi、Zongliang Fu、Shuo Chen、Bohan Zhao、Wei Xu、Changshui Zhang、Jian Li，AAAI 2026，Vol. 40 No. 30，pp. 25366–25373，DOI `10.1609/aaai.v40i30.39730`。[AAAI 正式出版页](https://ojs.aaai.org/index.php/AAAI/article/view/39730)。
- 机构：作者分别来自清华大学交叉信息研究院和自动化系。[AAAI 作者与机构列表](https://ojs.aaai.org/index.php/AAAI/article/view/39730)。
- 模型权重：`Kronos-mini`、`Kronos-small`、`Kronos-base` 以及两个 tokenizer 由 `NeoQuasar` 账号公开在 Hugging Face，模型卡标注 MIT 且不需要申请访问；`Kronos-large` 未公开。[官方模型表](https://github.com/shiyu-coder/Kronos/blob/master/README.md#-model-zoo)；[Kronos-base 模型卡](https://huggingface.co/NeoQuasar/Kronos-base)。

## 2. 它实际做什么

### 2.1 核心架构

Kronos 是两阶段架构：

1. tokenizer 用 Binary Spherical Quantization 把连续的 `open/high/low/close/volume/amount` 压成粗、细两级离散 token；
2. decoder-only Transformer 加上时间嵌入，以自回归方式逐根生成未来 K 线 token，再解码回连续值。

仓库源码显示 tokenizer 内有 Transformer 编解码块与 `BSQuantizer`，主模型使用分级嵌入、因果注意力、RoPE、RMSNorm、时间嵌入和依赖感知层；时间字段是分钟、小时、星期、日、月。[模型主体](https://github.com/shiyu-coder/Kronos/blob/master/model/kronos.py)；[基础模块](https://github.com/shiyu-coder/Kronos/blob/master/model/module.py)。

官方论文称预训练语料超过 120 亿根 K 线、来自 45 家全球交易所；AAAI 摘要明确支持这两个规模数字。文章所写“7 种时间粒度”出现在论文材料中，但原始预训练数据、逐条来源和完整预训练复现流水线并未随仓库公开，因此只能表述为**作者报告的训练规模**，不是本次独立复算的事实。[AAAI 摘要](https://ojs.aaai.org/index.php/AAAI/article/view/39730)；[论文 PDF](https://ojs.aaai.org/index.php/AAAI/article/download/39730/43691)。

### 2.2 已公开模型

| 模型 | 参数量 | 上下文长度 | 状态 |
|---|---:|---:|---|
| Kronos-mini | 4.1M | 2048 | 已公开 |
| Kronos-small | 24.7M | 512 | 已公开 |
| Kronos-base | 102.3M | 512 | 已公开 |
| Kronos-large | 499.2M | 512 | 未公开 |

来源：[官方 Model Zoo](https://github.com/shiyu-coder/Kronos/blob/master/README.md#-model-zoo)。`KronosPredictor.predict` 接受至少含 OHLC 的 DataFrame，`volume/amount` 可缺省；它会做单窗口标准化、截断、概率采样、样本路径平均和反标准化，返回未来 OHLCVA。`predict_batch` 可对等长历史窗口和等长预测窗口做批量推理。[预测器源码](https://github.com/shiyu-coder/Kronos/blob/master/model/kronos.py#L482)。

这意味着它能提供**概率预测路径**，但不会自动提供：股票池、交易日历、订单、持仓、T+1、板块涨跌停规则、风控、真实费用、实时行情、新闻或基本面。

## 3. 数据、策略与回测能力的真实边界

### 3.1 官方 A 股示例

仓库的正式示例链路是：准备 Qlib 中国市场日线 → 按股票构造滑动窗口 → 微调 tokenizer → 微调 predictor → 生成横截面分数 → 用 Qlib `TopkDropoutStrategy` 回测。[README 的 A 股微调章节](https://github.com/shiyu-coder/Kronos/blob/master/README.md#-finetuning-on-your-own-data-a-share-market-example)。

默认配置为 CSI 300、90 日回看、10 日预测；训练期 2011–2022，验证数据从 2022-09 开始，测试数据从 2024-04 开始，回测期 2024-07 至 2025-06。训练脚本按 README 设计为 `torchrun` 多 GPU；默认每卡 batch size 50、训练 30 epoch，且先训 tokenizer 再训 predictor。[配置源码](https://github.com/shiyu-coder/Kronos/blob/master/finetune/config.py)。

论文投资模拟使用的信号是：未来 10 根预测收盘价的算术平均值相对当前收盘价的收益，日线回看 90 日；在 CSI 300 上持有 50、每次替换 5，在 CSI 800 上持有 200、每次替换 10。论文声称每笔应用 0.15% 成本。[论文附录中的投资模拟设置](https://openreview.net/pdf/1032dad0bdf374a73ec0b7aa78ff401ab8b3d650.pdf)。

### 3.2 当前仓库的 Qlib 演示代码

当前 `finetune/qlib_test.py` 实际使用：

- `TopkDropoutStrategy(topk=50, n_drop=5, hold_thresh=5)`；
- 账户 1 亿元、CSI 300 基准；
- 日频、下一步延迟执行、开盘价成交；
- 买入成本 0.10%、卖出成本 0.15%、最低 5 元；
- 统一 `limit_threshold=0.095`；
- 从预测路径构造 `last/mean/max/min` 四种分数并分别回测。

这些是源码可核实的演示假设，不等于中国市场完整撮合规则。[Qlib 回测源码](https://github.com/shiyu-coder/Kronos/blob/master/finetune/qlib_test.py)。尤其是统一 9.5% 涨跌停阈值不能覆盖创业板、科创板和历史规则，代码也没有本项目已经实现的 T+1、停牌/一字板、股数取整、历史税费、滑点和成交额参与率状态机。[本项目撮合引擎](../a_share_lab/engine.py)。

官方自己在 README 中明确称这只是演示，不是生产级量化系统，并提醒还需要组合优化、风险因子中性化、动态仓位、止盈止损、交易成本、滑点和市场冲击建模。[官方免责声明与生产化注意事项](https://github.com/shiyu-coder/Kronos/blob/master/README.md#from-demo-to-production-important-considerations)。

## 4. 微信文章逐项核验

| 文章说法 | 核验结论 | 依据与补充 |
|---|---|---|
| “GitHub 3.5 万 Star” | **当前基本准确** | 2026-08-02 GitHub API 返回 35,502 stars；数值会继续变化。[实时仓库元数据](https://api.github.com/repos/shiyu-coder/Kronos) |
| “清华团队” | **准确** | AAAI 正式页列出的七位作者均来自清华两个院系。[AAAI](https://ojs.aaai.org/index.php/AAAI/article/view/39730) |
| “论文被 AAAI 2026 收录” | **准确，且已正式出版** | 2026-03-14 出版，不只是待录用状态。[AAAI](https://ojs.aaai.org/index.php/AAAI/article/view/39730) |
| “全球第一个面向金融 K 线的开源基础模型” | **只能确认是作者自述** | README 和论文这样定位；“全球第一”需要穷尽所有此前项目，本次无法独立证明。[README](https://github.com/shiyu-coder/Kronos/blob/master/README.md) |
| “120 多亿、45 家交易所、7 种粒度” | **前两项有正式论文支持；第 3 项见论文材料** | 原始预训练数据没有公开，无法独立复算规模、覆盖与去重质量。[论文](https://ojs.aaai.org/index.php/AAAI/article/download/39730/43691) |
| “能预测 OHLC、成交量、成交额” | **准确** | `predict` 返回六列；缺少成交量/额时会补零或估算 amount。[源码](https://github.com/shiyu-coder/Kronos/blob/master/model/kronos.py#L519) |
| “批量预测能用 GPU 并行” | **准确，但有等长窗口限制** | `predict_batch` 会堆叠 batch，要求各序列 lookback 与预测长度一致。[源码](https://github.com/shiyu-coder/Kronos/blob/master/model/kronos.py#L562) |
| “完整微调和回测链路已放出” | **部分准确** | 有 Qlib 预处理、两阶段微调和演示回测；但缺原始训练数据、完整预训练复现、生产级撮合与结果审计。[finetune 目录](https://github.com/shiyu-coder/Kronos/tree/master/finetune) |
| “前三个模型随下随用” | **权重可公开下载；完整示例不是开箱即跑** | README 快速示例引用 `./data/XSHG_5min_600977.csv`，但当前 `master` 没有该路径文件；需自行准备数据。[示例源码](https://github.com/shiyu-coder/Kronos/blob/master/examples/prediction_example.py) |
| “Python 3.10+，装 requirements 即可” | **只对核心推理近似成立** | 根依赖包含 PyTorch/Hugging Face 等；微调另需 `pyqlib`，训练脚本还无条件导入 `comet_ml`，但两者均不在根 requirements 中。[requirements](https://github.com/shiyu-coder/Kronos/blob/master/requirements.txt)；[训练脚本](https://github.com/shiyu-coder/Kronos/blob/master/finetune/train_predictor.py) |
| “官方回测图说明策略有效” | **不能据此下结论** | 图与论文结果属于作者实验；仓库没有给本次核查可直接复算的原始预训练数据、逐日信号、成交明细和完整结果表。官方也明确称回测是演示。 |
| “普通开发机器也跑得动” | **小模型推理可能，不能扩展成全市场微调承诺** | mini 仅 4.1M 参数；但全市场逐日、多路径、10 步自回归推理的工作量远大于单票演示，微调脚本明确面向多 GPU。[模型表](https://github.com/shiyu-coder/Kronos/blob/master/README.md#-model-zoo) |

## 5. 维护状态与工程成熟度

截至 2026-08-02 的 GitHub API 快照：仓库未归档，默认分支为 `master`，35,502 stars、5,913 forks、18 位 API 可见贡献者；有 202 个 open issues、50 个 open PR。最后一次推送和默认分支最新提交均为 2026-04-13，提交 `67b630e`；仓库没有 release 或 tag。[仓库 API](https://api.github.com/repos/shiyu-coder/Kronos)；[最新提交](https://github.com/shiyu-coder/Kronos/commit/67b630e67f6a18c9e9be918d9b4337c960db1e9a)；[Releases](https://github.com/shiyu-coder/Kronos/releases)；[开放 issues](https://github.com/shiyu-coder/Kronos/issues?q=is%3Aissue%20state%3Aopen)；[开放 PR](https://github.com/shiyu-coder/Kronos/pulls?q=is%3Apr%20state%3Aopen)。

这组信息应解读为：项目关注度和社区需求很高，但截至核查日主分支已有约三个半月没有合并更新，积压较多，也没有语义版本或发布包可固定。不能据此断言项目已停止维护，但集成时必须固定 commit 和模型 revision，不能直接追随浮动 `master` 或 Hugging Face `main`。

自动化测试也较窄：官方只有一个回归测试文件，覆盖两个上下文长度的固定输出和少量 MSE 样本；测试内值得借鉴的一点是它固定了模型与 tokenizer revision。仓库没有可见 GitHub Actions 工作流。[回归测试](https://github.com/shiyu-coder/Kronos/blob/master/tests/test_kronos_regression.py)。

## 6. 对本项目可复用的部分

### 6.1 推荐复用

1. **`KronosPredictor` 推理层**：直接输出未来 K 线路径，不引入其 WebUI、第三方示例或 Qlib 回测器。
2. **`predict_batch`**：把同一交易日所有具有足够历史的股票按小批次推理，降低逐票 Python 开销。
3. **论文的单一信号公式**：固定 `score_t = mean(pred_close[t+1:t+10]) / close_t - 1`，先不同时搜索 `last/mean/max/min`，避免新增多重尝试。
4. **revision 固定方式**：像官方回归测试一样固定 Git commit、模型 revision、tokenizer revision、随机种子、温度、top-p 和 sample count。
5. **模型输出缓存**：按 `signal_date + code + model_revision + data_manifest_sha256 + params` 保存预测，回测只消费冻结信号，不在每次参数扫描时重算模型。

### 6.2 不建议复用

1. **不复用 `finetune/qlib_test.py` 的撮合**：本项目 [`a_share_lab/engine.py`](../a_share_lab/engine.py) 对 A 股规则与成本更完整。
2. **不把预测 OHLC 当成交价**：它们只能产生分数，真实下单仍按下一交易日原始开盘价和可成交状态。
3. **不先搬 WebUI 和社区示例**：它们不解决信号是否有净 alpha 的核心问题，还会扩大依赖与维护面。
4. **不先做 A 股微调**：目前样本外区间已经被本轮策略研究看过；继续在同一时期训练或调参无法产生新的干净证据。
5. **不采用缺省“无量则全补零”作为唯一方案**：本项目已有真实 `volume/amount`，应保留；同时可将“只用 OHLC”作为预先声明的稳健性对照，而非事后择优。

## 7. 建议的集成接口

```text
BaoStock 原始日线
  ├─ 原始 OHLC → 现有撮合、涨跌停、费用、持仓估值
  └─ point-in-time 连续信号 K 线 → Kronos 90 日窗口
                                      ↓
                          未来 10 日预测收盘路径
                                      ↓
                      固定 score = 预测均价 / 当日收盘 - 1
                                      ↓
                       横截面排名 / 与现有策略组合
                                      ↓
                     t+1 开盘交给 a_share_lab 撮合
```

本项目当前数据表已有 `open/high/low/close/volume/amount/date/code`，字段层面与 Kronos 直接兼容。[数据模块](../a_share_lab/data.py)。真正需要处理的是复权与时点：原始未复权价必须继续用于成交；送入模型的 K 线应使用当日可知的连续价格尺度，避免除权缺口被模型当成暴跌。可以用本项目已有 `pctChg` 累乘的 `signal_price` 构造点时连续 close，再按当日比例同步缩放 open/high/low；这一做法必须新增单元测试，确保不借用未来复权因子。[特征构造](../a_share_lab/engine.py#L96)。

建议第一版只新增一个冻结规格：

- 模型：`Kronos-small`，固定 Hugging Face revision；
- 输入：90 个交易日、日线、真实 volume/amount；
- 输出：未来 10 个交易日；
- 推理：`T=0.6`、`top_p=0.9`、`sample_count=5`（资源允许后再对照论文的 10）；
- 分数：未来 10 日预测 close 均值相对当前 close 的收益；
- 股票池：沿用历史 CSI 300 + CSI 500 快照；
- 成交：`t` 日收盘生成，`t+1` 开盘尝试；
- 对照：当前固定策略、风险调整 20 日动量、中证 800、当日股票池等权；
- 窗口：分别报告最近 1 个月、3 个月、6 个月、1 年、3 年，但不得从这些窗口中挑冠军后反称为样本外结果。

## 8. 集成成本与本机约束

| 工作 | 成本判断 | 主要内容 |
|---|---|---|
| 单票/少量股票 smoke test | 低 | 独立研究依赖、下载 small/tokenizer、校验输入输出、固定 revision |
| 接入现有日线信号层 | 中 | 连续 K 线适配、交易日历、批量推理、缓存、确定性测试、失败恢复 |
| 1–3 年全股票池滚动推理 | 中高 | 每日约千只股票 × 多步自回归 × 多样本路径；GPU/缓存吞吐是主要瓶颈 |
| 复现实验级 A 股微调 | 高 | Qlib 数据、两阶段训练、`torchrun`、多 GPU、checkpoint 与验证治理 |
| 升级为生产实盘 | 很高且当前不建议 | 数据 SLA、延迟、漂移、模型版本、实盘滑点、监控、回滚、合规与风控 |

本次只读硬件检查显示当前机器为 GeForce MX250 2GB 显存、约 16GB 内存。它适合 CPU 或极小 batch 的 mini/small 冒烟验证，不适合把官方多 GPU 微调方案当成本地常规流程；`Kronos-base` 的全市场批量推理也应先做显存与耗时基准，不能凭参数量推断可用。

依赖应与现有研究环境隔离：Kronos 根依赖要求 `torch>=2.0`、`huggingface_hub`、`safetensors`、`einops` 等，而本项目目前的 [`requirements-research.txt`](../requirements-research.txt) 是轻量 NumPy/Pandas/BaoStock 环境。建议单独建立可选 extra 或独立虚拟环境，避免为了一个研究信号把交易脚本运行环境整体升级。

## 9. 主要风险与不能验证的宣传

1. **论文指标不是收益承诺。** 官方报告的 RankIC、波动预测和生成质量提升是相对特定基准的实验结果，未在本项目数据、费用和撮合下复现。[AAAI 摘要](https://ojs.aaai.org/index.php/AAAI/article/view/39730)。
2. **预训练数据不可完全审计。** 规模和交易所覆盖由作者报告，原始数据、许可、时间范围与完整清洗流水线没有随仓库发布，无法排除目标时期与评测市场重叠带来的记忆或分布泄漏风险。
3. **模型只看 K 线。** 它没有订单簿、公告、基本面、资金约束和交易规则；在消息跳空、停牌、除权和制度切换时容易失真。
4. **预测是随机的。** 温度、top-p、采样条数和随机种子会改变结果；不保存版本与预测缓存，就无法做审计一致的回测。
5. **上下文有限。** small/base 只看最多 512 根；日线足够覆盖约两年，但分钟线只覆盖很短历史，文章对“多时间粒度通吃”的直觉不能替代逐粒度验证。
6. **生成值没有交易可行性保证。** 源码直接解码六维连续值，没有显式强制每根预测满足 `low <= open/close <= high`，也不保证成交量非负；作为 close 排名信号尚可，不能拿整条路径模拟止损止盈成交。
7. **官方演示仍有工程缺口。** 快速示例缺被引用的样本 CSV；微调依赖未完整列入根 requirements；没有 release/tag 和持续集成；open issues/PR 较多。
8. **许可证不等于结果担保。** 代码和公开模型卡标 MIT，可使用、修改和再发布，但需保留版权与许可声明，且明确“按原样”提供、不承担损失担保。[LICENSE](https://github.com/shiyu-coder/Kronos/blob/master/LICENSE)。

## 10. 最终判断

Kronos 值得做一个**受控的零样本因子实验**，因为它的输入与本项目现有日线数据高度兼容，公开 small 模型不大，且论文给出了清晰的 90→10 日信号定义。它不值得直接接管现有策略，更不值得因为 3.5 万 stars 或一张回测图就进入模拟盘/实盘。

进入下一步的门槛应是：固定版本的 Kronos 信号在至少两个不重叠时期都带来增量 RankIC 或扣费收益，结果对相邻采样参数不过度敏感，在本项目高成本、T+1、涨跌停和容量约束下仍不劣于简单风险调整动量。否则将其归类为研究型特征，不继续投入微调算力。

## 一手来源索引

- [微信公众号原文](https://mp.weixin.qq.com/s/LKHQW9rn8GMFDZsl6i0P8Q)
- [Kronos 官方 GitHub 仓库](https://github.com/shiyu-coder/Kronos)
- [Kronos README](https://github.com/shiyu-coder/Kronos/blob/master/README.md)
- [AAAI 2026 正式论文页](https://ojs.aaai.org/index.php/AAAI/article/view/39730)
- [AAAI 论文 PDF](https://ojs.aaai.org/index.php/AAAI/article/download/39730/43691)
- [arXiv 论文页](https://arxiv.org/abs/2508.02739)
- [Kronos 模型源码](https://github.com/shiyu-coder/Kronos/blob/master/model/kronos.py)
- [Kronos 基础模块源码](https://github.com/shiyu-coder/Kronos/blob/master/model/module.py)
- [A 股微调配置](https://github.com/shiyu-coder/Kronos/blob/master/finetune/config.py)
- [Qlib 数据预处理](https://github.com/shiyu-coder/Kronos/blob/master/finetune/qlib_data_preprocess.py)
- [Qlib 推理与回测示例](https://github.com/shiyu-coder/Kronos/blob/master/finetune/qlib_test.py)
- [官方回归测试](https://github.com/shiyu-coder/Kronos/blob/master/tests/test_kronos_regression.py)
- [Kronos-base Hugging Face 模型卡](https://huggingface.co/NeoQuasar/Kronos-base)
- [MIT LICENSE](https://github.com/shiyu-coder/Kronos/blob/master/LICENSE)
- [GitHub 实时仓库元数据](https://api.github.com/repos/shiyu-coder/Kronos)
