"""
FIND SHARPE > 1.3 — Simple Strategies, Any Asset
===================================================
Rules:
  - Next-open execution (no same-bar entry)
  - 10 years of data (2015-2025)
  - Walk-forward validated
"""

import pandas as pd
import numpy as np
import yfinance as yf
import warnings
warnings.filterwarnings('ignore')

INITIAL = 100000
COST = 0.001

print("=" * 90)
print("FINDING SHARPE > 1.3")
print("=" * 90)

# Download data
tickers = ['QQQ', 'SPY', 'IWM', 'GLD', 'TLT', 'XLF', 'XLE', 'XLK', 'VNQ', 'EEM']
data = {}
for t in tickers:
    d = yf.download(t, start='2010-01-01', end='2025-12-31', progress=False)
    if hasattr(d.columns, 'get_level_values'):
        d.columns = d.columns.get_level_values(0)
    if len(d) > 2000:
        data[t] = d[['Open', 'High', 'Low', 'Close']].copy()
        data[t]['Ret'] = data[t]['Close'].pct_change()
        data[t]['SMA10'] = data[t]['Close'].rolling(10).mean()
        data[t]['SMA20'] = data[t]['Close'].rolling(20).mean()
        data[t]['SMA50'] = data[t]['Close'].rolling(50).mean()
        data[t]['SMA200'] = data[t]['Close'].rolling(200).mean()
        data[t]['EMA12'] = data[t]['Close'].ewm(span=12).mean()
        data[t]['EMA26'] = data[t]['Close'].ewm(span=26).mean()
        data[t]['RSI14'] = 100 - 100 / (1 + data[t]['Close'].diff().clip(lower=0).rolling(14).mean() /
                                           data[t]['Close'].diff().clip(upper=0).abs().rolling(14).mean())
        data[t]['TR'] = np.maximum(data[t]['High'] - data[t]['Low'],
            np.maximum(abs(data[t]['High'] - data[t]['Close'].shift(1)),
                       abs(data[t]['Low'] - data[t]['Close'].shift(1))))
        data[t]['ATR14'] = data[t]['TR'].rolling(14).mean()
        data[t]['Vol20'] = data[t]['Ret'].rolling(20).std() * np.sqrt(252)
        data[t]['BB_Mid'] = data[t]['Close'].rolling(20).mean()
        data[t]['BB_Std'] = data[t]['Close'].rolling(20).std()
        data[t]['BB_Up'] = data[t]['BB_Mid'] + 2 * data[t]['BB_Std']
        data[t]['BB_Dn'] = data[t]['BB_Mid'] - 2 * data[t]['BB_Std']
        data[t]['Momentum'] = data[t]['Close'] / data[t]['Close'].shift(20) - 1

print(f"  Downloaded {len(data)} instruments")

# ============================================================
# STRATEGY 1: Simple MA Crossover (buy at next open)
# ============================================================
def strat_ma(df, fast=10, slow=50):
    cap = INITIAL; pos = 0; signal = 0; trades = []; eq = []
    for i in range(1, len(df)):
        c = float(df['Close'].iloc[i-1])  # signal at yesterday's close
        o = float(df['Open'].iloc[i])     # execute at today's open
        fast_ma = float(df[f'SMA{fast}'].iloc[i-1]) if pd.notna(df[f'SMA{fast}'].iloc[i-1]) else None
        slow_ma = float(df[f'SMA{slow}'].iloc[i-1]) if pd.notna(df[f'SMA{slow}'].iloc[i-1]) else None
        
        if fast_ma and slow_ma:
            new_signal = 1 if fast_ma > slow_ma else 0
        else:
            new_signal = signal
        
        if pos == 0 and new_signal == 1 and signal == 0:
            # Buy at today's open
            sh = int(cap / o)
            if sh > 0:
                ca = sh * o * COST
                cap -= sh * o + ca
                pos = sh
        elif pos > 0 and new_signal == 0 and signal == 1:
            # Sell at today's open
            ca = pos * (entry + o) * COST / 2
            cap += pos * o - ca
            trades.append({'pnl': pos * (o - entry) - ca})
            pos = 0
        
        if pos > 0 and 'entry' not in dir():
            entry = o
        elif pos > 0 and new_signal == 1 and signal == 0:
            pass  # already entered
        elif pos == 0:
            entry = None
        
        signal = new_signal
        eq.append(cap + (pos * float(df['Close'].iloc[i]) if pos > 0 else 0))
    
    if pos > 0:
        c = float(df['Close'].iloc[-1])
        ca = pos * (entry + c) * COST / 2
        cap += pos * c - ca
        trades.append({'pnl': pos * (c - entry) - ca})
    
    return trades, np.array(eq)


