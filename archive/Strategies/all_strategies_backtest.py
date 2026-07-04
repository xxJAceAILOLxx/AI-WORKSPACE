"""
All Strategies Backtest — 10-Year Test (2016-2025)
===================================================
Backtests feasible strategies using daily data from yfinance.
Strategies requiring intraday data are marked as N/A.

Instruments: SPY, QQQ, IWM, VXX, SVXY, VIX
Period: 2016-01-01 to 2025-12-31
Costs: 0.1% round trip (ETFs), $40 round trip (VIX ETN)
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
COST_ETF = 0.001      # 0.1% round trip
COST_FUTURES = 40     # $40 round trip for VIX ETN
START = '2016-01-01'
END = '2025-12-31'

# ============================================================
# DATA DOWNLOAD
# ============================================================
print("=" * 80)
print("DOWNLOADING DATA...")
print("=" * 80)

tickers = ['SPY', 'QQQ', 'IWM', 'VXX', 'SVXY', '^VIX']
data = {}

for t in tickers:
    try:
        d = yf.download(t, start=START, end=END, progress=False)
        if hasattr(d.columns, 'get_level_values'):
            d.columns = d.columns.get_level_values(0)
        data[t] = d[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
        print(f"  {t}: {len(d)} bars")
    except Exception as e:
        print(f"  {t}: FAILED — {e}")

# Use ^VIX as VIX
if '^VIX' in data:
    data['VIX'] = data.pop('^VIX')

spy = data['SPY']
qqq = data['QQQ']
iwm = data['IWM']

# ============================================================
# INDICATOR HELPERS
# ============================================================

def calc_ibs(df):
    """Internal Bar Strength."""
    ibs = (df['Close'] - df['Low']) / (df['High'] - df['Low'])
    return ibs.fillna(0.5)

def calc_rsi(series, period=2):
    """RSI (Connors-style, period=2)."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calc_pct_b(df, period=20):
    """Connors %B — position within Bollinger Band."""
    sma = df['Close'].rolling(period).mean()
    std = df['Close'].rolling(period).std()
    upper = sma + 2 * std
    lower = sma - 2 * std
    return (df['Close'] - lower) / (upper - lower)

def calc_streak(series):
    """Consecutive down days streak."""
    streak = pd.Series(0, index=series.index)
    for i in range(1, len(series)):
        if series.iloc[i] < series.iloc[i-1]:
            streak.iloc[i] = streak.iloc[i-1] - 1
        else:
            streak.iloc[i] = 0
    return streak

def calc_atr(df, period=14):
    """Average True Range."""
    tr = np.maximum(
        df['High'] - df['Low'],
        np.maximum(
            abs(df['High'] - df['Close'].shift(1)),
            abs(df['Low'] - df['Close'].shift(1))
        )
    )
    return tr.rolling(period).mean()

# ============================================================
# BACKTEST ENGINE
# ============================================================

def backtest_long_only(df, signals, cost=COST_ETF, hold_period=None, stop_pct=None):
    """
    Simple long-only backtest.
    signals: boolean Series, True = buy at close
    hold_period: exit after N days (optional)
    stop_pct: stop loss % from entry (optional)
    Returns: trades list, equity curve
    """
    capital = INITIAL_CAPITAL
    position = 0
    entry_price = 0
    entry_idx = 0
    trades = []
    equity = []
    
    for i in range(len(df)):
        date = df.index[i]
        close = float(df['Close'].iloc[i])
        
        # Current equity
        eq = capital + (position * close if position > 0 else 0)
        equity.append(eq)
        
        # Check exits
        if position > 0:
            hold_days = i - entry_idx
            
            exit_signal = False
            exit_price = close
            
            # Hold period exit
            if hold_period and hold_days >= hold_period:
                exit_signal = True
            
            # Stop loss
            if stop_pct and close <= entry_price * (1 - stop_pct):
                exit_signal = True
                exit_price = entry_price * (1 - stop_pct)
            
            if exit_signal:
                cost_amt = position * exit_price * cost
                capital += position * exit_price - cost_amt
                pnl = position * (exit_price - entry_price) - cost_amt
                trades.append({
                    'entry_date': entry_date,
                    'exit_date': date,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'pnl': pnl,
                    'hold_days': hold_days,
                    'return_pct': (exit_price / entry_price - 1) * 100
                })
                position = 0
        
        # Check entry
        if position == 0 and i < len(signals) and bool(signals.iloc[i]):
            entry_price = close
            shares = int(capital * 0.95 / entry_price)  # 95% of capital
            cost_amt = shares * entry_price * cost
            if shares > 0 and capital >= shares * entry_price + cost_amt:
                capital -= (shares * entry_price + cost_amt)
                position = shares
                entry_date = date
                entry_idx = i
    
    # Close at end
    if position > 0:
        exit_price = float(df['Close'].iloc[-1])
        cost_amt = position * exit_price * cost
        capital += position * exit_price - cost_amt
        pnl = position * (exit_price - entry_price) - cost_amt
        trades.append({
            'entry_date': entry_date,
            'exit_date': df.index[-1],
            'entry_price': entry_price,
            'exit_price': exit_price,
            'pnl': pnl,
            'hold_days': len(df) - 1 - entry_idx,
            'return_pct': (exit_price / entry_price - 1) * 100
        })
    
    return trades, equity


