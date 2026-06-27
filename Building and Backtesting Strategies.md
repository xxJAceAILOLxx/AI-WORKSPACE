# Building and Backtesting Strategies

## One-Line Summary
A systematic process to turn a trading idea into a validated, live system — from hypothesis to live capital, with risk gates at every step.

---

## The Pipeline

> "Most failed systems fail before strategy design. They fail because the builder has an idea, not a hypothesis."

```
Idea → Hypothesis → Rules → Backtest → Forward Test → Live Test → Evaluate → Iterate
         Phase 1      Phase 2   Phase 3    Phase 4       Phase 5     Phase 6    Phase 7
```

Each phase has a **pass criterion** and a **stop criterion**. A strategy that fails at any stage is discarded or reformulated — not patched.

---

## Phase 1: Hypothesis Formation

### What Makes a Good Hypothesis

- **Specific and testable** — can be written as if/then statement
- **Falsifiable** — backtest can disprove it
- **Has economic logic** — you can explain WHY it should work
- Not HARKing (Hypothesizing After Results are Known)

### Good vs Bad Hypotheses

| Bad | Good |
|-----|------|
| "Breakouts work" | "Stocks that gap 3%+ on earnings with 2x avg volume continue higher in first 30 min" |
| "I can read price action" | "When RSI(14) < 30 AND price > EMA(200), buy with target at 2:1 R:R" |
| "Support holds" | "POC retest with absorption (negative delta but price holds) → fade with 1.5 ATR stop" |

### Where Ideas Come From

- Your own trading data (journal patterns)
- Academic papers (anomalies, factor research)
- Market observations (structural inefficiencies)
- Volume profile / order flow patterns
- Classic strategies (mean reversion, momentum, breakouts)

> "If you can't write it as an if/then statement, you can't backtest it."

---

## Phase 2: Define System Rules

Rules must be **mechanical and unambiguous** — two people watching the same chart should make the same decision.

### Entry Rules
Every condition that must be true before entry. Example:
```
Enter long when:
(1) RSI(14) < 30
(2) Price > EMA(200)
(3) MACD histogram crosses above zero
(4) Breakout candle volume > 1.5x prior bar
```

### Exit Rules
Three types — define ALL three:
- **Stop loss**: "1.5x ATR(14) below entry"
- **Take profit**: "2:1 R:R target"
- **Time exit**: "Close after 60 minutes regardless"

### Position Sizing Rules
"Risk 1% of account per trade. Calculate position size based on entry-to-stop distance."

### No-Trade Conditions
- No trades on FOMC days
- No trades if daily loss reached 2%
- No trades in first 5 minutes of open

> "The simpler the strategy, the more robust. Most profitable strategies have 2-4 main rules."

---

## Phase 3: Backtesting

### Minimum Requirements

| Requirement | Minimum | Ideal |
|-------------|---------|-------|
| Historical data | 2+ years | 5-10+ years |
| Trade count | 50+ | 200+ (1000+ for full validation) |
| Market regimes | 2+ | All (trending, choppy, volatile, quiet) |
| Costs modeled | Commissions + slippage | Full cost model (spread, impact, funding) |

### What to Measure

| Metric | Target | What It Tells You |
|--------|--------|-------------------|
| Profit Factor | > 1.3 (1.5+ strong) | Gross wins / gross losses |
| Sharpe Ratio | > 1.0 (1.5-2.0 good) | Return per unit of volatility |
| Sortino Ratio | > 1.5 | Return per downside volatility only |
| Max Drawdown | < 20% (15% personal, 5% prop) | Largest peak-to-trough drop |
| Win Rate | Depends on R:R | Meaningless alone |
| Expectancy | Positive (> 0.2R) | (Win% × Avg Win) - (Loss% × Avg Loss) |
| Trade Count | 200+ | Statistical significance |

### The 70% Rule
Live profit factor should be at least 70% of backtest profit factor. If backtest PF = 1.8, live target = 1.26+.

