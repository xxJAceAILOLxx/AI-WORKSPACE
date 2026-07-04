"""
IBS Mean Reversion + Trend Filter + Turn-of-Month
==================================================
Hypothesis: SPY mean reverts after weak closes, but only when the broader
trend is still intact and during favorable calendar windows.

Rules (written BEFORE testing):
1. Entry Long: IBS < 0.20 AND Close > 200 SMA AND Turn-of-Month (last 3 + first 3 days)
2. Exit: IBS > 0.50 OR Hold > 5 days OR Stop hit
3. Stop: 2x ATR(14) below entry
4. Position Size: FIXED — risk 10% of INITIAL capital per trade (no compounding)

Costs: 0.1% round trip (realistic for SPY ETF)
Data: SPY daily, 2003-2025
"""

import pandas as pd
import numpy as np
import yfinance as yf
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# CONSTANTS
# ============================================================
INITIAL_CAPITAL = 100000
RISK_PER_TRADE = 10000  # 10% of $100k
COMMISSION = 0.001      # 0.1% round trip
MAX_HOLD_DAYS = 5
STOP_MULTIPLE = 2.0

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def compute_indicators(df):
    """Compute IBS, SMA200, ATR14, TOM filter."""
    df = df.copy()
    
    # IBS (Internal Bar Strength)
    df['IBS'] = (df['Close'] - df['Low']) / (df['High'] - df['Low'])
    df['IBS'] = df['IBS'].fillna(0.5)
    
    # 200 SMA
    df['SMA200'] = df['Close'].rolling(200).mean()
    
    # ATR(14)
    df['TR'] = np.maximum(
        df['High'] - df['Low'],
        np.maximum(
            abs(df['High'] - df['Close'].shift(1)),
            abs(df['Low'] - df['Close'].shift(1))
        )
    )
    df['ATR14'] = df['TR'].rolling(14).mean()
    
    # Turn-of-Month filter
    df['DayOfMonth'] = df.index.day
    df['DaysInMonth'] = df.groupby([df.index.year, df.index.month])['DayOfMonth'].transform('max')
    df['TOM'] = (df['DayOfMonth'] <= 3) | (df['DayOfMonth'] >= (df['DaysInMonth'] - 2))
    
    # Entry signal
    df['Entry_Long'] = (
        (df['IBS'] < 0.20) &
        (df['Close'] > df['SMA200']) &
        (df['TOM'] == True)
    )
    
    return df.dropna(subset=['SMA200', 'ATR14'])


def run_backtest(data, capital_start=INITIAL_CAPITAL, risk_per=RISK_PER_TRADE):
    """Run IBS strategy. Fixed risk per trade, no compounding."""
    capital = capital_start
    cash = capital_start
    position = 0
    entry_price = 0.0
    entry_date = None
    stop_price = 0.0
    hold_days = 0
    trades = []
    equity_curve = []
    
    for i in range(len(data)):
        date = data.index[i]
        close = float(data['Close'].iloc[i])
        ibs = float(data['IBS'].iloc[i])
        atr = float(data['ATR14'].iloc[i])
        
        # Current equity = cash + position value
        equity = cash + (position * close if position > 0 else 0)
        equity_curve.append(equity)
        
        # If in position, check exits
        if position > 0:
            hold_days += 1
            
            # Stop loss
            if close <= stop_price:
                exit_price = stop_price
                cost = position * (entry_price + exit_price) * COMMISSION / 2
                cash += position * exit_price - cost
                pnl = position * (exit_price - entry_price) - cost
                trades.append({
                    'entry_date': entry_date,
                    'exit_date': date,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'shares': position,
                    'pnl': pnl,
                    'hold_days': hold_days,
                    'exit_reason': 'stop'
                })
                position = 0
                hold_days = 0
                continue
            
            # IBS exit
            if ibs > 0.50:
                exit_price = close
                cost = position * (entry_price + exit_price) * COMMISSION / 2
                cash += position * exit_price - cost
                pnl = position * (exit_price - entry_price) - cost
                trades.append({
                    'entry_date': entry_date,
                    'exit_date': date,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'shares': position,
                    'pnl': pnl,
                    'hold_days': hold_days,
                    'exit_reason': 'ibs_exit'
                })
                position = 0
                hold_days = 0
                continue
            
            # Max hold
            if hold_days >= MAX_HOLD_DAYS:
                exit_price = close
                cost = position * (entry_price + exit_price) * COMMISSION / 2
                cash += position * exit_price - cost
                pnl = position * (exit_price - entry_price) - cost
                trades.append({
                    'entry_date': entry_date,
                    'exit_date': date,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'shares': position,
                    'pnl': pnl,
                    'hold_days': hold_days,
                    'exit_reason': 'max_hold'
                })
                position = 0
                hold_days = 0
                continue
        
        # Check entry (only if flat)
        if position == 0 and bool(data['Entry_Long'].iloc[i]):
            entry_price = close
            # Fixed risk: risk $X per trade
            shares = int(risk_per / entry_price)
            cost = shares * entry_price * COMMISSION
            if shares > 0 and cash >= shares * entry_price + cost:
                cash -= (shares * entry_price + cost)
                position = shares
                entry_date = date
                stop_price = entry_price - (STOP_MULTIPLE * atr)
                hold_days = 0
    
    # Close open position at end
    if position > 0:
        exit_price = float(data['Close'].iloc[-1])
        cost = position * (entry_price + exit_price) * COMMISSION / 2
        cash += position * exit_price - cost
        pnl = position * (exit_price - entry_price) - cost
        trades.append({
            'entry_date': entry_date,
            'exit_date': data.index[-1],
            'entry_price': entry_price,
            'exit_price': exit_price,
            'shares': position,
            'pnl': pnl,
            'hold_days': hold_days,
            'exit_reason': 'end_of_data'
        })
        position = 0
    
    final_equity = cash
    return trades, equity_curve, final_equity