def calc_metrics(trades, equity, name="Strategy"):
    """Calculate and print metrics."""
    if not trades:
        return {'name': name, 'n_trades': 0}
    
    tdf = pd.DataFrame(trades)
    eq = np.array(equity)
    final = eq[-1]
    total_ret = (final / INITIAL_CAPITAL - 1) * 100
    
    # Drawdown
    rm = np.maximum.accumulate(eq)
    dd = (eq - rm) / rm
    max_dd = dd.min() * 100
    
    # Daily returns
    daily_ret = np.diff(eq) / eq[:-1]
    daily_ret = daily_ret[np.isfinite(daily_ret)]
    
    sharpe = (np.mean(daily_ret) / np.std(daily_ret)) * np.sqrt(252) if np.std(daily_ret) > 0 else 0
    
    # Trade stats
    n = len(tdf)
    winners = tdf[tdf['pnl'] > 0]
    losers = tdf[tdf['pnl'] <= 0]
    wr = len(winners) / n * 100
    avg_win = winners['return_pct'].mean() if len(winners) > 0 else 0
    avg_loss = losers['return_pct'].mean() if len(losers) > 0 else 0
    gp = winners['pnl'].sum() if len(winners) > 0 else 0
    gl = abs(losers['pnl'].sum()) if len(losers) > 0 else 0
    pf = gp / gl if gl > 0 else float('inf')
    expectancy = tdf['pnl'].mean()
    avg_hold = tdf['hold_days'].mean()
    
    # CAGR
    years = len(eq) / 252
    cagr = ((final / INITIAL_CAPITAL) ** (1 / years) - 1) * 100 if years > 0 else 0
    
    return {
        'name': name,
        'final_equity': final,
        'total_return': total_ret,
        'cagr': cagr,
        'max_drawdown': max_dd,
        'sharpe': sharpe,
        'n_trades': n,
        'win_rate': wr,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'profit_factor': pf,
        'expectancy': expectancy,
        'avg_hold': avg_hold,
        'trades_df': tdf
    }


def print_result(m):
    """Print single strategy result."""
    if m['n_trades'] == 0:
        print(f"  {m['name']:<35} NO TRADES")
        return
    
    print(f"  {m['name']:<35} T:{m['n_trades']:>5}  WR:{m['win_rate']:>5.1f}%  PF:{m['profit_factor']:>6.2f}  "
          f"CAGR:{m['cagr']:>7.1f}%  DD:{m['max_drawdown']:>7.1f}%  Sharpe:{m['sharpe']:>5.2f}  "
          f"E[X]:${m['expectancy']:>8,.0f}")


# ============================================================
# STRATEGY 1: Multiple Days Down (Connors)
# ============================================================
def strat_multiple_days_down():
    """Buy after 5 consecutive down days in SPY."""
    df = spy.copy()
    df['streak'] = calc_streak(df['Close'])
    df['sma200'] = df['Close'].rolling(200).mean()
    
    signals = (df['streak'] <= -5) & (df['Close'] > df['sma200'])
    signals = signals.reindex(df.index, fill_value=False)
    
    trades, equity = backtest_long_only(df, signals, hold_period=5)
    return calc_metrics(trades, equity, "Multiple Days Down (5d streak, 200SMA, 5d hold)")


