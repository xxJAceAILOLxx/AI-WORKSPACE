# Hedge Fund Markov Method

> Quantitative state-based trading using Markov chains to classify market regimes and generate directional signals.

---

## Core Concepts

### 1. States
Quantify the market state rather than relying on subjective assessment. Classify into numerical values.

| State | Definition (20-day lookback) |
|-------|------------------------------|
| Bull | Price up >5% |
| Sideways | Price between -5% and +5% |
| Bear | Price down >5% |

### 2. Markov Property
**The future depends only on the present, not the past.**

Where the market goes is entirely dependent on the state today. Historical path doesn't matter—only current position.

> "It's no good giving me directions from Grand Rapids, Michigan to get to New York City if I'm in Little Rock."

### 3. State Transitions
Track every instance where state changes:
- Bull → Bull, Bull → Sideways, Bull → Bear
- Sideways → Bull, Sideways → Sideways, Sideways → Bear
- Bear → Bull, Bear → Sideways, Bear → Bear

Count occurrences → calculate transition probabilities.

### 4. Stickiness
**Trends persist mathematically.**

If today is bull, tomorrow is most likely also bull. Same for bear states.

- Bull states are sticky
- Bear states are sticky
- This is why "the trend is your friend" works

**Important correction:** Use non-overlapping 20-day windows for accurate stickiness scores. Looking at overlapping windows inflates the numbers.

### 5. Signal Generation
```
Signal = P(Bull tomorrow) - P(Bear tomorrow)
```

- Positive signal → Long bias
- Negative signal → Short bias
- Magnitude = confidence level
- Scale position size with confidence

### 6. Multi-Day Projection
Project forward using exponentiation:
- Day 1: 0.6
- Day 2: 0.6² = 0.36
- Day 3: 0.6³ = 0.216

Beyond ~5-10 days, probabilities become too small to be actionable.

### 7. Walking Forward
**No look-ahead bias in backtesting.**

The agent only sees data that happened before the current bar. Never looks into the future.

### 8. Hidden Markov Method
Let the model discover states from data without predefined thresholds. Combines with Markov method for subjective + objective confirmation.

---

## Implementation Checklist

- [ ] Define state boundaries (5% threshold or Hidden Markov discovery)
- [ ] Calculate transition matrix from historical data
- [ ] Compute stickiness scores with non-overlapping windows
- [ ] Generate directional signal (bull - bear probability)
- [ ] Scale position size with confidence magnitude
- [ ] Walk-forward only (no look-ahead)

---

## Video Reference
- Source: Quant/ hedge fund method explanation by Roan
- Model: Fable 5 improved upon Opus 4.7 version
- Integration: Connects to TradingView via Pine Script

---

*Created: 2026-06-26*
