"""
BRUTE FORCE — Find Sharpe 1.3
==============================
Test everything: vol targeting, multi-factor, pairs, gap fill,
regime switching, reversal, combined signals
"""

import yfinance as yf
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# DOWNLOAD ALL DATA
# ============================================================
tickers = ['QQQ', 'SPY', 'IWM', 'XLK', 'GLD', 'TLT', 'VXX', 'XLF', 'XLV', 'XLI', 'XLC', 'XLRE', 'XLU', 'XLE']
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
            df['ATR14'] = pd.concat([
                df['High'] - df['Low'],
                (df['High'] - df['Close'].shift(1)).abs(),
                (df['Low'] - df['Close'].shift(1)).abs()
            ], axis=1).max(axis=1).rolling(14).mean()
            df['SMA5'] = df['Close'].rolling(5).mean()
            df['SMA10'] = df['Close'].rolling(10).mean()
            df['SMA20'] = df['Close'].rolling(20).mean()
            df['SMA50'] = df['Close'].rolling(50).mean()
            df['SMA200'] = df['Close'].rolling(200).mean()
            df['EMA5'] = df['Close'].ewm(span=5).mean()
            df['EMA12'] = df['Close'].ewm(span=12).mean()
            df['EMA26'] = df['Close'].ewm(span=26).mean()
            df['Mom5'] = df['Close'] / df['Close'].shift(5) - 1
            df['Mom10'] = df['Close'] / df['Close'].shift(10) - 1
            df['Mom20'] = df['Close'] / df['Close'].shift(20) - 1
            df['RSI14'] = 100 - 100 / (1 + df['Close'].diff().clip(lower=0).rolling(14).mean() /
                                         df['Close'].diff().clip(upper=0).abs().rolling(14).mean())
            df['Gap'] = df['Open'] / df['Close'].shift(1) - 1
            df['Body'] = (df['Close'] - df['Open']) / df['Open']
            df['UpperWick'] = (df['High'] - df[['Open', 'Close']].max(axis=1)) / df['Close']
            df['LowerWick'] = (df[['Open', 'Close']].min(axis=1) - df['Low']) / df['Close']
            df['Ret1'] = df['Close'].pct_change(1)
            df['Ret2'] = df['Close'].pct_change(2)
            df['Ret3'] = df['Close'].pct_change(3)
            df['Ret5'] = df['Close'].pct_change(5)
            df['Ret10'] = df['Close'].pct_change(10)
            df['VolRank20'] = df['Volume'].rolling(20).apply(lambda x: pd.Series(x).rank().iloc[-1] / len(x))
            df['ConsecUp'] = (df['Ret'] > 0).astype(int).rolling(5).sum()
            df['ConsecDn'] = (df['Ret'] < 0).astype(int).rolling(5).sum()
            raw[t] = df
    except:
        pass

print(f"Loaded {len(raw)} instruments: {list(raw.keys())}")

INITIAL = 100000
COST = 0.001

def run_eq(signals, closes, opens=None):
    """Run equity from signal array. signals: 1=long, 0=cash"""
    if opens is None: opens = closes
    cap = INITIAL; pos = 0; entry = 0; eq = []
    for i in range(len(signals)):
        o = float(opens.iloc[i]); c = float(closes.iloc[i])
        sig = int(signals.iloc[i]) if pd.notna(signals.iloc[i]) else 0
        if pos > 0 and sig == 0:
            ca = pos * (entry + o) * COST / 2
            cap += pos * o - ca; pos = 0
        elif pos == 0 and sig == 1:
            sh = int(cap / o)
            if sh > 0:
                ca = sh * o * COST; cap -= sh * o + ca; pos = sh; entry = o
        eq.append(cap + (pos * c if pos > 0 else 0))
    if pos > 0:
        ca = pos * (entry + float(closes.iloc[-1])) * COST / 2
        cap += pos * float(closes.iloc[-1]) - ca
    return np.array(eq)