# ============================================================
# STRATEGY 2: 5-Day Low of the Range
# ============================================================
def strat_5day_low():
    """IBS < 0.25 AND Close < Lowest Low of 5 days."""
    df = spy.copy()
    df['ibs'] = calc_ibs(df)
    df['lowest_5'] = df['Low'].rolling(5).min().shift(1)
    
    signals = (df['ibs'] < 0.25) & (df['Close'] < df['lowest_5'])
    signals = signals.reindex(df.index, fill_value=False)
    
    trades, equity = backtest_long_only(df, signals, hold_period=5)
    return calc_metrics(trades, equity, "5-Day Low of Range (IBS<0.25, 5d hold)")


# ============================================================
# STRATEGY 3: Turn-of-Month (TOM)
# ============================================================
def strat_turn_of_month():
    """Buy last trading day of month, sell 3rd day of new month."""
    df = spy.copy()
    
    # Identify month boundaries
    df['month'] = df.index.month
    df['year'] = df.index.year
    df['ym'] = df['year'] * 100 + df['month']
    
    # Last trading day of each month
    df['is_month_end'] = df['ym'] != df['ym'].shift(-1)
    
    # Count days in new month
    df['day_in_month'] = df.groupby('ym').cumcount() + 1
    
    signals = pd.Series(False, index=df.index)
    
    for i in range(len(df)):
        if df['is_month_end'].iloc[i]:
            # Buy at month end, hold for 3 days
            signals.iloc[i] = True
    
    trades, equity = backtest_long_only(df, signals, hold_period=4)  # month end + 3 days
    return calc_metrics(trades, equity, "Turn-of-Month (buy MOC, sell +3d)")


# ============================================================
# STRATEGY 4: Mean Reversion + Seasonal Filter
# ============================================================
def strat_mr_seasonal():
    """IBS < 0.20 with seasonal filter — avoid Sep."""
    df = spy.copy()
    df['ibs'] = calc_ibs(df)
    df['sma200'] = df['Close'].rolling(200).mean()
    
    # Seasonal filter: avoid September, favor Nov-Apr
    df['month'] = df.index.month
    df['favorable'] = ~df['month'].isin([9])  # exclude September
    
    signals = (df['ibs'] < 0.20) & (df['Close'] > df['sma200']) & (df['favorable'])
    signals = signals.reindex(df.index, fill_value=False)
    
    trades, equity = backtest_long_only(df, signals, hold_period=3)
    return calc_metrics(trades, equity, "MR + Seasonal (IBS<0.2, 200SMA, no Sep, 3d)")


# ============================================================
# STRATEGY 5: IBS Simple (our baseline)
# ============================================================
def strat_ibs_simple():
    """IBS < 0.20, exit IBS > 0.50 or 5 days."""
    df = spy.copy()
    df['ibs'] = calc_ibs(df)
    
    signals = df['ibs'] < 0.20
    signals = signals.reindex(df.index, fill_value=False)
    
    trades, equity = backtest_long_only(df, signals, hold_period=5)
    return calc_metrics(trades, equity, "IBS Simple (IBS<0.2, 5d hold)")


# ============================================================
# STRATEGY 6: RSI(2) Mean Reversion
# ============================================================
def strat_rsi2():
    """Buy when RSI(2) < 10, sell when RSI(2) > 70 or 5 days."""
    df = spy.copy()
    df['rsi2'] = calc_rsi(df['Close'], 2)
    df['sma200'] = df['Close'].rolling(200).mean()
    
    signals = (df['rsi2'] < 10) & (df['Close'] > df['sma200'])
    signals = signals.reindex(df.index, fill_value=False)
    
    trades, equity = backtest_long_only(df, signals, hold_period=5)
    return calc_metrics(trades, equity, "RSI(2) Mean Reversion (RSI<10, 200SMA, 5d)")