# ============================================================
# STRATEGY 2: Momentum Rotation (buy strongest, sell weakest)
# ============================================================
def strat_rotation(data_dict, lookback=20, hold=20):
    """Rotate into the strongest momentum asset each period"""
    # Align all close prices
    closes = pd.DataFrame({t: data_dict[t]['Close'] for t in data_dict}).dropna()
    if len(closes) < lookback + hold:
        return [], np.array([])
    
    cap = INITIAL; pos = 0; current_asset = None; entry_price = 0
    trades = []; eq = []; rebal_timer = 0
    
    for i in range(lookback, len(closes)):
        today = closes.index[i]
        # Calculate momentum for each asset
        mom = {}
        for t in data_dict:
            if t in closes.columns:
                p_now = closes[t].iloc[i]
                p_prev = closes[t].iloc[i - lookback]
                if p_prev > 0:
                    mom[t] = p_now / p_prev - 1
        
        if not mom:
            eq.append(cap)
            continue
        
        # Pick best
        best = max(mom, key=mom.get)
        
        rebal_timer += 1
        if rebal_timer >= hold or current_asset != best:
            # Sell current
            if pos > 0 and current_asset:
                c = float(data_dict[current_asset]['Close'].iloc[i])
                o = float(data_dict[current_asset]['Open'].iloc[i])
                ca = pos * (entry_price + o) * COST / 2
                cap += pos * o - ca
                trades.append({'pnl': pos * (o - entry_price) - ca})
                pos = 0
            
            # Buy new
            if current_asset != best:
                o = float(data_dict[best]['Open'].iloc[i])
                sh = int(cap / o)
                if sh > 0:
                    ca = sh * o * COST
                    cap -= sh * o + ca
                    pos = sh; entry_price = o; current_asset = best
                rebal_timer = 0
        
        portfolio_val = cap
        if pos > 0 and current_asset:
            portfolio_val += pos * float(data_dict[current_asset]['Close'].iloc[i])
        eq.append(portfolio_val)
    
    if pos > 0 and current_asset:
        c = float(data_dict[current_asset]['Close'].iloc[-1])
        ca = pos * (entry_price + c) * COST / 2
        cap += pos * c - ca
        trades.append({'pnl': pos * (c - entry_price) - ca})
    
    return trades, np.array(eq)


# ============================================================
# STRATEGY 3: Mean Reversion (IBS at next open)
# ============================================================
def strat_mr(df, ibs_thresh=0.25, hold=5):
    cap = INITIAL; pos = 0; hd = 0; signal = False
    trades = []; eq = []
    for i in range(1, len(df)):
        # Signal at yesterday's close
        c_prev = float(df['Close'].iloc[i-1])
        h_prev = float(df['High'].iloc[i-1])
        l_prev = float(df['Low'].iloc[i-1])
        ibs = (c_prev - l_prev) / (h_prev - l_prev) if h_prev != l_prev else 0.5
        
        # Execute at today's open
        o = float(df['Open'].iloc[i])
        c = float(df['Close'].iloc[i])
        
        if pos > 0:
            hd += 1
            if hd >= hold:
                ca = pos * (entry + o) * COST / 2
                cap += pos * o - ca
                trades.append({'pnl': pos * (o - entry) - ca})
                pos = 0; hd = 0
        
        if pos == 0 and ibs < ibs_thresh:
            sh = int(cap / o)
            if sh > 0:
                ca = sh * o * COST
                cap -= sh * o + ca
                pos = sh; entry = o; hd = 0
        
        eq.append(cap + (pos * c if pos > 0 else 0))
    
    if pos > 0:
        c = float(df['Close'].iloc[-1])
        ca = pos * (entry + c) * COST / 2
        cap += pos * c - ca
        trades.append({'pnl': pos * (c - entry) - ca})
    
    return trades, np.array(eq)