def run_eq_voltarget(signals, closes, vol, target_vol=0.15, max_lever=2.0, opens=None):
    """Volatility-targeted position sizing"""
    if opens is None: opens = closes
    cap = INITIAL; pos = 0; entry = 0; eq = []
    for i in range(len(signals)):
        o = float(opens.iloc[i]); c = float(closes.iloc[i])
        sig = int(signals.iloc[i]) if pd.notna(signals.iloc[i]) else 0
        v = float(vol.iloc[i]) if pd.notna(vol.iloc[i]) and vol.iloc[i] > 0 else 0.20
        leverage = min(target_vol / v, max_lever) if v > 0 else 1.0
        leverage = max(leverage, 0.1)
        if pos > 0 and sig == 0:
            ca = pos * (entry + o) * COST / 2
            cap += pos * o - ca; pos = 0
        elif pos == 0 and sig == 1:
            sh = int(cap * leverage / o)
            if sh > 0:
                ca = sh * o * COST; cap -= sh * o + ca; pos = sh; entry = o
        eq.append(cap + (pos * c if pos > 0 else 0))
    if pos > 0:
        ca = pos * (entry + float(closes.iloc[-1])) * COST / 2
        cap += pos * float(closes.iloc[-1]) - ca
    return np.array(eq)

def metrics(eq):
    dr = np.diff(eq) / eq[:-1]; dr = dr[np.isfinite(dr)]
    sharpe = (np.mean(dr) / np.std(dr)) * np.sqrt(252) if np.std(dr) > 0 else 0
    pk = np.maximum.accumulate(eq)
    dd = -((pk - eq) / pk).max() * 100
    cagr = ((eq[-1] / eq[0]) ** (252 / max(len(eq), 1)) - 1) * 100
    return sharpe, dd, cagr

# ============================================================
# STORE ALL RESULTS
# ============================================================
all_results = []

def add(name, eq):
    s, d, c = metrics(eq)
    all_results.append((name, s, d, c))

# ============================================================
# 1. VOLATILITY-TARGETED STRATEGIES
# ============================================================
print()
print("=" * 70)
print("1. VOLATILITY-TARGETED")
print("=" * 70)

QQ = raw['QQQ']
# SMA cross with vol targeting
sig = (QQ['SMA50'] > QQ['SMA200']).astype(int).shift(1).fillna(0)
for tv in [0.10, 0.12, 0.15, 0.18, 0.20]:
    for ml in [1.5, 2.0, 3.0]:
        eq = run_eq_voltarget(sig, QQ['Close'], QQ['Vol20'], tv, ml)
        s, d, c = metrics(eq)
        print(f"  SMA50/200 VolTarget({tv},{ml}x) Sharpe {s:.2f}  DD {d:.1f}%")
        add(f"SMA50200_VT({tv},{ml}x)", eq)

# IBS MR with vol targeting
ibs_sig = (QQ['IBS'].shift(1) < 0.2).astype(int)
ibs_sig[QQ['Vol20'] > 0.30] = 0  # skip high vol
for tv in [0.10, 0.12, 0.15, 0.18]:
    for ml in [1.5, 2.0, 3.0]:
        eq = run_eq_voltarget(ibs_sig, QQ['Close'], QQ['Vol20'], tv, ml)
        s, d, c = metrics(eq)
        print(f"  IBS MR VolTarget({tv},{ml}x) Sharpe {s:.2f}  DD {d:.1f}%")
        add(f"IBS_MR_VT({tv},{ml}x)", eq)

# ============================================================
# 2. MULTI-FACTOR SCORING
# ============================================================
print()
print("=" * 70)
print("2. MULTI-FACTOR SCORING")
print("=" * 70)

# Score each day: IBS, momentum, trend, volume, RSI
QQ['Score'] = 0.0
QQ['Score'] += np.where(QQ['IBS'].shift(1) < 0.2, 2,
               np.where(QQ['IBS'].shift(1) < 0.3, 1,
               np.where(QQ['IBS'].shift(1) > 0.8, -2,
               np.where(QQ['IBS'].shift(1) > 0.7, -1, 0))))
QQ['Score'] += np.where(QQ['Mom5'].shift(1) > 0.02, 1,
               np.where(QQ['Mom5'].shift(1) < -0.02, -1, 0))
