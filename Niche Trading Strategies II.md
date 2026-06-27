# Niche Trading Strategies — Scraped From Research (2026)

> Status: **Research Collection — Not Backtested**
> Scraped: 2026-06-26
> Sources: Substack quant blogs, Medium, GitHub repos, academic papers, trading research sites
> Purpose: Strategy ideas for future backtesting

---

## 1. Mean Reversion — Intraday IBS (RTY, 15-min)

**Source**: Alpha Algo Trading Research ("From the Lab: What Happens When IBS Becomes a Day Trading Strategy?")

| Metric | Long | Short | Combined |
|---|---|---|---|
| Net Profit | $30,615 | $46,190 | $76,805 |
| Profit Factor | 1.91 | 1.47 | 1.58 |
| Trades | 350 | 671 | 1,021 |
| Win Rate | 55% | 46% | ~50% |
| Time in Market | 1.5% | 1.5% | 1.5% |

**Rules**: IBS on 15-min RTY bars. Entry when IBS hits extreme, exit on mean reversion. Day trading only — no overnight positions.

**Why It Works**: Same IBS edge as daily, but on intraday timeframe = more trades. Low time in market = capital efficient.

**Monte Carlo**: Survives OHLC noise, trade shuffling, and parameter permutation. Median PF ~1.53 across surrounding parameters.

---

## 2. Mean Reversion Portfolio — RSI2 + Turnaround Tuesday + IBS + %B

**Source**: Alpha Algo Trading Research ("The Mean Reversion Portfolio That Had Only One Losing Year since 1998")

| Metric | Value |
|---|---|
| Net Profit | $710,946 |
| Max Drawdown | $17,183 |
| Return/DD | 41.37 |
| Only Losing Year | 1 (2015) |

**Components**:
- **RSI2**: Short-term oversold mean reversion
- **Turnaround Tuesday**: Calendar-based behavioral reversal
- **IBS**: Daily close-location mean reversion
- **Connors %B**: Volatility-stretch pullback model

**Key Insight**: Each strategy is imperfect alone. Combined, they produce a 41.37 Return/DD ratio. The diversification between strategy types (calendar, price-location, volatility-stretch) is what makes it robust.

---

## 3. Multiple Days Down — Connors/Alvarez 2009

**Source**: Alpha Algo Trading Research ("This 2009 Trading Strategy Still Wins 75% of the Time")

| Metric | ES | NQ | Combined |
|---|---|---|---|
| Total Profit | $115,038 | $198,150 | $313,188 |
| Win Rate | 75.24% | 75.00% | 75.13% |
| Profit Factor | 2.60 | 3.33 | 3.00 |
| Return/DD | — | — | 16.14 |
| Weekly Correlation | — | — | 0.25 |

**Rules**: Buy after N consecutive down days inside a broader bullish trend. Simple dip-buying model.

**Why It Works**: Published 2009, rules public for 17+ years. More than half the track record is post-publication out-of-sample. The edge survived because it exploits behavioral overreaction — humans keep panic-selling after bad days.

---

## 4. 5-Day Low of the Range

**Source**: QuantifiedStrategies.com

| Metric | Value |
|---|---|
| Total Trades | 517 |
| Winners | 309 (59.8%) |
| Avg Return/Trade | 0.46% |
| Annualized Return | 10.76% (3-7 day hold) |
| Max Drawdown | 20% |

**Rules**: IBS < 0.25 AND Close < Lowest Low of previous 5 days. Exit after 3-7 days.

**Key Insight**: Returns peak at 3-7 day holding period. The strategy captures mean reversion from oversold extremes that also broke below recent support.

---

## 5. Mean Reversion + Seasonal Filter

**Source**: QuantifiedStrategies.com

| Metric | Value |
|---|---|
| Total Trades | 288 |
| Avg Gain/Trade | 0.9% |
| Win Ratio | 79% |
| Profit Factor | 3.9 |
| CAGR | 7.8% |
| Time in Market | 11% |
| Risk-Adjusted Return | 70% (CAGR / exposure) |
| Max Drawdown | 16% |

**Rules**: Mean reversion entry + seasonal filter to avoid weak periods. Same rules across entire test period — no optimization.

**Key Insight**: Filtering for seasonal windows dramatically improves risk-adjusted returns. The strategy spends 89% of its time in cash.