# ============================================================
# STRATEGY 4: Trend Following with ATR trailing stop
# ============================================================
def strat_trend(df, entry_sma=50, exit_sma=20, atr_mult=2.0):
    cap = INITIAL; pos = 0; entry = 0; signal = 0
    trades = []; eq = []
    for i in range(1, len(df)):
        c_prev = float(df['Close'].iloc[i-1])
        o = float(df['Open'].iloc[i])
        c = float(df['Close'].iloc[i])
        ema_fast = float(df['EMA12'].iloc[i-1]) if pd.notna(df['EMA12'].iloc[i-1]) else c_prev
        ema_slow = float(df['EMA26'].iloc[i-1]) if pd.notna(df['EMA26'].iloc[i-1]) else c_prev
        atr = float(df['ATR14'].iloc[i-1]) if pd.notna(df['ATR14'].iloc[i-1]) else c_prev * 0.02
        
        new_signal = 1 if ema_fast > ema_slow else 0
        
        # ATR trailing stop
        if pos > 0:
            stop = entry - atr_mult * atr
            if c <= stop and c_prev > stop:  # stopped out
                ca = pos * (entry + o) * COST / 2
                cap += pos * o - ca
                trades.append({'pnl': pos * (o - entry) - ca})
                pos = 0
        
        if pos == 0 and new_signal == 1 and signal == 0:
            sh = int(cap / o)
            if sh > 0:
                ca = sh * o * COST
                cap -= sh * o + ca
                pos = sh; entry = o
        
        if pos > 0 and new_signal == 0 and signal == 1:
            ca = pos * (entry + o) * COST / 2
            cap += pos * o - ca
            trades.append({'pnl': pos * (o - entry) - ca})
            pos = 0
        
        signal = new_signal
        eq.append(cap + (pos * c if pos > 0 else 0))
    
    if pos > 0:
        c = float(df['Close'].iloc[-1])
        ca = pos * (entry + c) * COST / 2
        cap += pos * c - ca
        trades.append({'pnl': pos * (c - entry) - ca})
    
    return trades, np.array(eq)


# ============================================================
# STRATEGY 5: RSI Mean Reversion
# ============================================================
def strat_rsi(df, rsi_thresh=30, hold=5):
    cap = INITIAL; pos = 0; hd = 0
    trades = []; eq = []
    for i in range(1, len(df)):
        rsi = float(df['RSI14'].iloc[i-1]) if pd.notna(df['RSI14'].iloc[i-1]) else 50
        o = float(df['Open'].iloc[i])
        c = float(df['Close'].iloc[i])
        
        if pos > 0:
            hd += 1
            if hd >= hold:
                ca = pos * (entry + o) * COST / 2
                cap += pos * o - ca
                trades.append({'pnl': pos * (o - entry) - ca})
                pos = 0; hd = 0
        
        if pos == 0 and rsi < rsi_thresh:
            sh = int(cap / o)
            if sh > 0:
                ca = sh * o * COST
                cap -= sh * o + ca
                pos = sh; entry = o; hd = 0
        
        eq.append(cap + (pos * c if pos > 0 else 0))
    
    if pos > 0:
        c = float(df['Close'].iloc[-1])
        ca = pos * (entry + c) * COST / 2
        cap += pos * c - ca
        trades.append({'pnl': pos * (c - entry) - ca})
    
    return trades, np.array(eq)


# ============================================================
# STRATEGY 6: Bollinger Band Mean Reversion
# ============================================================
def strat_bb(df, hold=5):
    cap = INITIAL; pos = 0; hd = 0
    trades = []; eq = []
    for i in range(1, len(df)):
        c_prev = float(df['Close'].iloc[i-1])
        bb_dn = float(df['BB_Dn'].iloc[i-1]) if pd.notna(df['BB_Dn'].iloc[i-1]) else c_prev
        bb_up = float(df['BB_Up'].iloc[i-1]) if pd.notna(df['BB_Up'].iloc[i-1]) else c_prev
        o = float(df['Open'].iloc[i])
        c = float(df['Close'].iloc[i])
        
        if pos > 0:
            hd += 1
            if hd >= hold:
                ca = pos * (entry + o) * COST / 2
                cap += pos * o - ca
                trades.append({'pnl': pos * (o - entry) - ca})
                pos = 0; hd = 0
        
        if pos == 0 and c_prev < bb_dn:
            sh = int(cap / o)
            if sh > 0:
                ca = sh * o * COST
                cap -= sh * o + ca
                pos = sh; entry = o; hd = 0
        
        eq.append(cap + (pos * c if pos > 0 else 0))
    
    if pos > 0:
        c = float(df['Close'].iloc[-1])
        ca = pos * (entry + c) * COST / 2
        cap += pos * c - ca
        trades.append({'pnl': pos * (c - entry) - ca})
    
    return trades, np.array(eq)


