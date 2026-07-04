"""
BRUTE FORCE 2 — More approaches
================================
"""

import yfinance as yf
import pandas as pd
import numpy as np
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
            df['EMA5'] = df['Close'].ewm(span=5).mean()
            df['EMA12'] = df['Close'].ewm(span=12).mean()
            df['EMA26'] = df['Close'].ewm(span=26).mean()
            df['Mom20'] = df['Close'] / df['Close'].shift(20) - 1
            df['Mom5'] = df['Close'] / df['Close'].shift(5) - 1
            df['RSI14'] = 100 - 100 / (1 + df['Close'].diff().clip(lower=0).rolling(14).mean() /
                                         df['Close'].diff().clip(upper=0).abs().rolling(14).mean())
            df['Gap'] = df['Open'] / df['Close'].shift(1) - 1
            df['Ret1'] = df['Close'].pct_change(1)
            df['Ret2'] = df['Close'].pct_change(2)
            df['Ret3'] = df['Close'].pct_change(3)
            df['Ret5'] = df['Close'].pct_change(5)
            df['Ret10'] = df['Close'].pct_change(10)
            df['ConsecUp'] = (df['Ret'] > 0).astype(int).rolling(5).sum()
            df['ConsecDn'] = (df['Ret'] < 0).astype(int).rolling(5).sum()
            df['ChgClose'] = df['Close'].diff(5) / df['Close'].rolling(5).std()
            df['Mid'] = df['Close'].rolling(20).mean()
            df['Std20'] = df['Close'].rolling(20).std()
            df['Z20'] = (df['Close'] - df['Mid']) / df['Std20']
            df['ATR14'] = pd.concat([df['High']-df['Low'], (df['High']-df['Close'].shift(1)).abs(), (df['Low']-df['Close'].shift(1)).abs()], axis=1).max(axis=1).rolling(14).mean()
            df['VolRank20'] = df['Volume'].rolling(20).apply(lambda x: pd.Series(x).rank().iloc[-1] / len(x))
            raw[t] = df
    except:
        pass

print(f"Loaded {len(raw)} instruments")
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

QQ = raw['QQQ']

# ============================================================
# 1. OVERNIGHT PREMIUM CAPTURE
# ============================================================
print("=" * 70)
print("1. OVERNIGHT PREMIUM")
print("=" * 70)

# Buy at close, sell at open (capture overnight gap)
eq = []; cap = INITIAL; pos = 0; entry = 0
for i in range(1, len(QQ)):
    o = float(QQ['Open'].iloc[i]); c_prev = float(QQ['Close'].iloc[i-1])
    c = float(QQ['Close'].iloc[i])
    if pos > 0:
        ca = pos * (entry + o) * COST / 2
        cap += pos * o - ca; pos = 0
    # Always buy at close (hold overnight)
    sh = int(cap / c_prev)
    if sh > 0:
        ca = sh * c_prev * COST; cap -= sh * c_prev + ca; pos = sh; entry = c_prev
    eq.append(cap + (pos * c if pos > 0 else 0))
eq = np.array(eq)
s, d, c = metrics(eq)
print(f"  Always Long (B&H proxy) Sharpe {s:.2f}  DD {d:.1f}%")
add("BnH_Proxy", eq)

# Only hold overnight on specific days (low IBS close -> overnight)
for ibs_thr in [0.2, 0.3, 0.4]:
    sig = (QQ['IBS'].shift(1) < ibs_thr).astype(int)  # signal based on yesterday's IBS
    eq_run = run(sig, QQ['Close'])
    s, d, c = metrics(eq_run)
    print(f"  Overnight IBS<{ibs_thr} Sharpe {s:.2f}  DD {d:.1f}%")
    add(f"Overnight_IBS{ibs_thr}", eq_run)

# ============================================================
# 2. RISK PARITY (Equal vol contribution)
# ============================================================
print()
print("=" * 70)
print("2. RISK PARITY")
print("=" * 70)