---

## 6. Turn-of-Month (TOM) — Pure Calendar

**Source**: Multiple sources (QuantSeeker, BacktestedStrategies, QuantifiedStrategies)

| Metric | Value |
|---|---|
| Buy | Last trading day of month (close) |
| Sell | 3rd trading day of new month (close) |
| Win Rate | 62-67% |
| Profit Factor | 2.0-2.8 |
| CAGR | 4.2-7.4% |
| Time in Market | ~33% |
| Max Drawdown | 15-27% |

**Why It Works**: Institutional cash flows (pensions, retirement contributions) hit at month-end. Portfolio rebalancing and window dressing add buying pressure. The effect persists but has weakened in recent years on SPY — stronger in IWM and international markets.

---

## 7. VIX ETN Volatility Strategy (Concretum Research)

**Source**: Concretum Research / Quantpedia Awards 2026

| Metric | Value |
|---|---|
| CAGR | 16.3% |
| Sharpe Ratio | 1.00 |
| Max Drawdown | 12% |
| Correlation to SPY | ~15% |
| Alpha | 15% |
| Beta | 0.12 |
| Period | 2008-2025 |

**Rules**:
1. **Signal 1 (eVRP)**: Expected Volatility Risk Premium — short vol when VIX > realized vol
2. **Signal 2 (Term Structure)**: VIX vs VIX3M — short vol in contango, long vol in backwardation
3. **Sizing**: VIX/100 (dynamic — reduces size when vol is low, increases when vol is high)
4. **Execution**: Market-on-Close order, 3:45 PM ET daily

**Instruments**: SVXY (short vol) and VXX (long vol). Two instruments, one account.

**Key Insight**: The strategy is short vol 90% of the time, cash 6%, long vol 4%. The dynamic sizing is crucial — it prevents oversized positions during volmageddon events.

---

## 8. VIX Term Structure Arbitrage

**Source**: Valuelytica Research

| Metric | 20% Alloc | 30% Alloc | 50% Alloc |
|---|---|---|---|
| CAGR | 11.0% | 18.2% | 29.8% |
| Volatility | 6.14% | 9.43% | 15.37% |
| Sharpe | ~1.8 | ~1.9 | ~1.9 |

**Rules**: Short VIXY (front-month VIX futures) + Long VIXM (mid-term VIX futures). Beta-neutral. Harvests roll decay — front-month decays faster than back-month.

**Key Insight**: By being beta-neutral, you isolate the term-structure decay from directional vol exposure. Sharpe approaches 2.0 at higher allocations.

---

## 9. PTrans2PGEX — Options Market Structure

**Source**: GammaEdge

| Metric | Value |
|---|---|
| Total Return | 1,348% vs SPY 398% |
| Win Rate | 75.55% |
| Total Trades | 1,783 |
| Max Drawdown | 29.21% vs SPY 33.57% |
| Avg Trade | $755.97 |

**Rules**:
1. **Entry**: Stock starts below PTrans (call speculator control level), closes above PTrans → buy next open
2. **Exit**: Stock closes above PGEX (highest call gamma exposure) → sell next open
3. **Size**: 4-7% of equity per trade
4. **No stops** — options market structure provides natural exit

**Key Insight**: The options market creates structural forces that push prices predictably. PTrans = where call buyers take control. PGEX = where gamma exposure peaks. The move between these levels is the edge.

---

## 10. FVG Confluence (NQ Intraday)

**Source**: GitHub — prashanthaitha24/nq-strategy-b-bot

| Metric | Value |
|---|---|
| Total Trades | 432 (3 years) |
| Win Rate | 53.5% |
| Profit Factor | ~2.3 |
| Net P&L | +$17,187 |
| Max Drawdown | $786 |
| Return/DD | ~22x |
| Profitable Years | 4/4 |
| Profitable Quarters | 13/14 (93%) |

**Rules**: Long-only. Inverse FVG (Fair Value Gap) inside 15-min FVG on NQ futures. Entry at retest of the confluence zone. Exit at 2× R:R.

**Year-by-Year**:
| Year | Trades | WR | PF | Net | MaxDD |
|---|---|---|---|---|---|
| 2023 | 127 | 46.5% | 1.44 | +$1,974 | $621 |
| 2024 | 139 | 52.5% | 2.24 | +$5,430 | $610 |
| 2025 | 117 | 57.3% | 2.47 | +$6,623 | $786 |
| 2026 (4mo) | 47 | 68.1% | 2.82 | +$3,319 | $668 |

