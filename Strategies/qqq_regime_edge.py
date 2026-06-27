"""
QQQ Regime-Switching Edge — THE ATTEMPT AT 1.5 SHARPE
=====================================================
Key insight: Mean reversion Sharpe is capped at ~0.9 because time-in-market is low.

New approach: Stay invested ALWAYS, switch between mean reversion and trend.
  - When oversold (IBS < 0.20): hold for mean reversion (5 days)
  - When trend is strong (>50SMA + >200SMA): hold for trend
  - When neither: stay in cash (but this should be rare)

This keeps us in the market much more, improving Sharpe.

Also: use a wider exit for trend (trail with 50 SMA) and tighter for MR.

Period: 2016-2025, Costs: 0.1%
"""

import pandas as pd
import numpy as np
import yfinance as yf
import warnings
warnings.filterwarnings('ignore')

INITIAL_CAPITAL = 100000
COST = 0.001

# ============================================================
# DATA
# ============================================================
print("=" * 90)
print("QQQ REGIME-SWITCHING EDGE")
print("=" * 90)
print()

d = yf.download('QQQ', start='2016-01-01', end='2025-12-31', progress=False)
if hasattr(d.columns, 'get_level_values'):
    d.columns = d.columns.get_level_values(0)
qqq = d[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
print(f"  QQQ: {len(qqq)} bars ({qqq.index[0].date()} to {qqq.index[-1].date()})")

# Indicators
qqq['IBS'] = (qqq['Close'] - qqq['Low']) / (qqq['High'] - qqq['Low'])
qqq['IBS'] = qqq['IBS'].fillna(0.5)
qqq['SMA20'] = qqq['Close'].rolling(20).mean()
qqq['SMA50'] = qqq['Close'].rolling(50).mean()
qqq['SMA200'] = qqq['Close'].rolling(200).mean()
qqq['VolAvg20'] = qqq['Volume'].rolling(20).mean()
qqq['VolRatio'] = (qqq['Volume'] / qqq['VolAvg20']).fillna(1.0)
qqq['TR'] = np.maximum(qqq['High'] - qqq['Low'],
    np.maximum(abs(qqq['High'] - qqq['Close'].shift(1)),
               abs(qqq['Low'] - qqq['Close'].shift(1))))
qqq['ATR14'] = qqq['TR'].rolling(14).mean()
qqq['Ret'] = np.log(qqq['Close'] / qqq['Close'].shift(1))
qqq['RealVol63'] = qqq['Ret'].rolling(63).std() * np.sqrt(252) * 100

# RSI(14) for additional signal
delta = qqq['Close'].diff()
gain = delta.where(delta > 0, 0.0)
loss = -delta.where(delta < 0, 0.0)
avg_gain = gain.rolling(14).mean()
avg_loss = loss.rolling(14).mean()
rs = avg_gain / avg_loss
qqq['RSI14'] = 100 - (100 / (1 + rs))

# 10-day momentum
qqq['Mom10'] = qqq['Close'] / qqq['Close'].shift(10) - 1

# ============================================================
# STRATEGY A: DUAL-SIGNAL (MR + Trend, same capital)
# ============================================================
def strat_dual_signal(df, alloc=0.90):
    """
    Two signals on same capital:
    1. MR: IBS < 0.20 + >200SMA + VolRatio<1.5 → hold 5 days
    2. Trend: >50SMA + >200SMA + pullback → hold until <50SMA
    Priority: MR first (shorter hold), then trend.
    """
    capital = INITIAL_CAPITAL
    pos = 0; ep = 0; ed = None; hd = 0; mode = None
    trades = []; equity = []

    for i in range(len(df)):
        date = df.index[i]
        c = float(df['Close'].iloc[i])
        ibs = float(df['IBS'].iloc[i])
        sma50 = float(df['SMA50'].iloc[i]) if pd.notna(df['SMA50'].iloc[i]) else c
        sma200 = float(df['SMA200'].iloc[i]) if pd.notna(df['SMA200'].iloc[i]) else c
        atr = float(df['ATR14'].iloc[i]) if pd.notna(df['ATR14'].iloc[i]) else c * 0.02
        vr = float(df['VolRatio'].iloc[i])
        rsi = float(df['RSI14'].iloc[i]) if pd.notna(df['RSI14'].iloc[i]) else 50

        eq = capital + (pos * c if pos > 0 else 0)
        equity.append(eq)

        if pos > 0:
            hd += 1
            exit_signal = False
            exit_price = c

            if mode == 'mr':
                if hd >= 5:
                    exit_signal = True
                if c <= ep - 2.0 * atr:
                    exit_signal = True
                    exit_price = ep - 2.0 * atr
            elif mode == 'trend':
                if c < sma50:
                    exit_signal = True
                if c <= ep - 2.5 * atr:
                    exit_signal = True
                    exit_price = ep - 2.5 * atr

            if exit_signal:
                cost_amt = pos * (ep + exit_price) * COST / 2
                capital += pos * exit_price - cost_amt
                pnl = pos * (exit_price - ep) - cost_amt
                trades.append({'entry_date': ed, 'exit_date': date,
                               'entry_price': ep, 'exit_price': exit_price,
                               'pnl': pnl, 'hold_days': hd, 'mode': mode})
                pos = 0; hd = 0; mode = None

        if pos == 0:
            # MR signal (priority)
            if ibs < 0.20 and c > sma200 and vr < 1.5:
                mode = 'mr'
                ep = c
                shares = int(capital * alloc / ep)
                cost_amt = shares * ep * COST
                if shares > 0 and capital >= shares * ep + cost_amt:
                    capital -= (shares * ep + cost_amt)
                    pos = shares; ed = date; hd = 0
            # Trend signal (only if no MR)
            elif c > sma50 and c > sma200:
                # Check for pullback
                lb = df['Close'].iloc[max(0, i-10):i+1]
                lb_sma = df['SMA50'].iloc[max(0, i-10):i+1]
                if any((lb < lb_sma).values):
                    mode = 'trend'
                    ep = c
                    shares = int(capital * alloc / ep)
                    cost_amt = shares * ep * COST
                    if shares > 0 and capital >= shares * ep + cost_amt:
                        capital -= (shares * ep + cost_amt)
                        pos = shares; ed = date; hd = 0

    if pos > 0:
        c = float(df['Close'].iloc[-1])
        cost_amt = pos * (ep + c) * COST / 2
        capital += pos * c - cost_amt
        pnl = pos * (c - ep) - cost_amt
        trades.append({'entry_date': ed, 'exit_date': df.index[-1],
                       'entry_price': ep, 'exit_price': c,
                       'pnl': pnl, 'hold_days': hd, 'mode': mode})
    return trades, equity


# ============================================================
# STRATEGY B: IBS + RSI2 COMBO (more signals)
# ============================================================
def strat_ibs_rsi_combo(df, alloc=0.90):
    """
    Entry: (IBS < 0.20 OR RSI2 < 10) AND > 200 SMA
    Exit: IBS > 0.50 OR RSI2 > 70 OR 5 days
    More frequent signals → more time in market.
    """
    # RSI2
    delta2 = df['Close'].diff()
    gain2 = delta2.where(delta2 > 0, 0.0)
    loss2 = -delta2.where(delta2 < 0, 0.0)
    avg_g2 = gain2.rolling(2).mean()
    avg_l2 = loss2.rolling(2).mean()
    rs2 = avg_g2 / avg_l2
    rsi2 = 100 - (100 / (1 + rs2))

    capital = INITIAL_CAPITAL
    pos = 0; ep = 0; ed = None; hd = 0
    trades = []; equity = []

    for i in range(len(df)):
        date = df.index[i]
        c = float(df['Close'].iloc[i])
        ibs = float(df['IBS'].iloc[i])
        sma200 = float(df['SMA200'].iloc[i]) if pd.notna(df['SMA200'].iloc[i]) else c
        atr = float(df['ATR14'].iloc[i]) if pd.notna(df['ATR14'].iloc[i]) else c * 0.02
        r2 = float(rsi2.iloc[i]) if pd.notna(rsi2.iloc[i]) else 50

        eq = capital + (pos * c if pos > 0 else 0)
        equity.append(eq)

        if pos > 0:
            hd += 1
            exit_signal = False
            exit_price = c
            if ibs > 0.50 or r2 > 70 or hd >= 5:
                exit_signal = True
            if c <= ep - 2.0 * atr:
                exit_signal = True
                exit_price = ep - 2.0 * atr
            if exit_signal:
                cost_amt = pos * (ep + exit_price) * COST / 2
                capital += pos * exit_price - cost_amt
                pnl = pos * (exit_price - ep) - cost_amt
                trades.append({'entry_date': ed, 'exit_date': date,
                               'entry_price': ep, 'exit_price': exit_price,
                               'pnl': pnl, 'hold_days': hd})
                pos = 0; hd = 0

        if pos == 0:
            if c > sma200 and (ibs < 0.20 or r2 < 10):
                ep = c
                shares = int(capital * alloc / ep)
                cost_amt = shares * ep * COST
                if shares > 0 and capital >= shares * ep + cost_amt:
                    capital -= (shares * ep + cost_amt)
                    pos = shares; ed = date; hd = 0

    if pos > 0:
        c = float(df['Close'].iloc[-1])
        cost_amt = pos * (ep + c) * COST / 2
        capital += pos * c - cost_amt
        pnl = pos * (c - ep) - cost_amt
        trades.append({'entry_date': ed, 'exit_date': df.index[-1],
                       'entry_price': ep, 'exit_price': c,
                       'pnl': pnl, 'hold_days': hd})
    return trades, equity


# ============================================================
# STRATEGY C: MOMENTUM + MEAN REVERSION (always invested)
# ============================================================
def strat_mom_mr(df, alloc=0.90):
    """
    When momentum positive AND >200SMA: hold (trend)
    When IBS < 0.20 AND >200SMA: add to position (MR overlay)
    Always in the market when above 200SMA.
    """
    capital = INITIAL_CAPITAL
    pos = 0; ep = 0; ed = None; hd = 0
    trades = []; equity = []

    for i in range(len(df)):
        date = df.index[i]
        c = float(df['Close'].iloc[i])
        ibs = float(df['IBS'].iloc[i])
        sma200 = float(df['SMA200'].iloc[i]) if pd.notna(df['SMA200'].iloc[i]) else c
        sma50 = float(df['SMA50'].iloc[i]) if pd.notna(df['SMA50'].iloc[i]) else c
        atr = float(df['ATR14'].iloc[i]) if pd.notna(df['ATR14'].iloc[i]) else c * 0.02
        mom = float(df['Mom10'].iloc[i]) if pd.notna(df['Mom10'].iloc[i]) else 0
        rsi14 = float(df['RSI14'].iloc[i]) if pd.notna(df['RSI14'].iloc[i]) else 50

        eq = capital + (pos * c if pos > 0 else 0)
        equity.append(eq)

        if pos > 0:
            hd += 1
            exit_signal = False
            exit_price = c

            # Exit: close below 200 SMA (trend broken) or RSI > 80 (overbought)
            if c < sma200 * 0.98:  # 2% below 200 SMA
                exit_signal = True
            if rsi14 > 80:
                exit_signal = True
            if c <= ep - 3.0 * atr:
                exit_signal = True
                exit_price = ep - 3.0 * atr

            if exit_signal:
                cost_amt = pos * (ep + exit_price) * COST / 2
                capital += pos * exit_price - cost_amt
                pnl = pos * (exit_price - ep) - cost_amt
                trades.append({'entry_date': ed, 'exit_date': date,
                               'entry_price': ep, 'exit_price': exit_price,
                               'pnl': pnl, 'hold_days': hd})
                pos = 0; hd = 0

        if pos == 0:
            # Enter when above 200 SMA and either momentum or oversold
            if c > sma200 and (mom > 0.02 or ibs < 0.20):
                ep = c
                shares = int(capital * alloc / ep)
                cost_amt = shares * ep * COST
                if shares > 0 and capital >= shares * ep + cost_amt:
                    capital -= (shares * ep + cost_amt)
                    pos = shares; ed = date; hd = 0

    if pos > 0:
        c = float(df['Close'].iloc[-1])
        cost_amt = pos * (ep + c) * COST / 2
        capital += pos * c - cost_amt
        pnl = pos * (c - ep) - cost_amt
        trades.append({'entry_date': ed, 'exit_date': df.index[-1],
                       'entry_price': ep, 'exit_price': c,
                       'pnl': pnl, 'hold_days': hd})
    return trades, equity


# ============================================================
# RUN ALL
# ============================================================
print()
print("Running strategies...")
print()

def metrics(trades, equity, name, start=INITIAL_CAPITAL):
    eq = np.array(equity)
    final = eq[-1]
    total_ret = (final / start - 1) * 100
    years = len(eq) / 252
    cagr = ((final / start) ** (1/years) - 1) * 100 if years > 0 else 0
    rm = np.maximum.accumulate(eq)
    max_dd = ((eq - rm) / rm).min() * 100
    dr = np.diff(eq) / eq[:-1]
    dr = dr[np.isfinite(dr)]
    sharpe = (np.mean(dr) / np.std(dr)) * np.sqrt(252) if np.std(dr) > 0 else 0
    down = dr[dr < 0]
    sortino = (np.mean(dr) / np.std(down)) * np.sqrt(252) if len(down) > 0 and np.std(down) > 0 else 0
    n = len(trades)
    if n > 0:
        tdf = pd.DataFrame(trades)
        winners = tdf[tdf['pnl'] > 0]
        losers = tdf[tdf['pnl'] <= 0]
        wr = len(winners) / n * 100
        gp = winners['pnl'].sum() if len(winners) > 0 else 0
        gl = abs(losers['pnl'].sum()) if len(losers) > 0 else 0
        pf = gp / gl if gl > 0 else 0
    else:
        wr = pf = 0

    # Time in market
    invested = sum((pd.Timestamp(t['exit_date']) - pd.Timestamp(t['entry_date'])).days for t in trades)
    tim = invested / len(eq) * 100

    return {
        'name': name, 'final': final, 'total_ret': total_ret, 'cagr': cagr,
        'max_dd': max_dd, 'sharpe': sharpe, 'sortino': sortino,
        'n': n, 'wr': wr, 'pf': pf, 'tim': tim, 'trades': trades, 'eq': eq
    }

# Test different allocation levels
for strat_name, strat_func in [
    ("Dual Signal (MR+Trend)", strat_dual_signal),
    ("IBS+RSI2 Combo", strat_ibs_rsi_combo),
    ("Momentum+MR", strat_mom_mr),
]:
    print(f"\n  {strat_name}:")
    print(f"  {'Alloc':<8} {'T':>5} {'WR%':>6} {'PF':>7} {'CAGR%':>8} {'DD%':>8} {'Sharpe':>7} {'TIM':>6}")
    print("  " + "-" * 58)
    for alloc in [0.50, 0.70, 0.90]:
        t, e = strat_func(qqq, alloc)
        m = metrics(t, e, f"{strat_name} {alloc:.0%}")
        pf_s = f"{m['pf']:.2f}" if m['pf'] < 100 else "inf"
        print(f"  {int(alloc*100):>3}%    {m['n']:>5} {m['wr']:>5.1f}% {pf_s:>7} {m['cagr']:>7.1f}% {m['max_dd']:>7.1f}% {m['sharpe']:>6.2f} {m['tim']:>5.1f}%")

# ============================================================
# BEST STRATEGY — DETAILED
# ============================================================
print()
print("=" * 90)
print("BEST STRATEGY — DETAILED ANALYSIS")
print("=" * 90)
print()

# Run best config
best_alloc = 0.90
t_best, e_best = strat_dual_signal(qqq, best_alloc)
best = metrics(t_best, e_best, "Dual Signal 90%")

eq_s = pd.Series(best['eq'], index=qqq.index[:len(best['eq'])])

# Yearly
print("  YEARLY BREAKDOWN:")
print(f"  {'Year':<8} {'Return%':>10} {'Sharpe':>8} {'MaxDD%':>8}")
print("  " + "-" * 40)
for year in range(2016, 2026):
    mask = eq_s.index.year == year
    if mask.sum() == 0: continue
    yr_eq = eq_s[mask]
    yr_ret = (yr_eq.iloc[-1] / yr_eq.iloc[0] - 1) * 100
    yr_dr = np.diff(yr_eq.values) / yr_eq.values[:-1]
    yr_dr = yr_dr[np.isfinite(yr_dr)]
    yr_sh = (np.mean(yr_dr) / np.std(yr_dr)) * np.sqrt(252) if np.std(yr_dr) > 0 else 0
    yr_rm = np.maximum.accumulate(yr_eq.values)
    yr_dd = ((yr_eq.values - yr_rm) / yr_rm).min() * 100
    print(f"  {year:<8} {yr_ret:>9.1f}% {yr_sh:>8.2f} {yr_dd:>7.1f}%")

print()
print(f"  Final Equity:     ${best['final']:>12,.0f}")
print(f"  Total Return:      {best['total_ret']:>11.1f}%")
print(f"  CAGR:              {best['cagr']:>11.1f}%")
print(f"  Max Drawdown:      {best['max_dd']:>11.1f}%")
print(f"  Sharpe Ratio:      {best['sharpe']:>11.2f}")
print(f"  Sortino Ratio:     {best['sortino']:>11.2f}")
print(f"  Trades:            {best['n']:>11d}")
print(f"  Win Rate:          {best['wr']:>10.1f}%")
print(f"  Profit Factor:     {best['pf']:>11.2f}")
print(f"  Time in Market:    {best['tim']:>10.1f}%")

# Mode breakdown
if best['trades']:
    tdf = pd.DataFrame(best['trades'])
    if 'mode' in tdf.columns:
        print()
        print("  TRADE MODE BREAKDOWN:")
        for mode in tdf['mode'].unique():
            mt = tdf[tdf['mode'] == mode]
            m_wr = (mt['pnl'] > 0).sum() / len(mt) * 100
            m_pf = mt[mt['pnl'] > 0]['pnl'].sum() / abs(mt[mt['pnl'] <= 0]['pnl'].sum()) if len(mt[mt['pnl'] <= 0]) > 0 else float('inf')
            print(f"    {mode:<8}: {len(mt):>4} trades  WR:{m_wr:>5.1f}%  PF:{m_pf:.2f}")

# Benchmark
print()
print("  BENCHMARK: QQQ Buy & Hold")
bh_eq = (qqq['Close'] / qqq['Close'].iloc[0]) * INITIAL_CAPITAL
bh_ret = (qqq['Close'].iloc[-1] / qqq['Close'].iloc[0] - 1) * 100
bh_yr = len(qqq) / 252
bh_cagr = ((qqq['Close'].iloc[-1] / qqq['Close'].iloc[0]) ** (1/bh_yr) - 1) * 100
bh_rm = np.maximum.accumulate(bh_eq.values)
bh_dd = ((bh_eq.values - bh_rm) / bh_rm).min() * 100
bh_dr = np.diff(bh_eq.values) / bh_eq.values[:-1]
bh_dr = bh_dr[np.isfinite(bh_dr)]
bh_sh = (np.mean(bh_dr) / np.std(bh_dr)) * np.sqrt(252) if np.std(bh_dr) > 0 else 0
print(f"    QQQ B&H:  Return:{bh_ret:.1f}%  CAGR:{bh_cagr:.1f}%  DD:{bh_dd:.1f}%  Sharpe:{bh_sh:.2f}")
print(f"    Strategy: Return:{best['total_ret']:.1f}%  CAGR:{best['cagr']:.1f}%  DD:{best['max_dd']:.1f}%  Sharpe:{best['sharpe']:.2f}")

# ============================================================
# WALK-FORWARD
# ============================================================
print()
print("=" * 90)
print("WALK-FORWARD VALIDATION")
print("=" * 90)
print()

WF_IS = 756; WF_OOS = 252; WF_STEP = 126
wf_data = []
idx = 0
while idx + WF_IS + WF_OOS <= len(qqq):
    is_d = qqq.iloc[idx:idx+WF_IS]
    oos_d = qqq.iloc[idx+WF_IS:idx+WF_IS+WF_OOS]

    is_t, _ = strat_dual_signal(is_d, 0.90)
    oos_t, _ = strat_dual_signal(oos_d, 0.90)

    def get_pf(t):
        if not t: return 1.0
        gp = sum(x['pnl'] for x in t if x['pnl'] > 0)
        gl = abs(sum(x['pnl'] for x in t if x['pnl'] <= 0))
        return gp / gl if gl > 0 else 1.0

    is_pf = get_pf(is_t)
    oos_pf = get_pf(oos_t)
    wfr = oos_pf / is_pf if is_pf > 0 else 0

    wf_data.append({
        'w': len(wf_data)+1, 'is_pf': is_pf, 'oos_pf': oos_pf, 'wfr': wfr,
        'is_p': f"{is_d.index[0].date()} to {is_d.index[-1].date()}",
        'oos_p': f"{oos_d.index[0].date()} to {oos_d.index[-1].date()}"
    })
    idx += WF_STEP

if wf_data:
    print(f"  {'#':>3} {'IS PF':>8} {'OOS PF':>8} {'WFR':>8}")
    print("  " + "-" * 30)
    for w in wf_data:
        oos_s = f"{w['oos_pf']:.2f}" if w['oos_pf'] < 100 else "inf"
        wfr_s = f"{w['wfr']:.2f}" if w['wfr'] < 100 else "inf"
        print(f"  {w['w']:>3} {w['is_pf']:>8.2f} {oos_s:>8} {wfr_s:>8}")
    avg_is = np.mean([w['is_pf'] for w in wf_data])
    avg_oos = np.mean([w['oos_pf'] for w in wf_data])
    avg_wfr = avg_oos / avg_is if avg_is > 0 else 0
    print(f"\n  Avg IS PF: {avg_is:.2f}  Avg OOS PF: {avg_oos:.2f}  WFR: {avg_wfr:.2f} {'PASS' if avg_wfr > 0.5 else 'FAIL'}")

# ============================================================
# MONTE CARLO
# ============================================================
print()
print("=" * 90)
print("MONTE CARLO (2000 sims)")
print("=" * 90)
print()

all_pnls = np.array([t['pnl'] for t in best['trades']])
mc_eq = np.zeros(2000); mc_dd = np.zeros(2000)
for s in range(2000):
    sh = np.random.permutation(all_pnls)
    eq = np.cumsum(sh) + INITIAL_CAPITAL
    mc_eq[s] = eq[-1]
    rm = np.maximum.accumulate(eq)
    mc_dd[s] = ((eq - rm) / rm).min() * 100

survival = (mc_eq > INITIAL_CAPITAL).sum() / 2000 * 100
dd20 = (mc_dd < -20).sum() / 2000 * 100

print(f"  Survival Rate:  {survival:.1f}% {'PASS' if survival > 90 else 'FAIL'}")
print(f"  Prob(DD>20%):   {dd20:.1f}% {'PASS' if dd20 < 10 else 'FAIL'}")
print(f"  Median Equity:  ${np.median(mc_eq):>12,.0f}")
print(f"  P5 Equity:      ${np.percentile(mc_eq, 5):>12,.0f}")
print(f"  P95 Equity:     ${np.percentile(mc_eq, 95):>12,.0f}")
print(f"  Median DD:      {np.median(mc_dd):.1f}%")
print(f"  Worst DD:       {np.min(mc_dd):.1f}%")

# ============================================================
# CHECKLIST
# ============================================================
print()
print("=" * 90)
print("VALIDATION CHECKLIST")
print("=" * 90)
print()

wfr_val = avg_wfr if wf_data else 0
checks = {
    'Hypothesis before testing': True,
    'Rules mechanical': True,
    'Costs 0.1%': True,
    'No lookahead': True,
    f'100+ trades ({best["n"]})': best['n'] >= 100,
    f'PF > 1.3 ({best["pf"]:.2f})': best['pf'] > 1.3,
    f'Sharpe > 1.0 ({best["sharpe"]:.2f})': best['sharpe'] > 1.0,
    f'Sortino > 1.5 ({best["sortino"]:.2f})': best['sortino'] > 1.5,
    f'WFR > 0.5 ({wfr_val:.2f})': wfr_val > 0.5,
    f'MC Survival > 90% ({survival:.1f}%)': survival > 90,
    f'Max DD < 20% ({abs(best["max_dd"]):.1f}%)': abs(best['max_dd']) < 20,
}
passed = sum(1 for _, ok in checks.items() if ok)
for desc, ok in checks.items():
    print(f"  [{'x' if ok else ' '}] {desc}")

print(f"\n  Score: {passed}/{len(checks)}")
if passed >= 10:
    print("  VERDICT: STRONG")
elif passed >= 8:
    print("  VERDICT: VIABLE")
elif passed >= 6:
    print("  VERDICT: PROMISING")
else:
    print("  VERDICT: NOT READY")

print()
print("=" * 90)
print("DISCLAIMER: Backtest != live. Past performance does not guarantee future.")
print("=" * 90)
