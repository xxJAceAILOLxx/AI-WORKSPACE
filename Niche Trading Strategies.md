# Niche Trading Strategies

## One-Line Summary
Massively profitable strategies hiding in plain sight — most traders don't know these exist because they're too busy chasing indicators.

---

## The Edge Stacking Principle

> "Most traders have zero edges. Some have one. The best traders stack multiple edges from different categories."

| Edge Type | Example |
|-----------|---------|
| Strategy | Tested, robust system |
| Broker | Low commissions, smart routing |
| Time-based | Turn-of-month timing |
| Information | Domain expertise in one sector |
| Structural | Market mechanics (liquidations, wicks) |
| Volatility | VRP, VIX mean reversion |

---

## Category 1: Mean Reversion Edges

### IBS (Internal Bar Strength) — Daily Swing

**What it is:** Measures where the daily close sits within the high-low range. IBS near 0 = close at bottom (weak). IBS near 1 = close at top (strong).

**The edge:** When IBS is below 0.20, average next-day returns are +0.35%. When above 0.80, returns drop to -0.13%. (Pagonidis, 2013)

**Rules:**
- Entry: IBS < 0.20 (buy) or IBS > 0.80 (sell)
- Exit: IBS reverts to 0.50 or opposite threshold
- Hold time: 1-3 days

**Performance across assets:**
| Asset | Win Rate | CAGR | Max DD |
|-------|----------|------|--------|
| SPY | ~65% | ~40% | < 3% |
| QQQ | ~63% | ~35% | < 4% |
| Gold | ~61% | ~20% | < 5% |
| Bitcoin | ~62% | ~25% | < 6% |

**Key insight:** Same entry/exit thresholds across all markets. No optimization per asset.

### IBS Intraday — Day Trading Version

**What it is:** Same IBS concept but on 15-minute bars, flat by 15:00.

**The twist:** Doesn't blindly fade every extreme. Waits for price to confirm the reversal has started (stop entry).

**Performance on RTY (since 2002):**
- 1021 trades
- Profit factor: 1.58
- Only 1.5% market exposure
- Long side: PF 1.91, 55% win rate
- Short side: PF 1.47, 46% win rate

**Why it works:** Small caps produce sharp risk appetite changes. Downside moves are faster and more emotional → stronger reversals.

### Turnaround Tuesday

**What it is:** Buy Monday's close after a weak Monday (Monday closes below Friday's close). Exit Tuesday's close.

**The edge:** Markets absorb weekend fear on Monday. Shorts cover, dip buyers step in on Tuesday.

**Original by Larry Williams:**
- Buy: Monday close if Monday < Friday close
- Exit: Tuesday close
- Max 1 trade per week

**Improved version (Alpha Algo):**
- Added quality filters
- 2.5x more total profit
- 142 fewer trades
- Average trade: $621 vs $188
- PF: 2.26 vs 1.48
- Return/DD: 16.82 vs 7.39

**Why it survives:** One-day hold time = protection against being trapped in trends. Exploits one behavioral window.

### Multiple Days Down (Connors/Alvarez 2009)

**What it is:** Buy after X consecutive down days in a bull market.

**Rules:**
- Buy: SPY closes down 3+ consecutive days
- Exit: SPY closes above 5-day MA
- Long only in uptrend

**Performance:**
- 75%+ win rate across nearly 3 decades
- PF: 3.00 (ES + NQ combined)
- Return/DD: 16.14
- More than half of track record is post-publication OOS

**Key insight:** Even strategies published in 2009 still work because the behavioral edge persists.

---

## Category 2: Volatility Edges

### VIX Mean Reversion (SPY)

**What it is:** Use VIX to identify panic regimes, then buy SPY.

**Rules:**
- Signal: VIX spikes above threshold (volatility burst)
- Entry: MOC order when stress regime identified
- Exit: Market rebound captured
- Position sizing: Increase when stress persists

