"""
FUNDED ACCOUNT EDGE
====================
Prop firm rules:
- Target: 10% profit in 30 trading days
- Max drawdown: 10% (absolute)
- Daily loss limit: 5%
- Minimum trading days: 10
- Instruments: Forex, Indices, Crypto, Commodities

Strategy needs: positive expectancy, tight risk, many trades
"""

import yfinance as yf
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# DOWNLOAD FOREX + CRYPTO + COMMODITIES
# ============================================================
print("Downloading data...")
instruments = {
    'EURUSD=X': 'EURUSD',
    'GBPUSD=X': 'GBPUSD',
    'USDJPY=X': 'USDJPY',
    'AUDUSD=X': 'AUDUSD',
    'USDCAD=X': 'USDCAD',
    'USDCHF=X': 'USDCHF',
    'NZDUSD=X': 'NZDUSD',
    'GC=F': 'GOLD',
    'SI=F': 'SILVER',
    'CL=F': 'CRUDE',
    'BTC-USD': 'BTC',
    'ETH-USD': 'ETH',
    'QQQ': 'QQQ',
    'SPY': 'SPY',
    'IWM': 'IWM',
    'DIA': 'DIA',
    '^VIX': 'VIX',
    'EUR=X': 'DXY',
}

raw = {}
for ticker, name in instruments.items():
    try:
        d = yf.download(ticker, start='2010-01-01', end='2025-12-31', progress=False)
        if hasattr(d.columns, 'get_level_values'):
            d.columns = d.columns.get_level_values(0)
        if len(d) > 500:
            df = d[['Open', 'High', 'Low', 'Close']].copy()
            df['Ret'] = df['Close'].pct_change()
            df['Range'] = df['High'] - df['Low']
            df['IBS'] = np.where(df['Range'] > 0, (df['Close'] - df['Low']) / df['Range'], 0.5)
            df['Vol20'] = df['Ret'].rolling(20).std() * np.sqrt(252)
            df['SMA20'] = df['Close'].rolling(20).mean()
            df['SMA50'] = df['Close'].rolling(50).mean()
            df['SMA200'] = df['Close'].rolling(200).mean()
            df['Mom5'] = df['Close'] / df['Close'].shift(5) - 1
            df['Mom10'] = df['Close'] / df['Close'].shift(10) - 1
            df['Mom20'] = df['Close'] / df['Close'].shift(20) - 1
            df['Z20'] = (df['Close'] - df['SMA20']) / df['Close'].rolling(20).std()
            df['Ret1'] = df['Close'].pct_change(1)
            df['Ret2'] = df['Close'].pct_change(2)
            df['Ret3'] = df['Close'].pct_change(3)
            df['Ret5'] = df['Close'].pct_change(5)
            df['ConsecUp'] = (df['Ret'] > 0).astype(int).rolling(5).sum()
            df['ConsecDn'] = (df['Ret'] < 0).astype(int).rolling(5).sum()
            df['Gap'] = df['Open'] / df['Close'].shift(1) - 1
            raw[name] = df
            print(f"  {name}: {len(df)} bars")
    except:
        pass

print(f"Loaded {len(raw)} instruments")

INITIAL = 100000
# Prop firm risk: 10% DD max, 5% daily loss limit
MAX_RISK_PER_TRADE = 0.01  # 1% risk per trade (conservative)
MAX_DAILY_LOSS = 0.05  # 5% daily loss limit
MAX_DD = 0.10  # 10% max drawdown

