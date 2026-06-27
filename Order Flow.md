# Order Flow

## One-Line Summary
Order flow tells us **what participants are doing right now**. Structure tells you where to look; flow tells you whether to care.

---

## What It IS

- Real-time tape reading — actual buying and selling happening right now
- The "why" behind price moves
- Footprint of every trade executed at each price level
- Whether buyers or sellers were the aggressor at each price point
- Where significant imbalances exist between supply and demand at the micro-level

> "Price action tells you what happened. Order flow tells you why."

---

## What It Is NOT

Order flow does **not** tell us:

- The long-term direction with certainty
- Who specifically is trading (identity)
- Whether a position is a hedge or outright directional
- Future price — it's a probabilistic edge, not a crystal ball
- Everything — it's one half of "structure vs flow"

---

## Core Components

### The Order Book (Limit Order Book / CLOB)

![[Images/Volume Profile Anatomy.svg]]

The central data structure of every order-driven market. A live, sorted record of every resting bid and ask.

| Element | Definition |
|---------|-----------|
| **Bid** | Buy order — highest price a buyer will pay |
| **Ask (Offer)** | Sell order — lowest price a seller will accept |
| **Spread** | Gap between best bid and best ask — cost of immediacy |
| **Mid Price** | (Best Bid + Best Ask) / 2 — theoretical fair value |
| **Depth** | How much volume rests at each price level |
| **Top of Book (L1)** | Best bid and best ask — the "touch" |
| **L2 (MBP)** | Aggregated depth per price level — standard for most analysis |
| **L3 (MBO)** | Every individual order with queue position — full granularity |

> "The book IS the market: the best bid and best ask define the price, and the resting orders behind them define how much you can trade and at what cost."

See [[Concepts/Order Book]] for full detail.

### Order Types

| Type | What It Does | Trade-off |
|------|-------------|-----------|
| **Market Order** | Buy/sell now at best available price | Guaranteed fill, uncertain price |
| **Limit Order** | Buy/sell at specific price or better | Price certainty, no fill guarantee |
| **Stop-Loss** | Triggers at pre-defined level | Risk management, gap risk |
| **Iceberg** | Visible portion + hidden reserve | Hides true size |
| **IOC** | Fill what's available, cancel rest | Take liquidity without footprint |
| **FOK** | Fill entirely or cancel completely | All-or-nothing execution |

### Price-Time Priority

Orders execute by:
1. **Price priority** — better prices first
2. **Time priority** — earlier arrivals first at same price

Queue position matters. Being at the front = higher fill probability. Being at the back = may never fill.

---

## Key Order Flow Concepts

### Absorption

Large orders absorbing selling/buying pressure without letting price through.

- Heavy selling absorbed by equal or greater buying → floor
- Heavy buying absorbed by equal or greater selling → ceiling
- Level holds despite repeated attacks = strong positioning
- Break after absorption = trapped participants forced to cover

See [[Concepts/Absorption]] for full detail.

### Delta

Net difference between buying and selling volume at each price.

- **Positive delta** — more aggressive buying
- **Negative delta** — more aggressive selling
- **Delta = 0** — perfectly balanced

### Delta Divergence

When price and delta move in opposite directions — the earliest warning signal.

- **Price makes new highs + declining positive delta** — buyers losing conviction
- **Price makes new lows + declining negative delta** — sellers losing conviction
- Frequently appears at reversal points

See [[Concepts/Delta Divergence]] for full detail.

### Iceberg Orders

Hidden institutional orders — only a "tip" is visible, rest is concealed.

- Large order displays 1,000 shares, hides 9,000
- When 1,000 fills, another 1,000 appears
- Sign of institutional accumulation/distribution
- Detect via: repeated fills at same price that keep replenishing

See [[Concepts/Iceberg Orders]] for full detail.

### Spoofing & Layering

Manipulation patterns — fake orders to mislead other participants.

- **Spoofing**: Place large order with no intent to execute, cancel before fill
- **Layering**: Multiple fake orders at different levels to create illusion of depth
- Signs: large orders appear and disappear rapidly without filling
- Regulatory offense in most markets

See [[Concepts/Spoofing and Layering]] for full detail.

---

## Structure vs Flow (The Framework)

> "Profile gives you the areas of interest. But it's the actual **order flow** that tells you whether or not you should care."

| | Structure | Flow |
|---|---|---|
| **Tool** | Volume Profile | Order Flow / DOM / Footprint |
| **Gives** | Where to look | Whether to act |
| **Question** | Where are traders positioned? | What are they doing right now? |
| **Example** | POC at 61,200 | Bids absorbing every offer at 61,200 |

