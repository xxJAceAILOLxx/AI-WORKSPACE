import yfinance as yf
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

print("Downloading QQQ 1h data...")
d = yf.download('QQQ', period='730d', interval='1h', progress=False)
d.columns = d.columns.get_level_values(0)
print(f'{len(d)} bars, {d.index[0]} to {d.index[-1]}')
print(f'Years: {(d.index[-1] - d.index[0]).days / 365.25:.2f}')

d['H'] = d['High']; d['L'] = d['Low']; d['C'] = d['Close']; d['O'] = d['Open']
d['Range'] = d['H'] - d['L']
d['IBS'] = np.where(d['Range'] > 0, (d['C'] - d['L']) / d['Range'], 0.5)
d['SessionBar'] = 0
bars_in = 0; last_date = None
for i in range(len(d)):
    cur = d.index[i].date()
    if cur != last_date: bars_in = 0; last_date = cur
    d.iloc[i, d.columns.get_loc('SessionBar')] = bars_in
    bars_in += 1

INIT = 100000
COST = 0.01

def run_ibs(df, hold, ibs_thresh, early_only=False, late_only=False):
    cap = INIT; pos = 0; entry = 0; hc = 0; eq = []
    ibs_arr = df['IBS'].values
    o_arr = df['O'].values
    c_arr = df['C'].values
    sb_arr = df['SessionBar'].values
    n = len(df)
    for i in range(1, n):
        ibs = ibs_arr[i-1]; sb = sb_arr[i-1]
        o = o_arr[i]; c = c_arr[i]
        if pos > 0:
            hc += 1
            if hc >= hold:
                cap += pos * c - pos * COST; pos = 0; hc = 0
        elif ibs < ibs_thresh:
            if early_only and sb >= 13: pass
            elif late_only and sb < 13: pass
            else:
                sh = int(cap / o)
                if sh > 0:
                    cap -= sh * o + sh * COST; pos = sh; entry = o; hc = 0
        eq.append(cap + (pos * c if pos > 0 else 0))
    if pos > 0: cap += pos * c_arr[-1] - pos * COST
    return np.array(eq)

# ============================================================
# GRID SEARCH
# ============================================================
print()
print("=" * 70)
print("IBS GRID SEARCH")
print("=" * 70)

results = []
for hold in [1, 2, 3, 5, 8]:
    for thr in [0.10, 0.15, 0.20, 0.25, 0.30]:
        for mode in ['all', 'early', 'late']:
            eq = run_ibs(d, hold, thr, mode == 'early', mode == 'late')
            dr = np.diff(eq) / eq[:-1]; dr = dr[np.isfinite(dr)]
            sharpe = (np.mean(dr) / np.std(dr)) * np.sqrt(252 * 7) if np.std(dr) > 0 else 0
            pk = np.maximum.accumulate(eq)
            dd = -((pk - eq) / pk).max() * 100
            nt = sum(1 for i in range(len(eq)-1) if eq[i+1] != eq[i])
            cagr = ((eq[-1] / eq[0]) ** (365.25 * 7 / max(len(eq),1)) - 1) * 100
            results.append((hold, thr, mode, sharpe, cagr, dd, nt))

results.sort(key=lambda x: x[3], reverse=True)
print(f"  {'Hold':>4} {'IBS<':>5} {'Time':>5} {'Sharpe':>7} {'CAGR%':>7} {'DD%':>7} {'Trd':>5}")
print(f"  {'-'*45}")
for h, t, m, s, c, dd, n in results[:20]:
    print(f"  {h:>4} {t:>5.2f} {m:>5} {s:>7.2f} {c:>7.1f} {dd:>7.1f} {n:>5}")

# ============================================================
# WALK-FORWARD
# ============================================================
print()
print("=" * 70)
print("WALK-FORWARD (60/40 split)")
print("=" * 70)

split = int(len(d) * 0.6)
train = d.iloc[:split].copy().reset_index(drop=True)
test = d.iloc[split:].copy().reset_index(drop=True)

# Train
tr = []
for hold in [1, 2, 3, 5]:
    for thr in [0.10, 0.15, 0.20, 0.25, 0.30]:
        for mode in ['all', 'early', 'late']:
            eq = run_ibs(train, hold, thr, mode == 'early', mode == 'late')
            dr = np.diff(eq) / eq[:-1]; dr = dr[np.isfinite(dr)]
            s = (np.mean(dr) / np.std(dr)) * np.sqrt(252 * 7) if np.std(dr) > 0 else 0
            tr.append((hold, thr, mode, s))