# ============================================================
# PROP FIRM REALISTIC SIMULATION
# ============================================================
def run_prop(signals, closes, opens=None, risk_pct=0.01, stop_atr_mult=2.0):
    """
    Run with prop-firm-like risk management:
    - Fixed % risk per trade
    - ATR-based stop loss
    - Daily loss limit
    - Max drawdown circuit breaker
    """
    if opens is None: opens = closes
    cap = INITIAL; eq = []; daily_start = INITIAL
    pos = 0; entry = 0; stop = 0; direction = 0
    n_trades = 0; winning_trades = 0; total_pnl = 0
    current_day = None; max_cap = INITIAL; breaches = 0
    
    for i in range(1, len(signals)):
        o = float(opens.iloc[i]); c = float(closes.iloc[i])
        sig = int(signals.iloc[i]) if pd.notna(signals.iloc[i]) else 0
        
        # Track daily start
        try:
            day = closes.index[i].date()
        except:
            day = i // 20  # fallback
        if day != current_day:
            daily_start = cap
            current_day = day
        
        # Daily loss limit check
        if pos != 0:
            daily_pnl = (c - entry) * direction * pos if pos != 0 else 0
            if daily_start > 0 and (daily_start - cap) / daily_start >= MAX_DAILY_LOSS:
                # Force close
                pnl = (c - entry) * direction * pos
                cap += pnl - abs(pnl) * 0.001  # spread cost
                pos = 0; direction = 0
        
        # Max drawdown check
        max_cap = max(max_cap, cap)
        if (max_cap - cap) / max_cap >= MAX_DD:
            if pos != 0:
                pnl = (c - entry) * direction * pos
                cap += pnl - abs(pnl) * 0.001
                pos = 0; direction = 0
            breaches += 1
            if breaches > 3:
                eq.append(cap)
                continue
        
        # Exit on stop or signal reversal
        if pos > 0:
            if c <= stop or sig == 0:
                pnl = (c - entry) * pos
                cost = abs(pnl) * 0.001 + pos * 0.0001  # spread + commission
                cap += pnl - cost; pos = 0; direction = 0
                n_trades += 1
                if pnl > 0: winning_trades += 1
                total_pnl += pnl
        elif pos < 0:
            if c >= stop or sig == 0:
                pnl = (entry - c) * abs(pos)
                cost = abs(pnl) * 0.001 + abs(pos) * 0.0001
                cap += pnl - cost; pos = 0; direction = 0
                n_trades += 1
                if pnl > 0: winning_trades += 1
                total_pnl += pnl
        
        # Entry
        if pos == 0 and sig != 0:
            # Risk-based position sizing
            atr = abs(c - o) * 2  # rough ATR proxy
            if atr > 0:
                risk_amount = cap * risk_pct
                position_size = int(risk_amount / (atr * stop_atr_mult))
                position_size = max(1, min(position_size, int(cap * 0.1 / c)))  # max 10% per position
                
                if sig == 1:  # long
                    entry = o; stop = o - atr * stop_atr_mult
                    pos = position_size; direction = 1
                elif sig == -1:  # short
                    entry = o; stop = o + atr * stop_atr_mult
                    pos = -position_size; direction = -1
        
        # Mark to market
        if pos > 0:
            eq.append(cap + pos * (c - entry))
        elif pos < 0:
            eq.append(cap + abs(pos) * (entry - c))
        else:
            eq.append(cap)
    
    # Close remaining
    if pos != 0:
        c = float(closes.iloc[-1])
        pnl = (c - entry) * direction * pos
        cap += pnl - abs(pnl) * 0.001
    
    eq = np.array(eq)
    wr = winning_trades / n_trades * 100 if n_trades > 0 else 0
    return eq, n_trades, wr, total_pnl

def metrics(eq):
    dr = np.diff(eq) / eq[:-1]; dr = dr[np.isfinite(dr)]
    s = (np.mean(dr) / np.std(dr)) * np.sqrt(252) if np.std(dr) > 0 else 0
    pk = np.maximum.accumulate(eq)
    dd = -((pk - eq) / pk).max() * 100
    cagr = ((eq[-1] / eq[0]) ** (252 / max(len(eq), 1)) - 1) * 100
    return s, dd, cagr

# ============================================================
# TEST STRATEGIES
# ============================================================
print()
print("=" * 70)
print("STRATEGY TESTS (Prop Firm Focus)")
print("=" * 70)

results = []