QQ['Score'] += np.where(QQ['Close'].shift(1) > QQ['SMA50'].shift(1), 1, -1)
QQ['Score'] += np.where(QQ['RSI14'].shift(1) < 30, 1,
               np.where(QQ['RSI14'].shift(1) > 70, -1, 0))
QQ['Score'] += np.where(QQ['VolRank20'].shift(1) < 0.3, 1,
               np.where(QQ['VolRank20'].shift(1) > 0.8, -1, 0))

for threshold in [1, 2, 3, 4]:
    sig = (QQ['Score'] >= threshold).astype(int)
    eq = run_eq(sig, QQ['Close'])
    s, d, c = metrics(eq)
    print(f"  MultiFactor Score>={threshold} Sharpe {s:.2f}  DD {d:.1f}%")
    add(f"MultiFactor>={threshold}", eq)

# ============================================================
# 3. GAP FILL STRATEGIES
# ============================================================
print()
print("=" * 70)
print("3. GAP FILL")
print("=" * 70)

# Buy gap down opens, sell at close (or next open)
QQ['GapDn'] = QQ['Gap'] < -0.005
QQ['GapDn'] = QQ['GapDn'].shift(1).fillna(False)  # signal yesterday

# Strategy: Buy at open after gap down, sell at close
eq = []
cap = INITIAL; pos = 0; entry = 0
for i in range(1, len(QQ)):
    o = float(QQ['Open'].iloc[i]); c = float(QQ['Close'].iloc[i])
    gap = float(QQ['GapDn'].iloc[i-1]) if pd.notna(QQ['GapDn'].iloc[i-1]) else False
    if pos > 0:
        ca = pos * (entry + c) * COST / 2
        cap += pos * c - ca; pos = 0
    elif gap:
        sh = int(cap / o)
        if sh > 0:
            ca = sh * o * COST; cap -= sh * o + ca; pos = sh; entry = o
    eq.append(cap + (pos * c if pos > 0 else 0))
if pos > 0:
    ca = pos * (entry + float(QQ['Close'].iloc[-1])) * COST / 2
    cap += pos * float(QQ['Close'].iloc[-1]) - ca
eq = np.array(eq)
s, d, c = metrics(eq)
print(f"  GapDn->Close Sharpe {s:.2f}  DD {d:.1f}%")
add("GapDn_Close", eq)

# Gap down -> next day open (hold 1 day)
eq = []
cap = INITIAL; pos = 0; entry = 0
for i in range(1, len(QQ)):
    o = float(QQ['Open'].iloc[i]); c = float(QQ['Close'].iloc[i])
    gap = float(QQ['GapDn'].iloc[i-1]) if pd.notna(QQ['GapDn'].iloc[i-1]) else False
    if pos > 0:
        ca = pos * (entry + o) * COST / 2
        cap += pos * o - ca; pos = 0
    elif gap:
        sh = int(cap / o)
        if sh > 0:
            ca = sh * o * COST; cap -= sh * o + ca; pos = sh; entry = o
    eq.append(cap + (pos * c if pos > 0 else 0))
eq = np.array(eq)
s, d, c = metrics(eq)
print(f"  GapDn->NextOpen Sharpe {s:.2f}  DD {d:.1f}%")
add("GapDn_NextOpen", eq)

# Large gap down (< -1%) -> next open
QQ['BigGapDn'] = (QQ['Gap'] < -0.01).shift(1).fillna(False)
eq = []
cap = INITIAL; pos = 0; entry = 0
for i in range(1, len(QQ)):
    o = float(QQ['Open'].iloc[i]); c = float(QQ['Close'].iloc[i])
    gap = float(QQ['BigGapDn'].iloc[i-1]) if pd.notna(QQ['BigGapDn'].iloc[i-1]) else False
    if pos > 0:
        ca = pos * (entry + o) * COST / 2
        cap += pos * o - ca; pos = 0
    elif gap:
        sh = int(cap / o)
        if sh > 0:
            ca = sh * o * COST; cap -= sh * o + ca; pos = sh; entry = o
    eq.append(cap + (pos * c if pos > 0 else 0))
