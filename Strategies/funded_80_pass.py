"""
FUNDED ACCOUNT — 80% PASS RATE SEARCH (FAST)
=============================================
Optimized brute-force: fewer combos, smarter search.
"""

import yfinance as yf
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

print("Downloading data...")
raw = {}
for t, n in [('QQQ','QQQ'),('SPY','SPY'),('IWM','IWM'),('DIA','DIA'),
             ('GC=F','GLD'),('SLV','SLV'),('USO','USO'),
             ('EURUSD=X','EURUSD'),('GBPUSD=X','GBPUSD'),('USDJPY=X','USDJPY'),
             ('AUDUSD=X','AUDUSD'),('BTC-USD','BTC'),('ETH-USD','ETH'),('CL=F','CRUDE')]:
    try:
        d = yf.download(t, start='2016-01-01', end='2025-12-31', progress=False)
        if hasattr(d.columns, 'get_level_values'): d.columns = d.columns.get_level_values(0)
        if len(d) > 500:
            df = d[['Open','High','Low','Close']].copy()
            df['Ret'] = df['Close'].pct_change()
            df['Range'] = df['High'] - df['Low']
            df['IBS'] = np.where(df['Range']>0,(df['Close']-df['Low'])/df['Range'],0.5)
            df['SMA50'] = df['Close'].rolling(50).mean()
            df['SMA200'] = df['Close'].rolling(200).mean()
            df['Z20'] = (df['Close']-df['Close'].rolling(20).mean())/df['Close'].rolling(20).std()
            df['ConsecDn'] = (df['Ret']<0).astype(int).rolling(5).sum()
            df['VolRatio'] = df['Ret'].rolling(5).std() / df['Ret'].rolling(20).std()
            df['Ret20'] = df['Close']/df['Close'].shift(20)-1
            raw[n] = df
            print(f"  {n}: {len(df)} bars")
    except: pass
print(f"Loaded {len(raw)} instruments\n")

INITIAL = 100000

# ============================================================
# FAST PROP FIRM SIM (vectorized where possible)
# ============================================================
def run_fast(signals, closes, opens, regime, hold=5, risk=0.02, sizing='dynamic'):
    """Fast scalar sim. Returns (passed, dd, ret, trades)."""
    cap = INITIAL; max_cap = INITIAL; n_trades = 0
    pos = 0; entry = 0; days_held = 0; day_count = 0
    current_day = None; daily_start = INITIAL
    
    c = closes.values; o = opens.values; s = signals.values
    r = regime.values if regime is not None else np.ones(len(c))
    
    for i in range(1, len(c)):
        if np.isnan(s[i]): s[i] = 0
        if np.isnan(r[i]): r[i] = 0
        
        try:
            day = closes.index[i].date()
        except:
            day = i
        if day != current_day:
            daily_start = cap; current_day = day; day_count += 1
        
        # Daily loss limit
        if pos > 0 and (daily_start - cap) / daily_start >= 0.05:
            pnl = (c[i] - entry) * pos; cap += pnl - abs(pnl)*0.0002
            pos = 0; n_trades += 1
        
        # Max DD
        max_cap = max(max_cap, cap)
        dd = (max_cap - cap) / max_cap if max_cap > 0 else 0
        if dd >= 0.10:
            return False, dd, (cap-INITIAL)/INITIAL, n_trades
        
        # Target
        if (cap - INITIAL) / INITIAL >= 0.10:
            return True, dd, (cap-INITIAL)/INITIAL, n_trades
        
        # Time limit
        if day_count >= 30:
            return False, dd, (cap-INITIAL)/INITIAL, n_trades
        
        # Exit
        if pos > 0:
            days_held += 1
            if c[i] <= entry*0.98 or days_held >= hold or s[i] == 0:
                pnl = (c[i] - entry) * pos; cap += pnl - abs(pnl)*0.0002
                pos = 0; n_trades += 1; days_held = 0
        
        # Entry
        if pos == 0 and s[i] > 0 and r[i] >= 0 and day_count < 28:
            ar = risk
            if sizing == 'dynamic':
                if dd > 0.06: ar = risk*0.5
                elif dd > 0.03: ar = risk*0.75
            elif sizing == 'aggressive':
                if day_count <= 10: ar = risk*1.5
                elif day_count <= 20: ar = risk*1.0
                else: ar = risk*0.75
            
            shares = int(cap*ar / (o[i]*0.02)) if o[i]>0 else 0
            shares = min(shares, int(cap*0.25/o[i]))
            if shares > 0:
                entry = o[i]; pos = shares; days_held = 0
    
    if pos > 0: cap += (c[-1]-entry)*pos - abs((c[-1]-entry)*pos)*0.0002
    return False, (max_cap-cap)/max_cap if max_cap>0 else 0, (cap-INITIAL)/INITIAL, n_trades

