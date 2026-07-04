"""
UNIQUE EDGE: VIX REGIME + CROSS-ASSET FLOW + IBS TIMING
=========================================================
The edge: When VIX spikes and then starts mean-reverting,
stocks bounce hard. The key is detecting the REGIME CHANGE
(vix spike -> vix rolling over) and timing entries with IBS.

Additionally: cross-asset flow signals — when bonds sell off
(TLT down) and stocks are down, it's capitulation (buy).
When bonds rally and stocks rally, it's risk-on (buy trend).

This combines:
1. VIX regime (structural vol premium)
2. Cross-asset flow (bond/equity divergence = signal)
3. IBS timing (enter at oversold intraday levels)
"""

import yfinance as yf
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# Download VIX + assets
print("Downloading data...")
assets = {}
for t in ['QQQ', 'SPY', 'IWM', 'GLD', 'TLT', 'XLF', 'XLV', 'XLI', 'XLE', 'XLK', 'XLU']:
    d = yf.download(t, start='2010-01-01', end='2025-12-31', progress=False)
    if hasattr(d.columns, 'get_level_values'):
        d.columns = d.columns.get_level_values(0)
    if len(d) > 2000:
        df = d[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
        df['Ret'] = df['Close'].pct_change()
        df['Range'] = df['High'] - df['Low']
        df['IBS'] = np.where(df['Range'] > 0, (df['Close'] - df['Low']) / df['Range'], 0.5)
        assets[t] = df

# Download VIX
vix = yf.download('^VIX', start='2010-01-01', end='2025-12-31', progress=False)
if hasattr(vix.columns, 'get_level_values'):
    vix.columns = vix.columns.get_level_values(0)
vix['Ret'] = vix['Close'].pct_change()
vix['SMA10'] = vix['Close'].rolling(10).mean()
vix['SMA20'] = vix['Close'].rolling(20).mean()
vix['High20'] = vix['High'].rolling(20).max()
vix['Low20'] = vix['Low'].rolling(20).min()

QQ = assets['QQQ']
common = QQ.index.intersection(vix.index)
QQ = QQ.loc[common].copy()
V = vix.loc[common].copy()
QQ['SMA50'] = QQ['Close'].rolling(50).mean()
QQ['SMA200'] = QQ['Close'].rolling(200).mean()

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

results = []
def add(name, eq):
    s, d, c = metrics(eq)
    results.append((name, s, d, c))
    if s > 0.8:
        print(f"  {name:<50} Sharpe {s:.2f}  DD {d:.1f}%  CAGR {c:.1f}%")

# ============================================================
# 1. VIX REGIME SIGNALS
# ============================================================
print()
print("=" * 70)
print("1. VIX REGIME")
print("=" * 70)

# VIX regime: elevated and falling = buy stocks
V['VIX_falling'] = V['Close'] < V['SMA10']
V['VIX_low'] = V['Close'] < V['SMA20']
V['VIX_spike'] = V['Close'] > V['High20'].shift(1)  # new 20d high
V['VIX_rollover'] = (V['VIX_spike'].rolling(5).sum() > 0) & (V['Close'] < V['Close'].shift(1))

# Strategy: buy QQQ when VIX is elevated (>20) and falling
for vix_level in [15, 18, 20, 22, 25]:
    sig = ((V['Close'].shift(1) > vix_level) & V['VIX_falling'].shift(1)).astype(int)
    add(f'VIX>{vix_level}+Falling', run(sig, QQ['Close']))

# Buy when VIX drops from spike
for lookback in [5, 10, 20]:
    vix_drop = V['Close'] / V['Close'].rolling(lookback).max() - 1
    sig = (vix_drop.shift(1) < -0.10).astype(int)  # VIX dropped >10%
    add(f'VIX_Drop>{lookback}d_10pct', run(sig, QQ['Close']))

# ============================================================
# 2. CROSS-ASSET FLOW (Bond-Stock divergence)
# ============================================================
print()
print("=" * 70)
print("2. CROSS-ASSET FLOW")
print("=" * 70)

T = assets['TLT']
common2 = QQ.index.intersection(T.index)
QQ2 = QQ.loc[common2]; T2 = T.loc[common2]; V2 = V.loc[common2]

# Bond-stock divergence: both down = capitulation buy
QQ_ret5 = QQ2['Close'] / QQ2['Close'].shift(5) - 1
T_ret5 = T2['Close'] / T2['Close'].shift(5) - 1

# Capitulation: stocks down AND bonds down (liquidity crisis)
for thr in [-0.02, -0.03, -0.05]:
    capi = (QQ_ret5.shift(1) < thr) & (T_ret5.shift(1) < thr)
    add(f'Capitulation_QQQ+TLT<{thr*100:.0f}%', run(capi.astype(int), QQ2['Close']))

# Risk-on: both up
for thr in [0.02, 0.03, 0.05]:
    riskon = (QQ_ret5.shift(1) > thr) & (T_ret5.shift(1) > thr)
    add(f'RiskOn_QQQ+TLT>{thr*100:.0f}%', run(riskon.astype(int), QQ2['Close']))

# Divergence: stocks down but bonds up (flight to quality -> buy stocks)
for thr in [-0.02, -0.03]:
    div = (QQ_ret5.shift(1) < thr) & (T_ret5.shift(1) > abs(thr))
    add(f'DivStocksDown_BondsUp{thr*100:.0f}%', run(div.astype(int), QQ2['Close']))

# ============================================================
# 3. MULTI-ASSET IBS (spillover)
# ============================================================
print()
print("=" * 70)
print("3. MULTI-ASSET IBS")
print("=" * 70)

# When VXX is down hard + QQQ IBS low = double signal
if 'VXX' in assets:
    VX = assets['VXX']
    common3 = QQ.index.intersection(VX.index).intersection(V.index)
    QQ3 = QQ.loc[common3]; VX3 = VX.loc[common3]; V3 = V.loc[common3]
    
    vxx_down = VX3['Close'] < VX3['Close'].rolling(5).mean()
    for ibs_thr in [0.15, 0.20, 0.25, 0.30]:
        sig = (vxx_down.shift(1) & (QQ3['IBS'].shift(1) < ibs_thr)).astype(int)
        add(f'VXX_Down+QQQ_IBS<{ibs_thr}', run(sig, QQ3['Close']))

# When gold is up (risk-off) + stocks oversold = buy
G = assets['GLD']
common4 = QQ.index.intersection(G.index)
QQ4 = QQ.loc[common4]; G4 = G.loc[common4]
gold_up = G4['Close'] > G4['Close'].rolling(20).mean()
for ibs_thr in [0.20, 0.25, 0.30]:
    sig = (gold_up.shift(1) & (QQ4['IBS'].shift(1) < ibs_thr)).astype(int)
    add(f'Gold_Up+QQQ_IBS<{ibs_thr}', run(sig, QQ4['Close']))

# ============================================================
# 4. VIX + IBS COMBO (the core unique edge)
# ============================================================
print()
print("=" * 70)
print("4. VIX + IBS COMBO")
print("=" * 70)

# The idea: when VIX is HIGH and ROLLING OVER, and IBS is LOW,
# it's the perfect storm for a bounce
for vix_level in [18, 20, 22, 25, 30]:
    for ibs_thr in [0.15, 0.20, 0.25, 0.30, 0.35]:
        vix_high_rollover = (V['Close'].shift(1) > vix_level) & (V['Close'].shift(1) < V['SMA10'].shift(1))
        ibs_low = QQ['IBS'].shift(1) < ibs_thr
        sig = (vix_high_rollover & ibs_low).astype(int)
        add(f'VIX>{vix_level}_Rol+IBS<{ibs_thr}', run(sig, QQ['Close']))

# ============================================================
# 5. VOL CLUSTERING BREAKOUT
# ============================================================
print()
print("=" * 70)
print("5. VOL CLUSTERING")
print("=" * 70)

# When VIX is in a tight range (low vol), breakout is coming
# Buy before breakout (or sell after)
QQ['RealVol10'] = QQ['Ret'].rolling(10).std() * np.sqrt(252)
QQ['RealVol5'] = QQ['Ret'].rolling(5).std() * np.sqrt(252)
QQ['VolCompression'] = QQ['RealVol10'] / QQ['RealVol5']

# When vol compresses, breakout coming — go with trend
for comp_thr in [1.5, 2.0, 2.5]:
    sig = (QQ['VolCompression'].shift(1) > comp_thr) & (QQ['Close'].shift(1) > QQ['Close'].rolling(50).mean().shift(1))
    add(f'VolComp>{comp_thr}+Uptrend', run(sig.astype(int), QQ['Close']))

# ============================================================
# 6. MEAN REVERSION ACROSS MULTIPLE TIMEFRAMES
# ============================================================
print()
print("=" * 70)
print("6. MULTI-TIMEFRAME MR")
print("=" * 70)

# Daily oversold + weekly oversold = stronger signal
QQ['Ret5'] = QQ['Close'] / QQ['Close'].shift(5) - 1
QQ['Ret10'] = QQ['Close'] / QQ['Close'].shift(10) - 1
QQ['Ret20'] = QQ['Close'] / QQ['Close'].shift(20) - 1

for d1_thr in [-0.03, -0.05, -0.07]:
    for d5_thr in [-0.02, -0.03, -0.05]:
        sig = ((QQ['Ret'].shift(1) < d1_thr) & (QQ['Ret5'].shift(1) < d5_thr)).astype(int)
        add(f'D1<{d1_thr*100:.0f}+D5<{d5_thr*100:.0f}', run(sig, QQ['Close']))

# ============================================================
# 7. INSTITUTIONAL FLOW PROXY
# ============================================================
print()
print("=" * 70)
print("7. INSTITUTIONAL FLOW PROXY")
print("=" * 70)

# High volume + narrow range = accumulation (institutional buying)
QQ['VolRank'] = QQ['Volume'].rolling(20).apply(lambda x: pd.Series(x).rank().iloc[-1] / len(x))
QQ['RangeRank'] = QQ['Range'].rolling(20).apply(lambda x: pd.Series(x).rank().iloc[-1] / len(x))

# Buy when volume is high but range is narrow (accumulation)
for vol_pct in [0.7, 0.8, 0.9]:
    for range_pct in [0.1, 0.2, 0.3]:
        sig = ((QQ['VolRank'].shift(1) > vol_pct) & (QQ['RangeRank'].shift(1) < range_pct) & 
               (QQ['Close'].shift(1) > QQ['SMA50'].shift(1))).astype(int)
        add(f'Accum_V>{vol_pct}_R<{range_pct}', run(sig, QQ['Close']))

# ============================================================
# 8. CROSS-SECTOR ROTATION WITH VIX FILTER
# ============================================================
print()
print("=" * 70)
print("8. SECTOR ROTATION + VIX FILTER")
print("=" * 70)

sectors = ['XLK', 'XLF', 'XLV', 'XLI', 'XLU', 'XLE']
avail = [s for s in sectors if s in assets]

# Monthly: buy worst sector, but only when VIX > 20
common_s = QQ.index
for s in avail:
    common_s = common_s.intersection(assets[s].index)

eq = []; cap = INITIAL; holdings = {}
for i in range(200, len(common_s)):
    dt = common_s[i]
    vix_val = float(V.loc[dt, 'Close']) if dt in V.index else 20
    
    if i > 0 and dt.month != common_s[i-1].month:
        # Sell all
        for t, (sh, ep) in holdings.items():
            p = float(assets[t].loc[dt, 'Close'])
            ca = sh * (ep + p) * COST / 2
            cap += sh * p - ca
        holdings = {}
        
        if vix_val > 20:  # Only enter when VIX elevated
            scores = {}
            for s in avail:
                idx = assets[s].index.get_loc(dt)
                if idx >= 22:
                    mom = float(assets[s]['Close'].iloc[idx] / assets[s]['Close'].iloc[idx-22] - 1)
                    scores[s] = mom
            worst = sorted(scores, key=scores.get)[:2]
            alloc = cap / 2
            for s in worst:
                p = float(assets[s].loc[dt, 'Close'])
                sh = int(alloc / p)
                if sh > 0:
                    ca = sh * p * COST; cap -= sh * p + ca
                    holdings[s] = (sh, p)
    
    val = cap
    for t, (sh, ep) in holdings.items():
        val += sh * float(assets[t].loc[dt, 'Close'])
    eq.append(val)

eq = np.array(eq)
add('SectorRot_VIX>20', eq)

# ============================================================
# 9. ADAPTIVE IBS THRESHOLD
# ============================================================
print()
print("=" * 70)
print("9. ADAPTIVE IBS")
print("=" * 70)

# In high VIX: lower IBS threshold (more selective)
# In low VIX: higher IBS threshold (more trades)
for hi_vix in [20, 25, 30]:
    ibs_thr = pd.Series(0.25, index=QQ.index)
    ibs_thr[V['Close'] > hi_vix] = 0.35
    ibs_thr[V['Close'] > hi_vix + 5] = 0.40
    ibs_thr[V['Close'] < 15] = 0.15
    
    sig = (QQ['IBS'].shift(1) < ibs_thr.shift(1)).astype(int)
    add(f'AdaptiveIBS_VIX>{hi_vix}', run(sig, QQ['Close']))

# ============================================================
# 10. COMBINE EVERYTHING (the kitchen sink)
# ============================================================
print()
print("=" * 70)
print("10. KITCHEN SINK COMBO")
print("=" * 70)

# Multiple independent signals, all must agree
for n_signals in [2, 3, 4]:
    signal_sets = []
    
    # Signal 1: IBS low
    s1 = QQ['IBS'].shift(1) < 0.25
    
    # Signal 2: VIX elevated and falling
    s2 = (V['Close'].shift(1) > 18) & V['VIX_falling'].shift(1)
    
    # Signal 3: Trend up
    s3 = QQ['Close'].shift(1) > QQ['SMA50'].shift(1)
    
    # Signal 4: Bond-stock divergence (stocks down, bonds not down)
    s4 = (QQ_ret5.shift(1) < -0.02) & (T_ret5.shift(1) > -0.01)
    
    # Signal 5: Volume accumulation
    s5 = (QQ['VolRank'].shift(1) > 0.7) & (QQ['RangeRank'].shift(1) < 0.3)
    
    # Signal 6: Multi-day oversold
    s6 = (QQ['Ret5'].shift(1) < -0.03) & (QQ['Ret'].shift(1) < -0.01)
    
    all_sigs = [s1, s2, s3, s4, s5, s6]
    sig_names = ['IBS<0.25', 'VIX>18+Falling', 'TrendUp', 'Bond-StockDiv', 'Accum', 'MultiD_OB']
    
    from itertools import combinations
    for combo in combinations(range(6), n_signals):
        sig = pd.Series(False, index=QQ.index)
        for idx in combo:
            sig = sig | all_sigs[idx].fillna(False)
        # At least n_signals must be true
        count = sum(all_sigs[idx].fillna(False) for idx in combo)
        sig = (count >= n_signals).astype(int)
        names = '+'.join(sig_names[idx] for idx in combo)
        eq = run(sig, QQ['Close'])
        s, d, c = metrics(eq)
        if s > 0.8:
            add(f'Kitchen({n_sig}={n_signals})_{names}', eq)

# ============================================================
# FINAL RANKINGS
# ============================================================
print()
print("=" * 70)
print("FINAL RANKINGS (top 30)")
print("=" * 70)

results.sort(key=lambda x: x[1], reverse=True)
print(f"  {'#':>3} {'Strategy':<55} {'Sharpe':>7} {'DD%':>7} {'CAGR%':>7}")
print(f"  {'-'*83}")
for i, (name, s, d, c) in enumerate(results[:30]):
    marker = " ***" if s >= 1.3 else ""
    print(f"  {i+1:>3} {name[:55]:<55} {s:>7.2f} {d:>7.1f} {c:>7.1f}{marker}")

hits = sum(1 for _, s, _, _ in results if s >= 1.3)
print(f"\n  Strategies hitting Sharpe >= 1.3: {hits}/{len(results)}")