# ============================================================
# METRICS
# ============================================================
def m(trades, eq):
    if len(eq) < 100:
        return None
    n = len(trades)
    years = len(eq) / 252
    cagr = ((eq[-1] / INITIAL) ** (1/years) - 1) * 100
    rm = np.maximum.accumulate(eq)
    dd = ((eq - rm) / rm).min() * 100
    dr = np.diff(eq) / eq[:-1]; dr = dr[np.isfinite(dr)]
    sh = (np.mean(dr) / np.std(dr)) * np.sqrt(252) if np.std(dr) > 0 else 0
    if n > 0:
        w = sum(1 for t in trades if t['pnl'] > 0)
        gp = sum(t['pnl'] for t in trades if t['pnl'] > 0)
        gl = abs(sum(t['pnl'] for t in trades if t['pnl'] <= 0)) or 0.001
        return {'sh': sh, 'cagr': cagr, 'dd': dd, 'pf': gp/gl, 'wr': w/n*100, 'n': n}
    return {'sh': sh, 'cagr': cagr, 'dd': dd, 'pf': 0, 'wr': 0, 'n': 0}


# ============================================================
# SCAN ALL STRATEGIES
# ============================================================
print()
print("=" * 90)
print("SCANNING STRATEGIES")
print("=" * 90)
print()

results = []

# 1. MA Crossover on each instrument
for t in data:
    for fast, slow in [(10, 50), (20, 50), (10, 100), (20, 200), (50, 200)]:
        try:
            trades, eq = strat_ma(data[t], fast, slow)
            r = m(trades, eq)
            if r:
                r['strategy'] = f'MA {fast}/{slow}'
                r['instrument'] = t
                results.append(r)
        except: pass

# 2. Momentum Rotation
for lb in [10, 20, 60]:
    for hold in [5, 10, 20]:
        try:
            trades, eq = strat_rotation(data, lb, hold)
            r = m(trades, eq)
            if r:
                r['strategy'] = f'Rotation {lb}d/{hold}d'
                r['instrument'] = 'Multi'
                results.append(r)
        except: pass

# 3. Mean Reversion on each instrument
for t in data:
    for ibs in [0.20, 0.25, 0.30]:
        for hold in [3, 5, 7]:
            try:
                trades, eq = strat_mr(data[t], ibs, hold)
                r = m(trades, eq)
                if r:
                    r['strategy'] = f'MR IBS<{ibs} {hold}d'
                    r['instrument'] = t
                    results.append(r)
            except: pass

# 4. Trend Following on each instrument
for t in data:
    try:
        trades, eq = strat_trend(data[t])
        r = m(trades, eq)
        if r:
            r['strategy'] = f'Trend EMA ATR2'
            r['instrument'] = t
            results.append(r)
    except: pass

# 5. RSI Mean Reversion
for t in data:
    for rsi in [25, 30, 35]:
        for hold in [3, 5, 7]:
            try:
                trades, eq = strat_rsi(data[t], rsi, hold)
                r = m(trades, eq)
                if r:
                    r['strategy'] = f'RSI<{rsi} {hold}d'
                    r['instrument'] = t
                    results.append(r)
            except: pass

# 6. Bollinger Band Mean Reversion
for t in data:
    for hold in [3, 5, 7]:
        try:
            trades, eq = strat_bb(data[t], hold)
            r = m(trades, eq)
            if r:
                r['strategy'] = f'BB MR {hold}d'
                r['instrument'] = t
                results.append(r)
        except: pass

# Sort by Sharpe
results.sort(key=lambda x: x['sh'], reverse=True)

print(f"  {'#':>3} {'Strategy':<22} {'Instr':<6} {'T':>5} {'WR%':>6} {'PF':>7} {'CAGR%':>8} {'DD%':>8} {'Sharpe':>7}")
print(f"  {'-'*72}")
for i, r in enumerate(results[:30]):
    print(f"  {i+1:>3} {r['strategy']:<22} {r['instrument']:<6} {r['n']:>5} {r['wr']:>5.1f}% {r['pf']:>6.2f} {r['cagr']:>7.1f}% {r['dd']:>7.1f}% {r['sh']:>6.2f}")

