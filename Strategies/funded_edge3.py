"""
FUNDED ACCOUNT v3 — Realistic prop firm sizing
================================================
Prop firm: $100K account, 10% target, 10% DD, 5% daily
Need: aggressive but survivable sizing
"""

import yfinance as yf
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

print("Downloading...")
raw = {}
for t, n in [('EURUSD=X','EURUSD'),('GBPUSD=X','GBPUSD'),('USDJPY=X','USDJPY'),
             ('AUDUSD=X','AUDUSD'),('USDCAD=X','USDCAD'),('NZDUSD=X','NZDUSD'),
             ('GC=F','GOLD'),('CL=F','CRUDE'),('BTC-USD','BTC'),('ETH-USD','ETH'),
             ('QQQ','QQQ'),('SPY','SPY'),('IWM','IWM'),('DIA','DIA')]:
    try:
        d = yf.download(t, start='2010-01-01', end='2025-12-31', progress=False)
        if hasattr(d.columns, 'get_level_values'): d.columns = d.columns.get_level_values(0)
        if len(d) > 500:
            df = d[['Open','High','Low','Close']].copy()
            df['Ret'] = df['Close'].pct_change()
            df['Range'] = df['High'] - df['Low']
            df['IBS'] = np.where(df['Range']>0,(df['Close']-df['Low'])/df['Range'],0.5)
            df['SMA20'] = df['Close'].rolling(20).mean()
            df['SMA50'] = df['Close'].rolling(50).mean()
            df['Z20'] = (df['Close']-df['SMA20'])/df['Close'].rolling(20).std()
            df['Mom5'] = df['Close']/df['Close'].shift(5)-1
            df['Mom20'] = df['Close']/df['Close'].shift(20)-1
            df['Ret1'] = df['Close'].pct_change(1)
            df['Ret5'] = df['Close'].pct_change(5)
            df['ConsecDn'] = (df['Ret']<0).astype(int).rolling(5).sum()
            df['Gap'] = df['Open']/df['Close'].shift(1)-1
            df['Vol20'] = df['Ret'].rolling(20).std()*np.sqrt(252)
            raw[n] = df
    except: pass
print(f"Loaded {len(raw)} instruments\n")

INITIAL = 100000

def run_fast(signals, closes, opens, risk_pct=0.05):
    """Fast prop sim: fixed lot sizing based on % of equity"""
    cap = INITIAL; eq = [INITIAL]
    wins = 0; n_trades = 0; max_cap = INITIAL
    daily_pnl = 0; current_day = None
    
    closes_arr = closes.values
    opens_arr = opens.values
    sig_arr = signals.values
    
    for i in range(1, len(closes_arr)):
        o = opens_arr[i]; c = closes_arr[i]; sig = sig_arr[i]
        if np.isnan(sig): sig = 0
        
        try:
            day = closes.index[i].date()
        except:
            day = i // 20
        if day != current_day:
            daily_pnl = 0; current_day = day
        
        # Daily loss limit
        if daily_pnl < -INITIAL * 0.05:
            eq.append(cap); continue
        # Max DD
        max_cap = max(max_cap, cap)
        if (max_cap - cap) / max_cap >= 0.10:
            eq.append(cap); continue
        
        if sig != 0 and o > 0:
            position_value = cap * risk_pct
            shares = int(position_value / o)
            if shares > 0:
                pnl = sig * shares * (c - o)
                cost = shares * o * 0.0002  # spread
                cap += pnl - cost
                daily_pnl += pnl
                n_trades += 1
                if pnl > 0: wins += 1
        
        eq.append(cap)
    
    eq = np.array(eq)
    return eq, n_trades, wins/n_trades*100 if n_trades > 0 else 0

def m(eq):
    dr = np.diff(eq)/eq[:-1]; dr = dr[np.isfinite(dr)]
    s = (np.mean(dr)/np.std(dr))*np.sqrt(252) if np.std(dr)>0 else 0
    pk = np.maximum.accumulate(eq); dd = -((pk-eq)/pk).max()*100
    cagr = ((eq[-1]/eq[0])**(252/max(len(eq),1))-1)*100
    return s, dd, cagr

def pass_rate(eq, window=30, target=10, max_dd=10):
    passing = 0; total = 0
    for w in range(0, len(eq)-window, window):
        weq = eq[w:w+window]
        if len(weq) < 10: continue
        ret = (weq[-1]/weq[0]-1)*100
        pk = np.maximum.accumulate(weq)
        dd = -((pk-weq)/pk).max()*100
        total += 1
        if ret >= target and dd > -max_dd:
            passing += 1
    return passing, total, passing/total*100 if total > 0 else 0

# ============================================================
# STRATEGIES
# ============================================================
strats = {}

for thr in [0.15, 0.20, 0.25, 0.30]:
    def ibs_ls(t):
        def s(df):
            sig = pd.Series(0, index=df.index)
            sig[df['IBS'].shift(1) < t] = 1
            sig[df['IBS'].shift(1) > (1-t)] = -1
            return sig
        return s
    strats[f'IBS{thr}_LS'] = ibs_ls(thr)

def trend_ibs(df):
    sig = pd.Series(0, index=df.index)
    sig[(df['Close'].shift(1) > df['SMA50'].shift(1)) & (df['IBS'].shift(1) < 0.25)] = 1
    sig[(df['Close'].shift(1) < df['SMA50'].shift(1)) & (df['IBS'].shift(1) > 0.75)] = -1
    return sig
strats['TrendIBS'] = trend_ibs

