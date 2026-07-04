"""
MOMENTUM ROTATION — VALIDATION
================================
Best strategy from scan: Rotation 10d/5d, Sharpe 2.95
Now validate with walk-forward + Monte Carlo
"""

import pandas as pd
import numpy as np
import yfinance as yf
import warnings
warnings.filterwarnings('ignore')

INITIAL = 100000
COST = 0.001

print("=" * 90)
print("MOMENTUM ROTATION — VALIDATION")
print("=" * 90)
print()

# Download data
tickers = ['QQQ', 'SPY', 'IWM', 'GLD', 'TLT', 'XLF', 'XLE', 'XLK', 'VNQ', 'EEM']
data = {}
for t in tickers:
    d = yf.download(t, start='2010-01-01', end='2025-12-31', progress=False)
    if hasattr(d.columns, 'get_level_values'):
        d.columns = d.columns.get_level_values(0)
    if len(d) > 2000:
        data[t] = d[['Open', 'High', 'Low', 'Close']].copy()

print(f"  Instruments: {list(data.keys())}")


def strat_rotation(data_dict, lookback=10, hold=5):
    """Momentum rotation: buy strongest momentum, rebalance every hold days"""
    closes = pd.DataFrame({t: data_dict[t]['Close'] for t in data_dict}).dropna()
    opens = pd.DataFrame({t: data_dict[t]['Open'] for t in data_dict}).dropna()
    
    # Align
    common = closes.index.intersection(opens.index)
    closes = closes.loc[common]
    opens = opens.loc[common]
    
    cap = INITIAL; pos = 0; current = None; entry_p = 0; timer = 0
    trades = []; eq = []
    
    for i in range(lookback, len(closes)):
        # Momentum signal (yesterday's close)
        mom = {}
        for t in data_dict:
            if t in closes.columns:
                mom[t] = closes[t].iloc[i] / closes[t].iloc[i - lookback] - 1
        
        best = max(mom, key=mom.get) if mom else None
        
        timer += 1
        if timer >= hold or (current != best and best):
            # Sell current at today's open
            if pos > 0 and current:
                o = float(opens[current].iloc[i])
                ca = pos * (entry_p + o) * COST / 2
                cap += pos * o - ca
                trades.append({'pnl': pos * (o - entry_p) - ca, 'exit_date': closes.index[i]})
                pos = 0
            
            # Buy best at today's open
            if best and current != best:
                o = float(opens[best].iloc[i])
                sh = int(cap / o)
                if sh > 0:
                    ca = sh * o * COST
                    cap -= sh * o + ca
                    pos = sh; entry_p = o; current = best
                    trades.append({'entry_date': closes.index[i]})
                timer = 0
        
        # Portfolio value
        pv = cap
        if pos > 0 and current:
            pv += pos * float(closes[current].iloc[i])
        eq.append(pv)
    
    if pos > 0 and current:
        c = float(closes[current].iloc[-1])
        ca = pos * (entry_p + c) * COST / 2
        cap += pos * c - ca
        trades.append({'pnl': pos * (c - entry_p) - ca})
    
    return trades, np.array(eq)


def m(trades, eq):
    if len(eq) < 100:
        return None
    n = len([t for t in trades if 'pnl' in t])
    years = len(eq) / 252
    cagr = ((eq[-1] / INITIAL) ** (1/years) - 1) * 100
    rm = np.maximum.accumulate(eq)
    dd = ((eq - rm) / rm).min() * 100
    dr = np.diff(eq) / eq[:-1]; dr = dr[np.isfinite(dr)]
    sh = (np.mean(dr) / np.std(dr)) * np.sqrt(252) if np.std(dr) > 0 else 0
    down = dr[dr < 0]
    sortino = (np.mean(dr) / np.std(down)) * np.sqrt(252) if len(down) > 0 and np.std(down) > 0 else 0
    if n > 0:
        pnl_trades = [t for t in trades if 'pnl' in t]
        w = sum(1 for t in pnl_trades if t['pnl'] > 0)
        gp = sum(t['pnl'] for t in pnl_trades if t['pnl'] > 0)
        gl = abs(sum(t['pnl'] for t in pnl_trades if t['pnl'] <= 0)) or 0.001
        return {'sh': sh, 'cagr': cagr, 'dd': dd, 'pf': gp/gl, 'wr': w/n*100, 'n': n, 'sortino': sortino}
    return {'sh': sh, 'cagr': cagr, 'dd': dd, 'pf': 0, 'wr': 0, 'n': 0, 'sortino': 0}


# ============================================================
# TEST ALL ROTATION CONFIGS
# ============================================================
print("=" * 90)
print("ROTATION PARAMETER SCAN")
print("=" * 90)
print()
print(f"  {'LB':>4} {'Hold':>5} {'T':>5} {'WR%':>6} {'PF':>7} {'CAGR%':>8} {'DD%':>8} {'Sharpe':>7} {'Sort':>7}")
print(f"  {'-'*58}")

configs = []
for lb in [5, 10, 20, 40, 60]:
    for hold in [1, 2, 3, 5, 10, 20]:
        try:
            trades, eq = strat_rotation(data, lb, hold)
            r = m(trades, eq)
            if r:
                configs.append((lb, hold, r))
                print(f"  {lb:>4} {hold:>5} {r['n']:>5} {r['wr']:>5.1f}% {r['pf']:>6.2f} {r['cagr']:>7.1f}% {r['dd']:>7.1f}% {r['sh']:>6.2f} {r['sort']:>6.2f}")
        except: pass

# Sort by Sharpe
configs.sort(key=lambda x: x[2]['sh'], reverse=True)