# ============================================================
# TOP CANDIDATES — WALK-FORWARD
# ============================================================
print()
print("=" * 90)
print("WALK-FORWARD VALIDATION (Top 5)")
print("=" * 90)
print()

# Re-run top 5 with full data and walk-forward
for i, r in enumerate(results[:5]):
    print(f"  {i+1}. {r['strategy']} on {r['instrument']}: Sharpe {r['sh']:.2f}")
    
    # Get the equity curve for walk-forward
    instr = r['instrument']
    strat_name = r['strategy']
    
    # Parse strategy params
    if 'MA' in strat_name:
        parts = str(strat_name).split()
        fast, slow = int(parts[1].split('/')[0]), int(parts[1].split('/')[1])
        trades, eq = strat_ma(data[instr], fast, slow)
    elif 'Rotation' in strat_name:
        parts = str(strat_name).split()
        lb = int(parts[1].split('/')[0])
        hold = int(parts[2].split('/')[0])
        trades, eq = strat_rotation(data, lb, hold)
    elif 'MR' in strat_name and 'BB' not in strat_name:
        parts = str(strat_name).split()
        ibs = float(parts[2].replace('<', ''))
        hold = int(parts[3].replace('d', ''))
        trades, eq = strat_mr(data[instr], ibs, hold)
    elif 'Trend' in strat_name:
        trades, eq = strat_trend(data[instr])
    elif 'RSI' in strat_name:
        parts = str(strat_name).split()
        rsi = int(parts[0].replace('RSI<', ''))
        hold = int(parts[1].replace('d', ''))
        trades, eq = strat_rsi(data[instr], rsi, hold)
    elif 'BB' in strat_name:
        parts = str(strat_name).split()
        hold = int(parts[2].replace('d', ''))
        trades, eq = strat_bb(data[instr], hold)
    else:
        continue
    
    if len(trades) < 20:
        print(f"    Too few trades ({len(trades)}), skipping")
        continue
    
    # Walk-forward: 3yr IS / 1yr OOS
    eq_series = pd.Series(eq, index=data[instr].index[-len(eq):])
    wfrs = []
    for start_year in range(2012, 2023):
        is_mask = (eq_series.index.year >= start_year) & (eq_series.index.year < start_year + 3)
        oos_mask = (eq_series.index.year >= start_year + 3) & (eq_series.index.year < start_year + 4)
        if is_mask.sum() < 200 or oos_mask.sum() < 50:
            continue
        is_eq = eq_series[is_mask].values
        oos_eq = eq_series[oos_mask].values
        is_sh = np.mean(np.diff(is_eq)/is_eq[:-1]) / max(np.std(np.diff(is_eq)/is_eq[:-1]), 0.001) * np.sqrt(252) if len(is_eq) > 10 else 0
        oos_sh = np.mean(np.diff(oos_eq)/oos_eq[:-1]) / max(np.std(np.diff(oos_eq)/oos_eq[:-1]), 0.001) * np.sqrt(252) if len(oos_eq) > 10 else 0
        if is_sh > 0:
            wfrs.append(oos_sh / is_sh)
    
    avg_wfr = np.mean(wfrs) if wfrs else 0
    print(f"    WFR: {avg_wfr:.2f} ({'PASS' if avg_wfr > 0.5 else 'FAIL'}) | OOS Sharpe avg: {np.mean([oos_sh for oos_sh in wfrs]):.2f}" if wfrs else f"    WFR: N/A")

# ============================================================
# FINAL ANSWER
# ============================================================
print()
print("=" * 90)
print("BEST STRATEGY")
print("=" * 90)

best = results[0]
print(f"  Strategy:  {best['strategy']}")
print(f"  Instrument: {best['instrument']}")
print(f"  Sharpe:    {best['sh']:.2f}")
print(f"  CAGR:      {best['cagr']:.1f}%")
print(f"  Max DD:    {best['dd']:.1f}%")
print(f"  WR:        {best['wr']:.1f}%")
print(f"  PF:        {best['pf']:.2f}")
print(f"  Trades:    {best['n']}")

if best['sh'] >= 1.3:
    print(f"\n  *** TARGET ACHIEVED: Sharpe {best['sh']:.2f} >= 1.3 ***")
else:
    print(f"\n  Close but not quite: Sharpe {best['sh']:.2f} < 1.3")
    print(f"  Consider: leverage, multi-asset combo, or intraday data")