# ============================================================
# STRATEGY 7: Connors %B
# ============================================================
def strat_pct_b():
    """Buy when %B < 0.10 (below lower BB), sell when %B > 0.90 or 5 days."""
    df = spy.copy()
    df['pct_b'] = calc_pct_b(df, 20)
    df['sma200'] = df['Close'].rolling(200).mean()
    
    signals = (df['pct_b'] < 0.10) & (df['Close'] > df['sma200'])
    signals = signals.reindex(df.index, fill_value=False)
    
    trades, equity = backtest_long_only(df, signals, hold_period=5)
    return calc_metrics(trades, equity, "Connors %B (<0.10, 200SMA, 5d)")


# ============================================================
# STRATEGY 8: MR Portfolio (RSI2 + IBS + %B + TOM)
# ============================================================
def strat_mr_portfolio():
    """Combine RSI2, IBS, %B, TOM — enter when 2+ signal."""
    df = spy.copy()
    df['ibs'] = calc_ibs(df)
    df['rsi2'] = calc_rsi(df['Close'], 2)
    df['pct_b'] = calc_pct_b(df, 20)
    df['sma200'] = df['Close'].rolling(200).mean()
    
    # Individual signals
    df['sig_ibs'] = (df['ibs'] < 0.20).astype(int)
    df['sig_rsi'] = (df['rsi2'] < 10).astype(int)
    df['sig_pctb'] = (df['pct_b'] < 0.10).astype(int)
    df['sig_tom'] = df['index.day'].apply(lambda x: x <= 3 or x >= 28) if hasattr(df.index, 'day') else 0
    
    # Need at least 2 signals
    df['score'] = df['sig_ibs'] + df['sig_rsi'] + df['sig_pctb']
    
    signals = (df['score'] >= 2) & (df['Close'] > df['sma200'])
    signals = signals.reindex(df.index, fill_value=False)
    
    trades, equity = backtest_long_only(df, signals, hold_period=5)
    return calc_metrics(trades, equity, "MR Portfolio (2+ of IBS/RSI2/%B, 200SMA, 5d)")


# ============================================================
# STRATEGY 9: QQQ Dual MA Trend
# ============================================================
def strat_qqq_dual_ma():
    """Buy QQQ when above two MAs, sell on single exit condition."""
    df = qqq.copy()
    df['sma50'] = df['Close'].rolling(50).mean()
    df['sma200'] = df['Close'].rolling(200).mean()
    
    # Entry: price above both SMAs
    # Exit: price closes below 50 SMA
    signals = (df['Close'] > df['sma50']) & (df['Close'] > df['sma200'])
    signals = signals.reindex(df.index, fill_value=False)
    
    # Custom backtest with MA exit
    capital = INITIAL_CAPITAL
    position = 0
    entry_price = 0
    entry_date = None
    trades = []
    equity = []
    
    for i in range(len(df)):
        date = df.index[i]
        close = float(df['Close'].iloc[i])
        sma50 = float(df['sma50'].iloc[i]) if pd.notna(df['sma50'].iloc[i]) else close
        
        eq = capital + (position * close if position > 0 else 0)
        equity.append(eq)
        
        if position > 0:
            # Exit if close below 50 SMA
            if close < sma50:
                cost_amt = position * close * COST_ETF
                capital += position * close - cost_amt
                pnl = position * (close - entry_price) - cost_amt
                trades.append({
                    'entry_date': entry_date,
                    'exit_date': date,
                    'entry_price': entry_price,
                    'exit_price': close,
                    'pnl': pnl,
                    'hold_days': (date - entry_date).days,
                    'return_pct': (close / entry_price - 1) * 100
                })
                position = 0
        
        if position == 0 and i < len(signals) and bool(signals.iloc[i]):
            entry_price = close
            shares = int(capital * 0.95 / entry_price)
            cost_amt = shares * entry_price * COST_ETF
            if shares > 0 and capital >= shares * entry_price + cost_amt:
                capital -= (shares * entry_price + cost_amt)
                position = shares
                entry_date = date
    
    if position > 0:
        exit_price = float(df['Close'].iloc[-1])
        cost_amt = position * exit_price * COST_ETF
        capital += position * exit_price - cost_amt
        pnl = position * (exit_price - entry_price) - cost_amt
        trades.append({
            'entry_date': entry_date,
            'exit_date': df.index[-1],
            'entry_price': entry_price,
            'exit_price': exit_price,
            'pnl': pnl,
            'hold_days': (df.index[-1] - entry_date).days,
            'return_pct': (exit_price / entry_price - 1) * 100
        })
    
    return calc_metrics(trades, equity, "QQQ Dual MA Trend (50+200SMA, exit <50SMA)")