### Overfitting Detection

| Signal | What It Means |
|--------|--------------|
| Only works with exact parameters | Curve-fit, not real edge |
| One huge winning trade skews everything | Not a robust pattern |
| Performance collapses in certain years | Regime-dependent |
| Sharpe > 3.0 | Likely overfit or unrealistic |
| Suspiciously long flat periods | Strategy may be broken |

### What NOT to Do

- **Don't optimize before testing base logic** — if core doesn't work with simple params, optimization won't save it
- **Don't over-optimize** — keep params to 3-5 max
- **Don't ignore costs** — strategy that returns 8% but costs 6% is a 2% strategy
- **Don't skip the null hypothesis test** — compare against random chance

> "If you torture the data long enough, it will confess to anything." — Ronald Coase

---

## Phase 4: Forward Testing (Paper Trading)

### Purpose
Reveals whether the system is **actually tradeable** by a human in real-time conditions.

### Minimum Requirements
- 30+ setups (2-6 weeks depending on frequency)
- Compare results to backtest
- Forward-test PF should be within 80% of backtest PF

### What Forward Testing Catches
1. Can you identify the setup in real time?
2. Can you get filled at expected prices?
3. Can you resist overriding rules?
4. Does the current regime match your backtest assumptions?

### Red Flags
- Win rate 10+ points lower than backtest
- Consistently missing entries
- Frequent urge to override rules
- Difficulty getting fills near expected prices

> "A backtest checks history. A forward test checks execution here and now."

---

## Phase 5: Live Testing (Small Capital)

### Graduated Scaling

| Phase | Duration | Size | Purpose |
|-------|----------|------|---------|
| Demo/Min | Week 1-2 | Paper or min | Verify execution |
| Initial | Month 1 | 25% | Confirm metrics align |
| Intermediate | Month 2 | 50% | Validate consistency |
| Full | Month 3+ | 100% | Trade if consistent |

### Rule Adherence Score
Track every trade with "Rules Followed" / "Rules Broken" tags. Target: >80% adherence.

### Stop Criteria (Define BEFORE Trading)
- Drawdown exceeds Monte Carlo P5
- Win rate drops 15+ points from historical
- Losing streaks > 1.5x historical max
- Monthly return < expected P10 for 3 consecutive months

---

## Phase 6: Evaluation

### Three-Way Comparison

| Phase | What to Compare |
|-------|-----------------|
| Backtest | Historical edge |
| Forward Test | Real-time execution |
| Live Test | Real money execution |

### The 70% Rule (Again)
If live PF is at least 70% of backtest PF → system is viable at full size.

### If Live Results Are Worse
- Check Rule Adherence Score first — if < 80%, it's discipline, not the system
- Check execution quality — slippage may be higher than assumed
- Check market conditions — regime may have shifted

---

## Phase 7: Iteration (Permanent)

### Monthly Reviews
- Is win rate stable within historical range?
- Is profit factor still above 1.2?
- New patterns suggesting rule changes?

### Making Changes
Every parameter change = new hypothesis:
1. State the hypothesis
2. Backtest the change
3. Forward test 20+ trades at reduced size
4. Only implement at full size after validation

### When to Retire a System
- Profit factor < 1.0 over 50+ trades with clean execution
- Edge has disappeared (market conditions changed)
- Either wait for conditions to return or develop new hypothesis

---

## Robustness Tests

### Walk-Forward Analysis
Robert Pardo's method (1992):
1. Split data into rolling windows (e.g., 12mo IS + 3mo OOS)
2. Optimize on IS window
3. Test on next OOS window
4. Slide forward and repeat
5. Aggregate all OOS results

**Walk-Forward Ratio** = OOS return / IS return
- > 0.5 = robust
- < 0.3 = overfitting

### Monte Carlo Simulation
Randomize trade sequence thousands of times:
- Range of possible outcomes (not just single historical path)
- Probability of drawdown exceeding thresholds
- Confidence intervals around expected returns
- Survival rate target: 90%+