tr.sort(key=lambda x: x[3], reverse=True)
tb = tr[0]
print(f"Train best: hold={tb[0]}, IBS<{tb[1]}, time={tb[2]}, Sharpe={tb[3]:.2f}")

eq_oos = run_ibs(test, tb[0], tb[1], tb[2] == 'early', tb[2] == 'late')
dr = np.diff(eq_oos) / eq_oos[:-1]; dr = dr[np.isfinite(dr)]
s_oos = (np.mean(dr) / np.std(dr)) * np.sqrt(252 * 7) if np.std(dr) > 0 else 0
pk = np.maximum.accumulate(eq_oos)
dd = -((pk - eq_oos) / pk).max() * 100
print(f"OOS: Sharpe {s_oos:.2f}  DD {dd:.1f}%  Final ${eq_oos[-1]:,.0f}")

# ============================================================
# RANDOM BASELINE (fast: 200 sims)
# ============================================================
print()
print("=" * 70)
print("RANDOM BASELINE (200 sims)")
print("=" * 70)

np.random.seed(42)
rs = []
for _ in range(200):
    cap = INIT; pos = 0; hc = 0; eq = []
    o_arr = d['O'].values; c_arr = d['C'].values; n = len(d)
    for i in range(1, n):
        o = o_arr[i]; c = c_arr[i]
        if pos > 0:
            hc += 1
            if hc >= 2:
                cap += pos * c - pos * COST; pos = 0; hc = 0
        elif np.random.random() < 0.3:
            sh = int(cap / o)
            if sh > 0:
                cap -= sh * o + sh * COST; pos = sh; hc = 0
        eq.append(cap + (pos * c if pos > 0 else 0))
    eq = np.array(eq)
    dr = np.diff(eq) / eq[:-1]; dr = dr[np.isfinite(dr)]
    s = (np.mean(dr) / np.std(dr)) * np.sqrt(252 * 7) if np.std(dr) > 0 else 0
    rs.append(s)

rs = np.array(rs)
print(f"  Random mean: {rs.mean():.2f}  std: {rs.std():.2f}")
print(f"  90th: {np.percentile(rs, 90):.2f}  95th: {np.percentile(rs, 95):.2f}  99th: {np.percentile(rs, 99):.2f}")
pval = (rs >= results[0][3]).mean()
print(f"  Our best: {results[0][3]:.2f}  p-value: {pval:.4f}")

# ============================================================
# MOMENTUM
# ============================================================
print()
print("=" * 70)
print("HOURLY MOMENTUM")
print("=" * 70)

for lb in [5, 10, 20, 30, 50]:
    for hold in [1, 2, 3]:
        cap = INIT; pos = 0; hc = 0; eq = []
        o_arr = d['O'].values; c_arr = d['C'].values; n = len(d)
        for i in range(max(lb, 50), n):
            ret = c_arr[i-1] / c_arr[i-lb-1] - 1
            o = o_arr[i]; c = c_arr[i]
            if pos > 0:
                hc += 1
                if hc >= hold:
                    cap += pos * c - pos * COST; pos = 0; hc = 0
            elif ret > 0.001:
                sh = int(cap / o)
                if sh > 0:
                    cap -= sh * o + sh * COST; pos = sh; hc = 0
            eq.append(cap + (pos * c if pos > 0 else 0))
        eq = np.array(eq)
        if len(eq) < 10: continue
        dr = np.diff(eq) / eq[:-1]; dr = dr[np.isfinite(dr)]
        s = (np.mean(dr) / np.std(dr)) * np.sqrt(252 * 7) if np.std(dr) > 0 else 0
        pk = np.maximum.accumulate(eq)
        dd = -((pk - eq) / pk).max() * 100
        print(f"  LB={lb:>2} Hold={hold}: Sharpe {s:>7.2f}  DD {dd:>6.1f}%")

# ============================================================
# CONCLUSION
# ============================================================
print()
print("=" * 70)
print("CONCLUSION")
print("=" * 70)
best_ibsh = results[0][3]
best_oos = s_oos
print(f"Best in-sample Sharpe: {best_ibsh:.2f}")
print(f"Walk-forward OOS Sharpe: {best_oos:.2f}")
if best_oos > 1.3:
    print("*** TARGET ACHIEVED ***")
elif best_oos > 0:
    print(f"Positive OOS edge exists but below 1.3 target")
else:
    print(f"No robust OOS edge found")