eq = np.array(eq)
s, d, c = metrics(eq)
print(f"  BigGapDn->NextOpen Sharpe {s:.2f}  DD {d:.1f}%")
add("BigGapDn_NextOpen", eq)

# ============================================================
# 4. PAIRS TRADING (Long/Short)
# ============================================================
print()
print("=" * 70)
print("4. PAIRS TRADING (Long/Short)")
print("=" * 70)

# QQQ vs SPY spread
if 'SPY' in raw:
    SP = raw['SPY']
    # Align on common dates
    common = QQ.index.intersection(SP.index)
    qq_c = QQ.loc[common, 'Close']
    sp_c = SP.loc[common, 'Close']
    ratio = qq_c / sp_c
    ratio_ma = ratio.rolling(50).mean()
    ratio_std = ratio.rolling(50).std()
    z = (ratio - ratio_ma) / ratio_std

    # Long QQQ short SPY when spread is low
    eq = []
    cap = INITIAL; pos = 0; entry = 0
    for i in range(1, len(common)):
        z_val = float(z.iloc[i-1]) if pd.notna(z.iloc[i-1]) else 0
        qq_o = float(qq_c.iloc[i]); sp_o = float(sp_c.iloc[i])
        if pos > 0:  # long QQQ, short SPY
            if z_val > 0.5:
                ca = abs(pos) * (entry_q + qq_o) * COST / 2
                ca += abs(pos) * (entry_s + sp_o) * COST / 2  # closing short
                cap += pos * (qq_o - sp_o) - ca; pos = 0
        elif pos < 0:  # short QQQ, long SPY
            if z_val < -0.5:
                ca = abs(pos) * (entry_q + qq_o) * COST / 2
                ca += abs(pos) * (entry_s + sp_o) * COST / 2
                cap += abs(pos) * (sp_o - qq_o) - ca; pos = 0
        else:
            sh = int(cap / qq_o)
            if z_val < -1.0 and sh > 0:  # spread low: long QQQ, short SPY
                ca = sh * qq_o * COST + sh * sp_o * COST
                cap -= ca
                pos = sh; entry_q = qq_o; entry_s = sp_o
            elif z_val > 1.0 and sh > 0:  # spread high: short QQQ, long SPY
                ca = sh * qq_o * COST + sh * sp_o * COST
                cap -= ca
                pos = -sh; entry_q = qq_o; entry_s = sp_o
        if pos > 0:
            eq.append(cap + pos * (qq_o - sp_o))
        elif pos < 0:
            eq.append(cap + abs(pos) * (sp_o - qq_o))
        else:
            eq.append(cap)
    eq = np.array(eq)
    s, d, c = metrics(eq)
    print(f"  QQQ/SPY Pair z-score Sharpe {s:.2f}  DD {d:.1f}%")
    add("QQQ_SPY_Pair", eq)

# ============================================================
# 5. REGIME SWITCHING
# ============================================================
print()
print("=" * 70)
print("5. REGIME SWITCHING")
print("=" * 70)

# Risk-on: QQQ. Risk-off: TLT. Use SMA200 for regime.
QQ['Regime'] = np.where(QQ['Close'] > QQ['SMA200'], 1, 0)
QQ['Regime'] = QQ['Regime'].shift(1).fillna(0)

