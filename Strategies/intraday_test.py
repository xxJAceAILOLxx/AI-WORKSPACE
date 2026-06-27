import yfinance as yf
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

d = yf.download('QQQ', period='60d', interval='5m', progress=False)
d.columns = d.columns.get_level_values(0)
print(f'{len(d)} bars, {d.index[0]} to {d.index[-1]}')

d['Range'] = d['High'] - d['Low']
d['IBS'] = np.where(d['Range'] > 0, (d['Close'] - d['Low']) / d['Range'], 0.5)

INIT = 100000
COST_PER_SHARE = 0.01

def run_ibs(df, hold, ibs_thresh):
    cap = INIT; pos = 0; entry = 0; hc = 0; eq = []; signals = []
    for i in range(1, len(df)):
        ibs = float(df['IBS'].iloc[i-1])
        o = float(df['Open'].iloc[i]); c = float(df['Close'].iloc[i])
        sig = 0
        if pos > 0:
            hc += 1
            if hc >= hold:
                cost = pos * COST_PER_SHARE
                cap += pos * c - cost; pos = 0; hc = 0
                sig = -1
        elif ibs < ibs_thresh:
            sh = int(cap / o)
            if sh > 0:
                cost = sh * COST_PER_SHARE
                cap -= sh * o + cost; pos = sh; entry = o; hc = 0
                sig = 1
        eq.append(cap + (pos * c if pos > 0 else 0))
        signals.append(sig)
    if pos > 0:
        cost = pos * COST_PER_SHARE
        cap += pos * float(df['Close'].iloc[-1]) - cost
    return np.array(eq), signals

# ============================================================
# CRITICAL TEST 1: Same-bar vs Next-bar execution
# ============================================================
print()
print("=" * 70)
print("TEST 1: Same-bar (FAKE) vs Next-bar (HONEST)")
print("=" * 70)

def run_ibs_samebar(df, hold, ibs_thresh):
    """Buy at CURRENT bar open if IBS of THIS bar is low — lookahead!"""
    cap = INIT; pos = 0; entry = 0; hc = 0; eq = []
    for i in range(1, len(df)):
        ibs = float(df['IBS'].iloc[i])  # IBS of CURRENT bar = lookahead
        o = float(df['Open'].iloc[i]); c = float(df['Close'].iloc[i])
        if pos > 0:
            hc += 1
            if hc >= hold:
                cost = pos * COST_PER_SHARE
                cap += pos * c - cost; pos = 0; hc = 0
        elif ibs < ibs_thresh:
            sh = int(cap / o)
            if sh > 0:
                cost = sh * COST_PER_SHARE
                cap -= sh * o + cost; pos = sh; entry = o; hc = 0
        eq.append(cap + (pos * c if pos > 0 else 0))
    return np.array(eq)

# Same bar (fake)
eq_fake, _ = run_ibs(d, 2, 0.15)  # This is actually next-bar (correct)
# Next bar (honest) — already correct in run_ibs

# Actually let me rewrite clearly
def run_fake(df, hold, thr):
    """Uses IBS[i] to decide at Open[i] — lookahead"""
    cap = INIT; pos = 0; hc = 0; eq = []
    for i in range(1, len(df)):
        ibs = float(df['IBS'].iloc[i])  # LOOKAHEAD
        o = float(df['Open'].iloc[i]); c = float(df['Close'].iloc[i])
        if pos > 0:
            hc += 1
            if hc >= hold:
                cap += pos * c - pos * COST_PER_SHARE; pos = 0; hc = 0
        elif ibs < thr:
            sh = int(cap / o)
            if sh > 0:
                cap -= sh * o + sh * COST_PER_SHARE; pos = sh; hc = 0
        eq.append(cap + (pos * c if pos > 0 else 0))
    return np.array(eq)

def run_honest(df, hold, thr):
    """Uses IBS[i-1] to decide at Open[i] — honest"""
    cap = INIT; pos = 0; hc = 0; eq = []
    for i in range(1, len(df)):
        ibs = float(df['IBS'].iloc[i-1])  # PRIOR bar
        o = float(df['Open'].iloc[i]); c = float(df['Close'].iloc[i])
        if pos > 0:
            hc += 1
            if hc >= hold:
                cap += pos * c - pos * COST_PER_SHARE; pos = 0; hc = 0
        elif ibs < thr:
            sh = int(cap / o)
            if sh > 0:
                cap -= sh * o + sh * COST_PER_SHARE; pos = sh; hc = 0
        eq.append(cap + (pos * c if pos > 0 else 0))
    return np.array(eq)

eq_f = run_fake(d, 2, 0.15)
eq_h = run_honest(d, 2, 0.15)

for label, eq in [("FAKE (same-bar)", eq_f), ("HONEST (next-bar)", eq_h)]:
    dr = np.diff(eq) / eq[:-1]; dr = dr[np.isfinite(dr)]
    sharpe = (np.mean(dr) / np.std(dr)) * np.sqrt(252 * 78) if np.std(dr) > 0 else 0
    pk = np.maximum.accumulate(eq)
    dd = -((pk - eq) / pk).max() * 100
    print(f"  {label:<25} Sharpe {sharpe:>7.2f}  DD {dd:>6.1f}%  Final ${eq[-1]:,.0f}")