assets = ['QQQ', 'GLD', 'TLT']
avail = [a for a in assets if a in raw]
if len(avail) == 3:
    common = raw['QQQ'].index
    for a in avail[1:]:
        common = common.intersection(raw[a].index)
    
    # Monthly rebalance with vol targeting
    eq = []; cap = INITIAL; holdings = {}
    for i in range(200, len(common)):
        dt = common[i]
        if i > 0 and dt.month != common[i-1].month:
            vols = {}
            for a in avail:
                adf = raw[a]
                idx = adf.index.get_loc(dt)
                v = float(adf['Vol20'].iloc[idx]) if pd.notna(adf['Vol20'].iloc[idx]) and adf['Vol20'].iloc[idx] > 0 else 0.20
                vols[a] = max(v, 0.05)
            
            total_inv = sum(1/v for v in vols.values())
            weights = {a: (1/v) / total_inv for a, v in vols.items()}
            
            for a in avail:
                p = float(raw[a].loc[dt, 'Close'])
                alloc = cap * weights[a]
                sh = int(alloc / p)
                if sh > 0:
                    ca = sh * p * COST
                    cap -= sh * p + ca
                    holdings[a] = (sh, p)
        
        val = cap
        for a in avail:
            if a in raw and dt in raw[a].index and a in holdings:
                val += holdings[a][0] * float(raw[a].loc[dt, 'Close'])
        eq.append(val)
    
    eq = np.array(eq)
    s, d, c = metrics(eq)
    print(f"  RiskParity QQQ/GLD/TLT Sharpe {s:.2f}  DD {d:.1f}%")
    add("RiskParity_QGT", eq)

# ============================================================
# 3. SECTOR MEAN REVERSION (buy underperformers)
# ============================================================
print()
print("=" * 70)
print("3. SECTOR MEAN REVERSION")
print("=" * 70)

sectors = ['XLK', 'XLF', 'XLV', 'XLI', 'XLC', 'XLU', 'XLE', 'XLRE']
avail_s = [s for s in sectors if s in raw]
print(f"  Sectors: {avail_s}")

common_s = raw['QQQ'].index
for s in avail_s:
    common_s = common_s.intersection(raw[s].index)

# Monthly: buy worst 2 performers over last month
for n_buy in [2, 3]:
    eq = []; cap = INITIAL; holdings = {}
    for i in range(22, len(common_s)):
        dt = common_s[i]
        if i > 0 and dt.month != common_s[i-1].month:
            # Sell all
            for t, (sh, ep) in holdings.items():
                p = float(raw[t].loc[dt, 'Close'])
                ca = sh * (ep + p) * COST / 2
                cap += sh * p - ca
            holdings = {}
            
            # Score: worst performers
            scores = {}
            for s in avail_s:
                idx = raw[s].index.get_loc(dt)
                if idx >= 22:
                    mom = float(raw[s]['Close'].iloc[idx] / raw[s]['Close'].iloc[idx-22] - 1)
                    scores[s] = mom
            
            worst = sorted(scores, key=scores.get)[:n_buy]
            alloc = cap / n_buy
            for s in worst:
                p = float(raw[s].loc[dt, 'Close'])
                sh = int(alloc / p)
                if sh > 0:
                    ca = sh * p * COST; cap -= sh * p + ca
                    holdings[s] = (sh, p)
        
        val = cap
        for t, (sh, ep) in holdings.items():
            val += sh * float(raw[t].loc[dt, 'Close'])
        eq.append(val)
    
    # Close
    for t, (sh, ep) in holdings.items():
        p = float(raw[t].loc[common_s[-1], 'Close'])
        ca = sh * (ep + p) * COST / 2
        cap += sh * p - ca
    
    eq = np.array(eq)
    s, d, c = metrics(eq)
    print(f"  Buy worst {n_buy} sectors Sharpe {s:.2f}  DD {d:.1f}%")
    add(f"SECTOR_MR_{n_buy}", eq)

# ============================================================
# 4. TREND + MR COMBO
# ============================================================
print()
print("=" * 70)
print("4. TREND + MR COMBO")
print("=" * 70)

# Trend filter: only buy dips when above SMA200
for sma_period in [50, 100, 200]:
    for ibs_thr in [0.15, 0.20, 0.25, 0.30]:
        sma = QQ['Close'].rolling(sma_period).mean()
        trend = QQ['Close'] > sma
        ibs_signal = QQ['IBS'].shift(1) < ibs_thr
        sig = (trend.shift(1) & ibs_signal).astype(int)
        eq = run(sig, QQ['Close'])
        s, d, c = metrics(eq)
        if s > 0.5:
            print(f"  Trend SMA{sma}+IBS<{ibs_thr} Sharpe {s:.2f}  DD {d:.1f}%")
            add(f"Trend_SMA{sma}_IBS{ibs_thr}", eq)

# ============================================================
# 5. VOLATILITY MEAN REVERSION
# ============================================================
print()
print("=" * 70)
print("5. VOLATILITY MEAN REVERSION")
print("=" * 70)