# ============================================================
# STRATEGIES
# ============================================================
def make_signals(df, strat):
    if strat == 'IBS_MR':
        return (df['IBS'].shift(1) < 0.20).astype(int), 5
    elif strat == 'IBS_MR_Trend':
        return ((df['IBS'].shift(1) < 0.20) & (df['Close'].shift(1) > df['SMA200'].shift(1))).astype(int), 5
    elif strat == 'IBS_MR_Vol':
        return ((df['IBS'].shift(1) < 0.20) & (df['VolRatio'].shift(1) < 1.5)).astype(int), 5
    elif strat == 'Z_MR':
        return (df['Z20'].shift(1) < -2.0).astype(int), 5
    elif strat == 'Rev3':
        return (df['ConsecDn'].shift(1) >= 3).astype(int), 5
    elif strat == 'Rev5':
        return (df['ConsecDn'].shift(1) >= 5).astype(int), 5
    elif strat == 'IBS_Aggressive':
        return (df['IBS'].shift(1) < 0.30).astype(int), 3
    elif strat == 'IBS_Deep':
        return (df['IBS'].shift(1) < 0.15).astype(int), 5
    elif strat == 'MultiEdge':
        return ((df['IBS'].shift(1)<0.20)|(df['Z20'].shift(1)<-1.5)|(df['ConsecDn'].shift(1)>=3)).astype(int), 5
    return pd.Series(0, index=df.index), 5

def make_regime(df, method):
    if method == 'none': return pd.Series(1, index=df.index)
    r = pd.Series(0, index=df.index)
    r[df['Ret20'] > 0.05] = 1; r[df['Ret20'] < -0.05] = -1
    if method == 'markov':
        for i in range(21, len(df)):
            if r.iloc[i-1]==1 and df['Ret20'].iloc[i]>0: r.iloc[i]=1
            elif r.iloc[i-1]==-1 and df['Ret20'].iloc[i]<0: r.iloc[i]=-1
    return r

# ============================================================
# SEARCH
# ============================================================
print("=" * 90)
print("SEARCHING FOR 80%+ PASS RATE...")
print("=" * 90)

inst_list = list(raw.keys())
strats = ['IBS_MR','IBS_MR_Trend','IBS_MR_Vol','Z_MR','Rev3','Rev5',
          'IBS_Aggressive','IBS_Deep','MultiEdge']
risks = [0.01, 0.02, 0.03, 0.05, 0.08, 0.10]
sizings = ['fixed', 'dynamic', 'aggressive']
regimes = ['none', 'basic', 'markov']

# Test single instruments first
results = []
tests = 0

for inst in inst_list:
    df = raw[inst]
    for strat in strats:
        sig, hold = make_signals(df, strat)
        for regime_m in regimes:
            reg = make_regime(df, regime_m)
            for risk in risks:
                for sizing in sizings:
                    # Run 25 non-overlapping windows
                    pass_ct = 0; total = 0; rets = []; dds = []
                    for w in range(0, 750, 30):
                        if w+30 > len(df): break
                        ws = sig.iloc[w:w+30]; wc = df['Close'].iloc[w:w+30]
                        wo = df['Open'].iloc[w:w+30]; wr = reg.iloc[w:w+30]
                        passed, dd, ret, nt = run_fast(ws, wc, wo, wr, hold, risk, sizing)
                        total += 1
                        if passed: pass_ct += 1
                        rets.append(ret); dds.append(dd)
                    tests += 1
                    if total >= 15:
                        pr = pass_ct/total*100
                        results.append((pr, inst, strat, risk, sizing, regime_m, np.mean(rets)*100, np.mean(dds)*100, total, pass_ct))

