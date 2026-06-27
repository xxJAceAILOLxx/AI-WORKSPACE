"""
FUNDED ACCOUNT EDGE v2
=======================
Prop firm rules: 10% target, 10% DD max, 5% daily loss
Key: position sizing must be aggressive enough to HIT target
but conservative enough to SURVIVE drawdowns.
"""

import yfinance as yf
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

print("Downloading data...")
instruments = {
    'EURUSD=X': 'EURUSD', 'GBPUSD=X': 'GBPUSD', 'USDJPY=X': 'USDJPY',
    'AUDUSD=X': 'AUDUSD', 'USDCAD=X': 'USDCAD', 'USDCHF=X': 'USDCHF',
    'NZDUSD=X': 'NZDUSD', 'GC=F': 'GOLD', 'SI=F': 'SILVER',
    'CL=F': 'CRUDE', 'BTC-USD': 'BTC', 'ETH-USD': 'ETH',
    'QQQ': 'QQQ', 'SPY': 'SPY', 'IWM': 'IWM', 'DIA': 'DIA',
}

raw = {}
for ticker, name in instruments.items():
    try:
        d = yf.download(ticker, start='2010-01-01', end='2025-12-31', progress=False)
        if hasattr(d.columns, 'get_level_values'):
            d.columns = d.columns.get_level_values(0)
        if len(d) > 500:
            df = d[['Open', 'High', 'Low', 'Close']].copy()
            df['Ret'] = df['Close'].pct_change()
            df['Range'] = df['High'] - df['Low']
            df['IBS'] = np.where(df['Range'] > 0, (df['Close'] - df['Low']) / df['Range'], 0.5)
            df['Vol20'] = df['Ret'].rolling(20).std() * np.sqrt(252)
            df['SMA20'] = df['Close'].rolling(20).mean()
            df['SMA50'] = df['Close'].rolling(50).mean()
            df['Z20'] = (df['Close'] - df['SMA20']) / df['Close'].rolling(20).std()
            df['Mom5'] = df['Close'] / df['Close'].shift(5) - 1
            df['Mom20'] = df['Close'] / df['Close'].shift(20) - 1
            df['Ret1'] = df['Close'].pct_change(1)
            df['Ret5'] = df['Close'].pct_change(5)
            df['ConsecDn'] = (df['Ret'] < 0).astype(int).rolling(5).sum()
            df['Gap'] = df['Open'] / df['Close'].shift(1) - 1
            raw[name] = df
            print(f"  {name}: {len(df)} bars")
    except:
        pass

print(f"Loaded {len(raw)} instruments\n")

INITIAL = 100000

def run_prop(signals, closes, opens, risk_per_trade=0.02, reward_risk=2.0, max_pos_pct=0.25):
    """
    Prop firm simulation with FIXED fractional risk.
    risk_per_trade: % of equity risked per trade
    reward_risk: target reward/risk ratio
    max_pos_pct: max position as % of equity
    """
    cap = INITIAL; eq = []; n_trades = 0; wins = 0
    max_cap = INITIAL; current_day = None; daily_pnl = 0
    
    for i in range(1, len(signals)):
        o = float(opens.iloc[i]); c = float(closes.iloc[i])
        sig = int(signals.iloc[i]) if pd.notna(signals.iloc[i]) else 0
        
        try:
            day = closes.index[i].date()
        except:
            day = i // 20
        if day != current_day:
            daily_pnl = 0
            current_day = day
        
        # Daily loss limit (5%)
        if daily_pnl < -cap * 0.05:
            eq.append(cap)
            continue
        
        # Max drawdown (10%)
        max_cap = max(max_cap, cap)
        if (max_cap - cap) / max_cap >= 0.10:
            eq.append(cap)
            continue
        
        # Simple: hold direction for 1-5 days based on signal
        if sig != 0:
            risk_amount = cap * risk_per_trade
            price = o
            if price > 0:
                # Position size based on risk
                stop_distance = price * 0.01  # 1% stop
                shares = int(risk_amount / stop_distance) if stop_distance > 0 else 0
                max_shares = int(cap * max_pos_pct / price)
                shares = min(shares, max_shares)
                
                if shares > 0:
                    pnl = sig * shares * (c - o)
                    cost = abs(shares * o) * 0.0002  # spread
                    cap += pnl - cost
                    daily_pnl += pnl
                    n_trades += 1
                    if pnl > 0: wins += 1
        
        eq.append(cap)
    
    eq = np.array(eq)
    wr = wins / n_trades * 100 if n_trades > 0 else 0
    
    # Calculate metrics
    dr = np.diff(eq) / eq[:-1]; dr = dr[np.isfinite(dr)]
    s = (np.mean(dr) / np.std(dr)) * np.sqrt(252) if np.std(dr) > 0 else 0
    pk = np.maximum.accumulate(eq)
    dd = -((pk - eq) / pk).max() * 100
    cagr = ((eq[-1] / eq[0]) ** (252 / max(len(eq), 1)) - 1) * 100
    
    return eq, s, dd, cagr, n_trades, wr