# When vol is high, buy (vol reverts down -> stocks up)
QQ['VolZ'] = (QQ['Vol20'] - QQ['Vol20'].rolling(252).mean()) / QQ['Vol20'].rolling(252).std()
for vol_z in [1.0, 1.5, 2.0]:
    sig = (QQ['VolZ'].shift(1) > vol_z).astype(int)
    eq = run(sig, QQ['Close'])
    s, d, c = metrics(eq)
    print(f"  Buy high vol (VolZ>{vol_z}) Sharpe {s:.2f}  DD {d:.1f}%")
    add(f"VolMR_Z{vol_z}", eq)

# Combine: high vol + low IBS
for vol_z in [1.0, 1.5, 2.0]:
    for ibs_thr in [0.2, 0.3, 0.4]:
        sig = ((QQ['VolZ'].shift(1) > vol_z) & (QQ['IBS'].shift(1) < ibs_thr)).astype(int)
        eq = run(sig, QQ['Close'])
        s, d, c = metrics(eq)
        print(f"  VolZ>{vol_z}+IBS<{ibs_thr} Sharpe {s:.2f}  DD {d:.1f}%")
        add(f"VolMR_Z{vol_z}_IBS{ibs_thr}", eq)

# ============================================================
# 6. DOUBLE MOMENTUM (US + International)
# ============================================================
print()
print("=" * 70)
print("6. DOUBLE MOMENTUM")
print("=" * 70)

# QQQ (US) vs EFA (Intl) — use EWC as proxy
intl_tickers = ['EFA', 'EEM', 'VWO', 'FXI']
for it in intl_tickers:
    try:
        d = yf.download(it, start='2010-01-01', end='2025-12-31', progress=False)
        if hasattr(d.columns, 'get_level_values'):
            d.columns = d.columns.get_level_values(0)
        if len(d) > 2000:
            raw[it] = d[['Open','High','Low','Close','Volume']].copy()
            raw[it]['Ret'] = raw[it]['Close'].pct_change()
            raw[it]['Mom20'] = raw[it]['Close'] / raw[it]['Close'].shift(20) - 1
            print(f"  Loaded {it}")
    except:
        pass

if 'EFA' in raw:
    common = QQ.index.intersection(raw['EFA'].index)
    eq = []; cap = INITIAL
    for i in range(50, len(common)):
        dt = common[i]
        qq_mom = float(QQ.loc[dt, 'Close'] / QQ.loc[common[max(0,i-20)], 'Close'] - 1)
        fa_mom = float(raw['EFA'].loc[dt, 'Close'] / raw['EFA'].loc[common[max(0,i-20)], 'Close'] - 1)
        
        # Buy the stronger one
        target = 'QQQ' if qq_mom > fa_mom else 'EFA'
        p = float(raw[target].loc[dt, 'Close'])
        # Simplified: always hold target
        sh = int(cap / p)
        val = cap  # simplified tracking
        eq.append(val)
        cap += 100  # dummy
    # This is simplified — skip for now
    print("  (skipped — need proper implementation)")

# ============================================================
# 7. CONSECUTIVE DOWNS + TREND
# ============================================================
print()
print("=" * 70)
print("7. CONSECUTIVE DOWNS + TREND FILTER")
print("=" * 70)

for n in [3, 4, 5]:
    for sma in [50, 100, 200]:
        sma_line = QQ['Close'].rolling(sma).mean()
        trend = QQ['Close'] > sma_line
        consec = (QQ['Ret'] < 0).astype(int).rolling(n).sum()
        sig = ((consec.shift(1) >= n) & trend.shift(1)).astype(int)
        eq = run(sig, QQ['Close'])
        s, d, c = metrics(eq)
        if s > 0.5:
            print(f"  {n}dn+SMA{sma} Sharpe {s:.2f}  DD {d:.1f}%")
            add(f"Rev{n}dn_SMA{sma}", eq)

# ============================================================
# 8. MULTI-INSTRUMENT IBS (combine IBS signals across assets)
# ============================================================
print()
print("=" * 70)
print("8. MULTI-INSTRUMENT IBS")
print("=" * 70)