### Stress Tests
- Test on adjacent timeframes
- Test on similar assets
- Increase costs by 50-100%
- Test across different market regimes

### Out-of-Sample Validation
- Reserve 20-30% of data — never touch during development
- OOS performance should retain 60-70% of IS performance
- Below 0.3 Walk-Forward Ratio = clear overfitting

---

## Portfolio Diversification

### Why
Single strategies go through prolonged drawdowns. Portfolio of uncorrelated strategies smooths equity curve.

### Correlation Target
| Correlation | Verdict |
|-------------|---------|
| r < 0.3 | Low — ideal |
| 0.3 < r < 0.7 | Medium — acceptable |
| r > 0.7 | High — avoid |

### Benefit
A portfolio of 5 uncorrelated strategies can have Sharpe Ratio 2-3x higher than any individual strategy.

---

## Backtesting Tools

| Tool | Type | Best For |
|------|------|----------|
| TradingView (Pine Script) | No-code/scripting | Quick prototyping |
| Backtrader (Python) | Open-source | Full customization |
| vectorbt (Python) | Open-source | Fast parameter sweeps |
| backtesting.py | Open-source | Simple backtests |
| MetaTrader (MQL) | Built-in | Forex/CFD |
| TradeZella | Platform | Journal + backtest |
| Excel/Sheets | Manual | Simple rule-based systems |

---

## Key Formulas

### Expectancy
$$E = (Win\% \times AvgWin) - (Loss\% \times AvgLoss)$$

### Profit Factor
$$PF = \frac{GrossWins}{GrossLosses}$$

### Sharpe Ratio
$$SR = \frac{R_p - R_f}{\sigma_p}$$

### Walk-Forward Ratio
$$WFR = \frac{OOS_{return}}{IS_{return}}$$

### Book Imbalance (for order flow integration)
$$\rho = \frac{V_{bid} - V_{ask}}{V_{bid} + V_{ask}}$$

---

## Integration with Volume Profile & Order Flow

| Phase | VP/OF Integration |
|-------|-------------------|
| Hypothesis | VP levels as structural edges |
| Rules | Absorption/delta divergence as entry confirmation |
| Backtest | Test VP setups with flow filters |
| Forward Test | Verify real-time flow reading |
| Live Test | Confirm structure vs flow discipline |

---

## Validation Checklist (Before Going Live)

- [ ] 1000+ trades in backtest
- [ ] Profit Factor > 1.3
- [ ] Sharpe Ratio > 1.0
- [ ] Walk-Forward Ratio > 0.5
- [ ] Positive and stable OOS performance
- [ ] Monte Carlo survival > 90%
- [ ] Works on adjacent timeframes
- [ ] Can explain the strategy logic
- [ ] Size ramp-up plan defined
- [ ] Stop criteria documented
- [ ] 30+ forward test setups
- [ ] 20+ live trades at each size level

---

## Sources

- TradeZella, *How to Build a Trading System (7-Phase Guide 2026)*
- Rubén Villahermosa, *Complete Guide to Validate a Trading Strategy*
- Michael Brenndoerfer, *Research Pipeline & Deployment*
- HFT Book, *Research-to-Production Pipeline*
- QuantStart, *Backtesting Systematic Trading Strategies*
- Aligrithm, *The Backtest Integrity Checklist*
- Marcos López de Prado, *Advances in Financial Machine Learning*
- Robert Pardo, *The Evaluation and Optimization of Trading Strategies*

---

## Related
- [[Order Flow]] — structure vs flow integration
- [[Volume Profile]] — structural levels for hypotheses
- [[Concepts/Backtesting]] — detailed backtesting concepts
- [[Concepts/Strategy Development]] — idea to system process
- [[Concepts/Market Microstructure]] — execution reality
- [[Reflections/Volume Profile - Key Insights]] — mindset shifts