# ============================================================
# STRATEGY 10: VIX ETN Volatility (Concretum-style)
# ============================================================
def strat_vix_etn():
    """Short VXX when VRP positive + contango, long VXX when backwardation."""
    if 'VXX' not in data or 'SVXY' not in data or 'VIX' not in data:
        return {'name': 'VIX ETN Volatility', 'n_trades': 0, 'note': 'Missing VXX/SVXY data'}
    
    vxx = data['VXX'].copy()
    svxy = data['SVXY'].copy()
    vix = data['VIX'].copy()
    
    # Align dates
    common = vxx.index.intersection(vix.index).intersection(svxy.index)
    vxx = vxx.loc[common]
    svxy = svxy.loc[common]
    vix = vix.loc[common]
    
    # Calculate signals
    # eVRP: VIX > 10-day realized vol of SPY
    spy_aligned = spy.reindex(common)
    spy_ret = np.log(spy_aligned['Close'] / spy_aligned['Close'].shift(1))
    rv10 = spy_ret.rolling(10).std() * np.sqrt(252) * 100
    
    # Term structure: VIX vs VIX3M proxy (use 90-day simple avg of VIX as proxy)
    vix_sma90 = vix.rolling(90).mean()
    contango = vix < vix_sma90  # front < back = contango
    
    # Sizing: VIX/100
    size = vix / 100
    
    capital = INITIAL_CAPITAL
    position = 0  # +1 = long SVXY (short vol), -1 = long VXX (long vol)
    pos_size = 0
    entry_date = None
    trades = []
    equity = []
    
    for i in range(len(common)):
        date = common[i]
        svxy_close = float(svxy['Close'].iloc[i]) if pd.notna(svxy['Close'].iloc[i]) else 0
        vxx_close = float(vxx['Close'].iloc[i]) if pd.notna(vxx['Close'].iloc[i]) else 0
        vix_val = float(vix['Close'].iloc[i]) if pd.notna(vix['Close'].iloc[i]) else 20
        
        # Current equity
        if position == 1:
            eq = capital + pos_size * svxy_close
        elif position == -1:
            eq = capital + pos_size * vxx_close
        else:
            eq = capital
        equity.append(eq)
        
        # Exit if regime changes
        if position != 0:
            regime_change = False
            if position == 1 and not contango.iloc[i]:
                regime_change = True
            if position == -1 and contango.iloc[i]:
                regime_change = True
            
            if regime_change:
                if position == 1:
                    exit_price = svxy_close
                    cost_amt = pos_size * exit_price * COST_FUTURES / exit_price
                    capital += pos_size * exit_price - cost_amt
                    pnl = pos_size * (exit_price - entry_price) - cost_amt
                else:
                    exit_price = vxx_close
                    cost_amt = pos_size * exit_price * COST_FUTURES / exit_price
                    capital += pos_size * exit_price - cost_amt
                    pnl = pos_size * (exit_price - entry_price) - cost_amt
                
                trades.append({
                    'entry_date': entry_date,
                    'exit_date': date,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'pnl': pnl,
                    'hold_days': (date - entry_date).days,
                    'return_pct': (exit_price / entry_price - 1) * 100 * (1 if position == 1 else -1)
                })
                position = 0
        
        # Entry
        if position == 0:
            if contango.iloc[i] and rv10.iloc[i] < vix_val:
                # Short vol: buy SVXY
                entry_price = svxy_close
                alloc = capital * min(size.iloc[i], 0.3)  # cap at 30%
                pos_size = int(alloc / entry_price)
                if pos_size > 0:
                    capital -= pos_size * entry_price
                    position = 1
                    entry_date = date
            elif not contango.iloc[i]:
                # Long vol: buy VXX
                entry_price = vxx_close
                alloc = capital * min(size.iloc[i] * 0.5, 0.2)  # smaller size
                pos_size = int(alloc / entry_price)
                if pos_size > 0:
                    capital -= pos_size * entry_price
                    position = -1
                    entry_date = date
    
    # Close at end
    if position == 1:
        exit_price = float(svxy['Close'].iloc[-1])
        cost_amt = pos_size * exit_price * COST_FUTURES / exit_price
        capital += pos_size * exit_price - cost_amt
        pnl = pos_size * (exit_price - entry_price) - cost_amt
        trades.append({
            'entry_date': entry_date,
            'exit_date': common[-1],
            'entry_price': entry_price,
            'exit_price': exit_price,
            'pnl': pnl,
            'hold_days': (common[-1] - entry_date).days,
            'return_pct': (exit_price / entry_price - 1) * 100
        })
    elif position == -1:
        exit_price = float(vxx['Close'].iloc[-1])
        cost_amt = pos_size * exit_price * COST_FUTURES / exit_price
        capital += pos_size * exit_price - cost_amt
        pnl = pos_size * (exit_price - entry_price) - cost_amt
        trades.append({
            'entry_date': entry_date,
            'exit_date': common[-1],
            'entry_price': entry_price,
            'exit_price': exit_price,
            'pnl': pnl,
            'hold_days': (common[-1] - entry_date).days,
            'return_pct': (exit_price / entry_price - 1) * 100 * -1
        })
    
    return calc_metrics(trades, equity, "VIX ETN Volatility (eVRP + Term Structure)")


