"""
BRUTE FORCE 3 — Cross-asset strategy combo
============================================
Combine the BEST strategies across DIFFERENT instruments
to maximize diversification benefit.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from itertools import combinations
import warnings
warnings.filterwarnings('ignore')

# Download
tickers = ['QQQ', 'SPY', 'IWM', 'XLK', 'GLD', 'TLT', 'VXX', 'XLF', 'XLV', 'XLI', 'XLC', 'XLU', 'XLE', 'XLRE']
raw = {}
for t in tickers:
    try:
        d = yf.download(t, start='2010-01-01', end='2025-12-31', progress=False)
        if hasattr(d.columns, 'get_level_values'):
            d.columns = d.columns.get_level_values(0)
        if len(d) > 2000:
            df = d[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
            df['Ret'] = df['Close'].pct_change()
            df['Range'] = df['High'] - df['Low']
            df['IBS'] = np.where(df['Range'] > 0, (df['Close'] - df['Low']) / df['Range'], 0.5)
            df['Vol20'] = df['Ret'].rolling(20).std() * np.sqrt(252)
            df['SMA50'] = df['Close'].rolling(50).mean()
            df['SMA200'] = df['Close'].rolling(200).mean()
            df['Mom20'] = df['Close'] / df['Close'].shift(20) - 1
            df['Mom5'] = df['Close'] / df['Close'].shift(5) - 1
            df['Z20'] = (df['Close'] - df['Close'].rolling(20).mean()) / df['Close'].rolling(20).std()
            df['VolRank20'] = df['Volume'].rolling(20).apply(lambda x: pd.Series(x).rank().iloc[-1] / len(x))
            raw[t] = df
    except:
        pass

print(f"Loaded {len(raw)} instruments: {list(raw.keys())}")
INITIAL = 100000; COST = 0.001

def run(signals, closes, opens=None):
    if opens is None: opens = closes
    cap = INITIAL; pos = 0; entry = 0; eq = []
    for i in range(len(signals)):
        o = float(opens.iloc[i]); c = float(closes.iloc[i])
        sig = int(signals.iloc[i]) if pd.notna(signals.iloc[i]) else 0
        if pos > 0 and sig == 0:
            cap += pos * o - pos * (entry + o) * COST / 2; pos = 0
        elif pos == 0 and sig == 1:
            sh = int(cap / o)
            if sh > 0: cap -= sh * o + sh * o * COST; pos = sh; entry = o
        eq.append(cap + (pos * c if pos > 0 else 0))
    if pos > 0: cap += pos * float(closes.iloc[-1]) - pos * (entry + float(closes.iloc[-1])) * COST / 2
    return np.array(eq)

def metrics(eq):
    dr = np.diff(eq) / eq[:-1]; dr = dr[np.isfinite(dr)]
    s = (np.mean(dr) / np.std(dr)) * np.sqrt(252) if np.std(dr) > 0 else 0
    pk = np.maximum.accumulate(eq)
    dd = -((pk - eq) / pk).max() * 100
    cagr = ((eq[-1] / eq[0]) ** (252 / max(len(eq), 1)) - 1) * 100
    return s, dd, cagr

# ============================================================
# BUILD STRATEGY SIGNALS for each instrument
# ============================================================
strategies = {}

for t, df in raw.items():
    # IBS MR
    for thr in [0.15, 0.20, 0.25, 0.30]:
        sig = (df['IBS'].shift(1) < thr).astype(int)
        eq = run(sig, df['Close'])
        s, d, c = metrics(eq)
        strategies[f'{t}_IBS{thr}'] = (eq, s, d, c)
    
    # SMA cross
    if len(df) > 200:
        for fast, slow in [(10, 50), (20, 50), (50, 200)]:
            if fast in df.columns and slow in df.columns:
                pass
            sma_f = df['Close'].rolling(fast).mean()
            sma_s = df['Close'].rolling(slow).mean()
            sig = (sma_f.shift(1) > sma_s.shift(1)).astype(int)
            eq = run(sig, df['Close'])
            s, d, c = metrics(eq)
            strategies[f'{t}_SMA{fast}/{slow}'] = (eq, s, d, c)
    
    # Momentum
    for lb in [5, 10, 20]:
        sig = (df['Mom' + str(lb)].shift(1) > 0.01).astype(int) if f'Mom{lb}' in df.columns else None
        if sig is not None:
            eq = run(sig, df['Close'])
            s, d, c = metrics(eq)
            strategies[f'{t}_Mom{lb}'] = (eq, s, d, c)
    
    # Mean reversion bands
    sig = (df['Z20'].shift(1) < -1.5).astype(int)
    eq = run(sig, df['Close'])
    s, d, c = metrics(eq)
    strategies[f'{t}_MR_Z20'] = (eq, s, d, c)
    
    # Trend + IBS combo
    sig = ((df['Close'] > df['SMA50']).shift(1) & (df['IBS'].shift(1) < 0.25)).astype(int)
    eq = run(sig, df['Close'])
    s, d, c = metrics(eq)
    strategies[f'{t}_Trend50_IBS'] = (eq, s, d, c)
    
    if len(df) > 200:
        sig = ((df['Close'] > df['SMA200']).shift(1) & (df['IBS'].shift(1) < 0.25)).astype(int)
        eq = run(sig, df['Close'])
        s, d, c = metrics(eq)
        strategies[f'{t}_Trend200_IBS'] = (eq, s, d, c)

print(f"\nBuilt {len(strategies)} strategies")

# ============================================================
# TOP STRATEGIES by Sharpe
# ============================================================
strat_list = [(name, eq, s, d, c) for name, (eq, s, d, c) in strategies.items()]
strat_list.sort(key=lambda x: x[2], reverse=True)

print(f"\nTop 20 strategies:")
print(f"  {'#':>3} {'Name':<25} {'Sharpe':>7} {'DD%':>7}")
for i, (name, eq, s, d, c) in enumerate(strat_list[:20]):
    print(f"  {i+1:>3} {name:<25} {s:>7.2f} {d:>7.1f}%")

# ============================================================
# FIND BEST COMBOS (2 to 6 strategies)
# ============================================================
print()
print("=" * 70)
print("SEARCHING FOR BEST COMBOS...")
print("=" * 70)

# Precompute return series for correlation
returns = {}
for name, eq, s, d, c in strat_list[:30]:
    dr = np.diff(eq) / eq[:-1]
    returns[name] = dr

best_overall = []

# For speed, only test combos of top 30 strategies
top_names = [name for name, eq, s, d, c in strat_list[:30]]
top_eqs = {name: eq for name, eq, s, d, c in strat_list[:30]}

# Test 2-way combos
print("\n2-way combos:")
for i in range(len(top_names)):
    for j in range(i+1, len(top_names)):
        n1, n2 = top_names[i], top_names[j]
        # Skip if same instrument
        inst1 = n1.split('_')[0]; inst2 = n2.split('_')[0]
        if inst1 == inst2:
            continue
        eq1 = top_eqs[n1]; eq2 = top_eqs[n2]
        ml = min(len(eq1), len(eq2))
        combo = (eq1[:ml] + eq2[:ml]) / 2
        s, d, c = metrics(combo)
        best_overall.append((f'{n1}+{n2}', s, d, c))

best_2way = sorted(best_overall, key=lambda x: x[1], reverse=True)
for name, s, d, c in best_2way[:5]:
    print(f"  {name:<50} Sharpe {s:.2f}  DD {d:.1f}%")

# Test 3-way combos (top 20 instruments)
print("\n3-way combos (cross-instrument only):")
top30_names = top_names[:20]
best_3way = []
for combo in combinations(range(len(top30_names)), 3):
    names = [top30_names[i] for i in combo]
    instruments = set(n.split('_')[0] for n in names)
    if len(instruments) < 3:  # Need 3 different instruments
        continue
    ml = min(len(top_eqs[n]) for n in names)
    combo_eq = sum(top_eqs[n][:ml] for n in names) / 3
    s, d, c = metrics(combo_eq)
    best_3way.append(('+'.join(names), s, d, c))

best_3way.sort(key=lambda x: x[1], reverse=True)
for name, s, d, c in best_3way[:10]:
    print(f"  {name:<60} Sharpe {s:.2f}  DD {d:.1f}%")

# Test 4-way combos (top 15)
print("\n4-way combos:")
top15_names = top_names[:15]
best_4way = []
for combo in combinations(range(len(top15_names)), 4):
    names = [top15_names[i] for i in combo]
    instruments = set(n.split('_')[0] for n in names)
    if len(instruments) < 3:
        continue
    ml = min(len(top_eqs[n]) for n in names)
    combo_eq = sum(top_eqs[n][:ml] for n in names) / len(names)
    s, d, c = metrics(combo_eq)
    best_4way.append(('+'.join(names), s, d, c))

best_4way.sort(key=lambda x: x[1], reverse=True)
for name, s, d, c in best_4way[:5]:
    print(f"  {name[:80]}")
    print(f"    Sharpe {s:.2f}  DD {d:.1f}%")

# Test 5-way combos (top 12)
print("\n5-way combos:")
top12_names = top_names[:12]
best_5way = []
for combo in combinations(range(len(top12_names)), 5):
    names = [top12_names[i] for i in combo]
    instruments = set(n.split('_')[0] for n in names)
    if len(instruments) < 4:
        continue
    ml = min(len(top_eqs[n]) for n in names)
    combo_eq = sum(top_eqs[n][:ml] for n in names) / len(names)
    s, d, c = metrics(combo_eq)
    best_5way.append(('+'.join(names), s, d, c))

best_5way.sort(key=lambda x: x[1], reverse=True)
for name, s, d, c in best_5way[:5]:
    print(f"  {name[:80]}")
    print(f"    Sharpe {s:.2f}  DD {d:.1f}%")

# Test 6-way combos (top 10)
print("\n6-way combos:")
top10_names = top_names[:10]
best_6way = []
for combo in combinations(range(len(top10_names)), 6):
    names = [top10_names[i] for i in combo]
    instruments = set(n.split('_')[0] for n in names)
    if len(instruments) < 4:
        continue
    ml = min(len(top_eqs[n]) for n in names)
    combo_eq = sum(top_eqs[n][:ml] for n in names) / len(names)
    s, d, c = metrics(combo_eq)
    best_6way.append(('+'.join(names), s, d, c))

best_6way.sort(key=lambda x: x[1], reverse=True)
for name, s, d, c in best_6way[:5]:
    print(f"  {name[:80]}")
    print(f"    Sharpe {s:.2f}  DD {d:.1f}%")

# ============================================================
# FINAL ANSWER
# ============================================================
print()
print("=" * 70)
print("ABSOLUTE BEST ACROSS ALL COMBOS")
print("=" * 70)

all_combos = best_2way + best_3way + best_4way + best_5way + best_6way
all_combos.sort(key=lambda x: x[1], reverse=True)

hits = sum(1 for _, s, _, _ in all_combos if s >= 1.3)
print(f"\nStrategies hitting Sharpe >= 1.3: {hits}/{len(all_combos)}")
print()
for name, s, d, c in all_combos[:10]:
    marker = " ***" if s >= 1.3 else ""
    print(f"  {name[:70]}")
    print(f"    Sharpe {s:.2f}  DD {d:.1f}%  CAGR {c:.1f}%{marker}")