for inst_name, df in raw.items():
    # Strategy 1: IBS Mean Reversion (long only)
    for ibs_thr in [0.15, 0.20, 0.25, 0.30]:
        sig = pd.Series(0, index=df.index)
        sig[df['IBS'].shift(1) < ibs_thr] = 1
        eq, nt, wr, tp = run_prop(sig, df['Close'], df['Open'])
        s, d, c = metrics(eq)
        if nt > 50:
            results.append((f'{inst_name}_IBS{ibs_thr}_L', s, d, c, nt, wr))
    
    # Strategy 2: IBS Mean Reversion (long/short)
    for ibs_thr in [0.20, 0.25, 0.30]:
        sig = pd.Series(0, index=df.index)
        sig[df['IBS'].shift(1) < ibs_thr] = 1
        sig[df['IBS'].shift(1) > (1 - ibs_thr)] = -1
        eq, nt, wr, tp = run_prop(sig, df['Close'], df['Open'])
        s, d, c = metrics(eq)
        if nt > 50:
            results.append((f'{inst_name}_IBS{ibs_thr}_LS', s, d, c, nt, wr))
    
    # Strategy 3: Trend + IBS
    sig = pd.Series(0, index=df.index)
    sig[(df['Close'].shift(1) > df['SMA50'].shift(1)) & (df['IBS'].shift(1) < 0.25)] = 1
    sig[(df['Close'].shift(1) < df['SMA50'].shift(1)) & (df['IBS'].shift(1) > 0.75)] = -1
    eq, nt, wr, tp = run_prop(sig, df['Close'], df['Open'])
    s, d, c = metrics(eq)
    if nt > 30:
        results.append((f'{inst_name}_TrendIBS', s, d, c, nt, wr))
    
    # Strategy 4: Z-score mean reversion
    for z_thr in [1.5, 2.0, 2.5]:
        sig = pd.Series(0, index=df.index)
        sig[df['Z20'].shift(1) < -z_thr] = 1
        sig[df['Z20'].shift(1) > z_thr] = -1
        eq, nt, wr, tp = run_prop(sig, df['Close'], df['Open'])
        s, d, c = metrics(eq)
        if nt > 30:
            results.append((f'{inst_name}_Z{z_thr}', s, d, c, nt, wr))
    
    # Strategy 5: Momentum + Reversal
    for lb in [5, 10, 20]:
        mom = df['Close'] / df['Close'].shift(lb) - 1
        sig = pd.Series(0, index=df.index)
        sig[mom.shift(1) > 0.02] = 1  # buy momentum
        sig[mom.shift(1) < -0.02] = -1  # short momentum
        eq, nt, wr, tp = run_prop(sig, df['Close'], df['Open'])
        s, d, c = metrics(eq)
        if nt > 30:
            results.append((f'{inst_name}_Mom{lb}', s, d, c, nt, wr))
    
    # Strategy 6: Consecutive + Reversal
    for n in [3, 4, 5]:
        sig = pd.Series(0, index=df.index)
        dn = (df['Ret'] < 0).astype(int).rolling(n).sum()
        up = (df['Ret'] > 0).astype(int).rolling(n).sum()
        sig[dn.shift(1) >= n] = 1   # buy after N down days
        sig[up.shift(1) >= n] = -1  # sell after N up days
        eq, nt, wr, tp = run_prop(sig, df['Close'], df['Open'])
        s, d, c = metrics(eq)
        if nt > 30:
            results.append((f'{inst_name}_Rev{n}', s, d, c, nt, wr))
    
    # Strategy 7: Gap + Mean Reversion
    sig = pd.Series(0, index=df.index)
    sig[df['Gap'].shift(1) < -0.005] = 1  # buy gap down
    sig[df['Gap'].shift(1) > 0.005] = -1  # sell gap up
    eq, nt, wr, tp = run_prop(sig, df['Close'], df['Open'])
    s, d, c = metrics(eq)
    if nt > 30:
        results.append((f'{inst_name}_Gap', s, d, c, nt, wr))

# Sort by Sharpe
results.sort(key=lambda x: x[1], reverse=True)

print(f"\n  {'#':>3} {'Strategy':<30} {'Sharpe':>7} {'DD%':>7} {'CAGR%':>7} {'Trades':>6} {'WR%':>6}")
print(f"  {'-'*73}")
for i, (name, s, d, c, nt, wr) in enumerate(results[:30]):
    marker = " ***" if s >= 1.0 else ""
    print(f"  {i+1:>3} {name:<30} {s:>7.2f} {d:>7.1f} {c:>7.1f} {nt:>6} {wr:>5.1f}%{marker}")

# ============================================================
# FUNDED ACCOUNT SIMULATION
# ============================================================
print()
print("=" * 70)
print("FUNDED ACCOUNT SIMULATION (30-day windows)")
print("=" * 70)

# For top strategies, simulate passing rate
top_strats = results[:10]

