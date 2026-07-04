"""
SIMPLE STRATEGIES — HONEST TEST
=================================
Testing classic strategies with next-open execution
"""

import pandas as pd
import numpy as np
import yfinance as yf
import warnings
warnings.filterwarnings('ignore')

INITIAL = 100000
COST = 0.001

tickers = ['QQQ', 'SPY', 'IWM', 'XLK', 'XLF', 'XLE', 'GLD', 'TLT', 'EEM', 'VNQ']
data = {}
for t in tickers:
    d = yf.download(t, start='2010-01-01', end='2025-12-31', progress=False)
    if hasattr(d.columns, 'get_level_values'):
        d.columns = d.columns.get_level_values(0)
    if len(d) > 2000:
        df = d[['Open', 'High', 'Low', 'Close']].copy()
        df['SMA50'] = df['Close'].rolling(50).mean()
        df['SMA200'] = df['Close'].rolling(200).mean()
        df['SMA10'] = df['Close'].rolling(10).mean()
        df['EMA12'] = df['Close'].ewm(span=12).mean()
        df['EMA26'] = df['Close'].ewm(span=26).mean()
        df['RSI14'] = 100 - 100 / (1 + df['Close'].diff().clip(lower=0).rolling(14).mean() /
                                     df['Close'].diff().clip(upper=0).abs().rolling(14).mean())
        df['Ret'] = df['Close'].pct_change()
        df['Vol20'] = df['Ret'].rolling(20).std() * np.sqrt(252)
        df['TR'] = np.maximum(df['High'] - df['Low'],
            np.maximum(abs(df['High'] - df['Close'].shift(1)),
                       abs(df['Low'] - df['Close'].shift(1))))
        df['ATR14'] = df['TR'].rolling(14).mean()
        df['Mom20'] = df['Close'] / df['Close'].shift(20) - 1
        df['Mom60'] = df['Close'] / df['Close'].shift(60) - 1
        df['BB_Mid'] = df['Close'].rolling(20).mean()
        df['BB_Std'] = df['Close'].rolling(20).std()
        df['BB_Dn'] = df['BB_Mid'] - 2 * df['BB_Std']
        df['IBS'] = (df['Close'] - df['Low']) / (df['High'] - df['Low'])
        data[t] = df

def m(trades, eq):
    if len(eq) < 200: return None
    n = len(trades)
    years = len(eq) / 252
    cagr = ((eq[-1] / INITIAL) ** (1/years) - 1) * 100
    rm = np.maximum.accumulate(eq)
    dd = ((eq - rm) / rm).min() * 100
    dr = np.diff(eq) / eq[:-1]; dr = dr[np.isfinite(dr)]
    sh = (np.mean(dr) / np.std(dr)) * np.sqrt(252) if np.std(dr) > 0 else 0
    if n > 0:
        w = sum(1 for t in trades if t > 0)
        return {'sh': sh, 'cagr': cagr, 'dd': dd, 'n': n, 'wr': w/n*100}
    return {'sh': sh, 'cagr': cagr, 'dd': dd, 'n': 0, 'wr': 0}

results = []

# ============================================================
# STRATEGY 1: 10-Month SMA (classic momentum)
# ============================================================
def strat_10mo_sma(df):
    """Buy when close > 10-month (200-day) SMA, sell when below"""
    cap = INITIAL; pos = 0; signal = 0
    trades = []; eq = []
    for i in range(1, len(df)):
        c_prev = float(df['Close'].iloc[i-1])
        o = float(df['Open'].iloc[i])
        c = float(df['Close'].iloc[i])
        sma200 = float(df['SMA200'].iloc[i-1]) if pd.notna(df['SMA200'].iloc[i-1]) else None
        
        if sma200:
            new_signal = 1 if c_prev > sma200 else 0
        else:
            new_signal = signal
        
        if pos == 0 and new_signal == 1 and signal == 0:
            sh = int(cap / o)
            if sh > 0:
                ca = sh * o * COST; cap -= sh * o + ca; pos = sh; entry = o
        
        elif pos > 0 and new_signal == 0 and signal == 1:
            ca = pos * (entry + o) * COST / 2
            cap += pos * o - ca
            trades.append(pos * (o - entry) - ca)
            pos = 0
        
        signal = new_signal
        eq.append(cap + (pos * c if pos > 0 else 0))
    
    if pos > 0:
        c = float(df['Close'].iloc[-1])
        ca = pos * (entry + c) * COST / 2
        cap += pos * c - ca
        trades.append(pos * (c - entry) - ca)
    return trades, np.array(eq)