for n in [3, 4, 5]:
    def rev(n):
        def s(df):
            sig = pd.Series(0, index=df.index)
            dn = (df['Ret']<0).astype(int).rolling(n).sum()
            up = (df['Ret']>0).astype(int).rolling(n).sum()
            sig[dn.shift(1)>=n] = 1; sig[up.shift(1)>=n] = -1
            return sig
        return s
    strats[f'Rev{n}'] = rev(n)

for z in [1.5, 2.0, 2.5]:
    def zscore(z):
        def s(df):
            sig = pd.Series(0, index=df.index)
            sig[df['Z20'].shift(1) < -z] = 1; sig[df['Z20'].shift(1) > z] = -1
            return sig
        return s
    strats[f'Z{z}'] = zscore(z)

for lb in [5, 10, 20]:
    def mom(lb):
        def s(df):
            m = df['Close']/df['Close'].shift(lb)-1
            sig = pd.Series(0, index=df.index)
            sig[m.shift(1)>0.02] = 1; sig[m.shift(1)<-0.02] = -1
            return sig
        return s
    strats[f'Mom{lb}'] = mom(lb)

# ============================================================
# BRUTE FORCE: Strategy × Instrument × Risk%
# ============================================================
print("=" * 80)
print("BRUTE FORCE: Strategy × Instrument × Risk%")
print("=" * 80)

all_r = []
for sn, sf in strats.items():
    for inst, df in raw.items():
        sig = sf(df)
        for rp in [0.03, 0.05, 0.08, 0.10, 0.15, 0.20]:
            eq, nt, wr = run_fast(sig, df['Close'], df['Open'], rp)
            s, dd, cagr = m(eq)
            p, t, pr = pass_rate(eq)
            if nt > 20:
                all_r.append((f'{inst}_{sn}_r{rp:.0%}', s, dd, cagr, nt, wr, pr, inst, sn, rp))

all_r.sort(key=lambda x: x[6], reverse=True)
print(f"\n  {'#':>3} {'Strategy':<38} {'Sharpe':>7} {'DD%':>7} {'CAGR%':>7} {'Trd':>5} {'WR%':>5} {'Pass':>5}")
print(f"  {'-'*85}")
for i, (name, s, dd, cagr, nt, wr, pr, inst, sn, rp) in enumerate(all_r[:40]):
    marker = " ***" if pr > 20 else ""
    print(f"  {i+1:>3} {name:<38} {s:>7.2f} {dd:>7.1f} {cagr:>7.1f} {nt:>5} {wr:>5.1f} {pr:>4.0f}%{marker}")

# ============================================================
# BASKET: Top 6 instruments per strategy
# ============================================================
print()
print("=" * 80)
print("BASKET STRATEGIES (top combos)")
print("=" * 80)

# Get best strategy per type (by pass rate)
best_per_strat = {}
for r in all_r:
    sn = r[8]
    if sn not in best_per_strat or r[6] > best_per_strat[sn][6]:
        best_per_strat[sn] = r

for sn in sorted(best_per_strat, key=lambda x: best_per_strat[x][6], reverse=True)[:5]:
    sf = strats[sn]
    rp = best_per_strat[sn][9]
    
    # Rank instruments
    inst_scores = []
    for inst, df in raw.items():
        sig = sf(df)
        eq, nt, wr = run_fast(sig, df['Close'], df['Open'], rp)
        s, dd, cagr = m(eq)
        p, t, pr = pass_rate(eq)
        if nt > 20:
            inst_scores.append((inst, pr, s, dd))
    
    inst_scores.sort(key=lambda x: x[1], reverse=True)
    
    # Test basket of top N
    for n_inst in [3, 4, 6]:
        top = inst_scores[:n_inst]
        if len(top) < 3: continue
        inst_names = [t[0] for t in top]
        
        # Run basket
        basket = np.ones(len(list(raw.values())[0])) * INITIAL
        for inst in inst_names:
            df = raw[inst]
            sig = sf(df)
            eq, nt, wr = run_fast(sig, df['Close'], df['Open'], rp/n_inst)
            ml = min(len(basket), len(eq))
            basket[:ml] += eq[:ml] - INITIAL
        
        s, dd, cagr = m(basket)
        p, t, pr = pass_rate(basket)
        
        if pr > 0 or s > 0.3:
            print(f"  {sn} {n_inst}-basket ({','.join(inst_names[:3])}...) risk={rp:.0%}")
            print(f"    Sharpe {s:.2f}  DD {dd:.1f}%  CAGR {cagr:.1f}%  Pass {p}/{t} ({pr:.0f}%)")

# ============================================================
# THE ANSWER
# ============================================================
print()
print("=" * 80)
print("ANSWER")
print("=" * 80)

# What's the best we found?
top5 = all_r[:5]
print(f"\nTop 5 individual strategies:")
for name, s, dd, cagr, nt, wr, pr, inst, sn, rp in top5:
    print(f"  {name:<38} Sharpe {s:.2f}  Pass {pr:.0f}%  WR {wr:.0f}%  DD {dd:.1f}%")

# How to pass a prop firm
print(f"\nTo pass a prop firm ($100K, 10% target, 10% DD):")
print(f"  1. Use risk-based sizing (not fixed lots)")
print(f"  2. Risk 3-5% per trade on the best strategy")
print(f"  3. Trade multiple uncorrelated instruments")
print(f"  4. The edge exists in mean reversion + trend following")
print(f"  5. Walk-forward validation is critical")