# Strategy: QQQ when risk-on, TLT when risk-off
if 'TLT' in raw:
    T = raw['TLT']
    common2 = QQ.index.intersection(T.index)
    eq = []
    cap = INITIAL; pos_q = 0; pos_t = 0; eq_q = 0; eq_t = 0
    for i in range(1, len(common2)):
        qq_o = float(QQ.loc[common2[i], 'Open']); qq_c = float(QQ.loc[common2[i], 'Close'])
        t_o = float(T.loc[common2[i], 'Open']); t_c = float(T.loc[common2[i], 'Close'])
        regime = int(QQ.loc[common2[i], 'Regime']) if pd.notna(QQ.loc[common2[i], 'Regime']) else 0

        # Exit current positions
        if pos_q > 0:
            ca = pos_q * (eq_q + qq_o) * COST / 2
            cap += pos_q * qq_o - ca; pos_q = 0
        elif pos_q < 0:
            ca = abs(pos_q) * (eq_q + qq_o) * COST / 2
            cap += abs(pos_q) * (2 * eq_q - qq_o) - ca; pos_q = 0  # short P&L
        if pos_t > 0:
            ca = pos_t * (eq_t + t_o) * COST / 2
            cap += pos_t * t_o - ca; pos_t = 0

        # Enter new positions
        if regime == 1:  # risk-on: long QQQ
            sh = int(cap / qq_o)
            if sh > 0:
                ca = sh * qq_o * COST; cap -= sh * qq_o + ca; pos_q = sh; eq_q = qq_o
        else:  # risk-off: long TLT
            sh = int(cap / t_o)
            if sh > 0:
                ca = sh * t_o * COST; cap -= sh * t_o + ca; pos_t = sh; eq_t = t_o

        val = cap
        if pos_q > 0: val += pos_q * qq_c
        if pos_t > 0: val += pos_t * t_c
        eq.append(val)
    if pos_q > 0:
        ca = pos_q * (eq_q + float(QQ.loc[common2[-1], 'Close'])) * COST / 2
        cap += pos_q * float(QQ.loc[common2[-1], 'Close']) - ca
    if pos_t > 0:
        ca = pos_t * (eq_t + float(T.loc[common2[-1], 'Close'])) * COST / 2
        cap += pos_t * float(T.loc[common2[-1], 'Close']) - ca
    eq = np.array(eq)
    s, d, c = metrics(eq)
    print(f"  Regime QQQ/TLT Sharpe {s:.2f}  DD {d:.1f}%")
    add("Regime_QQQ_TLT", eq)

# ============================================================
# 6. SHORT-TERM REVERSAL
# ============================================================
print()
print("=" * 70)
print("6. SHORT-TERM REVERSAL")
print("=" * 70)

# Buy after N consecutive down days
for n in [2, 3, 4, 5]:
    for hold in [1, 2, 3, 5]:
        consec = (QQ['Ret'] < 0).astype(int).rolling(n).sum()
        sig = (consec.shift(1) >= n).astype(int)
        # Sell after hold days
        sell_at = sig.copy()
        for i in range(len(sig)):
            if sig.iloc[i] == 1:
                end = min(i + hold, len(sig) - 1)
                sig.iloc[i:end] = 0
                sig.iloc[end] = 0
        eq = run_eq(sig, QQ['Close'])
        s, d, c = metrics(eq)
        if s > 0.5:
            print(f"  Rev {n}dn Hold{hold} Sharpe {s:.2f}  DD {d:.1f}%")
            add(f"Rev{n}dn_H{hold}", eq)

# ============================================================
# 7. CONSECUTIVE UP/DOWN with volume
# ============================================================
print()
print("=" * 70)
print("7. CONSECUTIVE + VOLUME")
print("=" * 70)

for n in [3, 4, 5]:
    up = (QQ['Ret'] > 0).astype(int).rolling(n).sum()
    sig_up = (up.shift(1) >= n).astype(int)  # buy after N up days (reversal)
    dn = (QQ['Ret'] < 0).astype(int).rolling(n).sum()
    sig_dn = (dn.shift(1) >= n).astype(int)  # buy after N down days

    eq_up = run_eq(sig_up, QQ['Close'])
    s, d, c = metrics(eq_up)
    print(f"  {n} ConsecUp->Sell Sharpe {s:.2f}  DD {d:.1f}%")
    add(f"ConsecUp{n}", eq_up)

    eq_dn = run_eq(sig_dn, QQ['Close'])
    s, d, c = metrics(eq_dn)
    print(f"  {n} ConsecDn->Buy  Sharpe {s:.2f}  DD {d:.1f}%")
    add(f"ConsecDn{n}", eq_dn)

# With low volume filter
for n in [3, 4, 5]:
    dn = (QQ['Ret'] < 0).astype(int).rolling(n).sum()
    low_vol = QQ['VolRank20'] < 0.4
    sig = ((dn.shift(1) >= n) & low_vol.shift(1)).astype(int)
    eq = run_eq(sig, QQ['Close'])
    s, d, c = metrics(eq)
    print(f"  {n} ConsecDn+LowVol Sharpe {s:.2f}  DD {d:.1f}%")
    add(f"ConsecDn{n}_LowVol", eq)

