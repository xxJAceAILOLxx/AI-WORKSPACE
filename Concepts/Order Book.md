# Order Book

## One-Line Summary
The order book is the live, sorted record of every resting bid and ask — the central data structure of every order-driven market.

---

## What It Is

- A real-time list of all buy (bid) and sell (ask) orders organized by price level
- The book IS the market — best bid/ask define price, resting orders define depth
- Where liquidity lives, where slippage is born, where institutional activity shows

> "The order book is the most informative single view in any trading interface."

---

## Core Components

| Element | Definition |
|---------|-----------|
| **Bid** | Buy order — highest price a buyer will pay |
| **Ask (Offer)** | Sell order — lowest price a seller will accept |
| **Spread** | Gap between best bid and best ask — cost of immediacy |
| **Mid Price** | (Best Bid + Best Ask) / 2 — theoretical fair value |
| **Depth** | How much volume rests at each price level |
| **Top of Book (L1)** | Best bid and best ask — the "touch" |
| **L2 (MBP)** | Aggregated depth per price level |
| **L3 (MBO)** | Every individual order with queue position |

---

## How It Works

### Order Matching
1. Market buy order arrives → hits lowest ask first, then next level up
2. Market sell order arrives → hits highest bid first, then next level down
3. If order size > volume at best price → **walks the book** (each fill at worse price)
4. This walk **IS** market impact

### Price-Time Priority
- **Price priority** — better prices execute first
- **Time priority** — earlier arrivals first at same price
- Queue position matters — front of queue = higher fill probability

### The Spread
$$\text{Spread} = \text{Best Ask} - \text{Best Bid}$$
$$\text{Mid} = \frac{\text{Best Bid} + \text{Best Ask}}{2}$$

- Narrow spread = liquid market, cheap to trade
- Wide spread = illiquidity or uncertainty

### Slippage
$$\text{Slippage} = \text{VWAP of fills} - \text{Pre-trade Mid}$$

When your order walks the book, each level's price × size contributes to your average fill. The gap between that and the pre-trade mid is your implicit cost.

---

## Reading the Book

### What to Look For

| Signal | Interpretation |
|--------|---------------|
| **Large bid cluster** | Potential support (buyers defending) |
| **Large ask cluster** | Potential resistance (sellers defending) |
| **Imbalance** (one side much larger) | Directional bias |
| **Dense book** | Good liquidity, smooth execution |
| **Thin book** | Slippage risk, use limit orders |
| **Stacks building** | Genuine interest, conviction |
| **Stacks disappearing** | Manipulation or spoofing |

### Depth Chart
Cumulative volume plotted against price:
- Green (bid) curve on left = available buying power
- Red (ask) curve on right = available selling pressure
- Gap between = spread
- Steeper curve = more liquidity near best prices

---

## Order Types

| Type | What It Does | Key Trade-off |
|------|-------------|---------------|
| **Market Order** | Buy/sell now at best available | Guaranteed fill, uncertain price |
| **Limit Order** | Buy/sell at specific price or better | Price certainty, no fill guarantee |
| **Stop-Loss** | Triggers at pre-defined level | Risk management, gap risk |
| **Iceberg** | Visible portion + hidden reserve | Hides true size |
| **IOC** | Fill what's available, cancel rest | Take liquidity without footprint |
| **FOK** | Fill entirely or cancel completely | All-or-nothing |
| **GTC** | Active until filled or cancelled | Longer-term orders |
| **Pegged** | Adjusts relative to NBBO/midpoint | Auto-adjusts with market |

---

## Iceberg Orders

- Display only a "tip" in the book, rest is hidden
- When visible portion fills, hidden quantity refreshes it
- Sign of institutional activity
- Detect via: repeated fills at same price that keep replenishing

See [[Iceberg Orders]]

---

## Manipulation Patterns

### Spoofing
- Place large order with no intent to execute
- Cancel before fill after others react
- Creates illusion of supply/demand

### Layering
- Multiple fake orders at different levels
- Creates illusion of depth
- Orders disappear when approached

See [[Spoofing and Layering]]

---

## Book Imbalance

$$\rho = \frac{V_{\text{bid}} - V_{\text{ask}}}{V_{\text{bid}} + V_{\text{ask}}}$$

- $\rho > 0$ = more buying pressure (bids dominate)
- $\rho < 0$ = more selling pressure (asks dominate)
- $\rho = 0$ = perfectly balanced

Empirically, order book imbalance tends to predict short-term price movements.

---

## Limitations

- Orders can be cancelled quickly — may not reflect true intent
- Hidden/dark pool orders are not visible
- Large players may split orders to avoid detection
- Book is dynamic — changes within seconds in fast markets
- Visible book represents only part of available liquidity

---

## Data Feed Levels

| Level | What You See | Use Case |
|-------|-------------|----------|
| **L1** | Best bid/ask only | Price monitoring |
| **L2** | Aggregated depth per level | Standard microstructure analysis |
| **L3** | Every individual order with queue position | Queue modeling, fill probability |

---

## Related
- [[Order Flow]] — main note
- [[Absorption]] — when large orders absorb pressure
- [[Iceberg Orders]] — hidden liquidity
- [[Spoofing and Layering]] — manipulation patterns
- [[Market Microstructure]] — underlying mechanics
- [[Structure vs Flow]] — order book = flow side
- [[Volume Profile]] — structure side (where to look)