# Test 2-instrument baskets (top combos only)
print("Testing 2-instrument baskets...")
for i, inst1 in enumerate(inst_list):
    for inst2 in inst_list[i+1:]:
        for strat in ['IBS_MR','IBS_MR_Trend','MultiEdge']:
            for risk in [0.02, 0.03, 0.05]:
                for sizing in ['dynamic', 'aggressive']:
                    for regime_m in ['basic', 'markov']:
                        pass_ct = 0; total = 0; rets = []; dds = []
                        for w in range(0, 750, 30):
                            if w+30 > len(raw[inst1]): break
                            # Combine signals from both instruments
                            for inst in [inst1, inst2]:
                                df = raw[inst]
                                sig, hold = make_signals(df, strat)
                                reg = make_regime(df, regime_m)
                                ws = sig.iloc[w:w+30]; wc = df['Close'].iloc[w:w+30]
                                wo = df['Open'].iloc[w:w+30]; wr = reg.iloc[w:w+30]
                                passed, dd, ret, nt = run_fast(ws, wc, wo, wr, hold, risk/2, sizing)
                                total += 1
                                if passed: pass_ct += 1
                                rets.append(ret); dds.append(dd)
                        tests += 1
                        if total >= 20:
                            pr = pass_ct/total*100
                            results.append((pr, f"{inst1}+{inst2}", strat, risk, sizing, regime_m, np.mean(rets)*100, np.mean(dds)*100, total, pass_ct))

results.sort(key=lambda x: x[0], reverse=True)

print(f"\nCompleted {tests} tests\n")
print(f"{'#':>3} {'Inst':<25} {'Strat':<16} {'Risk':>5} {'Size':<10} {'Regime':<8} {'Pass%':>6} {'AvgRet':>7} {'AvgDD':>7}")
print("-" * 95)
for i, (pr, inst, strat, risk, sizing, regime, avgret, avgdd, total, passed) in enumerate(results[:40]):
    m = " ***" if pr >= 80 else (" **" if pr >= 70 else "")
    print(f"{i+1:>3} {inst:<25} {strat:<16} {risk:>5.0%} {sizing:<10} {regime:<8} {pr:>5.0f}% {avgret:>6.1f}% {avgdd:>6.1f}%{m}")

# Findings
eighty = [r for r in results if r[0] >= 80]
seventy = [r for r in results if r[0] >= 70]
print(f"\n{'='*90}")
print(f"RESULTS: {len(eighty)} strategies with 80%+ pass rate, {len(seventy)} with 70%+")
print(f"{'='*90}")

if eighty:
    print("\n80%+ PASS RATE STRATEGIES:")
    for pr, inst, strat, risk, sizing, regime, avgret, avgdd, total, passed in eighty[:15]:
        print(f"  {pr:.0f}% — {strat} on {inst} (risk={risk:.0%}, {sizing}, {regime})")
elif seventy:
    print("\n70%+ PASS RATE (closest to 80%):")
    for pr, inst, strat, risk, sizing, regime, avgret, avgdd, total, passed in seventy[:15]:
        print(f"  {pr:.0f}% — {strat} on {inst} (risk={risk:.0%}, {sizing}, {regime})")
else:
    print("\nTop 10 by pass rate:")
    for pr, inst, strat, risk, sizing, regime, avgret, avgdd, total, passed in results[:10]:
        print(f"  {pr:.0f}% — {strat} on {inst} (risk={risk:.0%}, {sizing}, {regime})")