**Always together:**
- Structure without flow = guessing
- Flow without structure = no roadmap

### Flow Confirmation Examples

Profile shows a POC (structurally important). Flow shows:
- Big bids eating every offer → flow disagrees with shorting → don't short the POC
- Offers stacking above POC, bids pulling → flow agrees → fade the POC
- Conviction push through level → real break, not head fake
- Absorption at level → don't trade against it

---

## Order Book Reading

### How to Assess Supply/Demand

- **Large bid clusters** = potential support (buyers defending)
- **Large ask clusters** = potential resistance (sellers defending)
- **Imbalance** (one side much larger) = directional bias
- **Walls** that hold = genuine interest
- **Walls that disappear** = manipulation or spoofing

### Reading Depth

- **Dense book** (many orders at each level) = better liquidity, smoother execution
- **Thin book** (few orders) = slippage risk, use limit orders
- **Cumulative book** = total bids/asks at each price and below/above

### What to Watch

1. **Stacks building and evaporating** — reveals conviction
2. **Large orders appearing/disappearing** — may be manipulation
3. **Absorption patterns** — selling into bids that won't budge
4. **Iceberg detection** — repeated fills at same price, keeps replenishing
5. **Delta spikes** — sudden aggressive buying/selling

---

## Order Flow Setups (Integration with Volume Profile)

### 1. Fading + Flow Confirmation
- Profile shows VAH/VAL
- Flow shows absorption at level (selling into bids at VAL = buy)
- Don't fade without flow confirmation

### 2. Head Fake + Flow Reading
- Profile shows sweep of level
- Flow shows: punchy move, minimal follow-through, drifting = fake
- Flow shows: conviction push, real volume = real break

### 3. Throwback + Flow on Retest
- Profile shows break outside value, retest of VAH/VAL
- Flow shows: momentum stalls, absorption on retest = entry
- Flow shows: continued aggression through level = no trade

---

## Market Participants to Watch

| Participant | What to Look For |
|-------------|-----------------|
| **Market Makers** | Providing liquidity, tight spreads |
| **Institutions** | Iceberg orders, large resting blocks |
| **Algorithms** | Consistent patterns, VWAP adherence |
| **Retail** | Often trapped at extremes, emotional flow |
| **HFTs** | Front-running, queue position, speed |

---

## Biggest Mistakes

1. **Trading flow without structure** — no roadmap, random entries
2. **Ignoring flow at key levels** — structural level without conviction is noise
3. **Confusing spoofing for genuine interest** — large orders that disappear are traps
4. **Overtrading on noise** — not every delta spike is a signal
5. **Ignoring context** — flow in a range-bound market vs trending market means different things
6. **Not confirming with volume profile** — flow alone can't tell you WHERE to act

---

## Best Instruments for Order Flow

| Market | Why |
|--------|-----|
| **ES / NQ / RTY** | Deep books, readable institutional flow |
| **BTC/USDT** | 24/7, retail-driven, lots of practice |
| **CL (Crude Oil)** | Active, but curve-traded — be careful |
| **Forex majors** | Deep liquidity, but fragmented across venues |

> "Order flow is best used for day trading. The most popular markets are equity index futures."

---

## Related Concepts

- [[Volume Profile]] — the structure side of the equation
- [[Concepts/Structure vs Flow]] — always together
- [[Concepts/Order Book]] — the raw data structure
- [[Concepts/Absorption]] — key confirmation pattern
- [[Concepts/Delta Divergence]] — earliest warning signal
- [[Concepts/Spoofing and Layering]] — manipulation to avoid
- [[Concepts/Iceberg Orders]] — hidden institutional flow
- [[Concepts/Market Microstructure]] — underlying mechanics
- [[Concepts/Positioning vs Context]] — short-term flow = positioning
- [[Concepts/The Proximity Principle]] — fresh flow matters most

---

## Key Quotes

> "Markets are just positions." — Michael Platt

> "It's structure vs flow, always."

> "The shorter and cleaner it is, the more you could tell about live positioning."

> "Profile gives you the areas of interest. But it's the actual order flow that tells you whether or not you should care."

---

## Sources

- Michael Valtos, *Trading Order Flow* (orderflows.com)
- Trader Dale, *Order Flow Trading Setups*
- HFT Book (hftradingbook.com) — Limit Order Book mechanics
- Michael Brenndoerfer, *Market Microstructure: Order Books & Execution Mechanics*
- Bookmap Learning Center — Order Flow analysis
- ATAS Blog — Order Book Trading strategies
- Optiver — Orders and the Order Book