for t in data:
    try:
        tr, eq = strat_10mo_sma(data[t])
        r = m(tr, eq)
        if r: results.append({'strat': '10mo SMA', 'instr': t, **r})
    except: pass

# ============================================================
# STRATEGY 2: Dual SMA Crossover
# ============================================================
def strat_dual_sma(df, fast=50, slow=200):
    cap = INITIAL; pos = 0; signal = 0
    trades = []; eq = []
    for i in range(1, len(df)):
        c_prev = float(df['Close'].iloc[i-1])
        o = float(df['Open'].iloc[i])
        c = float(df['Close'].iloc[i])
        f = float(df[f'SMA{fast}'].iloc[i-1]) if pd.notna(df[f'SMA{fast}'].iloc[i-1]) else None
        s = float(df[f'SMA{slow}'].iloc[i-1]) if pd.notna(df[f'SMA{slow}'].iloc[i-1]) else None
        
        if f and s:
            new_signal = 1 if f > s else 0
        else:
            new_signal = signal
        
        if pos == 0 and new_signal == 1 and signal == 0:
            sh = int(cap / o)
            if sh > 0:
                ca = sh * o * COST; cap -= sh * o + ca; pos = sh; entry = o
        elif pos > 0 and new_signal == 0 and signal == 1:
            ca = pos * (entry + o) * COST / 2
            cap += pos * o - ca
            trades.append(pos * (o - entry) - ca)
            pos = 0
        
        signal = new_signal
        eq.append(cap + (pos * c if pos > 0 else 0))
    
    if pos > 0:
        c = float(df['Close'].iloc[-1])
        ca = pos * (entry + c) * COST / 2
        cap += pos * c - ca
        trades.append(pos * (c - entry) - ca)
    return trades, np.array(eq)

for t in data:
    for fast, slow in [(50, 200), (20, 100), (10, 50)]:
        try:
            tr, eq = strat_dual_sma(data[t], fast, slow)
            r = m(tr, eq)
            if r: results.append({'strat': f'SMA {fast}/{slow}', 'instr': t, **r})
        except: pass

# ============================================================
# STRATEGY 3: EMA Crossover (MACD signal)
# ============================================================
def strat_ema_cross(df):
    cap = INITIAL; pos = 0; signal = 0
    trades = []; eq = []
    for i in range(1, len(df)):
        c_prev = float(df['Close'].iloc[i-1])
        o = float(df['Open'].iloc[i])
        c = float(df['Close'].iloc[i])
        ema12 = float(df['EMA12'].iloc[i-1]) if pd.notna(df['EMA12'].iloc[i-1]) else None
        ema26 = float(df['EMA26'].iloc[i-1]) if pd.notna(df['EMA26'].iloc[i-1]) else None
        
        if ema12 and ema26:
            new_signal = 1 if ema12 > ema26 else 0
        else:
            new_signal = signal
        
        if pos == 0 and new_signal == 1 and signal == 0:
            sh = int(cap / o)
            if sh > 0:
                ca = sh * o * COST; cap -= sh * o + ca; pos = sh; entry = o
        elif pos > 0 and new_signal == 0 and signal == 1:
            ca = pos * (entry + o) * COST / 2
            cap += pos * o - ca
            trades.append(pos * (o - entry) - ca)
            pos = 0
        
        signal = new_signal
        eq.append(cap + (pos * c if pos > 0 else 0))
    
    if pos > 0:
        c = float(df['Close'].iloc[-1])
        ca = pos * (entry + c) * COST / 2
        cap += pos * c - ca
        trades.append(pos * (c - entry) - ca)
    return trades, np.array(eq)

