# Memory

## Last Updated
2026-06-26 03:15 UTC+8

---

## Trading Framework (From Vault)

### Core Concepts
1. **Structure vs Flow** — Profile gives areas of interest, order flow gives conviction/timing
2. **Proximity Principle** — Recent positioning (minutes/sessions) is actionable; old positioning (months) is context only
3. **Positioning vs Context** — Short-term = execution; Long-term = shorelines, not lines
4. **Repeat tests degrade levels** — Early tests = information; repeated tests = pressure buildup → violent resolution

### Volume Profile Rules
- POC = most agreed upon price, max balance
- HVN = consolidation, expect reactions FROM these levels (magnets)
- LVN = rejection/stops, expect reactions THROUGH these levels (speed bumps)
- Value Area = ~68-70% of volume (1 std dev)
- Composite profiles only when market is tightly compressed — not loose

### Three Setups
1. **Fading Edges of Balance** — Buy/sell return to VAH/VAL in range; trust degrades with each test
2. **Head Fake (Retail Trap)** — Sweep level → HVN forms above → back below → target POC then range lows
3. **Throwback (Post-Breakout Retest)** — Violent high-volume break → first retest = highest probability trade

### Order Flow Integration
- Absorption at level = don't trade against it
- Conviction push = real break, not head fake
- Always confirm structure with flow before entry
- **Delta divergence** = earliest warning signal (price new high + declining delta = buyers losing)
- **Spoofing** = fake orders that disappear — don't trust at face value
- **Iceberg orders** = hidden institutional activity — detect via repeated fills at same price

### Order Book Concepts
- Order book = live record of all resting bids and asks
- Spread = cost of immediacy (Best Ask - Best Bid)
- Depth = how much volume at each level
- Price-time priority = better prices first, then earlier arrivals
- Queue position matters for fill probability
- Market orders walk the book → slippage
- Limit orders provide price certainty but no fill guarantee

### Strategy Development & Backtesting
- 7-phase pipeline: Hypothesis → Rules → Backtest → Forward Test → Live Test → Evaluate → Iterate
- **Hypothesis** must be specific, testable, falsifiable with economic logic
- **Rules** must be mechanical — two people, same chart, same decision
- **Backtest** minimum: 2+ years data, 50+ trades, realistic costs, PF > 1.3
- **Forward test** 30+ setups, PF within 80% of backtest
- **Live test** starts at 25% size, scales through 50%, 75%, 100%
- **Walk-Forward Ratio** > 0.5 = robust, < 0.3 = overfitting
- **Monte Carlo** survival rate > 90%
- **70% rule**: Live PF at least 70% of backtest PF = viable
- Only 1 in 20 ideas survives full validation (Kevin Davey)

### CRITICAL: Data Quality & Execution Assumptions
- **Yahoo Finance forex data is interpolated mid-prices** — NOT real tick data
- **Never buy at "close" in backtest** — by the time signal fires at close, you can't execute at that price
- **Always use NEXT OPEN for entry** — this is the realistic execution
- **Same-bar entry/exit = look-ahead bias** — if you compute signal and execute on same bar, you're using future data
- **IBS < 0.18 on GBPUSD looked like Sharpe 3.80** — completely vanished when buying at next open (Sharpe -7.81, WR 2%)
- **Why it looked real**: Yahoo's interpolated close prices are smoother than real ticks, creating artificial mean reversion patterns
- **The test**: if strategy works at close but fails at next open, it's a data artifact
- **QQQ same logic**: Sharpe 0.19 (no edge) — proves the GBPUSD result was fake
- **Lesson**: ALWAYS test with next-open execution. If edge disappears, it was never real.

### Backtest Results — IBS Mean Reversion (SPY, 2005-2025)
- **Edge**: PF 1.57, Win Rate 66.9%, Expectancy $16.16/trade
- **Problem**: Only 148 trades in 20 years (~7/year) — too few
- **Total Return**: 0.9% over 20 years — practically nothing
- **Sharpe**: 0.14 (way below 1.0 threshold)
- **Walk-Forward Ratio**: 3.30 (strong out-of-sample)
- **Monte Carlo**: 100% survival, worst DD -1.7%
- **Verdict**: Statistically valid but practically useless — edge exists, filters too restrictive

### All Strategies Backtest (10-Year, 2016-2025)
**Winner: QQQ Mean Reversion** — PF 1.71, 62.4% WR, 10.6% CAGR, -14.9% DD, 186 trades
**Runner-up: IBS Simple SPY** — PF 1.77, 61.2% WR, 9.0% CAGR, -16.3% DD, 258 trades
**Trend: QQQ Dual MA** — PF 2.67, 32.8% WR, 9.8% CAGR, -19.1% DD, 61 trades
**Disappointing**: TOM (PF 1.32), RSI(2) (PF 1.20), Multiple Days Down (10 trades)
**Key Insight**: QQQ beats SPY for mean reversion. Higher volatility = deeper oversold = stronger snap-back.