**Key Insight**: Win rate improving over time. FVGs represent institutional order flow imbalances. Multi-timeframe confluence (5-min entry + 15-min structure) filters noise.

---

## 11. Improved ORB (Opening Range Breakout)

**Source**: Alpha Algo Trading Research ("The Simple Day Trading ORB Model That Beat the Original by 672%")

| Metric | Classic ORB | Improved ORB |
|---|---|---|
| Net Profit | $24,930 | $192,390 |
| Profit Factor | 1.07 | 1.39 |
| Trades | 6,502 | 1,425 |
| Win Rate | 41.80% | 45.61% |
| Avg Trade | $24.93 | $135.01 |
| Max DD | $83,613 | $22,744 |
| Return/DD | — | 845.89% |

**Improvements**:
1. Daily filter — only trade when broader setup is favorable
2. Prior day's ORB level as reference (not same-day)
3. ATR-based exits instead of fixed targets
4. Intraday confirmation before entry

**Key Insight**: Classic ORB takes too many trades with thin edge. Adding a daily filter + using prior ORB level reduces trades by 78% while increasing profit by 672%.

---

## 12. QQQ Dual Moving Average Trend + One Exit

**Source**: The Rogue Quant ("The Too Simple to Work QQQ Strategy")

| Metric | Value |
|---|---|
| Total Trades | 178 |
| Win Rate | 69% |
| Profit Factor | 2.64 |
| Worst Year | -4.36% (2008) |

**Rules**: Two trend filters (not crossovers). Buy when price above both. Exit on a single condition unrelated to trend.

**Key Insight**: Adding 2008 GFC data: 191 trades, 68.59% WR, PF 2.53. Strategy lost less than 5% during the Great Financial Crisis. The filter "got out of the way" — it didn't predict the crash, it just stopped buying when trend broke.

---

## 13. Candlestick Pattern Backtesting — Engulfing Holding Up

**Source**: Anup Shinde ("I backtested six classical candlestick patterns. One held up.")

| Pattern | Result |
|---|---|
| Engulfing | PF 2.17 on 15-min NQ (46 trades, 61% WR) — but fails on ES and GC |
| Harami | Surprisingly better than Engulfing reputation suggests |
| Hammer | Fails across all instruments at 1H timeframe |
| Morning/Evening Star | Too few trades to evaluate |

**Key Insight**: Only 1 of 6 patterns held up. The Engulfing works on NQ 15-min but doesn't generalize to ES or GC. Pattern edges are instrument-specific, not universal.

---

## 14. Multi-Pattern Scoring System (Nifty/BankNifty)

**Source**: Abhay Patil ("4 of my 15 trading patterns actually have edge")

| Pattern | PF | Win Rate | Trades | Notes |
|---|---|---|---|---|
| Gap Down Rejection | 1.73 | — | — | Nifty only (0.74 on BankNifty) |
| Evening Money Maker | 1.32 | 49% | 96 | Consistent |
| Virgin CPR Reversal | 1.17 | 47.5% | 432 | Highest sample size |
| Big Red Break | 1.15 | 44% | 125 | Needs CPR filter |

**Key Insight**: Fixed 2R targets are wrong for Nifty — daily pivots are only 0.18% apart. Dynamic targets (exit at next pivot providing ≥1R) improved win rate from 42% to 66.5%.

---

## 15. Bayesian Signal Grading (AutoQuant)

**Source**: Sachin Rai ("What I Learned After 6 Months of Bayesian Signal Grading")

| Signal | Win Rate | Samples | Weight |
|---|---|---|---|
| Options flow | 63% | 800+ | High |
| Key level tests + volume | 61% | 400+ | High |
| Earnings momentum (next week) | 58% | 180 | High |
| RSI alone (no volume) | 49% | — | Low (noise) |
| Bollinger touches (no RSI) | 51% | — | Low |
| Gap fills (no options confirm) | 50% | — | Low |

**Key Insight**: Static rules go stale. Bayesian updating adjusts signal weights based on actual hit rates. RSI alone is noise (49%). Options flow is real edge (63%). The system improved from 46% to 57% win rate over 6 months.

