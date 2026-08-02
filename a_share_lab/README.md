# A 股公开数据策略实验室

这个目录用于公开、可重复的日线研究，不读取真实账户、密钥或券商 API，也不会向模拟盘/实盘下单。

## 快速运行

```powershell
python -m pip install -r requirements-research.txt
python -m a_share_lab.experiments --download
python -m a_share_lab.horizons
python -m pytest -q tests/test_a_share_lab.py
```

## 可选 Kronos 信号（低资源模式）

Kronos 仅产生收盘后横截面分数，实际成交仍由本目录的 A 股撮合引擎处理。
模型、tokenizer、官方源码提交、随机种子和采样参数均固定；默认使用 CPU、1 线程、
`Kronos-mini`、batch 1、sample 1。模型权重和预测缓存不会写入 Git。

```powershell
python -m pip install -r requirements-kronos.txt
python -m a_share_lab.kronos_setup
python -m a_share_lab.kronos_experiment `
  --codes sh.600000 `
  --start 2026-07-01 --end 2026-07-31 `
  --max-signal-dates 1
```

本机工程冒烟可以使用少量股票和日期；完整 CSI800 多年滚动推理应转移到内存和
算力更充足的机器。少量股票的 pilot 回测只能验证信号、缓存和撮合链路，不构成
收益有效性证据。

首次运行会从 BaoStock 下载历史沪深 300 + 中证 500 成分股快照和日线，缓存到已被 `.gitignore` 排除的 `data/a_share_lab/`。单股票文件支持断点续传；再次执行同一命令会复用缓存。小型汇总结果写到 `research/results/`。

默认协议：

- 研究区间：2021-01-01 至 2026-07-31；
- 训练/研究：2021-01-01 至 2024-12-31；
- 样本外：2025-01-01 至 2026-07-31；
- 股票池：历史日期可获得的沪深 300 + 中证 500 半年度快照；
- 信号：收盘后计算，下一交易日开盘尝试成交；
- 撮合：不复权 OHLC，停牌和一字板不假定成交；
- 连续信号：使用点时 `pctChg` 累乘，避免把除权缺口当成收益；
- 约束：普通 A 股 T+1、主板 100 股单位、科创板最低 200 股；
- 成本：可配置佣金、最低佣金、分时代印花税、过户费和滑点；
- 同一日 K 同时触及止损止盈时，保守地先按止损处理。

## 研究边界

这是日线代理实验，不能冒充当前 `stock_auto_trade.py` 的盘中 3 分钟扫描回测。它回答的是：“如果只用每天收盘后可知的数据，下一开盘执行，这类动量/反转假设是否仍有净收益？”

第一版仍有明确限制：

- 指数成分使用半年度点时快照，不是每日全市场可交易列表；
- OHLCV 看不到盘口排队，普通触板成交只能近似；
- `pctChg` 连续序列不是精确分红再投资组合；
- 默认佣金假设是全包佣金，若改成逐项费率必须避免重复扣证管费/经手费；
- 没有分钟数据，无法复刻盘中排名变化与实际买入时点。

规则、数据风险和策略假设的一手来源见 [`research/a_share_strategy_research.md`](../research/a_share_strategy_research.md)。

首轮完整结论见 [`research/a_share_backtest_report_2026-08-02.md`](../research/a_share_backtest_report_2026-08-02.md)。报告明确区分冻结样本外与看过测试集后的二代探索；当前没有策略通过真实自动交易验收。