### Volume-Scaled IBS (Novel Strategy — Backtested 2026-06-26)
**The Novel Edge**: IBS threshold scales continuously with volume ratio (not binary filter)
- VolRatio > 1.5 → threshold relaxes to 0.25 (accept weaker setup)
- VolRatio < 0.5 → threshold tightens to 0.15 (demand deeper oversold)
**Results on SPY**: PF 1.65, 63.8% WR, 337 trades, Sharpe 0.54, DD -1.6%
**Improvement over Fixed IBS**: PF +4.4%, Sharpe +17.4%, smaller drawdown
**Walk-Forward**: WFR 1.33 (OOS beats IS by 33%)
**Monte Carlo**: 100% survival, worst DD -3.3%
**Surprise**: High-volume IBS entries are net losers (33.3% WR) — institutions distribute, not accumulate
**Score**: 9/10 checklist (only Sharpe below 1.0 fails)
**Status**: VIABLE — best risk-adjusted strategy in vault

### QQQ Dual-Signal Edge (Backtested 2026-06-26)
- **Instrument**: QQQ (daily)
- **Rule**: IBS < 0.20 for MR (5-day hold) + Trend following (SMA pullback)
- **Sharpe**: 0.88 | **CAGR**: 11.0% | **DD**: -14.8% | **PF**: 2.06 | **WR**: 44%
- **Walk-Forward**: WFR 1.34 (OOS beats IS by 34%)
- **Monte Carlo**: 100% survival
- **Status**: BEST EQUITY STRATEGY — Sharpe below 1.0 but solid edge

---

## Active Zones — BTC/USDT (2026-06-25)

| Zone | Type | Entry | Stop | Target | Status |
|------|------|-------|------|--------|--------|
| 1 | Long | 61,200–61,250 | < 61,100 | 61,450 → 61,600 | Watching |
| 2 | Long | 61,000–61,050 | < 60,900 | 61,250 → 61,400 | Watching |
| 3 | Short | 61,500–61,650 | > 61,750 | 61,300 → 61,100 | Watching |
| 4 | Short | 61,750–61,800 | > 61,900 | 61,500 → 61,300 | Watching |

**Current Price:** 61,334.30
**Bias:** Neutral — no-man's land, wait for zone touch + flow

---

## Key Quotes
> "Markets are just positions." — Michael Platt

> "Volume profile's not a magic map of support and resistance."

> "The shorter and cleaner it is, the more you could tell about live positioning."

> "Structure vs flow, always."

> "Price action tells you what happened. Order flow tells you why."

> "The order book is the most informative single view in any trading interface."

> "If you torture the data long enough, it will confess to anything." — Ronald Coase

> "Simplicity is an advantage, not a limitation."

> "Only 1 out of every 20 strategy ideas survives a complete validation process." — Kevin Davey

---

## Vault Sync Setup
- **Primary remote**: GitLab → https://gitlab.com/aitrading69/Nigger-project.git
- **Secondary remote**: GitHub → https://github.com/xxJAceAILOLxx/AI-WORKSPACE.git
- **Plugin**: obsidian-git (auto-commit, auto-push, auto-pull)
- **Auto-pull interval**: 3 minutes
- **Auto-push interval**: 10 minutes
- **Auto-save interval**: 5 minutes
- **Auto-pull on boot**: enabled

---

## Vault Structure
- **Volume Profile** — Core note (155 lines)
- **Order Flow** — Core order flow/order book note (expanded)
- **Building and Backtesting Strategies** — 7-phase pipeline, validation framework
- **Concepts/** — 20 atomic notes (AMT, Positioning vs Context, Structure vs Flow, Order Book, Absorption, Delta Divergence, Spoofing, Iceberg Orders, Market Microstructure, Backtesting, Strategy Development, etc.)
- **Strategies/** — Volume Profile Throwback, IBS Mean Reversion, All Strategies Backtest, Volume-Scaled IBS (novel)
- **Reflections/** — Key Insights, mindset shifts

---

## Open Questions
- How to systematically measure "freshness" of positioning?
- When does a level transition from actionable positioning to just context?
- How to quantify absorption strength? (volume decay at level)
- Best way to backtest order flow setups vs volume profile setups?
- How to improve IBS strategy trade frequency? (relax filters, add assets, shorter timeframes)
- Should we combine QQQ MR + IBS Simple SPY as a portfolio? (uncorrelated instruments, same edge)
- Can we get intraday data to test ORB, FVG, and IBS Intraday strategies?
- Should we invert the volume scaling? (demand deeper oversold on high volume, not weaker)

---

*Update this file when vault changes or new zones are identified.*
