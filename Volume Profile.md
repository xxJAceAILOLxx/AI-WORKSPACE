# Volume Profile

## One-Line Summary
Volume profile tells us **where business was done**. Everything else is an assumption.

---

## What It IS

- Where turnover took place
- Where the market transacted
- Where volume came in (two-way trade)

> "It just tells us where business was done. That's it."

---

## What It Is NOT

The profile does **not** tell us:

- Who bought or sold
- Whether positions were bought/sold to open or close
- Whether participants are longs or shorts
- Whether they are directional traders, short-term specs, long-term specs
- Whether they are delta neutral
- Whether the trade is part of a hedge or multi-leg trade
- Whether they're trading in the curve (e.g. buying front month, selling rear months)

Everything beyond "this is where a lot of business came in" is an assumption.

---

## Core Structure

![[Images/Volume Profile Anatomy.svg]]

| Element | Definition |
|---------|-----------|
| **High Volume Node (HVN)** | Areas of most turnover — consolidation, market spending time. Can be spotted without a profile. |
| **Low Volume Node (LVN)** | Areas where volume drops off — market sped through, rejected, stops run, liquidations. |
| **Value Area** | ~68-70% of volume for the session (~1 standard deviation of the distribution). |
| **Value Area High (VAH)** | Upper bound of the value area. |
| **Value Area Low (VAL)** | Lower bound of the value area. |
| **Point of Control (POC)** | Single price level with the most volume — "most agreed upon price," fair value, area of max balance. |

> Caveat: POC may not be meaningfully more important than nearby HVNs if the difference is marginal. Platform/tick settings can shift which level shows as POC.

---

## Three Best Use Cases

### 1. Fading the Edges of Balance
- Market has been favoring a range — cut off at extremes.
- Buy/sell a return to VAH or VAL.
- Expectation: market continues to chop (mean reverting).
- **Nuance**: The more times a level is tested, the less trustworthy. First/second attempts > third/fourth/fifth.
- Early tests = information. Repeated tests = buildup of pressure. Longer sideways = more violent resolution.

### 2. Head Fake (Failed Breakout)

![[Images/Head Fake Diagram.svg]]

- Price sweeps a level, punches through, volume comes in, then dies.
- Signs of weakness: punchy move, minimal follow-through, drifting back.
- Setup: sweep of level → HVN formed above → trades back below → target POC (midpoint), then potentially range lows.
- "Where retail gets trapped."

### 3. Retest After a Real Break (Throwback)
- The cleanest concept.
- Convincing, violent, high-volume break outside value.
- Immediately puts one side offside.
- First retest back toward value = highest probability trade.
- Why: recent positioning was balanced inside value. On return, trapped participants cover or don't re-add.
- Think: "If you were long and the market gaps against you, are you holding or looking to get out near breakeven?"

---

## Proximity Principle

$$
\text{Relevance} \propto \frac{1}{\text{Time Since Turnover}}
$$

- Positioning from **minutes/sessions ago** → likely still relevant → actionable.
- Positioning from **months ago** → likely turned over many times → context only, not positioning.
- Further back = includes different regimes, volatility, liquidity, contract rolls, expiries, rate cycles, FOMC chairs.
- Old profiles are about **context**, not positioning.

---

## Biggest Mistakes

1. **Using composites on loose markets** — composites only make sense when profiles are tightly overlapped and compressed. Not when there's dislocation and loose trading.
2. **Using profiles from too far back** — assuming dormant positioning from months ago is still relevant. It's not.
3. **Confusing context for execution** — long-term profiles give context (shorelines), not razor-sharp levels (lines in the sand).
4. **Treating profile as a magic map of support/resistance.**

---

## When Longer-Term Profiles ARE Useful

- **Context, not positioning.**
- Extremes become more actionable than value areas.
- Think of them as **shorelines**, not lines in the sand.
- A loose, spread-out monthly profile tells you: the market hasn't found agreement, it's not balanced.

---

## Trader's Checklist

1. **What auction am I studying?** Current session vs. months ago?
2. **Where is value being accepted?**
3. **Where was the market rejected?**
4. **Who is likely trapped?**
5. **Is this level still fresh?**
6. **What does current flow say?**

> "Profile gives you the areas of interest. But it's the actual **order flow** that tells you whether or not you should care. Structure vs. flow, always."

---

## Asset Considerations

- Works best for: equity index futures, Bitcoin (retail-driven), short-to-mid timeframes.
- Less straightforward for: curve-traded assets (crude oil, commodity futures) — front-month volume may be part of curve trades, not outright directional.

---

## Related Concepts

- [[MOC - Trading]] — full map of content
- [[Order Flow]] — structure vs flow
- [[Market Profile]] — related but distinct
- [[Value Area]] — 68-70% of distribution
- [[Auction Market Theory]]
- [[Positioning vs Context]]
- [[The Proximity Principle]]
- [[Structure vs Flow]]
- [[HVN vs LVN Actionability]]
- [[Composite Profiles]]
- [[Market Regime Context]]
- [[Fading the Edges of Balance]]
- [[Head Fakes (Retail Traps)]]
- [[The Throwback (Post-Breakout Retest)]]

---

## Key Quotes

> "Markets are just positions." — Michael Platt

> "Volume profile's not a magic map of support and resistance."

> "The shorter and cleaner it is, the more you could tell about live positioning."