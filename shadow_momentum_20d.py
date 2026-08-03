"""
"风险调整20日动量"纸面观察线（对应 research/a_share_backtest_report_2026-08-02.md
建议②：从2026-08起冻结两个纸面组合观察3-6个月，不改规则）。

只读公开行情（baostock），只在本地记录模拟净值/持仓/成交，不碰真实账户、密钥，
不向任何broker下单——跟 stock_auto_trade.py 完全独立，不共用任何真实交易通道。

做法：复用 a_share_lab 已经验证过的回测引擎（entry/exit规则、成本假设跟
research/results/a_share_strategy_specs.json 里 risk_adjusted20_4_ma20 完全一致），
每天收盘后把行情缓存增量补到当天，再对 [FROZEN_START_DATE, 今天] 这个只增不改的窗口
重新跑一遍回测——这样"实时纸面结果"和"当初验证过的规则"保证是同一套代码，不会因为
另外手写一套实时交易循环而产生逻辑分叉。

用法：
    python3 shadow_momentum_20d.py          # 跑一次，日结用
"""
from __future__ import annotations

import datetime
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from a_share_lab.data import (
    default_cache_dir,
    fetch_symbol_history,
    fetch_benchmark,
    load_public_bundle,
)
from a_share_lab.engine import BacktestConfig, StrategySpec, prepare_features, run_backtest

# 报告建议②："从2026-08起冻结两个纸面组合"——这个日期定了就不再改，改了这条观察线就失去意义
FROZEN_START_DATE = '2026-08-04'

# 跟 a_share_lab/experiments.py 里 risk_adjusted20_4_ma20、
# research/results/a_share_strategy_specs.json 里存的定义完全一致，不能私自调参数——
# 调了就不是"观察报告里验证过的方案"了
SPEC = StrategySpec(
    name='risk_adjusted20_4_ma20',
    entry_model='risk_adjusted_20d',
    max_positions=4,
    stop_loss=-0.08,
    take_profit=0.15,
    max_holding_days=20,
    exit_model='ma20',
)

_DIR = Path(__file__).resolve().parent
NAV_LOG = _DIR / 'shadow_momentum_20d_nav.local.csv'
TRADE_LOG = _DIR / 'shadow_momentum_20d_trades.local.csv'


def _incremental_update_cache(cache_dir: Path, end_date: str) -> tuple[int, list]:
    """只把每只股票缓存补到end_date为止的新增行情，不重新下载整段历史。"""
    import baostock as bs

    prices_dir = cache_dir / 'prices'
    membership_path = cache_dir / 'memberships.csv.gz'
    benchmark_path = cache_dir / 'benchmark_csi800.csv.gz'
    if not membership_path.exists() or not prices_dir.exists():
        raise FileNotFoundError(
            '本地缓存不存在，先跑一次全量下载: '
            "python3 -c \"from a_share_lab.data import download_public_bundle, default_cache_dir; "
            "download_public_bundle('2021-01-01', '<今天>', default_cache_dir())\""
        )

    memberships = pd.read_csv(membership_path, parse_dates=['snapshot_date'])
    codes = sorted(memberships['code'].unique())

    login = bs.login()
    if login.error_code != '0':
        raise RuntimeError(f'BaoStock登录失败: {login.error_code} {login.error_msg}')
    updated, failed = 0, []
    try:
        for code in codes:
            symbol_path = prices_dir / f"{code.replace('.', '_')}.csv.gz"
            if not symbol_path.exists():
                continue
            existing = pd.read_csv(symbol_path, parse_dates=['date'])
            if existing.empty:
                continue
            last_date = existing['date'].max()
            if last_date >= pd.Timestamp(end_date):
                continue
            fetch_start = (last_date + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
            try:
                new_rows = fetch_symbol_history(bs, code, fetch_start, end_date)
            except Exception as e:
                failed.append((code, str(e)))
                continue
            if new_rows.empty:
                continue
            combined = (
                pd.concat([existing, new_rows], ignore_index=True)
                .drop_duplicates(['date', 'code'])
                .sort_values('date')
            )
            combined.to_csv(symbol_path, index=False, compression='gzip')
            updated += 1

        if benchmark_path.exists():
            benchmark = pd.read_csv(benchmark_path, parse_dates=['date'])
            last_bench_date = benchmark['date'].max()
            if last_bench_date < pd.Timestamp(end_date):
                fetch_start = (last_bench_date + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
                try:
                    new_bench = fetch_benchmark(bs, fetch_start, end_date)
                except RuntimeError:
                    # 当天还没收盘/还没有新的交易日数据可取，跳过，明天再补——不算失败
                    new_bench = pd.DataFrame()
                if not new_bench.empty:
                    benchmark = (
                        pd.concat([benchmark, new_bench], ignore_index=True)
                        .drop_duplicates(['date'])
                        .sort_values('date')
                    )
                    benchmark.to_csv(benchmark_path, index=False, compression='gzip')
    finally:
        bs.logout()
    return updated, failed


def _append_nav_row(row: dict) -> None:
    """按日期去重追加，重复跑同一天不会在日志里留两行。"""
    if NAV_LOG.exists():
        existing = pd.read_csv(NAV_LOG)
        existing = existing[existing['date'] != row['date']]
        combined = pd.concat([existing, pd.DataFrame([row])], ignore_index=True)
    else:
        combined = pd.DataFrame([row])
    combined.to_csv(NAV_LOG, index=False)


def run() -> None:
    today = datetime.date.today().strftime('%Y-%m-%d')
    cache_dir = default_cache_dir()

    updated, failed = _incremental_update_cache(cache_dir, today)
    if failed:
        print(f'⚠️ {len(failed)}只股票增量更新失败(不影响其它股票的观察结果): {failed[:5]}')
    print(f'增量更新了{updated}只股票的行情缓存')

    bundle = load_public_bundle(cache_dir)
    features = prepare_features(bundle.prices)
    result = run_backtest(
        features, bundle.memberships, bundle.benchmark, SPEC,
        start_date=FROZEN_START_DATE, end_date=today,
    )

    equity_curve = result['equity_curve']
    if equity_curve.empty:
        print(f'{today}: 冻结观察从{FROZEN_START_DATE}开始，还没有可用的交易日结果')
        return

    latest = equity_curve.iloc[-1]
    initial_capital = BacktestConfig().initial_capital
    nav = float(latest['equity']) / initial_capital
    row = {
        'date': today,
        'equity': round(float(latest['equity']), 2),
        'nav': round(nav, 4),
        'positions': int(latest['positions']),
        'total_return_pct': round((nav - 1) * 100, 2),
    }
    _append_nav_row(row)

    trades = result['trades']
    if not trades.empty:
        trades.to_csv(TRADE_LOG, index=False)

    print(
        f"[{today}] 纸面观察(风险调整20日动量): "
        f"净值{nav:.4f} 累计{row['total_return_pct']}% 当前持仓{row['positions']}只"
    )


if __name__ == '__main__':
    run()