# ============================================================
# 8. MEAN REVERSION BANDS
# ============================================================
print()
print("=" * 70)
print("8. MEAN REVERSION BANDS")
print("=" * 70)

QQ['Mid'] = QQ['Close'].rolling(20).mean()
QQ['Std20'] = QQ['Close'].rolling(20).std()
QQ['Lower'] = QQ['Mid'] - 2 * QQ['Std20']
QQ['Upper'] = QQ['Mid'] + 2 * QQ['Std20']
QQ['Z20'] = (QQ['Close'] - QQ['Mid']) / QQ['Std20']

# Buy when Z < -2, sell when Z > 0
eq = []; cap = INITIAL; pos = 0; entry = 0
for i in range(1, len(QQ)):
    z = float(QQ['Z20'].iloc[i-1]) if pd.notna(QQ['Z20'].iloc[i-1]) else 0
    o = float(QQ['Open'].iloc[i]); c = float(QQ['Close'].iloc[i])
    if pos > 0 and z > 0:
        ca = pos * (entry + o) * COST / 2
        cap += pos * o - ca; pos = 0
    elif pos == 0 and z < -2:
        sh = int(cap / o)
        if sh > 0:
            ca = sh * o * COST; cap -= sh * o + ca; pos = sh; entry = o
    eq.append(cap + (pos * c if pos > 0 else 0))
if pos > 0:
    ca = pos * (entry + float(QQ['Close'].iloc[-1])) * COST / 2
    cap += pos * float(QQ['Close'].iloc[-1]) - ca
eq = np.array(eq)
s, d, c = metrics(eq)
print(f"  Z20 MeanReversion (buy<-2, sell>0) Sharpe {s:.2f}  DD {d:.1f}%")
add("MR_Z20_-2_0", eq)

# Buy when Z < -1.5, sell when Z > 0.5
eq = []; cap = INITIAL; pos = 0; entry = 0
for i in range(1, len(QQ)):
    z = float(QQ['Z20'].iloc[i-1]) if pd.notna(QQ['Z20'].iloc[i-1]) else 0
    o = float(QQ['Open'].iloc[i]); c = float(QQ['Close'].iloc[i])
    if pos > 0 and z > 0.5:
        ca = pos * (entry + o) * COST / 2
        cap += pos * o - ca; pos = 0
    elif pos == 0 and z < -1.5:
        sh = int(cap / o)
        if sh > 0:
            ca = sh * o * COST; cap -= sh * o + ca; pos = sh; entry = o
    eq.append(cap + (pos * c if pos > 0 else 0))
eq = np.array(eq)
s, d, c = metrics(eq)
print(f"  Z20 MeanReversion (buy<-1.5, sell>0.5) Sharpe {s:.2f}  DD {d:.1f}%")
add("MR_Z20_-1.5_0.5", eq)

# ============================================================
# 9. MULTI-ASSET MOMENTUM + MEAN REVERSION COMBO
# ============================================================
print()
print("=" * 70)
print("9. ASSET ROTATION + MR OVERLAY")
print("=" * 70)

# Each month: pick top 2 momentum assets, apply IBS filter
assets = ['QQQ', 'SPY', 'IWM', 'XLK', 'GLD', 'TLT']
available = [a for a in assets if a in raw]
print(f"  Available: {available}")

