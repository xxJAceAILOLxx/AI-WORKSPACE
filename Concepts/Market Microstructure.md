# Market Microstructure

## One-Line Summary
The underlying mechanics of how orders match, prices form, and trades execute at the granular level.

---

## Why It Matters

- Traditional finance treats markets as frictionless — they're not
- Orders queue in electronic books, compete for priority, leave footprints
- Understanding mechanics = understanding why fills happen at certain prices
- This is the "plumbing" behind order flow

---

## The Order Book

The central mechanism — a real-time record of all outstanding buy and sell orders, organized by price level and arrival time.

See [[Order Book]]

### Structure
- **Bids** (buy orders) — sorted highest price first
- **Asks** (sell orders) — sorted lowest price first
- **Best bid/ask** = Level 1 (the touch)
- **Aggregated depth** = Level 2 (standard analysis)
- **Order-by-order** = Level 3 (full queue visibility)

### The Matching Engine
- Venue software that receives every order message
- Enforces matching rules, executes crossing orders
- Broadcasts resulting book updates
- Single source of truth — order only exists when engine says so

---

## Order Priority

### Price-Time Priority (FIFO)
Most common system:
1. **Price priority** — better prices execute first
2. **Time priority** — earlier arrivals first at same price

### Pro-Rata
Some markets (options, certain futures):
1. **Price priority** still applies
2. **Size priority** — at same price, filled proportionally to size

---

## Queue Position

Your place in line at a price level — critical for fill probability.

| Queue Position | Fill Probability |
|----------------|-----------------|
| Front 10% | Very high |
| Middle 50% | Moderate |
| Back 90% | Low |

> "Simply having an order at the 'right' price is not enough; you must also arrive early enough to be near the front of the queue."

This is why HFT invests in latency — microseconds = queue position.

---

## The Spread

$$\text{Spread} = \text{Best Ask} - \text{Best Bid}$$

### Components of the Spread
1. **Order processing costs** — fixed costs of market-making
2. **Inventory risk** — risk of prices moving against position
3. **Adverse selection** — risk of trading against informed participants

$$S = C_{\text{proc}} + C_{\text{inv}} + C_{\text{adv}}$$

- Narrow spread = liquid market
- Wide spread = illiquidity or uncertainty

---

## Market Impact

When a market order walks the book:
- Each level consumed at progressively worse prices
- VWAP of fills differs from pre-trade mid
- That gap = slippage = implicit cost of immediacy

$$\text{Slippage} = \text{VWAP} - \text{Mid}$$

This is why execution algorithms slice large orders rather than sweep in one go.

---

## Dark Pools and Hidden Liquidity

- Private trading venues that match orders without displaying quotes
- Pre-trade anonymity
- Reduced information leakage
- Many match at midpoint — potential price improvement
- Represent substantial portion of equity volume (>50% off-exchange)

### Implication
Visible order book = only part of available liquidity
Execution algorithms send to multiple venues to access hidden liquidity

---

## Order Lifecycle

1. **Submitted** — sent to exchange
2. **Acknowledged** — exchange validates
3. **Queued** — enters the book at specified price
4. **Partially filled** — some counterparties arrived
5. **Filled** — fully executed
6. **Cancelled** — pulled by trader
7. **Expired** — time-in-force reached
8. **Rejected** — failed validation

---

## Key Concepts for Traders

| Concept | Why It Matters |
|---------|---------------|
| **Queue position** | Fill probability depends on where you are in line |
| **Spread** | Cost of immediacy — narrower = cheaper to trade |
| **Depth** | How much you can trade before price moves |
| **Walk the book** | Large orders consume multiple levels |
| **Adverse selection** | Risk of trading against better-informed participants |
| **Iceberg orders** | Hidden liquidity — detect via patterns |
| **Spoofing** | Fake orders — don't trust at face value |

---

## Related
- [[Order Book]] — the data structure
- [[Order Flow]] — reading the tape
- [[Absorption]] — when large orders hold
- [[Iceberg Orders]] — hidden liquidity
- [[Spoofing and Layering]] — manipulation
- [[Structure vs Flow]] — microstructure = flow mechanics
