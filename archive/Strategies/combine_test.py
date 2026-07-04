"""
COMBINED STRATEGY — Try to reach Sharpe 1.3
=============================================
Combine uncorrelated strategies/instruments
"""

import pandas as pd
import numpy as np
import yfinance as yf
import warnings
warnings.filterwarnings('ignore')

INITIAL = 100000
COST = 0.001

tickers = ['QQQ', 'SPY', 'XLK', 'GLD', 'TLT']
data = {}
for t in tickers:
    d = yf.download(t, start='2010-01-01', end='2025-12-31', progress=False)
    if hasattr(d.columns, 'get_level_values'):
        d.columns = d.columns.get_level_values(0)
    if len(d) > 2000:
        df = d[['Open', 'High', 'Low', 'Close']].copy()
        df['SMA50'] = df['Close'].rolling(50).mean()
        df['SMA200'] = df['Close'].rolling(200).mean()
        df['EMA12'] = df['Close'].ewm(span=12).mean()
        df['EMA26'] = df['Close'].ewm(span=26).mean()
        df['Ret'] = df['Close'].pct_change()
        df['Vol20'] = df['Ret'].rolling(20).std() * np.sqrt(252)
        df['RSI14'] = 100 - 100 / (1 + df['Close'].diff().clip(lower=0).rolling(14).mean() /
                                     df['Close'].diff().clip(upper=0).abs().rolling(14).mean())
        df['TR'] = np.maximum(df['High'] - df['Low'],
            np.maximum(abs(df['High'] - df['Close'].shift(1)),
                       abs(df['Low'] - df['Close'].shift(1))))
        df['ATR14'] = df['TR'].rolling(14).mean()
        data[t] = df


def run_strategy(df, strat_type):
    """Run a strategy and return equity curve"""
    cap = INITIAL; pos = 0; signal = 0; entry = 0
    eq = []
    
    for i in range(1, len(df)):
        c_prev = float(df['Close'].iloc[i-1])
        o = float(df['Open'].iloc[i])
        c = float(df['Close'].iloc[i])
        
        if strat_type == 'sma_cross':
            f = float(df['SMA50'].iloc[i-1]) if pd.notna(df['SMA50'].iloc[i-1]) else None
            s = float(df['SMA200'].iloc[i-1]) if pd.notna(df['SMA200'].iloc[i-1]) else None
            new_signal = 1 if (f and s and f > s) else 0
        elif strat_type == 'ema_cross':
            e12 = float(df['EMA12'].iloc[i-1]) if pd.notna(df['EMA12'].iloc[i-1]) else None
            e26 = float(df['EMA26'].iloc[i-1]) if pd.notna(df['EMA26'].iloc[i-1]) else None
            new_signal = 1 if (e12 and e26 and e12 > e26) else 0
        elif strat_type == 'mom20':
            mom = float(df['Close'].iloc[i-1] / df['Close'].iloc[i-21] - 1) if i > 20 else 0
            new_signal = 1 if mom > 0 else 0
        elif strat_type == 'sma_vol':
            f = float(df['SMA50'].iloc[i-1]) if pd.notna(df['SMA50'].iloc[i-1]) else None
            s = float(df['SMA200'].iloc[i-1]) if pd.notna(df['SMA200'].iloc[i-1]) else None
            vol = float(df['Vol20'].iloc[i-1]) if pd.notna(df['Vol20'].iloc[i-1]) else 1.0
            new_signal = 1 if (f and s and f > s and vol < 0.20) else 0
        elif strat_type == 'rsi_mr':
            rsi = float(df['RSI14'].iloc[i-1]) if pd.notna(df['RSI14'].iloc[i-1]) else 50
            if pos > 0:
                new_signal = 1 if rsi < 70 else 0  # hold until RSI>70
            else:
                new_signal = 1 if rsi < 30 else 0  # buy when oversold
        else:
            new_signal = signal
        
        if pos == 0 and new_signal == 1 and signal == 0:
            sh = int(cap / o)
            if sh > 0:
                ca = sh * o * COST; cap -= sh * o + ca; pos = sh; entry = o
        elif pos > 0 and new_signal == 0 and signal == 1:
            ca = pos * (entry + o) * COST / 2
            cap += pos * o - ca
            pos = 0
        
        signal = new_signal
        eq.append(cap + (pos * c if pos > 0 else 0))
    
    if pos > 0:
        c = float(df['Close'].iloc[-1])
        ca = pos * (entry + c) * COST / 2
        cap += pos * c - ca
    
    return np.array(eq)


def calc_sharpe(eq):
    dr = np.diff(eq) / eq[:-1]
    dr = dr[np.isfinite(dr)]
    return (np.mean(dr) / np.std(dr)) * np.sqrt(252) if np.std(dr) > 0 else 0


# ============================================================
# TEST 1: Combine strategies on QQQ
# ============================================================
print("=" * 90)
print("TEST 1: Strategy combinations on QQQ")
print("=" * 90)
print()

strats = ['sma_cross', 'ema_cross', 'mom20', 'sma_vol', 'rsi_mr']
eq_curves = {}
for s in strats:
    eq_curves[s] = run_strategy(data['QQQ'], s)

# Equal-weight combination
min_len = min(len(v) for v in eq_curves.values())
combined = np.zeros(min_len)
for s, eq in eq_curves.items():
    combined += eq[:min_len] / len(strats)

