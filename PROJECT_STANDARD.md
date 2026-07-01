# AI 炒股项目规范

---

## 📋 项目概述

- **目标市场**：A股 + ETF（不含港股、美股）
- **比赛**：
  - 东方财富（6.8-6.12）
  - 华泰柏瑞（6.11-7.20）
- **风险接受度**：最大回撤 -30% 以内

---

## 🔧 环境准备

### 必装依赖

```bash
pip3 install akshare baostock pandas numpy
```

### 数据获取

| 数据源 | 用途 | 命令 |
|--------|------|------|
| **baostock** | 指数历史数据（主用） | `bs.query_history_k_data_plus()` |
| akshare | ETF数据（备用） | `ak.fund_etf_hist_em()` |

### 登录baostock

```python
import baostock as bs
bs.login()
# ... 数据获取 ...
bs.logout()
```

---

## 📊 回测标准流程

### 1. 数据获取

```python
def get_index_data(code, name, start_date="2016-01-01", end_date="2026-06-07"):
    """获取指数历史数据"""
    rs = bs.query_history_k_data_plus(
        code,
        "date,open,high,low,close,volume",
        start_date=start_date,
        end_date=end_date,
        frequency="d",
        adjustflag="2"  # 前复权
    )
    # 转换DataFrame...
    return df
```

### 2. 策略逻辑（均线金叉）

```python
def ma_cross_strategy(df, short=5, long=20):
    """均线金叉策略"""
    df = df.copy()

    # 计算均线
    df["ma_short"] = df["close"].rolling(short).mean()
    df["ma_long"] = df["close"].rolling(long).mean()

    # 信号
    df["signal"] = 0
    # 金叉买入
    df.loc[(df["ma_short"] > df["ma_long"]) &
           (df["ma_short"].shift(1) <= df["ma_long"].shift(1)), "signal"] = 1
    # 死叉卖出
    df.loc[(df["ma_short"] < df["ma_long"]) &
           (df["ma_short"].shift(1) >= df["ma_long"].shift(1)), "signal"] = -1

    # 持仓
    df["position"] = df["signal"].replace(-1, 0).cumsum().clip(lower=0)
    df["position"] = df["position"].apply(lambda x: 1 if x > 0 else 0)

    # 收益
    df["daily_return"] = df["close"].pct_change()
    df["strategy_return"] = df["position"].shift(1) * df["daily_return"]

    # 累计
    df["cum_bh"] = (1 + df["daily_return"]).cumprod()
    df["cum_strat"] = (1 + df["strategy_return"]).cumprod()

    # 最大回撤
    rolling_max = df["cum_strat"].cummax()
    df["drawdown"] = (df["cum_strat"] - rolling_max) / rolling_max
    max_dd = df["drawdown"].min() * 100

    return {
        "持有总收益": (df["cum_bh"].iloc[-1] - 1) * 100,
        "策略总收益": (df["cum_strat"].iloc[-1] - 1) * 100,
        "最大回撤": max_dd,
    }
```

### 3. 回测时间段

| 时间段 | 天数 | 用途 |
|--------|------|------|
| 近5年 | 365*5 | 长期评估 |
| 近3年 | 365*3 | 中期评估 |
| **近1年** | 365 | 标准评估 |
| 近6月 | 180 | 短期评估 |
| 近3月 | 90 | 近期评估 |
| **近1月** | 30 | 比赛参考 |
| **近2周** | 14 | 比赛参考 |

### 4. 评估指标

| 指标 | 计算方式 | 风险阈值 |
|------|---------|---------|
| 持有总收益 | 买入持有策略累计收益 | - |
| 策略总收益 | 均线策略累计收益 | - |
| 差异 | 策略收益 - 持有收益 | 正数=策略胜出 |
| **最大回撤** | (策略净值 - 历史最高) / 历史最高 | **< -30% 为高风险** |

### 5. 风险评估标准

| 符号 | 最大回撤范围 | 含义 |
|------|-------------|------|
| 🟢 | > -20% | 低风险 |
| 🟡 | -20% ~ -30% | 中风险 |
| 🔴 | < -30% | **高风险（超出用户接受度）** |

