# Strategies

Framework-aware strategy specs and runners. The `.md` files are the
original Obsidian-vault strategy notes; the two `.py` files are the
framework runners.

## Runners

### `run_all.py` — run every registered strategy

```bash
python3 Strategies/run_all.py
python3 Strategies/run_all.py --sort-by sharpe --top 5
python3 Strategies/run_all.py --execution close --cost-model vix_etn_40
```

Runs every strategy in `backtest.strategies.registry.REGISTRY` on the
default 2016-2025 window, prints the ranking table, and the per-metric
winners. Supports `--include` / `--exclude` to filter the list.

### `run_strategy.py` — run a single strategy

```bash
python3 Strategies/run_strategy.py --strategy ibs_spy
python3 Strategies/run_strategy.py --strategy volume_scaled_ibs --start 2018-01-01
python3 Strategies/run_strategy.py --strategy qqq_dual_ma --execution close
```

Supports walk-forward and Monte Carlo validation:

```bash
python3 Strategies/run_strategy.py --strategy ibs_spy --walk-forward
python3 Strategies/run_strategy.py --strategy ibs_spy --monte-carlo
```

Use `--list` to see every registered strategy name.

## Strategy Notes

| Note | Description |
|---|---|
| [`IBS Mean Reversion.md`](IBS%20Mean%20Reversion.md) | Original SPY IBS<0.20 backtest (2005-2025). |
| [`Volume-Scaled IBS.md`](Volume-Scaled%20IBS.md) | IBS threshold scales inversely with volume (gap-fixed). |
| [`QQQ Dual-Signal Edge.md`](QQQ%20Dual-Signal%20Edge.md) | QQQ mean reversion + trend pullback. |
| [`All Strategies Backtest.md`](All%20Strategies%20Backtest.md) | 12-strategy comparison; superseded by `run_all.py`. |
| [`Funded 80% Pass Strategy.md`](Funded%2080%25%20Pass%20Strategy.md) | Honest prop-firm pass-rate study. |
| [`Hedge Fund Markov Method.md`](Hedge%20Fund%20Markov%20Method.md) | State-based regime classifier (concept). |
| [`Volume Profile Throwback.md`](Volume%20Profile%20Throwback.md) | Post-breakout retest setup. |

## Implemented Strategies (Registry)

The framework registry in `backtest/strategies/` currently includes:

- `ibs_spy`, `ibs_trend`, `qqq_mr`
- `rsi2_mr`, `pct_b_mr`, `multiple_days_down`, `turn_of_month`
- `volume_scaled_ibs`
- `qqq_dual_ma`, `vix_etn`, `mr_portfolio`

Run `python3 Strategies/run_strategy.py --list` for the live list.

## Execution Semantics

Default is **next-open** (honest execution). To reproduce same-bar /
close execution — and the inflated Sharpe that comes with it — pass
`--execution close`. The framework warns when this is selected.

## Costs

Strategies pull costs from `backtest.costs`. Use
`--cost-model NAME` to override per run. Available names:

- `etf_0.1pct` — default; 0.1% round-trip (SPY/QQQ/IWM)
- `vix_etn_40` — flat $40 round-trip (SVXY/VXX)
- `per_share_0.01` — $0.01/share round-trip

## Legacy Scripts

The original one-off scripts (`brute_force*.py`, `funded_edge*.py`,
`intraday_test.py`, etc.) have been moved to
[`../archive/Strategies/`](../archive/Strategies/) and are not part of
the framework.
