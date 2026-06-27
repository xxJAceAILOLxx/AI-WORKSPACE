# Backtesting

## One-Line Summary
Running strategy rules against historical data to estimate whether an edge is real — and how it behaves under realistic conditions.

---

## What It IS

- Replay of strategy against historical price data
- Estimation of risk-adjusted return, capacity, and decay
- Statistical validation before risking real capital
- The filter that kills 90% of bad ideas before they cost money

## What It Is NOT

- Proof of future performance
- A single number (it's a distribution + verdict)
- Optional for systematic trading
- A substitute for forward testing

> "A backtest that admits look-ahead bias, survivorship bias or optimistic fills will conjure an edge that does not exist live."

---

## Minimum Requirements

| Requirement | Minimum | Ideal |
|-------------|---------|-------|
| Historical data | 2+ years | 5-10+ years |
| Trade count | 50+ | 200+ (1000+ gold standard) |
| Market regimes | 2+ | All types |
| Cost model | Commissions + slippage | Full cost model |

---

## Key Metrics

| Metric | Target | Interpretation |
|--------|--------|---------------|
| Profit Factor | > 1.3 | Gross wins / gross losses |
| Sharpe Ratio | > 1.0 | Risk-adjusted return |
| Sortino Ratio | > 1.5 | Downside-only volatility |
| Max Drawdown | < 20% | Largest peak-to-trough |
| Expectancy | Positive > 0.2R | Edge per trade |
| Win Rate | Depends on R:R | Alone is meaningless |
| Trade Count | 200+ | Statistical significance |

---

## The Five Levels of Backtesting

### Level 1: Visual Replay
Manual chart review — slow, subjective, not repeatable.

### Level 2: Spreadsheet
Excel/Sheets — decent for simple rule-based systems, limited scale.

### Level 3: Event-Driven (Professional)
Tick-by-tick simulation — closest to real execution, handles complex order logic.

### Level 4: Walk-Forward (Institutional)
Rolling optimization + validation windows — catches overfitting.

### Level 5: Monte Carlo + Stress Testing (Quantitative)
Randomized trade sequences — reveals range of outcomes, not just single path.

---

## Overfitting

### What It Is
Strategy tuned so precisely to historical data that it fails on new data. Like memorizing exam answers — perfect on that exam, fails any other.

### How to Detect

| Signal | Meaning |
|--------|---------|
| Only works with exact parameters | Curve-fit |
| One huge trade skews everything | Not robust |
| Performance collapses in certain years | Regime-dependent |
| Sharpe > 3.0 | Likely overfit |
| Many parameters (5+) | High overfitting risk |

### How to Prevent
- Keep rules simple (2-4 max)
- Formulate hypothesis BEFORE testing
- Never optimize before base logic works
- Walk-forward validation
- Monte Carlo simulation
- Reserve out-of-sample data

> "Only 1 out of every 20 strategy ideas survives a complete validation process." — Kevin Davey

---

## Common Biases

| Bias | What It Is | How to Avoid |
|------|-----------|-------------|
| Look-ahead | Using future data in decisions | Point-in-time data only |
| Survivorship | Only testing assets that still exist | Use delisted/failed assets |
| Data snooping | Testing many variants, picking best | Out-of-sample validation |
| Selection bias | Cherry-picking favorable periods | Test full history |
| Cost underestimation | Ignoring slippage/spread | Model real costs |

---

## Walk-Forward Analysis

Robert Pardo's method (1992):
1. Split data into rolling windows (e.g., 12mo IS + 3mo OOS)
2. Optimize on IS window
3. Test on next OOS window
4. Slide forward and repeat
5. Aggregate all OOS results

**Walk-Forward Ratio** = OOS return / IS return
- > 0.5 = robust
- < 0.3 = overfitting

---

## Monte Carlo Simulation

- Randomize trade sequence thousands of times
- Reveals range of possible outcomes (not just single historical path)
- Shows probability of drawdown exceeding thresholds
- Provides confidence intervals around expected returns
- Target: 90%+ survival rate with tolerable drawdown

---

## Cost Modeling

| Cost | Impact |
|------|--------|
| Commissions | Direct per-trade cost |
| Slippage | Difference between expected and actual fill |
| Spread | Cost of crossing bid-ask |
| Market impact | Price moves against you when trading size |
| Funding rates | Overnight costs (crypto, forex) |

**Golden Rule**: If strategy becomes unprofitable when doubling estimated costs, it's too sensitive.

---

## Related
- [[Building and Backtesting Strategies]] — main note
- [[Strategy Development]] — idea to system
- [[Order Flow]] — execution reality
- [[Market Microstructure]] — fills and slippage