---

## 16. VRP Short Put Spreads — Honest Fill Model

**Source**: FlashAlpha ("The Fill Model Is the Edge")

| Fill Model | SPY Return | QQQ Return | Sharpe |
|---|---|---|---|
| Idealized (instant mid-fill) | +62% | +71% | 1.12 |
| Honest (post-and-wait limit) | -1.6% | -1.6% | -0.08 |

**Key Insight**: The VRP is real (65-72% win rate across fills). But the headline return is entirely a function of execution assumptions. A retail VRP seller's result depends on execution skill, not signal quality. The fill IS the edge.

---

## Strategy Comparison Matrix

| Strategy | Type | Win Rate | PF | Trades | Time in Market | Complexity |
|---|---|---|---|---|---|---|
| IBS Intraday (RTY) | Mean Reversion | ~50% | 1.58 | 1,021 | 1.5% | Low |
| MR Portfolio (4-strat) | Mean Reversion | ~65% | — | ~765 | 36% | Medium |
| Multiple Days Down | Mean Reversion | 75% | 3.00 | ~300 | ~20% | Low |
| 5-Day Low Range | Mean Reversion | 60% | — | 517 | ~40% | Low |
| MR + Seasonal Filter | Mean Reversion | 79% | 3.90 | 288 | 11% | Low |
| Turn-of-Month | Calendar | 65% | 2.50 | ~240 | 33% | Low |
| VIX ETN Volatility | Volatility | — | — | ~500 | 90% | Medium |
| PTrans2PGEX | Options Structure | 76% | — | 1,783 | ~30% | Medium |
| FVG Confluence (NQ) | Order Flow | 54% | 2.30 | 432 | ~20% | Medium |
| Improved ORB | Breakout | 46% | 1.39 | 1,425 | 3% | Medium |
| QQQ Dual MA Trend | Trend | 69% | 2.64 | 178 | ~60% | Low |

---

## Priority for Backtesting

### Tier 1 — High Edge, Simple Rules
1. **Multiple Days Down** — PF 3.00, 75% WR, published 2009, 17 years post-publication OOS
2. **MR + Seasonal Filter** — PF 3.90, 79% WR, 11% time in market
3. **Turn-of-Month** — PF 2.50, 65% WR, pure calendar, zero indicators
4. **IBS Intraday (RTY)** — PF 1.58, 1021 trades, 1.5% time in market

### Tier 2 — Strong Edge, Moderate Complexity
5. **MR Portfolio (4-strat)** — Return/DD 41.37, only 1 losing year since 1998
6. **FVG Confluence (NQ)** — PF 2.30, improving WR over time, $786 max DD
7. **VIX ETN Volatility** — 16.3% CAGR, Sharpe 1.0, uncorrelated to equities
8. **PTrans2PGEX** — 1,348% total return, 76% WR, 1,783 trades

### Tier 3 — Interesting, Needs More Research
9. **Improved ORB** — 672% improvement over classic, but 46% WR
10. **QQQ Dual MA Trend** — PF 2.64, survived 2008 with -4.36%
11. **Bayesian Signal Grading** — Adaptive weights, 57% WR (improving)
12. **VRP Short Put Spreads** — Real edge, but fill model is everything

---

## Key Takeaways

1. **Mean reversion dominates** — 7 of the top 12 strategies are mean reversion variants
2. **Simple rules win** — Most strategies have 2-4 conditions max
3. **Portfolio > Individual** — Combining 3-4 uncorrelated mean reversion strategies produces 40+ Return/DD
4. **Time in market matters** — Best strategies spend 10-33% of time in market, earning while others wait
5. **Execution is underestimated** — VRP research shows the fill model matters more than the signal
6. **Post-publication edges persist** — Multiple Days Down has been public since 2009 and still works
7. **Instrument specificity is real** — Candlestick patterns work on NQ but not ES/GC
8. **Dynamic sizing protects** — VIX strategy's VIX/100 sizing prevents blowups

---

## Related Notes
- [[Building and Backtesting Strategies]] — validation framework
- [[Concepts/Backtesting]] — metrics and overfitting
- [[Concepts/Strategy Development]] — hypothesis to rules
- [[IBS Mean Reversion]] — our backtested strategy
- [[Niche Trading Strategies]] — original collection
- [[MOC - Trading]] — map of content