for n_assets in [2, 3]:
    eq = []
    cap = INITIAL
    portfolio = {}  # {ticker: (shares, entry_price)}
    
    for i in range(200, len(QQ)):
        dt = QQ.index[i]
        o = float(QQ['Open'].iloc[i]); c = float(QQ['Close'].iloc[i])
        
        # Monthly rebalance: 1st of month
        if i > 0 and QQ.index[i].month != QQ.index[i-1].month:
            # Score assets: momentum + IBS
            scores = {}
            for a in available:
                adf = raw[a]
                if dt in adf.index:
                    idx = adf.index.get_loc(dt)
                    if idx >= 20:
                        mom = float(adf['Close'].iloc[idx] / adf['Close'].iloc[idx-20] - 1)
                        ibs = float(adf['IBS'].iloc[idx]) if pd.notna(adf['IBS'].iloc[idx]) else 0.5
                        vol = float(adf['Vol20'].iloc[idx]) if pd.notna(adf['Vol20'].iloc[idx]) and adf['Vol20'].iloc[idx] > 0 else 0.20
                        # Score: high mom, low IBS, low vol
                        sc = mom * 2 - ibs * 0.5 - vol * 0.5
                        scores[a] = sc
            
            if scores:
                top = sorted(scores, key=scores.get, reverse=True)[:n_assets]
                # Sell current holdings
                for t, (sh, ep) in portfolio.items():
                    if t in raw and dt in raw[t].index:
                        sell_p = float(raw[t].loc[dt, 'Close'])
                        ca = sh * (ep + sell_p) * COST / 2
                        cap += sh * sell_p - ca
                portfolio = {}
                # Buy new
                alloc = cap / n_assets
                for t in top:
                    if t in raw and dt in raw[t].index:
                        buy_p = float(raw[t].loc[dt, 'Close'])
                        sh = int(alloc / buy_p)
                        if sh > 0:
                            ca = sh * buy_p * COST
                            cap -= sh * buy_p + ca
                            portfolio[t] = (sh, buy_p)
        
        # Track portfolio value
        val = cap
        for t, (sh, ep) in portfolio.items():
            if t in raw and dt in raw[t].index:
                val += sh * float(raw[t].loc[dt, 'Close'])
        eq.append(val)
    
    # Close remaining
    for t, (sh, ep) in portfolio.items():
        sell_p = float(raw[t].loc[QQ.index[-1], 'Close'])
        ca = sh * (ep + sell_p) * COST / 2
        cap += sh * sell_p - ca
    
    eq = np.array(eq)
    s, d, c = metrics(eq)
    print(f"  Top {n_assets} Rotation+MR Sharpe {s:.2f}  DD {d:.1f}%")
    add(f"Top{n_assets}_Rotation", eq)

# ============================================================
# 10. BEST DAILY STRATEGIES ACROSS ALL INSTRUMENTS
# ============================================================
print()
print("=" * 70)
print("10. BEST PER-INSTRUMENT STRATEGIES")
print("=" * 70)

# IBS MR on each instrument
for t in raw:
    df = raw[t]
    for ibs_thr in [0.15, 0.20, 0.25]:
        for hold in [3, 5, 7, 10]:
            sig = (df['IBS'].shift(1) < ibs_thr).astype(int)
            # Apply hold period
            sig_held = sig.copy()
            in_trade = 0
            for i in range(len(sig)):
                if sig.iloc[i] == 1 and in_trade == 0:
                    in_trade = hold
                elif in_trade > 0:
                    sig_held.iloc[i] = 1
                    in_trade -= 1
                else:
                    sig_held.iloc[i] = 0
            sig_held = sig_held.shift(1).fillna(0)
            eq = run_eq(sig_held, df['Close'])
            s, d, c = metrics(eq)
            if s > 0.8:
                print(f"  {t} IBS<{ibs_thr} H{hold} Sharpe {s:.2f}  DD {d:.1f}%")
                add(f"{t}_IBS{ibs_thr}_H{hold}", eq)

# ============================================================
# FINAL RANKINGS
# ============================================================
print()
print("=" * 70)
print("FINAL RANKINGS (top 30)")
print("=" * 70)
print()

all_results.sort(key=lambda x: x[1], reverse=True)
print(f"  {'#':>3} {'Strategy':<35} {'Sharpe':>7} {'DD%':>7} {'CAGR%':>7}")
print(f"  {'-'*63}")
for i, (name, s, d, c) in enumerate(all_results[:30]):
    marker = " ***" if s >= 1.3 else ""
    print(f"  {i+1:>3} {name:<35} {s:>7.2f} {d:>7.1f} {c:>7.1f}{marker}")

# Count how many hit 1.3
hits = sum(1 for _, s, _, _ in all_results if s >= 1.3)
print(f"\n  Strategies hitting Sharpe >= 1.3: {hits}/{len(all_results)}")