for name, s, d, c, nt, wr in top_strats:
    inst = name.split('_')[0]
    strat_type = '_'.join(name.split('_')[1:])
    
    # Get the equity curve and split into 30-day windows
    df = raw[inst]
    
    # Rebuild signals
    if 'IBS' in strat_type:
        ibs_thr = float(strat_type.split('_')[0][3:])
        if '_LS' in strat_type:
            sig = pd.Series(0, index=df.index)
            sig[df['IBS'].shift(1) < ibs_thr] = 1
            sig[df['IBS'].shift(1) > (1 - ibs_thr)] = -1
        else:
            sig = pd.Series(0, index=df.index)
            sig[df['IBS'].shift(1) < ibs_thr] = 1
    elif 'Trend' in strat_type:
        sig = pd.Series(0, index=df.index)
        sig[(df['Close'].shift(1) > df['SMA50'].shift(1)) & (df['IBS'].shift(1) < 0.25)] = 1
        sig[(df['Close'].shift(1) < df['SMA50'].shift(1)) & (df['IBS'].shift(1) > 0.75)] = -1
    elif 'Z' in strat_type:
        z_thr = float(strat_type[1:])
        sig = pd.Series(0, index=df.index)
        sig[df['Z20'].shift(1) < -z_thr] = 1
        sig[df['Z20'].shift(1) > z_thr] = -1
    else:
        continue
    
    eq, nt2, wr2, tp = run_prop(sig, df['Close'], df['Open'])
    
    # Split into 30-day windows
    window_size = 30
    n_windows = len(eq) // window_size
    passing = 0
    total_windows = 0
    avg_dd = []
    
    for w in range(n_windows):
        start = w * window_size
        end = min((w + 1) * window_size, len(eq))
        window_eq = eq[start:end]
        if len(window_eq) < 10: continue
        
        window_return = (window_eq[-1] / window_eq[0] - 1) * 100
        pk = np.maximum.accumulate(window_eq)
        window_dd = -((pk - window_eq) / pk).max() * 100
        
        total_windows += 1
        avg_dd.append(window_dd)
        
        if window_return >= 10 and window_dd > -10:
            passing += 1
    
    if total_windows > 0:
        print(f"  {name:<30} Pass: {passing}/{total_windows} ({passing/total_windows*100:.0f}%)  Avg DD: {np.mean(avg_dd):.1f}%")

# ============================================================
# BASKET STRATEGY (trade multiple instruments)
# ============================================================
print()
print("=" * 70)
print("BASKET STRATEGY (portfolio approach)")
print("=" * 70)

# Use IBS MR on top 6 instruments
basket_insts = ['EURUSD', 'GBPUSD', 'GOLD', 'QQQ', 'BTC', 'SPY']
basket_insts = [i for i in basket_insts if i in raw]

for ibs_thr in [0.20, 0.25, 0.30]:
    total_eq = np.ones(len(list(raw.values())[0])) * INITIAL
    n_active = 0
    
    for inst in basket_insts:
        df = raw[inst]
        sig = pd.Series(0, index=df.index)
        sig[df['IBS'].shift(1) < ibs_thr] = 1
        
        eq, nt, wr, tp = run_prop(sig, df['Close'], df['Open'])
        
        # Align lengths
        ml = min(len(total_eq), len(eq))
        total_eq[:ml] += eq[:ml] - INITIAL
        n_active += 1
    
    total_eq /= n_active
    total_eq += INITIAL * (n_active - 1)
    
    s, d, c = metrics(total_eq)
    print(f"  Basket IBS<{ibs_thr} ({n_active} insts) Sharpe {s:.2f}  DD {d:.1f}%  CAGR {c:.1f}%")
    
    # Simulate funded account
    window_size = 30
    n_windows = len(total_eq) // window_size
    passing = 0
    total_windows = 0
    for w in range(n_windows):
        start = w * window_size
        end = min((w + 1) * window_size, len(total_eq))
        weq = total_eq[start:end]
        if len(weq) < 10: continue
        ret = (weq[-1] / weq[0] - 1) * 100
        pk = np.maximum.accumulate(weq)
        dd = -((pk - weq) / pk).max() * 100
        total_windows += 1
        if ret >= 10 and dd > -10:
            passing += 1
    
    if total_windows > 0:
        print(f"    Pass rate: {passing}/{total_windows} ({passing/total_windows*100:.0f}%)")