# ============================================================
# STRATEGY 11: IWM Small Cap Mean Reversion
# ============================================================
def strat_iwm_mr():
    """IBS on IWM — small cap mean reversion."""
    df = iwm.copy()
    df['ibs'] = calc_ibs(df)
    df['sma200'] = df['Close'].rolling(200).mean()
    
    signals = (df['ibs'] < 0.20) & (df['Close'] > df['sma200'])
    signals = signals.reindex(df.index, fill_value=False)
    
    trades, equity = backtest_long_only(df, signals, hold_period=5)
    return calc_metrics(trades, equity, "IWM Mean Reversion (IBS<0.2, 200SMA, 5d)")


# ============================================================
# STRATEGY 12: QQQ Mean Reversion
# ============================================================
def strat_qqq_mr():
    """IBS on QQQ."""
    df = qqq.copy()
    df['ibs'] = calc_ibs(df)
    df['sma200'] = df['Close'].rolling(200).mean()
    
    signals = (df['ibs'] < 0.20) & (df['Close'] > df['sma200'])
    signals = signals.reindex(df.index, fill_value=False)
    
    trades, equity = backtest_long_only(df, signals, hold_period=5)
    return calc_metrics(trades, equity, "QQQ Mean Reversion (IBS<0.2, 200SMA, 5d)")


# ============================================================
# STRATEGY 13: Turnaround Tuesday
# ============================================================
def strat_turnaround_tuesday():
    """Buy SPY on Monday close if down Friday+Monday, sell Wednesday close."""
    df = spy.copy()
    
    df['day_of_week'] = df.index.dayofweek  # 0=Mon, 4=Fri
    
    # Friday down
    df['fri_down'] = (df['day_of_week'] == 4) & (df['Close'] < df['Open'])
    # Monday down
    df['mon_down'] = (df['day_of_week'] == 0) & (df['Close'] < df['Open'])
    
    # Buy at Monday close if both Friday and Monday were down
    df['fri_was_down'] = df['fri_down'].rolling(3).max().fillna(0).astype(bool)
    
    signals = (df['day_of_week'] == 0) & (df['mon_down']) & (df['fri_was_down'])
    signals = signals.reindex(df.index, fill_value=False)
    
    trades, equity = backtest_long_only(df, signals, hold_period=3)  # holdTue-Thu
    return calc_metrics(trades, equity, "Turnaround Tuesday (buy Mon close, hold 3d)")