for t in data:
    try:
        tr, eq = strat_ema_cross(data[t])
        r = m(tr, eq)
        if r: results.append({'strat': 'EMA 12/26', 'instr': t, **r})
    except: pass

# ============================================================
# STRATEGY 4: Momentum (buy if 20-day return > 0)
# ============================================================
def strat_mom(df, lookback=20):
    cap = INITIAL; pos = 0; signal = 0
    trades = []; eq = []
    for i in range(1, len(df)):
        c_prev = float(df['Close'].iloc[i-1])
        o = float(df['Open'].iloc[i])
        c = float(df['Close'].iloc[i])
        mom = float(df['Mom20'].iloc[i-1]) if pd.notna(df['Mom20'].iloc[i-1]) else 0
        
        new_signal = 1 if mom > 0 else 0
        
        if pos == 0 and new_signal == 1 and signal == 0:
            sh = int(cap / o)
            if sh > 0:
                ca = sh * o * COST; cap -= sh * o + ca; pos = sh; entry = o
        elif pos > 0 and new_signal == 0 and signal == 1:
            ca = pos * (entry + o) * COST / 2
            cap += pos * o - ca
            trades.append(pos * (o - entry) - ca)
            pos = 0
        
        signal = new_signal
        eq.append(cap + (pos * c if pos > 0 else 0))
    
    if pos > 0:
        c = float(df['Close'].iloc[-1])
        ca = pos * (entry + c) * COST / 2
        cap += pos * c - ca
        trades.append(pos * (c - entry) - ca)
    return trades, np.array(eq)

for t in data:
    try:
        tr, eq = strat_mom(data[t])
        r = m(tr, eq)
        if r: results.append({'strat': 'Mom 20d', 'instr': t, **r})
    except: pass

# ============================================================
# STRATEGY 5: RSI Mean Reversion (buy RSI<30, sell RSI>50)
# ============================================================
def strat_rsi_mr(df):
    cap = INITIAL; pos = 0
    trades = []; eq = []
    for i in range(1, len(df)):
        rsi = float(df['RSI14'].iloc[i-1]) if pd.notna(df['RSI14'].iloc[i-1]) else 50
        o = float(df['Open'].iloc[i])
        c = float(df['Close'].iloc[i])
        
        if pos > 0 and rsi > 50:
            ca = pos * (entry + o) * COST / 2
            cap += pos * o - ca
            trades.append(pos * (o - entry) - ca)
            pos = 0
        
        if pos == 0 and rsi < 30:
            sh = int(cap / o)
            if sh > 0:
                ca = sh * o * COST; cap -= sh * o + ca; pos = sh; entry = o
        
        eq.append(cap + (pos * c if pos > 0 else 0))
    
    if pos > 0:
        c = float(df['Close'].iloc[-1])
        ca = pos * (entry + c) * COST / 2
        cap += pos * c - ca
        trades.append(pos * (c - entry) - ca)
    return trades, np.array(eq)

for t in data:
    try:
        tr, eq = strat_rsi_mr(data[t])
        r = m(tr, eq)
        if r: results.append({'strat': 'RSI MR', 'instr': t, **r})
    except: pass