**Performance (2007-2026):**
- 10.8% CAGR net of fees
- Active only 14% of trading days
- Simple MOC workflow

**Why it works:** Investors overpay for downside protection. Downside moves are over-amplified by technical and behavioral forces.

### Volatility Risk Premium (Selling Options)

**What it is:** Sell overpriced options when implied volatility > realized volatility.

**The edge:** VRP works ~85% of the time. The 15% can wipe you out if over-leveraged.

**Warning:** Always size conservatively. Have hard stop for max loss per trade and per month.

---

## Category 3: Calendar/Time-Based Edges

### Turn of Month (TOM)

**What it is:** Stocks tend to outperform in the last few trading days of the month and first few days of the next month.

**Edge:** Combine with mean reversion for significantly better results.

### January Effect

**What it is:** Small caps tend to outperform in January.

**Status:** Weakening but hasn't disappeared.

### Holiday Effect

**What it is:** Markets tend to rise before holidays.

**Status:** Still exploitable with other edges.

> "Calendar edges are weakening but they haven't disappeared. The key is combining them with other edges."

---

## Category 4: Structural Edges

### Crypto Liquidation Cascade Sniping

**What it is:** Place limit orders at deep discount levels during high-leverage periods. Let the liquidation cascade come to you.

**The mechanic:**
1. Crypto allows extreme leverage (10x-100x)
2. Market drops → triggers cascade of forced liquidations
3. Exchanges forced to close positions at market price
4. Price crashes further
5. Liquidations done → no more sellers → price snaps back

**How to exploit:**
- Monitor liquidation data (Coinglass)
- Place limit orders at 10-20% below current price
- Let the cascade fill your orders
- Exit on the snap-back

**Why it's niche:** Most traders don't understand market microstructure mechanics.

### Earnings Volatility Spike Trading

**What it is:** Trade the volatility spike after earnings, not the earnings themselves.

**Rules:**
- 3-12 days before: Look for stocks with strong momentum
- Post-earnings: Analyze beat/miss, price reaction, volume
- When clear volatility spike appears → enter (long or short)
- Conservative sizing: 1-2% per trade

**Best on:** Highly liquid names (NVDA, TSLA, AAPL, AMZN, META)

**Key insight:** Success comes from having a fast, adaptive system that reacts when volatility explodes, not from predicting the report.

---

## Category 5: Prediction Market Edges

### Polymarket Sports Arbitrage (RN1 — $6.2M Profit)

**What it is:** Harvest mispriced liquidity across short-duration sporting events. Buy at prices so depressed that even modest probability shifts generate outsized returns.

**Stats:**
- 50 wins, 0 losses (on resolved positions)
- $310M+ in volume
- $6.24M profit
- Average entry: 34.1 cents (buying 34% probability outcomes)
- When they resolve at $1.00 → ~3:1 payout

**The real edge:** Not prediction accuracy. It's:
1. Identifying systematic mispricings (gap between Polymarket and sharper sportsbooks)
2. Sizing positions to survive variance
3. Cutting losers before resolution (enter 43K+ markets, only 50 reach resolution as winners)

**Key insight:** "Enter wide, hold winners, cut losers early."

### BTC 5-Minute Up/Down Markets

**What it is:** Systematic buying of contracts at extreme low prices (2-10 cents) on BTC micro-markets.

**Performance:**
- $90k profit from systematic approach
- Repeated same type of trade 16,500+ times
- Individual wins: +400% to +1,354%

**Key insight:** Edge comes from identifying moments when the market significantly misprices short-term probabilities, not from predicting BTC direction.

---

## Category 6: Options Strategies

### Time Flies (Delta-Neutral)

**What it is:** Advanced delta-neutral options strategy using diagonals and broken-wing butterflies to profit from theta decay while handling volatility changes.

**Rules:**
- Put diagonal below market (benefits when vol rises during declines)
- Broken-wing butterfly above market (benefits when vol contracts during rallies)
- Target: 10% of buying power profit
- Exit at least 24 hours before closest expiry