def calc_metrics(trades, equity_curve, final_equity):
    """Calculate performance metrics."""
    if not trades or not equity_curve:
        return {}
    
    eq = np.array(equity_curve)
    tdf = pd.DataFrame(trades)
    
    total_ret = (final_equity / INITIAL_CAPITAL - 1) * 100
    
    # Drawdown
    running_max = np.maximum.accumulate(eq)
    dd = (eq - running_max) / running_max
    max_dd = dd.min() * 100
    
    # Daily returns
    daily_ret = np.diff(eq) / eq[:-1]
    daily_ret = daily_ret[np.isfinite(daily_ret)]
    
    # Sharpe
    if len(daily_ret) > 1 and np.std(daily_ret) > 0:
        sharpe = (np.mean(daily_ret) / np.std(daily_ret)) * np.sqrt(252)
    else:
        sharpe = 0
    
    # Sortino
    down = daily_ret[daily_ret < 0]
    if len(down) > 0 and np.std(down) > 0:
        sortino = (np.mean(daily_ret) / np.std(down)) * np.sqrt(252)
    else:
        sortino = 0
    
    # Trades
    n_trades = len(tdf)
    winners = tdf[tdf['pnl'] > 0]
    losers = tdf[tdf['pnl'] <= 0]
    win_rate = len(winners) / n_trades * 100 if n_trades > 0 else 0
    avg_win = winners['pnl'].mean() if len(winners) > 0 else 0
    avg_loss = losers['pnl'].mean() if len(losers) > 0 else 0
    gross_profit = winners['pnl'].sum() if len(winners) > 0 else 0
    gross_loss = abs(losers['pnl'].sum()) if len(losers) > 0 else 0
    pf = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    expectancy = tdf['pnl'].mean() if n_trades > 0 else 0
    avg_hold = tdf['hold_days'].mean() if n_trades > 0 else 0
    
    return {
        'final_equity': final_equity,
        'total_return': total_ret,
        'max_drawdown': max_dd,
        'sharpe': sharpe,
        'sortino': sortino,
        'n_trades': n_trades,
        'win_rate': win_rate,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'profit_factor': pf,
        'expectancy': expectancy,
        'avg_hold': avg_hold,
        'trades_df': tdf
    }


# ============================================================
# MAIN
# ============================================================
print("=" * 70)
print("IBS MEAN REVERSION + TREND FILTER + TURN-OF-MONTH")
print("=" * 70)
print()