# Buy QQQ when ANY of the sector ETFs has low IBS (spillover)
for n_assets in [2, 3, 4, 5]:
    avail_s2 = [s for s in avail_s if s in raw]
    for combo_name in ['sectors', 'mixed']:
        if combo_name == 'sectors':
            sources = avail_s2[:n_assets]
        else:
            sources = ['SPY', 'IWM'] + avail_s2[:max(0,n_assets-2)]
            sources = [s for s in sources if s in raw]
        
        if len(sources) < n_assets:
            continue
        
        # Signal: buy QQQ when any source has IBS < 0.2
        combined_ibs = pd.Series(False, index=QQ.index)
        for s in sources:
            combined_ibs = combined_ibs | (raw[s]['IBS'].shift(1) < 0.2)
        
        sig = combined_ibs.astype(int)
        eq = run(sig, QQ['Close'])
        s, d, c = metrics(eq)
        print(f"  {n_assets}-asset IBS spillover ({combo_name}) Sharpe {s:.2f}  DD {d:.1f}%")
        add(f"MultiIBS_{n_assets}_{combo_name}", eq)

# ============================================================
# 9. DAILY + WEEKLY COMBO
# ============================================================
print()
print("=" * 70)
print("9. DAILY + WEEKLY COMBO")
print("=" * 70)

# Weekly: is 5-day return positive? Daily: IBS
QQ['WeekRet'] = QQ['Close'] / QQ['Close'].shift(5) - 1
for weekly_filter in ['up', 'down', 'any']:
    for ibs_thr in [0.15, 0.20, 0.25, 0.30]:
        if weekly_filter == 'up':
            wfilter = QQ['WeekRet'].shift(1) > 0
        elif weekly_filter == 'down':
            wfilter = QQ['WeekRet'].shift(1) < 0
        else:
            wfilter = pd.Series(True, index=QQ.index)
        
        sig = (wfilter & (QQ['IBS'].shift(1) < ibs_thr)).astype(int)
        eq = run(sig, QQ['Close'])
        s, d, c = metrics(eq)
        if s > 0.6:
            print(f"  Weekly{weekly_filter}+IBS<{ibs_thr} Sharpe {s:.2f}  DD {d:.1f}%")
            add(f"Weekly{weekly_filter}_IBS{ibs_thr}", eq)

# ============================================================
# 10. ADAPTIVE MOMENTUM (shorter lookback in high vol)
# ============================================================
print()
print("=" * 70)
print("10. ADAPTIVE MOMENTUM")
print("=" * 70)

# In high vol: use shorter lookback (10d). In low vol: longer (20d)
for hi_vol_lookback in [5, 10, 15]:
    for lo_vol_lookback in [20, 30, 40]:
        vol_median = QQ['Vol20'].rolling(252).median()
        high_vol = QQ['Vol20'] > vol_median
        
        # Adaptive lookback
        lb = pd.Series(20, index=QQ.index)
        lb[high_vol] = hi_vol_lookback
        lb[~high_vol] = lo_vol_lookback
        
        # Momentum signal with adaptive lookback
        mom = pd.Series(0.0, index=QQ.index)
        for i in range(50, len(QQ)):
            lookback = int(lb.iloc[i])
            mom.iloc[i] = QQ['Close'].iloc[i] / QQ['Close'].iloc[i - lookback] - 1
        
        sig = (mom.shift(1) > 0.01).astype(int)
        eq = run(sig, QQ['Close'])
        s, d, c = metrics(eq)
        if s > 0.6:
            print(f"  AdaptiveMom({hi_vol_lookback}/{lo_vol_lookback}) Sharpe {s:.2f}  DD {d:.1f}%")
            add(f"AdaptMom_{hi_vol_lookback}_{lo_vol_lookback}", eq)

# ============================================================
# 11. BREAKOUT + REVERSAL COMBO
# ============================================================
print()
print("=" * 70)
print("11. BREAKOUT + REVERSAL COMBO")
print("=" * 70)

# Buy on breakout, add on pullback
QQ['High20'] = QQ['High'].rolling(20).max()
QQ['Low20'] = QQ['Low'].rolling(20).min()
QQ['BreakoutUp'] = QQ['Close'] > QQ['High20'].shift(1)
QQ['Pullback'] = QQ['IBS'] < 0.3