def run_multi_inst(strat_fn, instruments, risk_per_trade=0.01):
    """Run strategy across multiple instruments, allocate risk equally"""
    n_inst = len(instruments)
    inst_risk = risk_per_trade / n_inst
    
    all_eqs = {}
    for inst in instruments:
        if inst not in raw: continue
        df = raw[inst]
        sig = strat_fn(df)
        if sig is not None:
            eq, s, dd, cagr, nt, wr = run_prop(sig, df['Close'], df['Open'], risk_per_trade=inst_risk)
            all_eqs[inst] = (eq, s, dd, cagr, nt, wr)
    
    return all_eqs

# ============================================================
# STRATEGIES
# ============================================================
strategies = {}

# 1. IBS Mean Reversion
for thr in [0.15, 0.20, 0.25, 0.30]:
    def make_ibs(thr):
        def strat(df):
            sig = pd.Series(0, index=df.index)
            sig[df['IBS'].shift(1) < thr] = 1
            sig[df['IBS'].shift(1) > (1-thr)] = -1
            return sig
        return strat
    strategies[f'IBS{thr}_LS'] = make_ibs(thr)

# 2. Z-score Mean Reversion
for z in [1.5, 2.0, 2.5]:
    def make_z(z):
        def strat(df):
            sig = pd.Series(0, index=df.index)
            sig[df['Z20'].shift(1) < -z] = 1
            sig[df['Z20'].shift(1) > z] = -1
            return sig
        return strat
    strategies[f'Z{z}'] = make_z(z)

# 3. Trend + IBS
def trend_ibs(df):
    sig = pd.Series(0, index=df.index)
    sig[(df['Close'].shift(1) > df['SMA50'].shift(1)) & (df['IBS'].shift(1) < 0.25)] = 1
    sig[(df['Close'].shift(1) < df['SMA50'].shift(1)) & (df['IBS'].shift(1) > 0.75)] = -1
    return sig
strategies['TrendIBS'] = trend_ibs

# 4. Consecutive Reversal
for n in [3, 4, 5]:
    def make_rev(n):
        def strat(df):
            sig = pd.Series(0, index=df.index)
            dn = (df['Ret'] < 0).astype(int).rolling(n).sum()
            up = (df['Ret'] > 0).astype(int).rolling(n).sum()
            sig[dn.shift(1) >= n] = 1
            sig[up.shift(1) >= n] = -1
            return sig
        return strat
    strategies[f'Rev{n}'] = make_rev(n)

# 5. Gap Reversal
def gap_rev(df):
    sig = pd.Series(0, index=df.index)
    sig[df['Gap'].shift(1) < -0.005] = 1
    sig[df['Gap'].shift(1) > 0.005] = -1
    return sig
strategies['Gap'] = gap_rev

# 6. Multi-day momentum
for lb in [5, 10, 20]:
    def make_mom(lb):
        def strat(df):
            mom = df['Close'] / df['Close'].shift(lb) - 1
            sig = pd.Series(0, index=df.index)
            sig[mom.shift(1) > 0.02] = 1
            sig[mom.shift(1) < -0.02] = -1
            return sig
        return strat
    strategies[f'Mom{lb}'] = make_mom(lb)

# ============================================================
# TEST ALL STRATEGIES × INSTRUMENTS
# ============================================================
print("=" * 80)
print("RESULTS: All Strategy × Instrument combinations")
print("=" * 80)

all_results = []
inst_list = list(raw.keys())

for strat_name, strat_fn in strategies.items():
    for inst in inst_list:
        df = raw[inst]
        sig = strat_fn(df)
        if sig is None: continue
        
        for risk in [0.01, 0.02, 0.03]:
            eq, s, dd, cagr, nt, wr = run_prop(sig, df['Close'], df['Open'], risk_per_trade=risk)
            
            # Prop firm pass simulation
            window = 30
            passing = 0; total = 0
            for w in range(0, len(eq) - window, window):
                weq = eq[w:w+window]
                if len(weq) < 10: continue
                ret = (weq[-1] / weq[0] - 1) * 100
                pk = np.maximum.accumulate(weq)
                wdd = -((pk - weq) / pk).max() * 100
                total += 1
                if ret >= 10 and wdd > -10:
                    passing += 1
            
            pass_rate = passing / total * 100 if total > 0 else 0
            
            if nt > 30:
                all_results.append((f'{inst}_{strat_name}_r{risk:.0%}', s, dd, cagr, nt, wr, pass_rate, inst, strat_name, risk))