**Performance (2024-2026):**
- 2024: 45.2% annualized
- 2025: 100.3%
- 2026: 41.0% (104.6% annualized)
- 57 trades, 46 winners
- Average net profit: 5.33% per trade
- Average trade duration: 5.7 days

**Key insight:** Create the "perfect curve" — balanced profit curve that benefits from time decay while tolerating normal market movement.

### Wheel Strategy on Futures

**What it is:** Sell OTM puts on futures Sunday nights for 15 minutes. Follow institutions after hours.

**Edge:**
- After hours trading
- Fibonacci structures
- Market context

**If assigned:** SP500 at a discount → sell calls or hold

### LEAPS Momentum with Affordability Ladder

**What it is:** Buy long-dated calls (150-365 days) on the strongest 20 names ranked by 252-day rate of change.

**Rules:**
- Rank names by 252-day momentum
- Buy strongest via affordability ladder:
  - Plain ATM call when affordable
  - Tighter call spreads when expensive
- Take gain on runner at +356%
- Trim position up +48.6% within 29 days of expiry
- ~8% per name, up to 30% per rebalance

**Performance:**
- 5-year return: +4,609%
- Max drawdown: 65.8%
- Sortino: 2.32
- Stays ~80% invested

**Key insight:** The machine's book — odd numbers (+356%, +48.6%) are optimizer thresholds, not round human ones.

---

## Category 7: Multi-Strategy Portfolios

### The Mean Reversion Portfolio (One Losing Year Since 1998)

**Components:**
1. RSI2 — short-term oversold mean reversion
2. Turnaround Tuesday — calendar-based behavioral reversal
3. IBS — daily close-location mean reversion
4. Connors %B — volatility-stretch pullback

**Performance:**
- $710,946 profit
- Max drawdown: $17,183
- Return/DD: 41.37

**Why it works:**
- Low correlation between components
- Each strategy has different weaknesses
- Weaknesses get diluted, strengths compound

> "You don't need one perfect strategy. You need a portfolio of good strategies that behave differently."

### The 2-Strategy Portfolio (ORB + RSI2)

**Components:**
1. Opening Range Breakout (ORB) — trend-following
2. RSI2 with VIX filter — mean reversion

**Performance:**
- Return/DD: 18.34 (combined)
- Stagnation reduced by ~60%
- Weekly correlation: only 0.25

**Key insight:** When one strategy is quiet, the other may still be working. If both work, the portfolio accelerates.

---

## The Framework: How to Find Niche Edges

1. **Read academic papers** (SSRN, arXiv) — look for large sample sizes, OOS testing, results surviving transaction costs
2. **Subscribe to quality trading Substacks** — people share backtested strategies and real code
3. **Understand market microstructure** — structural edges are the most persistent
4. **Stack edges** — combine strategy + timing + information + execution
5. **Think in portfolios** — not one perfect strategy, but multiple uncorrelated edges

> "A real strategy edge is not 5 magic indicators. It's usually a repeatable, tested process that exploits a genuine market behavior."

---

## Sources

- SetupAlpha, *60+ Market Edges Systematic Traders Use in 2026*
- Alpha Algo Trading Research, *IBS Day Trading*, *Turnaround Tuesday*, *Mean Reversion Portfolio*
- Concretum Research, *VIX Mean Reversion Strategy*
- FrenFlow, *RN1's $6.2M Polymarket Edge*
- TradingWarz, *Sell Options, Buy Multi Baggers*
- Theta Profits, *Time Flies Strategy*
- Radiant, *Earnings Trading Strategy*
- Build Alpha, *Edge in Trading*

---

## Related
- [[Building and Backtesting Strategies]] — validation framework
- [[Volume Profile]] — structural edges
- [[Order Flow]] — flow confirmation
- [[Concepts/Backtesting]] — how to test these
- [[Concepts/Strategy Development]] — how to build these
