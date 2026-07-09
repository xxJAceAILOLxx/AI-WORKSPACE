---
tags: [strategy, mean-reversion, volume, prop-firm, novel]
---

# LVPR — Low-Volume Pullback Reversion (and `funded_reversion` portfolio)

## Why this exists (novel vs common)

The vault already has IBS / RSI(2) / %B / TOM / dual-MA mean-reversion. Those are
*common* and, per the backtests, weak (PF ~1.2-1.7, Sharpe <1). This strategy is
deliberately different and is built on a vault gotcha:

> **High-volume selloffs in broad ETFs are institutional distribution — net losers.**
> (memory.md §8: high-volume IBS entries = 33.3% WR.)

So instead of the usual "volume *confirms* the reversal," LVPR fades only **quiet
pullbacks** — price stretched below its mean **on below-average volume**. Low effort
(volume) vs a stretched result (price) = exhaustion, not distribution.

## Rules (`backtest/strategies/lvpr.py`)

**Entry (long):**
- Stretch: `IBS < 0.30` **OR** `Close < lower Bollinger(20, 2)`
- Quiet: `vol_ratio <= 1.0` (volume vs 20-day avg)
- Trend filter: `Close > SMA200`

**Exit:** `Close >= SMA20` (reversion done) **OR** 2×ATR(14) stop **OR** 10-day hold.

**Sizing:** `percent_of_equity` (default 0.95) — never `fixed_risk` at 10% (that
over-leverages low-ATR ETFs ~4-10× and blows the 5% daily-loss limit).

## Best single config (2016-2025, next-open, etf_0.1pct)

| Ticker | ibs_max | vol_max | PF | Sharpe | WR | trades | eq_dd |
|---|---|---|---|---|---|---|---|
| QQQ | 0.30 | 0.80 | **2.59** | 0.86 | 69.7% | 89 | 6.2% |
| SPY | 0.30 | 0.80 | 1.54 | 0.26 | 63.0% | 81 | 6.7% |

OOS (2022-2025) QQQ: PF 1.66, Sharpe 0.32, WR 72.2% — edge holds, decays normally.

## Portfolio deployment — `funded_reversion`

Runs LVPR across a basket, each on its own capital slice, equity summed over a
common calendar. Two modes:

- **SAFE (1x):** SPY,QQQ,IWM,GLD,DIA,MDY,SLV @ alloc 0.95 → PF 1.30, Sharpe 0.44,
  eq_dd 6.25%, max daily 1.54%, 1227 trades. MC survival 100%, P(maxDD<10%) 99.8%.
  **Passes prop risk rules almost always.** CAGR only ~1.4% — too slow for a 30-day +10% target.
- **TURBO (2x):** SSO,QLD,UWM,DDM @ alloc 0.6 → CAGR ~3%, eq_dd 11%, MC P(maxDD<10%) 88%.
  Borderline on the hard 10% DD limit; use alloc ~0.5 to stay <10%.

## Honest verdict for prop-firm passing

- Risk rules (10% DD, 5% daily): trivially passed by SAFE mode (~99%+).
- **+10% in 30 days is NOT achievable on daily ETF MR at safe sizing.** Options:
  intraday variants, 2x ETFs with elevated DD risk, or a longer/"flex" challenge window.
- Payout consistency rules are naturally satisfied (frequent trades, tiny daily loss).
- Once funded: scale with 2x ETFs and add instruments (KRE, XLE, …) to compound.

## Related

[[Volume-Scaled IBS]] (the inverse approach) · [[Funded 80% Pass Strategy]] · [[All Strategies Backtest]]