# ============================================================
# STRATEGY 14: Double 7s
# ============================================================
def strat_double_7s():
    """Buy SPY at 7-day low, sell at 7-day high."""
    df = spy.copy()
    
    df['low_7'] = df['Low'].rolling(7).min()
    df['high_7'] = df['High'].rolling(7).max()
    
    signals = df['Close'] <= df['low_7'].shift(1)
    signals = signals.reindex(df.index, fill_value=False)
    
    # Custom backtest: exit at 7-day high
    capital = INITIAL_CAPITAL
    position = 0
    entry_price = 0
    entry_date = None
    trades = []
    equity = []
    
    for i in range(len(df)):
        date = df.index[i]
        close = float(df['Close'].iloc[i])
        high_7 = float(df['high_7'].iloc[i]) if pd.notna(df['high_7'].iloc[i]) else close * 1.1
        
        eq = capital + (position * close if position > 0 else 0)
        equity.append(eq)
        
        if position > 0:
            if close >= high_7:
                cost_amt = position * close * COST_ETF
                capital += position * close - cost_amt
                pnl = position * (close - entry_price) - cost_amt
                trades.append({
                    'entry_date': entry_date,
                    'exit_date': date,
                    'entry_price': entry_price,
                    'exit_price': close,
                    'pnl': pnl,
                    'hold_days': (date - entry_date).days,
                    'return_pct': (close / entry_price - 1) * 100
                })
                position = 0
        
        if position == 0 and i < len(signals) and bool(signals.iloc[i]):
            entry_price = close
            shares = int(capital * 0.95 / entry_price)
            cost_amt = shares * entry_price * COST_ETF
            if shares > 0 and capital >= shares * entry_price + cost_amt:
                capital -= (shares * entry_price + cost_amt)
                position = shares
                entry_date = date
    
    if position > 0:
        exit_price = float(df['Close'].iloc[-1])
        cost_amt = position * exit_price * COST_ETF
        capital += position * exit_price - cost_amt
        pnl = position * (exit_price - entry_price) - cost_amt
        trades.append({
            'entry_date': entry_date,
            'exit_date': df.index[-1],
            'entry_price': entry_price,
            'exit_price': exit_price,
            'pnl': pnl,
            'hold_days': (df.index[-1] - entry_date).days,
            'return_pct': (exit_price / entry_price - 1) * 100
        })
    
    return calc_metrics(trades, equity, "Double 7s (buy 7d low, sell 7d high)")


# ============================================================
# STRATEGY 15: Mean Reversion Portfolio (4 strategies combined)
# ============================================================
def strat_mr_portfolio_combined():
    """Run RSI2, IBS, %B, TOM separately and combine equity curves."""
    rsi2_m = strat_rsi2()
    ibs_m = strat_ibs_simple()
    pctb_m = strat_pct_b()
    tom_m = strat_turn_of_month()
    
    # Combine equity curves (simple average)
    min_len = min(
        len(rsi2_m.get('trades_df', pd.DataFrame())) if 'trades_df' in rsi2_m else 0,
        len(ibs_m.get('trades_df', pd.DataFrame())) if 'trades_df' in ibs_m else 0
    )
    
    # Just report individual results
    return {
        'name': 'MR Portfolio (RSI2+IBS+%B+TOM combined)',
        'rsi2': rsi2_m,
        'ibs': ibs_m,
        'pctb': pctb_m,
        'tom': tom_m,
        'n_trades': rsi2_m['n_trades'] + ibs_m['n_trades'] + pctb_m['n_trades'] + tom_m['n_trades'],
        'note': 'Individual results shown — proper portfolio needs equal-weight allocation'
    }


# ============================================================
# RUN ALL
# ============================================================
print()
print("=" * 80)
print("BACKTESTING ALL STRATEGIES — 10 YEARS (2016-2025)")
print("=" * 80)
print()

results = []

strategies = [
    ("1. Multiple Days Down", strat_multiple_days_down),
    ("2. 5-Day Low of Range", strat_5day_low),
    ("3. Turn-of-Month", strat_turn_of_month),
    ("4. MR + Seasonal Filter", strat_mr_seasonal),
    ("5. IBS Simple", strat_ibs_simple),
    ("6. RSI(2) Mean Reversion", strat_rsi2),
    ("7. Connors %B", strat_pct_b),
    ("8. QQQ Dual MA Trend", strat_qqq_dual_ma),
    ("9. VIX ETN Volatility", strat_vix_etn),
    ("10. IWM Mean Reversion", strat_iwm_mr),
    ("11. QQQ Mean Reversion", strat_qqq_mr),
    ("12. Turnaround Tuesday", strat_turnaround_tuesday),
    ("13. Double 7s", strat_double_7s),
]