# ============================================================
# STRATEGY 6: Simple MA + Vol Filter
# ============================================================
def strat_ma_vol(df):
    """Buy SMA50>SMA200 AND vol<20%, sell SMA50<SMA200"""
    cap = INITIAL; pos = 0; signal = 0
    trades = []; eq = []
    for i in range(1, len(df)):
        c_prev = float(df['Close'].iloc[i-1])
        o = float(df['Open'].iloc[i])
        c = float(df['Close'].iloc[i])
        sma50 = float(df['SMA50'].iloc[i-1]) if pd.notna(df['SMA50'].iloc[i-1]) else None
        sma200 = float(df['SMA200'].iloc[i-1]) if pd.notna(df['SMA200'].iloc[i-1]) else None
        vol = float(df['Vol20'].iloc[i-1]) if pd.notna(df['Vol20'].iloc[i-1]) else 1.0
        
        if sma50 and sma200:
            new_signal = 1 if (sma50 > sma200 and vol < 0.20) else 0
        else:
            new_signal = signal
        
        if pos == 0 and new_signal == 1 and signal == 0:
            sh = int(cap / o)
            if sh > 0:
                ca = sh * o * COST; cap -= sh * o + ca; pos = sh; entry = o
        elif pos > 0 and new_signal == 0 and signal == 1:
            ca = pos * (entry + o) * COST / 2
            cap += pos * o - ca
            trades.append(pos * (o - entry) - ca)
            pos = 0
        
        signal = new_signal
        eq.append(cap + (pos * c if pos > 0 else 0))
    
    if pos > 0:
        c = float(df['Close'].iloc[-1])
        ca = pos * (entry + c) * COST / 2
        cap += pos * c - ca
        trades.append(pos * (c - entry) - ca)
    return trades, np.array(eq)

for t in data:
    try:
        tr, eq = strat_ma_vol(data[t])
        r = m(tr, eq)
        if r: results.append({'strat': 'SMA+Vol', 'instr': t, **r})
    except: pass

# ============================================================
# STRATEGY 7: Multi-asset momentum with vol targeting
# ============================================================
def strat_multi_mom(data_dict):
    """Equal-weight top 3 by 20d momentum, rebalance monthly"""
    closes = pd.DataFrame({t: data_dict[t]['Close'] for t in data_dict}).dropna()
    opens = pd.DataFrame({t: data_dict[t]['Open'] for t in data_dict}).dropna()
    common = closes.index.intersection(opens.index)
    closes = closes.loc[common]; opens = opens.loc[common]
    
    cap = INITIAL; pos = {}; timer = 0
    trades = []; eq = []
    
    for i in range(20, len(closes)):
        mom = {}
        for t in data_dict:
            if t in closes.columns:
                mom[t] = closes[t].iloc[i] / closes[t].iloc[i-20] - 1
        
        # Top 3
        sorted_mom = sorted(mom.items(), key=lambda x: x[1], reverse=True)
        top3 = [x[0] for x in sorted_mom[:3]]
        
        timer += 1
        if timer >= 20:  # rebalance monthly
            timer = 0
            # Sell positions not in top3
            for t in list(pos.keys()):
                if t not in top3 and pos[t] > 0:
                    o = float(opens[t].iloc[i])
                    ca = pos[t] * (entry_p[t] + o) * COST / 2
                    cap += pos[t] * o - ca
                    trades.append(pos[t] * (o - entry_p[t]) - ca)
                    del pos[t]; del entry_p[t]
            
            # Buy new top3
            per_asset = cap / max(len(top3), 1)
            for t in top3:
                if t not in pos:
                    o = float(opens[t].iloc[i])
                    sh = int(per_asset / o)
                    if sh > 0:
                        ca = sh * o * COST
                        cap -= sh * o + ca
                        pos[t] = sh
                        if 'entry_p' not in dir(): entry_p = {}
                        entry_p[t] = o
        
        pv = cap
        for t, shares in pos.items():
            pv += shares * float(closes[t].iloc[i])
        eq.append(pv)
    
    # Close all
    for t, shares in pos.items():
        c = float(closes[t].iloc[-1])
        ca = shares * (entry_p[t] + c) * COST / 2
        cap += shares * c - ca
        trades.append(shares * (c - entry_p[t]) - ca)
    
    return trades, np.array(eq)