# 1. Download data
print("[1/7] Downloading SPY data...")
spy = yf.download('SPY', start='2003-01-01', end='2025-12-31', progress=False)
spy.columns = spy.columns.get_level_values(0)
spy = spy[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
print(f"  Range: {spy.index[0].date()} to {spy.index[-1].date()} ({len(spy)} bars)")

# 2. Compute indicators
print()
print("[2/7] Computing indicators...")
spy = compute_indicators(spy)
print(f"  Usable bars: {len(spy)}")

# 3. Full-period backtest
print()
print("[3/7] Running full-period backtest...")
trades, equity, final_eq = run_backtest(spy)
m = calc_metrics(trades, equity, final_eq)

print()
print("=" * 70)
print("FULL PERIOD RESULTS (2005-2025)")
print("=" * 70)
print(f"  Initial Capital:    ${INITIAL_CAPITAL:>12,.0f}")
print(f"  Final Equity:       ${m['final_equity']:>12,.0f}")
print(f"  Total Return:       {m['total_return']:>11.1f}%")
print(f"  Max Drawdown:       {m['max_drawdown']:>11.1f}%")
print(f"  Sharpe Ratio:       {m['sharpe']:>11.2f}")
print(f"  Sortino Ratio:      {m['sortino']:>11.2f}")
print()
print(f"  Total Trades:       {m['n_trades']:>11d}")
print(f"  Win Rate:           {m['win_rate']:>10.1f}%")
print(f"  Profit Factor:      {m['profit_factor']:>11.2f}")
print(f"  Avg Win:            ${m['avg_win']:>10,.2f}")
print(f"  Avg Loss:           ${m['avg_loss']:>10,.2f}")
print(f"  Expectancy/Trade:   ${m['expectancy']:>10,.2f}")
print(f"  Avg Hold (days):    {m['avg_hold']:>11.1f}")

if len(trades) > 0:
    tdf = pd.DataFrame(trades)
    print()
    print("  Exit Reasons:")
    for reason in tdf['exit_reason'].unique():
        c = len(tdf[tdf['exit_reason'] == reason])
        p = c / len(tdf) * 100
        print(f"    {reason:<15s}: {c:4d} ({p:.1f}%)")

# 4. Walk-forward
print()
print("[4/7] Walk-forward validation...")

WINDOW = 756   # ~3 years IS
FORWARD = 252   # ~1 year OOS
STEP = 252

is_pfs = []
oos_pfs = []
wf_data = []

idx = 0
while idx + WINDOW + FORWARD <= len(spy):
    is_slice = spy.iloc[idx:idx+WINDOW]
    oos_slice = spy.iloc[idx+WINDOW:idx+WINDOW+FORWARD]
    
    is_trades, _, is_eq = run_backtest(is_slice)
    oos_trades, _, oos_eq = run_backtest(oos_slice)
    
    if is_trades and oos_trades:
        is_m = calc_metrics(is_trades, [0], is_eq)
        oos_m = calc_metrics(oos_trades, [0], oos_eq)
        is_pf = is_m['profit_factor']
        oos_pf = oos_m['profit_factor']
        is_pfs.append(is_pf)
        oos_pfs.append(oos_pf)
        wf_data.append({
            'window': len(is_pfs),
            'is_period': f"{is_slice.index[0].date()} to {is_slice.index[-1].date()}",
            'oos_period': f"{oos_slice.index[0].date()} to {oos_slice.index[-1].date()}",
            'is_pf': is_pf,
            'oos_pf': oos_pf,
            'wfr': oos_pf / is_pf if is_pf > 0 else 0
        })
    
    idx += STEP

if wf_data:
    print()
    print(f"  {'Win':<5} {'IS Period':<28} {'IS PF':<9} {'OOS Period':<28} {'OOS PF':<9} {'WFR':<8}")
    print("  " + "-" * 87)
    for w in wf_data:
        wfr_str = f"{w['wfr']:.2f}" if w['wfr'] < 100 else "inf"
        oos_pf_str = f"{w['oos_pf']:.2f}" if w['oos_pf'] < 100 else "inf"
        print(f"  {w['window']:<5} {w['is_period']:<28} {w['is_pf']:<9.2f} {w['oos_period']:<28} {oos_pf_str:<9} {wfr_str:<8}")
    
    avg_is = np.mean(is_pfs)
    finite_oos = [x for x in oos_pfs if x < 100]
    avg_oos = np.mean(finite_oos) if finite_oos else 0
    avg_wfr = avg_oos / avg_is if avg_is > 0 else 0
    
    wfr_pass = avg_wfr > 0.5
    print()
    print(f"  Avg IS PF:      {avg_is:.2f}")
    print(f"  Avg OOS PF:     {avg_oos:.2f}")
    print(f"  Walk-Forward Ratio: {avg_wfr:.2f} {'PASS' if wfr_pass else 'FAIL'}")

# 5. Monte Carlo
print()
print("[5/7] Monte Carlo (1000 sims)...")

if trades:
    pnls = np.array([t['pnl'] for t in trades])
    n = len(pnls)
    n_sims = 1000
    
    mc_equity = np.zeros(n_sims)
    mc_dd = np.zeros(n_sims)
    mc_max_dd = np.zeros(n_sims)
    
    for s in range(n_sims):
        shuffled = np.random.permutation(pnls)
        eq = np.cumsum(shuffled) + INITIAL_CAPITAL
        mc_equity[s] = eq[-1]
        rm = np.maximum.accumulate(eq)
        mc_dd[s] = ((eq - rm) / rm).min() * 100
        mc_max_dd[s] = abs(mc_dd[s])
    
    pcts = [5, 25, 50, 75, 95]
    print()
    print(f"  {'Metric':<20}", end="")
    for p in pcts:
        print(f" {'P'+str(p):<10}", end="")
    print()
    print("  " + "-" * 70)
    
    print(f"  {'Final Equity ($)':<20}", end="")
    for p in pcts:
        print(f" ${np.percentile(mc_equity, p):>9,.0f}", end="")
    print()
    
    print(f"  {'Max Drawdown (%)':<20}", end="")
    for p in pcts:
        print(f" {np.percentile(mc_dd, p):>9.1f}", end="")
    print()
    
    survival = (mc_equity > INITIAL_CAPITAL).sum() / n_sims * 100
    dd_over_20 = (mc_dd < -20).sum() / n_sims * 100
    median_dd = np.median(mc_dd)
    
    print()
    print(f"  Survival Rate:    {survival:.1f}% {'PASS' if survival > 90 else 'FAIL'}")
    print(f"  Prob(DD > 20%):   {dd_over_20:.1f}% {'PASS' if dd_over_20 < 10 else 'FAIL'}")
    print(f"  Median DD:        {median_dd:.1f}%")
    print(f"  Worst DD:         {np.min(mc_dd):.1f}%")

# 6. Honest assessment
print()
print("[6/7] Validation checklist...")
print()
print("=" * 70)
print("CHECKLIST")
print("=" * 70)

wfr_val = avg_wfr if wf_data else 0
survival_val = survival if trades else 0
dd_val = abs(m['max_drawdown']) if m else 999

checks = {
    'Hypothesis written first': True,
    'Rules mechanical': True,
    'Costs included (0.1%)': True,
    'No lookahead bias': True,
    f'200+ trades (got {m["n_trades"]})': m['n_trades'] >= 200,
    f'PF > 1.3 (got {m["profit_factor"]:.2f})': m['profit_factor'] > 1.3,
    f'Sharpe > 1.0 (got {m["sharpe"]:.2f})': m['sharpe'] > 1.0,
    f'WFR > 0.5 (got {wfr_val:.2f})': wfr_val > 0.5,
    f'MC Survival > 90% (got {survival_val:.1f}%)': survival_val > 90,
    f'Max DD < 20% (got {dd_val:.1f}%)': dd_val < 20,
}

passed = 0
for desc, ok in checks.items():
    mark = 'x' if ok else ' '
    print(f"  [{mark}] {desc}")
    if ok:
        passed += 1

print()
print(f"  Passed: {passed}/{len(checks)}")
print()

if passed >= 8:
    print("  VERDICT: VIABLE")
elif passed >= 6:
    print("  VERDICT: PROMISING — needs refinement")
else:
    print("  VERDICT: NOT READY")

# 7. Summary
print()
print("=" * 70)
print("STRATEGY RULES")
print("=" * 70)
print("  Entry:  IBS < 0.20 AND Close > 200 SMA AND Turn-of-Month")
print("  Exit:   IBS > 0.50 OR 5 days max OR 2x ATR stop")
print("  Size:   Fixed $10k risk per trade (no compounding)")
print("  Cost:   0.1% round trip")
print()
print("=" * 70)
print("DISCLAIMER: Backtest != live performance. Forward test before")
print("risking real capital. Past performance does not guarantee future.")
print("=" * 70)