for name, func in strategies:
    print(f"  Running: {name}...")
    try:
        m = func()
        results.append(m)
    except Exception as e:
        print(f"    ERROR: {e}")
        results.append({'name': name, 'n_trades': 0, 'error': str(e)})

# MR Portfolio
print(f"  Running: MR Portfolio...")
try:
    mr_port = strat_mr_portfolio_combined()
    results.append(mr_port)
except Exception as e:
    print(f"    ERROR: {e}")

# ============================================================
# RESULTS
# ============================================================
print()
print("=" * 80)
print("RESULTS SUMMARY — 10 YEARS (2016-2025)")
print("=" * 80)
print()
print(f"  {'Strategy':<38} {'Trades':>7} {'WR%':>6} {'PF':>7} {'CAGR%':>8} {'MaxDD%':>8} {'Sharpe':>7} {'E[X]/trade':>12}")
print("  " + "-" * 100)

for m in results:
    if m['n_trades'] == 0:
        print(f"  {m['name']:<38} {'N/A':>7}")
    elif 'rsi2' in m:
        # Portfolio - print sub-results
        print(f"  {m['name']:<38} {m['n_trades']:>7} (combined)")
        for sub in ['rsi2', 'ibs', 'pctb', 'tom']:
            if sub in m and m[sub]['n_trades'] > 0:
                s = m[sub]
                print(f"    {sub.upper():<36} {s['n_trades']:>7} {s['win_rate']:>5.1f}% {s['profit_factor']:>6.2f} {s['cagr']:>7.1f}% {s['max_drawdown']:>7.1f}% {s['sharpe']:>6.2f} ${s['expectancy']:>10,.0f}")
    else:
        print(f"  {m['name']:<38} {m['n_trades']:>7} {m['win_rate']:>5.1f}% {m['profit_factor']:>6.2f} {m['cagr']:>7.1f}% {m['max_drawdown']:>7.1f}% {m['sharpe']:>6.2f} ${m['expectancy']:>10,.0f}")

# Not feasible
print()
print("=" * 80)
print("STRATEGIES NOT FEASIBLE WITH DAILY DATA (need intraday/options)")
print("=" * 80)
not_feasible = [
    "IBS Intraday (RTY 15-min) — needs intraday data",
    "FVG Confluence (NQ) — needs intraday data + order flow",
    "Improved ORB — needs intraday data",
    "Engulfing Candlestick — needs intraday data",
    "PTrans2PGEX — needs options market structure data",
    "Multi-Pattern Scoring — needs Nifty data",
    "Bayesian Signal Grading — needs options flow data",
    "VRP Short Put Spreads — needs options chain data",
    "VIX Term Structure Arbitrage — needs VIX futures data",
]
for nf in not_feasible:
    print(f"  - {nf}")

# ============================================================
# RANKING
# ============================================================
print()
print("=" * 80)
print("RANKING BY PROFIT FACTOR (feasible strategies only)")
print("=" * 80)
print()

feasible = [m for m in results if m['n_trades'] > 0 and 'rsi2' not in m]
feasible.sort(key=lambda x: x.get('profit_factor', 0) if x.get('profit_factor', 0) < 100 else 50, reverse=True)

for i, m in enumerate(feasible, 1):
    pf_str = f"{m['profit_factor']:.2f}" if m['profit_factor'] < 100 else "inf"
    print(f"  #{i}  {m['name']:<38} PF:{pf_str:>6}  WR:{m['win_rate']:>5.1f}%  Trades:{m['n_trades']:>5}  CAGR:{m['cagr']:>6.1f}%  DD:{m['max_drawdown']:>6.1f}%")

print()
print("=" * 80)
print("DISCLAIMER: Backtest != live. These are hypothetical results.")
print("Past performance does not guarantee future results.")
print("All strategies use 0.1% round-trip costs. No slippage modeled.")
print("=" * 80)