# Strategy: buy on breakout, hold until IBS > 0.7
eq = []; cap = INITIAL; pos = 0; entry = 0
for i in range(1, len(QQ)):
    o = float(QQ['Open'].iloc[i]); c = float(QQ['Close'].iloc[i])
    ibs = float(QQ['IBS'].iloc[i-1]) if pd.notna(QQ['IBS'].iloc[i-1]) else 0.5
    breakout = bool(QQ['BreakoutUp'].iloc[i-1]) if pd.notna(QQ['BreakoutUp'].iloc[i-1]) else False
    if pos > 0:
        if ibs > 0.7:
            ca = pos * (entry + o) * COST / 2; cap += pos * o - ca; pos = 0
    elif breakout:
        sh = int(cap / o)
        if sh > 0:
            ca = sh * o * COST; cap -= sh * o + ca; pos = sh; entry = o
    eq.append(cap + (pos * c if pos > 0 else 0))
eq = np.array(eq)
s, d, c = metrics(eq)
print(f"  Breakout->IBS_exit Sharpe {s:.2f}  DD {d:.1f}%")
add("Breakout_IBSexit", eq)

# ============================================================
# 12. BEST COMBINATION OF TOP STRATEGIES
# ============================================================
print()
print("=" * 70)
print("12. TOP STRATEGY COMBOS")
print("=" * 70)

# We need to find uncorrelated strategies that boost Sharpe
# Let's build equity curves for many candidates
candidates = {
    'IBS_MR_QQQ': run((QQ['IBS'].shift(1) < 0.2).astype(int), QQ['Close']),
    'Trend50_IBS': run(((QQ['Close'] > QQ['SMA50']).shift(1) & (QQ['IBS'].shift(1) < 0.25)).astype(int), QQ['Close']),
    'Trend200_IBS': run(((QQ['Close'] > QQ['SMA200']).shift(1) & (QQ['IBS'].shift(1) < 0.25)).astype(int), QQ['Close']),
    'MR_Z20': run((QQ['Z20'].shift(1) < -1.5).astype(int), QQ['Close']),
    'ConsecDn5': run(((QQ['Ret'] < 0).astype(int).rolling(5).sum().shift(1) >= 5).astype(int), QQ['Close']),
    'VolMR': run((QQ['VolZ'].shift(1) > 1.5).astype(int), QQ['Close']),
}

# Test all pairs
names = list(candidates.keys())
for i in range(len(names)):
    for j in range(i+1, len(names)):
        eq1 = candidates[names[i]]; eq2 = candidates[names[j]]
        ml = min(len(eq1), len(eq2))
        combo = (eq1[:ml] + eq2[:ml]) / 2
        s, d, c = metrics(combo)
        if s > 0.8:
            # Also check correlation
            r1 = np.diff(eq1[:ml]) / eq1[:ml-1]
            r2 = np.diff(eq2[:ml]) / eq2[:ml-1]
            r1 = r1[np.isfinite(r1)]; r2 = r2[np.isfinite(r2)]
            ml2 = min(len(r1), len(r2))
            corr = np.corrcoef(r1[:ml2], r2[:ml2])[0, 1] if ml2 > 10 else 0
            print(f"  {names[i]}+{names[j]} (corr={corr:.2f}) Sharpe {s:.2f}  DD {d:.1f}%")
            add(f"{names[i]}+{names[j]}", combo)

# Test triples
for i in range(len(names)):
    for j in range(i+1, len(names)):
        for k in range(j+1, len(names)):
            eq1 = candidates[names[i]]; eq2 = candidates[names[j]]; eq3 = candidates[names[k]]
            ml = min(len(eq1), len(eq2), len(eq3))
            combo = (eq1[:ml] + eq2[:ml] + eq3[:ml]) / 3
            s, d, c = metrics(combo)
            if s > 0.8:
                print(f"  {names[i]}+{names[j]}+{names[k]} Sharpe {s:.2f}  DD {d:.1f}%")
                add(f"{names[i]}+{names[j]}+{names[k]}", combo)

# ============================================================
# FINAL RANKINGS
# ============================================================
print()
print("=" * 70)
print("FINAL RANKINGS (top 30)")
print("=" * 70)

results.sort(key=lambda x: x[1], reverse=True)
print(f"  {'#':>3} {'Strategy':<40} {'Sharpe':>7} {'DD%':>7} {'CAGR%':>7}")
print(f"  {'-'*68}")
for i, (name, s, d, c) in enumerate(results[:30]):
    marker = " ***" if s >= 1.3 else ""
    print(f"  {i+1:>3} {name:<40} {s:>7.2f} {d:>7.1f} {c:>7.1f}{marker}")

hits = sum(1 for _, s, _, _ in results if s >= 1.3)
print(f"\n  Strategies hitting Sharpe >= 1.3: {hits}/{len(results)}")
