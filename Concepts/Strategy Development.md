# Strategy Development

## One-Line Summary
The process of turning a trading idea into a testable, mechanical system — from hypothesis to validated rules.

---

## The Process

```
Observation → Hypothesis → Edge Identification → Rule Design → Code → Validate
```

---

## Phase 1: Observation

### Where Ideas Come From

| Source | Example |
|--------|---------|
| Your own data | "My morning trades have 62% win rate vs 41% afternoon" |
| Academic research | "Momentum factor persists across markets" |
| Market structure | "POC retests with absorption reverse 70% of the time" |
| Volume profile patterns | "Throwback after real break = highest probability setup" |
| Order flow patterns | "Delta divergence at VAH = earliest reversal signal" |

---

## Phase 2: Hypothesis

### Requirements
- **Specific** — can be written as if/then
- **Testable** — backtest can disprove it
- **Falsifiable** — has clear pass/fail criteria
- **Has economic logic** — you can explain WHY

### Good Hypothesis Template
"When [condition], enter [direction] with [stop placement] and [target]. Expect [edge explanation]."

### HARKing Warning
Hypothesizing After Results are Known — formulating hypothesis after seeing what worked. Guarantees overfitting.

---

## Phase 3: Edge Identification

### What Is an Edge
A systematic advantage that allows superior returns consistently. Can come from:

| Edge Type | Example |
|-----------|---------|
| Price inefficiency | Mean reversion at extremes |
| Behavioral | Retail trapping at breakouts |
| Structural | VP throwback after real breaks |
| Execution | Better fills via order flow reading |
| Informational | Understanding institutional positioning |

### Key Question
"Can I explain WHY this should work?" If not, there's no reason to believe it will persist.

---

## Phase 4: Rule Design

### Entry Rules
- Every condition that must be true
- Specific indicator values or price action
- All four must be met (if multiple)

### Exit Rules
- Stop loss placement
- Take profit target
- Time-based exit

### Position Sizing
- Fixed risk per trade (e.g., 1% of equity)
- Based on entry-to-stop distance

### No-Trade Conditions
- FOMC days
- After daily loss limit
- First/last X minutes

> "Simplicity is an advantage, not a limitation. The most robust strategies typically have 2-4 main rules."

---

## Phase 5: Code

### Best Practices
- Version control (Git)
- Descriptive commits
- Every parameter justified (not "because it worked better")
- No lookahead bias
- Realistic cost model

### Documentation
- Original hypothesis written before testing
- Entry and exit logic in words
- Parameters and their justification
- Target markets and timeframe
- Changelog of changes with dates

---

## Phase 6: Validate

See [[Backtesting]] for full detail.

### Quick Checklist
- 1000+ trades in backtest
- Profit Factor > 1.3
- Walk-Forward Ratio > 0.5
- Monte Carlo survival > 90%
- Positive out-of-sample performance

---

## Integration with Volume Profile

| VP Concept | Strategy Application |
|------------|---------------------|
| POC retest | Mean reversion at fair value |
| VAH/VAL fade | Fading edges of balance |
| Head fake | Fade failed breakouts |
| Throwback | Trade first retest after real break |
| Absorption + flow | Confirmation filter for all setups |

---

## Common Mistakes

1. **Skipping hypothesis** — "I'll just try stuff" = random exploration
2. **Optimizing before testing base logic** — core must work with simple params
3. **Too many parameters** — rule: 10 trades per free parameter
4. **No out-of-sample** — always reserve 20-30% of data
5. **Ignoring costs** — slippage kills marginal strategies
6. **HARKing** — formulating hypothesis after seeing results
7. **Not documenting** — can't reproduce or learn from past decisions

---

## Related
- [[Building and Backtesting Strategies]] — main note
- [[Backtesting]] — validation details
- [[Volume Profile]] — structural edges
- [[Order Flow]] — flow confirmation
- [[Structure vs Flow]] — always together
