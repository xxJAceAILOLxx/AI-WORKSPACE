# Funded 80% Pass Strategy — Honest Results

> Status: **Backtested — Realistic Assessment**
> Backtested: 2026-06-26
> Period: 2016-2025 (10 years)
> Instruments: QQQ, SPY, IWM, DIA, GLD, BTC, ETH, EURUSD, GBPUSD, USDJPY
> Code: `Strategies/funded_80_pass.py`

---

## The Honest Truth

**80% pass rate is not achievable with daily-bar strategies and realistic sizing.**

The best individual instrument pass rate found was **23% (BTC Trend)**. Through portfolio diversification across uncorrelated instruments, we can reach **60-72%** pass rate.

---

## Single-Instrument Pass Rates (30-day window)

| Rank | Instrument | Strategy | Pass Rate |
|------|-----------|----------|-----------|
| 1 | BTC | Trend (Close > 50 SMA) | 23% |
| 2 | QQQ | Trend (Close > 50 SMA) | 18% |
| 3 | SPY | Trend (Close > 50 SMA) | 16% |
| 4 | QQQ | IBS < 0.30 | 15% |
| 5 | SPY | IBS < 0.30 | 14% |
| 6 | QQQ | Combo (IBS + Z-score) | 14% |
| 7 | IWM | IBS < 0.30 | 13% |
| 8 | GLD | Trend (Close > 50 SMA) | 12% |

---

## Portfolio Pass Rates (P at least 1 instrument passes)

| Portfolio | Instruments | Avg Single PR | Portfolio PR |
|-----------|-------------|---------------|--------------|
| QQQ+SPY+BTC+GLD | 4 | 17% | **52%** |
| QQQ+SPY+BTC+ETH+GLD | 5 | 15% | **57%** |
| QQQ+SPY+IWM+BTC+GLD | 5 | 16% | **58%** |
| QQQ+SPY+BTC+IWM+ETH+GLD | 6 | 15% | **63%** |
| QQQ+SPY+BTC+IWM+ETH+GLD+DIA | 7 | 15% | **68%** |
| 8-instrument portfolio | 8 | 14% | **72%** |

---

## Recommended Configuration

### Instruments (6-7)
| Instrument | Strategy | Why |
|------------|----------|-----|
| BTC | Trend (50 SMA) | Highest single pass rate (23%) |
| QQQ | Trend (50 SMA) | Strong momentum (18%) |
| SPY | IBS < 0.30 | Mean reversion diversification |
| IWM | IBS < 0.30 | Uncorrelated to QQQ/SPY |
| GLD | Trend (50 SMA) | Safe haven, uncorrelated |
| ETH | Trend (50 SMA) | Crypto diversification |
| DIA | IBS < 0.30 | Sector diversification |

### Risk Parameters
| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Risk per instrument | 2-3% | Total portfolio risk 12-21% |
| Stop loss | 2-3% | Tight enough to survive DD |
| Take profit | 2-3% | 1:1 R:R for high win rate |
| Max position | 25% | Never over-concentrate |
| Hold period | 2-5 days | Short hold = more opportunities |

### Position Sizing (Dynamic)
| Current DD | Risk Adjustment |
|------------|-----------------|
| 0-3% | Full size (100%) |
| 3-6% | Reduced (75%) |
| 6-8% | Minimal (50%) |
| >8% | Stop trading |

---

## Monte Carlo Results (1000 simulations)

| Portfolio | Pass Rate | Avg Pass Day |
|-----------|-----------|--------------|
| 4 instruments | 46% | 14.4 days |
| 5 instruments | 49-57% | 13.3-13.5 days |
| 3 instruments | 40% | 13.6 days |

---

## Why 80% Is Not Achievable

1. **Daily bars limit trade frequency** — max 1-3 trades per 30-day window
2. **Realistic sizing caps return** — can't risk 50%+ per trade
3. **DD limit of 10% is tight** — one bad trade can end the challenge
4. **Market regimes matter** — bear markets kill momentum strategies
5. **No strategy has >23% individual pass rate** — even the best fails 77% of the time

---

## What Would Push Pass Rate Higher

1. **Intraday data** — more trades per day = more chances to hit target
2. **Leverage** — 2x leverage doubles expected return (and risk)
3. **Higher volatility instruments** — crypto, small caps, forex crosses
4. **Aggressive front-loading** — risk 5-10% per trade in first 10 days
5. **News/event trading** — targeted catalyst plays for 5-10% moves

---

## Honest Verdict

| Metric | Value |
|--------|-------|
| Best individual pass rate | 23% (BTC Trend) |
| Best portfolio pass rate | 63% (6 instruments) |
| Achievable with 8 instruments | ~72% |
| 80%+ achievable? | Only with intraday data or leverage |

**The 80% target is a good aspiration but not realistic with daily-bar strategies. A 60-70% pass rate is achievable and still profitable over multiple attempts.**

---

## Related
- [[Strategies/All Strategies Backtest]] — 12-strategy comparison
- [[Strategies/Hedge Fund Markov Method]] — regime-based filtering
- [[Building and Backtesting Strategies]] — 7-phase pipeline
