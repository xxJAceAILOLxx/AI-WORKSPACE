# Iceberg Orders

## One-Line Summary
Hidden institutional orders — only a visible "tip" is displayed, rest is concealed and replenishes automatically.

---

## What It Is

- Large order split into visible portion + hidden reserve
- When visible portion fills, hidden quantity refreshes it
- Process repeats until order fully executed or cancelled
- Sign of institutional accumulation or distribution

> "An iceberg order displays only a portion of the total order quantity in the visible order book. As the visible portion executes, more quantity is automatically revealed from the hidden reserve."

---

## Example

| Parameter | Value |
|-----------|-------|
| Total Size | 10,000 shares |
| Display Size | 500 shares |
| What Market Sees | 500 shares @ price |
| Actual Hidden | 9,500 shares |

After 3 fills of 500:
- Filled: 1,500
- Still visible: 500
- Hidden remaining: 8,000

---

## How to Detect

| Signal | What It Means |
|--------|--------------|
| Repeated fills at same price, keeps replenishing | Likely iceberg |
| Same size appears again and again at one level | Hidden liquidity |
| Volume at level exceeds what's displayed | Hidden orders active |
| Price can't break through despite heavy volume | Absorption via iceberg |

---

## Why Institutions Use It

- Hides true size to avoid market impact
- If market sees 100,000 shares on bid, price moves up before they can fill
- Iceberg lets them accumulate/distribute gradually
- Reveals intent through patterns, not display

---

## What It Tells You

| Iceberg on Bid | Iceberg on Ask |
|----------------|----------------|
| Institutional buying | Institutional selling |
| Accumulation | Distribution |
| Support (real, not spoofed) | Resistance (real, not spoofed) |

---

## Iceberg vs Spoofing

| | Iceberg | Spoof |
|---|---------|-------|
| **Intent** | Wants to fill | Wants to mislead |
| **Behavior** | Keeps replenishing | Disappears before fill |
| **Fills** | Actually fills repeatedly | Rarely fills |
| **Detection** | Repeated same-size fills | Orders pulled on approach |

---

## Integration with Volume Profile

- Iceberg at a profile level = strong confirmation of genuine interest
- Iceberg + absorption at POC/VAH/VAL = high-probability level
- Iceberg that breaks = trapped institution → violent move

---

## Related
- [[Order Book]] — where icebergs are visible
- [[Absorption]] — icebergs absorb pressure
- [[Spoofing and Layering]] — fake vs real liquidity
- [[Order Flow]] — main note
- [[Market Microstructure]] — underlying mechanics