# ============================================================
# CRITICAL TEST 2: Walk-forward within 60 days
# ============================================================
print()
print("=" * 70)
print("TEST 2: Walk-forward (train first 30 days, test last 30)")
print("=" * 70)

split = len(d) // 2
train = d.iloc[:split].copy().reset_index(drop=True)
test = d.iloc[split:].copy().reset_index(drop=True)

# Optimize on train
best_sh = 0; best_params = (2, 0.15)
for hold in [1, 2, 3, 5]:
    for thr in [0.10, 0.15, 0.20, 0.25, 0.30]:
        eq = run_honest(train, hold, thr)
        dr = np.diff(eq) / eq[:-1]; dr = dr[np.isfinite(dr)]
        sharpe = (np.mean(dr) / np.std(dr)) * np.sqrt(252 * 78) if np.std(dr) > 0 else 0
        if sharpe > best_sh:
            best_sh = sharpe
            best_params = (hold, thr)

print(f"  Train best: hold={best_params[0]}, IBS<{best_params[1]}, Sharpe={best_sh:.2f}")

# Test on out-of-sample
eq_oos = run_honest(test, best_params[0], best_params[1])
dr = np.diff(eq_oos) / eq_oos[:-1]; dr = dr[np.isfinite(dr)]
sharpe_oos = (np.mean(dr) / np.std(dr)) * np.sqrt(252 * 78) if np.std(dr) > 0 else 0
pk = np.maximum.accumulate(eq_oos)
dd = -((pk - eq_oos) / pk).max() * 100
print(f"  Test OOS: Sharpe {sharpe_oos:.2f}  DD {dd:.1f}%  Final ${eq_oos[-1]:,.0f}")

# ============================================================
# CRITICAL TEST 3: Split into weeks
# ============================================================
print()
print("=" * 70)
print("TEST 3: Weekly Sharpe breakdown")
print("=" * 70)

eq_h = run_honest(d, 2, 0.15)
eq_h_with_dates = pd.Series(eq_h, index=d.index[1:])

for week_start in range(0, len(d), 78*5):  # ~5 trading days per week
    week_end = min(week_start + 78*5, len(eq_h))
    if week_end - week_start < 10:
        continue
    w_eq = eq_h[week_start:week_end]
    w_dr = np.diff(w_eq) / w_eq[:-1]; w_dr = w_dr[np.isfinite(w_dr)]
    w_sharpe = (np.mean(w_dr) / np.std(w_dr)) * np.sqrt(252 * 78) if np.std(w_dr) > 0 and len(w_dr) > 1 else 0
    w_date = d.index[min(week_start, len(d)-1)].strftime('%Y-%m-%d')
    print(f"  Week of {w_date}: Sharpe {w_sharpe:>7.2f}  Final ${w_eq[-1]:,.0f}")

# ============================================================
# CRITICAL TEST 4: Random signal test
# ============================================================
print()
print("=" * 70)
print("TEST 4: Random signals (null distribution)")
print("=" * 70)

np.random.seed(42)
random_sharpes = []
for _ in range(1000):
    cap = INIT; pos = 0; hc = 0; eq = []
    for i in range(1, len(d)):
        o = float(d['Open'].iloc[i]); c = float(df['Close'].iloc[i]) if False else float(d['Close'].iloc[i])
        if pos > 0:
            hc += 1
            if hc >= 2:
                cap += pos * c - pos * COST_PER_SHARE; pos = 0; hc = 0
        elif np.random.random() < 0.3:  # Random entry ~30% of the time
            sh = int(cap / o)
            if sh > 0:
                cap -= sh * o + sh * COST_PER_SHARE; pos = sh; hc = 0
        eq.append(cap + (pos * c if pos > 0 else 0))
    eq = np.array(eq)
    dr = np.diff(eq) / eq[:-1]; dr = dr[np.isfinite(dr)]
    sharpe = (np.mean(dr) / np.std(dr)) * np.sqrt(252 * 78) if np.std(dr) > 0 else 0
    random_sharpes.append(sharpe)

random_sharpes = np.array(random_sharpes)
print(f"  Random signal Sharpe distribution:")
print(f"    Mean: {random_sharpes.mean():.2f}")
print(f"    Std:  {random_sharpes.std():.2f}")
print(f"    95th pct: {np.percentile(random_sharpes, 95):.2f}")
print(f"    99th pct: {np.percentile(random_sharpes, 99):.2f}")
print(f"    Our strategy Sharpe: 4.90")
print(f"    p-value: {(random_sharpes >= 4.90).mean():.4f}")

# ============================================================
# CRITICAL TEST 5: Impact of holding period
# ============================================================
print()
print("=" * 70)
print("TEST 5: Sharpe vs number of bars held (is there decay?)")
print("=" * 70)

for hold in [1, 2, 3, 5, 10, 15, 20, 30, 50, 78]:
    eq = run_honest(d, hold, 0.15)
    dr = np.diff(eq) / eq[:-1]; dr = dr[np.isfinite(dr)]
    sharpe = (np.mean(dr) / np.std(dr)) * np.sqrt(252 * 78) if np.std(dr) > 0 else 0
    pk = np.maximum.accumulate(eq)
    dd = -((pk - eq) / pk).max() * 100
    n = len([x for x in dr if x != 0])
    print(f"  Hold {hold:>3} bars: Sharpe {sharpe:>7.2f}  DD {dd:>6.1f}%  Trades ~{n}")