all_results.sort(key=lambda x: x[6], reverse=True)  # Sort by pass rate

print(f"\n  {'#':>3} {'Strategy':<35} {'Sharpe':>7} {'DD%':>7} {'CAGR%':>7} {'Trd':>5} {'WR%':>5} {'Pass%':>6}")
print(f"  {'-'*82}")
for i, (name, s, dd, cagr, nt, wr, pr, inst, strat, risk) in enumerate(all_results[:40]):
    marker = " ***" if pr > 50 else ""
    print(f"  {i+1:>3} {name:<35} {s:>7.2f} {dd:>7.1f} {cagr:>7.1f} {nt:>5} {wr:>5.1f} {pr:>5.0f}%{marker}")

# ============================================================
# TOP STRATEGIES: MULTI-INSTRUMENT BASKET
# ============================================================
print()
print("=" * 80)
print("MULTI-INSTRUMENT BASKETS (Top strategies)")
print("=" * 80)

# Find best strategy per type
best_strats = {}
for name, s, dd, cagr, nt, wr, pr, inst, strat, risk in all_results:
    key = f'{strat}_r{risk:.0%}'
    if key not in best_strats or pr > best_strats[key][6]:
        best_strats[key] = (name, s, dd, cagr, nt, wr, pr, inst, strat, risk)

# Test baskets
top_strats = sorted(best_strats.values(), key=lambda x: x[6], reverse=True)[:5]

for _, _, _, _, _, _, _, _, strat_name, risk in top_strats:
    strat_fn = strategies[strat_name]
    
    # Pick top 6 instruments for this strategy
    inst_scores = []
    for inst in inst_list:
        df = raw[inst]
        sig = strat_fn(df)
        if sig is not None:
            _, s, dd, _, nt, _ = run_prop(sig, df['Close'], df['Open'], risk_per_trade=risk)
            if nt > 30:
                inst_scores.append((inst, s, dd))
    
    inst_scores.sort(key=lambda x: x[1], reverse=True)
    top_insts = [i for i, _, _ in inst_scores[:6]]
    
    if len(top_insts) < 3: continue
    
    # Run basket
    basket_eq = np.ones(len(list(raw.values())[0])) * INITIAL
    for inst in top_insts:
        df = raw[inst]
        sig = strat_fn(df)
        eq, s, dd, cagr, nt, wr = run_prop(sig, df['Close'], df['Open'], risk_per_trade=risk/len(top_insts))
        ml = min(len(basket_eq), len(eq))
        basket_eq[:ml] += (eq[:ml] - INITIAL)
    
    dr = np.diff(basket_eq) / basket_eq[:-1]; dr = dr[np.isfinite(dr)]
    s = (np.mean(dr) / np.std(dr)) * np.sqrt(252) if np.std(dr) > 0 else 0
    pk = np.maximum.accumulate(basket_eq)
    dd = -((pk - basket_eq) / pk).max() * 100
    cagr = ((basket_eq[-1] / basket_eq[0]) ** (252 / max(len(basket_eq), 1)) - 1) * 100
    
    # Pass rate
    window = 30; passing = 0; total = 0
    for w in range(0, len(basket_eq) - window, window):
        weq = basket_eq[w:w+window]
        if len(weq) < 10: continue
        ret = (weq[-1] / weq[0] - 1) * 100
        pk2 = np.maximum.accumulate(weq)
        wdd = -((pk2 - weq) / pk2).max() * 100
        total += 1
        if ret >= 10 and wdd > -10:
            passing += 1
    
    pr = passing / total * 100 if total > 0 else 0
    print(f"\n  {strat_name} Basket ({', '.join(top_insts[:4])}...) risk={risk:.0%}")
    print(f"  Sharpe {s:.2f}  DD {dd:.1f}%  CAGR {cagr:.1f}%  Pass {passing}/{total} ({pr:.0f}%)")

# ============================================================
# THE EDGE: What actually passes prop firms?
# ============================================================
print()
print("=" * 80)
print("THE EDGE: Strategies with >30% pass rate")
print("=" * 80)

good = [r for r in all_results if r[6] > 30]
if good:
    for name, s, dd, cagr, nt, wr, pr, inst, strat, risk in good[:10]:
        print(f"  {name:<35} Pass {pr:.0f}%  Sharpe {s:.2f}  DD {dd:.1f}%  CAGR {cagr:.1f}%")
else:
    print("  No strategies found with >30% pass rate")
    print("\n  Top 5 by pass rate:")
    for name, s, dd, cagr, nt, wr, pr, inst, strat, risk in all_results[:5]:
        print(f"  {name:<35} Pass {pr:.0f}%  Sharpe {s:.2f}  DD {dd:.1f}%  CAGR {cagr:.1f}%")