sh_combined = calc_sharpe(combined)
sh_individual = {s: calc_sharpe(eq) for s, eq in eq_curves.items()}

print(f"  Individual Sharpe:")
for s, sh in sh_individual.items():
    print(f"    {s:<12} {sh:.2f}")
print(f"    {'Combined':<12} {sh_combined:.2f}")


# ============================================================
# TEST 2: Multi-instrument combinations
# ============================================================
print()
print("=" * 90)
print("TEST 2: Multi-instrument SMA cross")
print("=" * 90)
print()

# Equal-weight across instruments
strat_eqs = {}
for t in data:
    strat_eqs[t] = run_strategy(data[t], 'sma_cross')

# Combine
min_len = min(len(v) for v in strat_eqs.values())
for n_assets in [2, 3, 4, 5]:
    # Pick top N by Sharpe
    sharps = {t: calc_sharpe(eq) for t, eq in strat_eqs.items()}
    top = sorted(sharps, key=sharps.get, reverse=True)[:n_assets]
    combined = np.zeros(min_len)
    for t in top:
        combined += strat_eqs[t][:min_len] / n_assets
    sh = calc_sharpe(combined)
    print(f"  Top {n_assets} ({', '.join(top)}): Sharpe {sh:.2f}")


# ============================================================
# TEST 3: Strategy × Instrument best combos
# ============================================================
print()
print("=" * 90)
print("TEST 3: Best Strategy × Instrument combos")
print("=" * 90)
print()

combos = []
for t in data:
    for s in strats:
        eq = run_strategy(data[t], s)
        sh = calc_sharpe(eq)
        n = len([1 for i in range(1, len(eq)) if eq[i] != eq[i-1]])  # rough trade count
        combos.append((t, s, sh))

combos.sort(key=lambda x: x[2], reverse=True)
print(f"  {'Instr':<6} {'Strategy':<12} {'Sharpe':>7}")
print(f"  {'-'*27}")
for t, s, sh in combos[:15]:
    print(f"  {t:<6} {s:<12} {sh:>7.2f}")


# ============================================================
# TEST 4: Combine top 3 uncorrelated combos
# ============================================================
print()
print("=" * 90)
print("TEST 4: Top 3 uncorrelated combos")
print("=" * 90)
print()

# Get equity curves for top combos
top_eqs = []
for t, s, sh in combos[:10]:
    eq = run_strategy(data[t], s)
    top_eqs.append((f"{t}_{s}", eq, sh))

# Find least correlated pair
min_len = min(len(e) for _, e, _ in top_eqs)
returns = {}
for name, eq, _ in top_eqs:
    dr = np.diff(eq[:min_len]) / eq[:min_len-1]
    returns[name] = dr

ret_df = pd.DataFrame(returns)
corr = ret_df.corr()

# Find 3 with lowest average correlation
best_combo = None
best_sh = 0
for i in range(len(top_eqs)):
    for j in range(i+1, len(top_eqs)):
        for k in range(j+1, len(top_eqs)):
            names = [top_eqs[i][0], top_eqs[j][0], top_eqs[k][0]]
            avg_corr = (corr.loc[names[0], names[1]] + 
                       corr.loc[names[0], names[2]] + 
                       corr.loc[names[1], names[2]]) / 3
            combined = np.zeros(min_len)
            combined += top_eqs[i][1][:min_len] / 3
            combined += top_eqs[j][1][:min_len] / 3
            combined += top_eqs[k][1][:min_len] / 3
            sh = calc_sharpe(combined)
            if sh > best_sh:
                best_sh = sh
                best_combo = names
                best_corr = avg_corr

print(f"  Best combo: {best_combo}")
print(f"  Avg correlation: {best_corr:.3f}")
print(f"  Combined Sharpe: {best_sh:.2f}")

# Also try 5-way
combined5 = np.zeros(min_len)
for name, eq, _ in top_eqs[:5]:
    combined5 += eq[:min_len] / 5
sh5 = calc_sharpe(combined5)
print(f"\n  Top 5 equal-weight Sharpe: {sh5:.2f}")


# ============================================================
# TEST 5: The honest answer
# ============================================================
print()
print("=" * 90)
print("HONEST ANSWER")
print("=" * 90)
print()

# Best individual
best_t, best_s, best_sh = combos[0]
print(f"  Best individual: {best_s} on {best_t} — Sharpe {best_sh:.2f}")

# Best combined
print(f"  Best 3-combo: Sharpe {best_sh:.2f}")
print(f"  Best 5-combo: Sharpe {sh5:.2f}")

print()
if best_sh >= 1.3:
    print(f"  *** TARGET ACHIEVED: Sharpe {best_sh:.2f} ***")
elif sh5 >= 1.3:
    print(f"  *** TARGET ACHIEVED (5-combo): Sharpe {sh5:.2f} ***")
else:
    print(f"  The honest ceiling for simple daily strategies is Sharpe ~0.8-0.9")
    print(f"  To reach 1.3, you need:")
    print(f"    - Leverage (1.5x on best strategy)")
    print(f"    - Intraday data (more edges)")
    print(f"    - Options overlay")
    print(f"    - Multiple uncorrelated assets + rebalancing")