---

## 📈 ETF/指数对照表

### 宽基ETF

| ETF | 代码 | 对应指数 | 市场 |
|------|------|---------|------|
| 上证50ETF | 510050 | sh.000016 | 沪市 |
| 沪深300ETF | 510300 | sh.000300 | 沪市 |
| 中证500ETF | 510500 | sh.000905 | 沪市 |
| 中证1000ETF | 512100 | sh.000852 | 沪市 |
| 科创50ETF | 588000 | sh.000688 | 沪市 |

### 科技/半导体ETF

| ETF | 代码 | 对应指数 | 市场 |
|------|------|---------|------|
| 半导体ETF | 512480 | - | 沪市 |
| 芯片ETF | 512760 | - | 沪市 |
| 科创芯片ETF | 588780 | - | 沪市 |

### 金融ETF

| ETF | 代码 | 对应指数 | 市场 |
|------|------|---------|------|
| 证券ETF | 512880 | - | 沪市 |
| 银行ETF | 515180 | - | 沪市 |

### 医药ETF

| ETF | 代码 | 对应指数 | 市场 |
|------|------|---------|------|
| 医药ETF | 512010 | - | 沪市 |
| 医疗ETF | 512170 | - | 沪市 |

### 新能源ETF

| ETF | 代码 | 对应指数 | 市场 |
|------|------|---------|------|
| 新能源车ETF | 515030 | - | 沪市 |
| 光伏ETF | 515790 | - | 沪市 |
| 新能源ETF | 516160 | - | 沪市 |

### 消费ETF

| ETF | 代码 | 对应指数 | 市场 |
|------|------|---------|------|
| 酒ETF | 512690 | - | 沪市 |
| 房地产ETF | 512200 | - | 沪市 |

### 周期/资源ETF

| ETF | 代码 | 对应指数 | 市场 |
|------|------|---------|------|
| 有色金属ETF | 512400 | - | 沪市 |
| 有色ETF | 512990 | - | 沪市 |

### 其他ETF

| ETF | 代码 | 对应指数 | 市场 |
|------|------|---------|------|
| 军工ETF | 512660 | - | 沪市 |
| 传媒ETF | 512980 | - | 沪市 |
| 中概互联ETF | 513050 | - | 沪市 |

---

## 📁 文件命名规范

| 文件 | 用途 |
|------|------|
| `backtest.py` | 回测脚本 |
| `backtest_result.csv` | 近1年回测结果 |
| `backtest_full_result.csv` | 全时间段回测结果 |
| `strategy_log.md` | 策略日志 |
| `PROJECT_STANDARD.md` | 本文档 |

---

## ⚠️ 注意事项

1. **baostock 每次使用前要 login，使用后要 logout**
2. **数据获取失败要先检查网络，再换数据源**
3. **回测必须覆盖多个时间段，不能只看近1年**
4. **风险评估是核心，最大回撤超过 -30% 要警惕**
5. **比赛只有一周时，简单持有可能优于均线策略**

---

## 🎯 决策流程

```
获取数据
    ↓
多时间段回测（5年/3年/1年/6月/3月/1月/2周）
    ↓
评估指标：收益 vs 持有、最大回撤、风险评估
    ↓
决策：
- 策略收益 > 持有 且 最大回撤 < -30% → 考虑使用
- 策略收益 < 持有 → 简单持有
- 最大回撤 > -30% → 不使用该策略
    ↓
执行交易
    ↓
每日记录净值到 strategy_log.md
```

---

## 📝 策略日志模板

```markdown
## 📅 YYYY.MM.DD | 记录

### 当前持仓
| 标的 | 代码 | 数量 | 市值 | 仓位 | 盈亏 |

### 当日操作
| 时间 | 操作 | 代码 | 数量 | 成交价 | 委托单号 |

### 净值记录
| 日期 | 总资产 | 收益率 | 备注 |

### 策略思考
- 市场分析
- 策略调整
- 风险评估

### 待办
- [ ] ...
```

---
