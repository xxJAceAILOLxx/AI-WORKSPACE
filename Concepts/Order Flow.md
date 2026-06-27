# Order Flow

## Core Idea
Real-time tape reading — the actual buying and selling happening *right now*. The "why" behind price moves.

---

## What Order Flow Tells You

- Is buying being absorbed? (price can't advance despite aggressive bids)
- Is selling drying up? (price holds despite aggressive offers)
- Is there conviction? (high-volume directional pushes)
- Are participants trapping? (sweep then fade)
- Who was the aggressor at each price point?
- Where do significant imbalances exist between supply and demand?

---

## Structure vs Flow

> "Profile gives you the areas of interest. But it's the actual **order flow** that tells you whether or not you should care."

| | Structure | Flow |
|---|---|---|
| **Tool** | Volume Profile | Order Flow / DOM / Footprint |
| **Gives** | Where to look | Whether to act |
| **Question** | Where are traders positioned? | What are they doing right now? |
| **Gives you** | Areas of interest | Conviction and timing |

**Always Together:**
- Structure without flow = guessing
- Flow without structure = no roadmap

---

## Core Metrics

### Delta
Net difference between buying and selling volume at each price.
- Positive delta = aggressive buying dominates
- Negative delta = aggressive selling dominates
- Delta = 0 = perfectly balanced

### Delta Divergence
Price and delta move in opposite directions — earliest warning signal.
- Price makes new highs + declining positive delta → buyers losing conviction
- Price makes new lows + declining negative delta → sellers losing conviction

See [[Delta Divergence]]

### Absorption
Large orders absorbing selling/buying pressure without letting price through.
- Selling absorbed by bids → floor
- Buying absorbed by offers → ceiling

See [[Absorption]]

---

## Example

Profile shows a POC (structurally important). Flow shows:
- Big bids eating every offer → flow disagrees → don't short the POC
- Offers stacking above POC, bids getting pulled → flow agrees → fade the POC
- Conviction push through level → real break, not head fake

---

## Key Patterns

| Pattern | What Flow Shows | Action |
|---------|----------------|--------|
| Absorption at level | Selling into bids that won't budge | Don't short, buy the dip |
| Conviction push | High-volume directional move through level | Trade the break |
| Delta divergence | Price new high, delta declining | Reversal warning |
| Iceberg detection | Repeated fills at same price, keeps replenishing | Institutional activity |
| Spoofing | Large orders appear and disappear rapidly | Manipulation — don't trust the level |

---

## Integration with Volume Profile

| Setup | Flow Confirmation |
|-------|-------------------|
| Fading Edges of Balance | Absorption at VAH/VAL → fade |
| Head Fake (Retail Trap) | Punchy move, minimal follow-through → fade the sweep |
| Throwback (Post-Breakout Retest) | Momentum stalls on retest → trade the retest |

---

## Related
- [[Order Flow]] — main note
- [[Structure vs Flow]] — always together
- [[Order Book]] — the raw data structure
- [[Absorption]] — key confirmation pattern
- [[Delta Divergence]] — earliest warning signal
- [[Volume Profile]] — the structure side
