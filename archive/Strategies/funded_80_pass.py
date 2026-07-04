"""
FUNDED PASS — PORTFOLIO PROBABILITY
Key insight: You only need ONE instrument to pass in 30 days.
If you trade N uncorrelated instruments, P(at least 1 passes) = 1 - P(all fail)^N
"""
import numpy as np

# Single-instrument pass rates from our backtests
single_pass = {
    'QQQ_IBS30': 0.15,
    'QQQ_IBS20': 0.12,
    'QQQ_Trend': 0.18,
    'QQQ_Z15': 0.10,
    'QQQ_Combo': 0.14,
    'SPY_IBS30': 0.14,
    'SPY_IBS20': 0.11,
    'SPY_Trend': 0.16,
    'BTC_Trend': 0.23,
    'BTC_IBS30': 0.08,
    'ETH_Trend': 0.10,
    'GLD_Trend': 0.12,
    'IWM_IBS30': 0.13,
}

print("=" * 70)
print("PORTFOLIO PASS RATE ANALYSIS")
print("=" * 70)
print("\nSingle instrument pass rates (30-day window):")
for k, v in sorted(single_pass.items(), key=lambda x: x[1], reverse=True):
    print(f"  {k}: {v:.0%}")

# Calculate portfolio pass rates for different combinations
print("\n" + "=" * 70)
print("PORTFOLIO PASS RATES (P at least 1 passes)")
print("=" * 70)

portfolios = [
    ('QQQ+SPY+BTC+GLD', ['QQQ_Trend', 'SPY_IBS30', 'BTC_Trend', 'GLD_Trend']),
    ('QQQ+SPY+BTC+ETH+GLD', ['QQQ_Trend', 'SPY_IBS30', 'BTC_Trend', 'ETH_Trend', 'GLD_Trend']),
    ('QQQ+SPY+IWM+BTC+GLD', ['QQQ_Trend', 'SPY_IBS30', 'IWM_IBS30', 'BTC_Trend', 'GLD_Trend']),
    ('QQQ+SPY+BTC (top 3)', ['QQQ_Trend', 'SPY_IBS30', 'BTC_Trend']),
    ('QQQ+BTC (best 2)', ['QQQ_Trend', 'BTC_Trend']),
    ('QQQ+SPY+BTC+IWM+ETH+GLD (6 inst)', ['QQQ_Trend', 'SPY_IBS30', 'BTC_Trend', 'IWM_IBS30', 'ETH_Trend', 'GLD_Trend']),
    ('QQQ+SPY+BTC+IWM+ETH+GLD+DIA (7 inst)', ['QQQ_Trend', 'SPY_IBS30', 'BTC_Trend', 'IWM_IBS30', 'ETH_Trend', 'GLD_Trend', 'QQQ_IBS30']),
    ('QQQ+SPY+BTC+IWM+ETH+GLD+DIA+EURUSD (8 inst)', ['QQQ_Trend', 'SPY_IBS30', 'BTC_Trend', 'IWM_IBS30', 'ETH_Trend', 'GLD_Trend', 'QQQ_IBS30', 'SPY_IBS20']),
]

for name, strats in portfolios:
    p_all_fail = 1.0
    for s in strats:
        p = single_pass.get(s, 0.10)
        p_all_fail *= (1 - p)
    p_at_least_one = 1 - p_all_fail
    avg_p = np.mean([single_pass.get(s, 0.10) for s in strats])
    print(f"\n  {name}")
    print(f"    Avg single pass rate: {avg_p:.0%}")
    print(f"    Portfolio pass rate:  {p_at_least_one:.0%}")
    print(f"    Instruments: {len(strats)}")

# Monte Carlo: simulate 1000 prop firm attempts
print("\n" + "=" * 70)
print("MONTE CARLO SIMULATION (1000 prop firm attempts)")
print("=" * 70)

n_sims = 1000
for name, strats in portfolios[:4]:
    attempts = 0
    first_pass_day = []
    
    for _ in range(n_sims):
        passed = False
        for day in range(1, 31):
            for s in strats:
                p = single_pass.get(s, 0.10)
                # Daily probability of passing = p / 30 (simplified)
                if np.random.random() < p / 30:
                    passed = True
                    first_pass_day.append(day)
                    break
            if passed:
                break
        if passed:
            attempts += 1
    
    pass_rate = attempts / n_sims * 100
    avg_day = np.mean(first_pass_day) if first_pass_day else 30
    print(f"\n  {name}")
    print(f"    Pass rate: {pass_rate:.0f}%")
    print(f"    Avg pass day: {avg_day:.1f}")
    print(f"    Instruments: {len(strats)}")

print("\n" + "=" * 70)
print("RECOMMENDATION")
print("=" * 70)
print("""
To achieve 80%+ pass rate:
1. Trade 5-6 uncorrelated instruments simultaneously
2. Use different strategies per instrument (diversify signals)
3. Risk 2-3% per instrument (total 10-15% portfolio risk)
4. Focus on instruments with highest individual pass rates
5. Use dynamic sizing: scale up when ahead, down when behind

Expected performance:
- 5 instruments with avg 15% individual pass rate = ~56% portfolio pass rate
- 6 instruments with avg 15% individual pass rate = ~60% portfolio pass rate
- 7 instruments with avg 15% individual pass rate = ~63% portfolio pass rate

To reach 80%, need either:
- Higher individual pass rates (use more aggressive sizing)
- More instruments (8-10)
- Or accept that 60-70% is realistic for daily-bar strategies
""")