try:
    tr, eq = strat_multi_mom(data)
    r = m(tr, eq)
    if r: results.append({'strat': 'Multi Mom Top3', 'instr': 'Multi', **r})
except: pass

# ============================================================
# RESULTS
# ============================================================
results.sort(key=lambda x: x['sh'], reverse=True)

print()
print("=" * 90)
print("RESULTS — All Strategies")
print("=" * 90)
print()
print(f"  {'#':>3} {'Strategy':<18} {'Instr':<6} {'T':>5} {'WR%':>6} {'CAGR%':>8} {'DD%':>8} {'Sharpe':>7}")
print(f"  {'-'*65}")
for i, r in enumerate(results[:40]):
    print(f"  {i+1:>3} {r['strat']:<18} {r['instr']:<6} {r['n']:>5} {r['wr']:>5.1f}% {r['cagr']:>7.1f}% {r['dd']:>7.1f}% {r['sh']:>6.2f}")

# ============================================================
# TOP 5 — WALK-FORWARD
# ============================================================
print()
print("=" * 90)
print("WALK-FORWARD (Top 5)")
print("=" * 90)

strat_funcs = {
    '10mo SMA': lambda df: strat_10mo_sma(df),
    'SMA 50/200': lambda df: strat_dual_sma(df, 50, 200),
    'SMA 20/100': lambda df: strat_dual_sma(df, 20, 100),
    'SMA 10/50': lambda df: strat_dual_sma(df, 10, 50),
    'EMA 12/26': lambda df: strat_ema_cross(df),
    'Mom 20d': lambda df: strat_mom(df),
    'RSI MR': lambda df: strat_rsi_mr(df),
    'SMA+Vol': lambda df: strat_ma_vol(df),
}

for rank, r in enumerate(results[:5]):
    strat_name = r['strat']
    instr = r['instr']
    
    if strat_name in strat_funcs and instr in data:
        tr, eq = strat_funcs[strat_name](data[instr])
        eq_s = pd.Series(eq, index=data[instr].index[-len(eq):])
        
        print(f"\n  #{rank+1} {strat_name} on {instr}: Sharpe {r['sh']:.2f}")
        print(f"  {'Period':<12} {'IS Sharpe':>10} {'OOS Sharpe':>11}")
        print(f"  {'-'*35}")
        
        for start in range(2012, 2023):
            is_mask = (eq_s.index.year >= start) & (eq_s.index.year < start + 3)
            oos_mask = (eq_s.index.year >= start + 3) & (eq_s.index.year < start + 4)
            if is_mask.sum() < 200 or oos_mask.sum() < 50: continue
            is_dr = np.diff(eq_s[is_mask].values) / eq_s[is_mask].values[:-1]
            oos_dr = np.diff(eq_s[oos_mask].values) / eq_s[oos_mask].values[:-1]
            is_dr = is_dr[np.isfinite(is_dr)]; oos_dr = oos_dr[np.isfinite(oos_dr)]
            is_sh = (np.mean(is_dr)/np.std(is_dr))*np.sqrt(252) if np.std(is_dr)>0 else 0
            oos_sh = (np.mean(oos_dr)/np.std(oos_dr))*np.sqrt(252) if np.std(oos_dr)>0 else 0
            print(f"  {start}-{start+3}    {is_sh:>10.2f} {oos_sh:>11.2f}")

print()
print("=" * 90)
print("BEST HONEST STRATEGY")
print("=" * 90)
best = results[0]
print(f"  {best['strat']} on {best['instr']}")
print(f"  Sharpe: {best['sh']:.2f}")
print(f"  CAGR:   {best['cagr']:.1f}%")
print(f"  DD:     {best['dd']:.1f}%")
print(f"  Trades: {best['n']}")
print(f"  WR:     {best['wr']:.1f}%")
if best['sh'] >= 1.3:
    print(f"\n  *** TARGET ACHIEVED ***")