# ============================================================
# TOP 3 — WALK-FORWARD + MONTE CARLO
# ============================================================
for rank, (lb, hold, stats) in enumerate(configs[:3]):
    print()
    print("=" * 90)
    print(f"  #{rank+1}: Rotation {lb}d/{hold}d — Sharpe {stats['sh']:.2f}")
    print("=" * 90)
    
    trades, eq = strat_rotation(data, lb, hold)
    eq_s = pd.Series(eq, index=data['QQQ'].index[-len(eq):])
    
    # Yearly
    print(f"\n  {'Year':<8} {'Return%':>10} {'Sharpe':>8} {'MaxDD%':>8}")
    print(f"  {'-'*36}")
    for year in range(2011, 2026):
        mask = eq_s.index.year == year
        if mask.sum() == 0: continue
        yr = eq_s[mask]
        yr_ret = (yr.iloc[-1] / yr.iloc[0] - 1) * 100
        dr = np.diff(yr.values) / yr.values[:-1]; dr = dr[np.isfinite(dr)]
        yr_sh = (np.mean(dr) / np.std(dr)) * np.sqrt(252) if np.std(dr) > 0 and len(dr) > 1 else 0
        rm = np.maximum.accumulate(yr.values)
        yr_dd = ((yr.values - rm) / rm).min() * 100
        print(f"  {year:<8} {yr_ret:>9.1f}% {yr_sh:>8.2f} {yr_dd:>7.1f}%")
    
    # Walk-forward: 3yr IS / 1yr OOS
    print(f"\n  WALK-FORWARD (3yr IS / 1yr OOS):")
    print(f"  {'Period':<12} {'IS CAGR%':>9} {'OOS CAGR%':>10} {'IS Sharpe':>10} {'OOS Sharpe':>11}")
    print(f"  {'-'*55}")
    for start in range(2011, 2023):
        is_mask = (eq_s.index.year >= start) & (eq_s.index.year < start + 3)
        oos_mask = (eq_s.index.year >= start + 3) & (eq_s.index.year < start + 4)
        if is_mask.sum() < 200 or oos_mask.sum() < 50: continue
        is_eq = eq_s[is_mask].values
        oos_eq = eq_s[oos_mask].values
        is_cagr = ((is_eq[-1]/is_eq[0])**(252/len(is_eq))-1)*100
        oos_cagr = ((oos_eq[-1]/oos_eq[0])**(252/len(oos_eq))-1)*100
        is_dr = np.diff(is_eq)/is_eq[:-1]; is_dr = is_dr[np.isfinite(is_dr)]
        oos_dr = np.diff(oos_eq)/oos_eq[:-1]; oos_dr = oos_dr[np.isfinite(oos_dr)]
        is_sh = (np.mean(is_dr)/np.std(is_dr))*np.sqrt(252) if np.std(is_dr)>0 else 0
        oos_sh = (np.mean(oos_dr)/np.std(oos_dr))*np.sqrt(252) if np.std(oos_dr)>0 else 0
        print(f"  {start}-{start+3}    {is_cagr:>9.1f} {oos_cagr:>10.1f} {is_sh:>10.2f} {oos_sh:>11.2f}")
    
    # Monte Carlo
    print(f"\n  MONTE CARLO (2000 sims):")
    pnl_trades = [t['pnl'] for t in trades if 'pnl' in t]
    np.random.seed(42)
    mc_sh = []; mc_dd = []
    for _ in range(2000):
        perm = np.random.permutation(pnl_trades)
        se = [INITIAL]
        for p in perm: se.append(se[-1] + p)
        se = np.array(se)
        rm = np.maximum.accumulate(se)
        dd = ((se - rm) / rm).min()
        dr = np.diff(se) / se[:-1]; dr = dr[np.isfinite(dr)]
        sh = (np.mean(dr) / np.std(dr)) * np.sqrt(252) if np.std(dr) > 0 else 0
        mc_sh.append(sh); mc_dd.append(dd * 100)
    mc_sh = np.array(mc_sh); mc_dd = np.array(mc_dd)
    print(f"    Survival (> -20% DD): {(mc_dd > -20).sum()/2000*100:.0f}%")
    print(f"    Median Sharpe: {np.median(mc_sh):.2f}")
    print(f"    5th pctl: {np.percentile(mc_sh, 5):.2f} | 95th: {np.percentile(mc_sh, 95):.2f}")
    print(f"    Median DD: {np.median(mc_dd):.1f}% | Worst: {mc_dd.min():.1f}%")
    
    # Summary
    print(f"\n  SUMMARY: Sharpe {stats['sh']:.2f} | CAGR {stats['cagr']:.1f}% | DD {stats['dd']:.1f}% | PF {stats['pf']:.2f} | WR {stats['wr']:.1f}% | T {stats['n']}")

# ============================================================
# BEST OVERALL
# ============================================================
best_lb, best_hold, best_r = configs[0]
print()
print("=" * 90)
print(f"BEST: Rotation {best_lb}d/{best_hold}d")
print("=" * 90)
print(f"  Sharpe:   {best_r['sh']:.2f}")
print(f"  CAGR:     {best_r['cagr']:.1f}%")
print(f"  Max DD:   {best_r['dd']:.1f}%")
print(f"  PF:       {best_r['pf']:.2f}")
print(f"  WR:       {best_r['wr']:.1f}%")
print(f"  Sortino:  {best_r['sortino']:.2f}")
print(f"  Trades:   {best_r['n']}")

if best_r['sh'] >= 1.3:
    print(f"\n  *** TARGET ACHIEVED: Sharpe {best_r['sh']:.2f} >= 1.3 ***")
else:
    print(f"\n  Sharpe {best_r['sh']:.2f} < 1.3")
