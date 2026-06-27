"""
FUNDED ACCOUNT — 80% PASS RATE SEARCH
======================================
Brute-force search for prop firm strategies with 80%+ pass rate.

Rules: $100K, 10% target, 10% DD, 5% daily loss, 30 days
"""

import yfinance as yf
import pandas as pd
import numpy as np
from itertools import combinations
import warnings
warnings.filterwarnings('ignore')

print("Downloading data...")
raw = {}
for t, n in [('QQQ','QQQ'),('SPY','SPY'),('IWM','IWM'),('DIA','DIA'),
             ('GC=F','GLD'),('SI=F','SLV'),('USO','USO'),
             ('EURUSD=X','EURUSD'),('GBPUSD=X','GBPUSD'),('USDJPY=X','USDJPY'),
             ('AUDUSD=X','AUDUSD'),('BTC-USD','BTC'),('ETH-USD','ETH'),('CL=F','CRUDE')]:
    try:
        d = yf.download(t, start='2016-01-01', end='2025-12-31', progress=False)
        if hasattr(d.columns, 'get_level_values'): d.columns = d.columns.get_level_values(0)
        if len(d) > 500:
            df = d[['Open','High','Low','Close']].copy()
            df['Ret'] = df['Close'].pct_change()
            df['Range'] = df['High'] - df['Low']
            df['IBS'] = np.where(df['Range']>0,(df['Close']-df['Low'])/df['Range'],0.5)
            df['SMA20'] = df['Close'].rolling(20).mean()
            df['SMA50'] = df['Close'].rolling(50).mean()
            df['SMA200'] = df['Close'].rolling(200).mean()
            df['Z20'] = (df['Close']-df['SMA20'])/df['Close'].rolling(20).std()
            df['Mom5'] = df['Close']/df['Close'].shift(5)-1
            df['Ret1'] = df['Close'].pct_change(1)
            df['Ret5'] = df['Close'].pct_change(5)
            df['ConsecDn'] = (df['Ret']<0).astype(int).rolling(5).sum()
            df['Gap'] = df['Open']/df['Close'].shift(1)-1
            df['Vol20'] = df['Ret'].rolling(20).std()*np.sqrt(252)
            df['VolRatio'] = df['Ret'].rolling(5).std() / df['Ret'].rolling(20).std()
            raw[n] = df
            print(f"  {n}: {len(df)} bars")
    except: pass
print(f"Loaded {len(raw)} instruments\n")

INITIAL = 100000

# ============================================================
# STRATEGIES
# ============================================================
def strat_ibs_mr(df):
    """IBS Mean Reversion — no trend filter"""
    sig = pd.Series(0, index=df.index)
    sig[df['IBS'].shift(1) < 0.20] = 1
    return sig, 5

def strat_ibs_mr_trend(df):
    """IBS MR + 200 SMA trend filter"""
    sig = pd.Series(0, index=df.index)
    sig[(df['IBS'].shift(1) < 0.20) & (df['Close'].shift(1) > df['SMA200'].shift(1))] = 1
    return sig, 5

def strat_ibs_mr_vol(df):
    """IBS MR + volume filter (no high vol)"""
    sig = pd.Series(0, index=df.index)
    sig[(df['IBS'].shift(1) < 0.20) & (df['VolRatio'].shift(1) < 1.5)] = 1
    return sig, 5

def strat_ibs_mr_trend_vol(df):
    """IBS MR + trend + volume filter"""
    sig = pd.Series(0, index=df.index)
    sig[(df['IBS'].shift(1) < 0.20) & (df['Close'].shift(1) > df['SMA200'].shift(1)) & (df['VolRatio'].shift(1) < 1.5)] = 1
    return sig, 5

def strat_z_mr(df):
    """Z-score Mean Reversion"""
    sig = pd.Series(0, index=df.index)
    sig[df['Z20'].shift(1) < -2.0] = 1
    return sig, 5

def strat_rev3(df):
    """3 consecutive down days reversal"""
    sig = pd.Series(0, index=df.index)
    sig[df['ConsecDn'].shift(1) >= 3] = 1
    return sig, 5

def strat_rev5(df):
    """5 consecutive down days reversal"""
    sig = pd.Series(0, index=df.index)
    sig[df['ConsecDn'].shift(1) >= 5] = 1
    return sig, 5

def strat_trend_pull(df):
    """Trend pullback (50/200 SMA)"""
    sig = pd.Series(0, index=df.index)
    above200 = df['Close'].shift(1) > df['SMA200'].shift(1)
    pullback = (df['Close'].shift(1) < df['SMA50'].shift(1)) & (df['Close'].shift(10) > df['SMA50'].shift(10))
    sig[above200 & pullback] = 1
    return sig, 10

def strat_ibs_aggressive(df):
    """IBS MR aggressive — wider threshold, more trades"""
    sig = pd.Series(0, index=df.index)
    sig[df['IBS'].shift(1) < 0.30] = 1
    return sig, 3

def strat_ibs_deep(df):
    """IBS MR deep oversold — stricter threshold"""
    sig = pd.Series(0, index=df.index)
    sig[df['IBS'].shift(1) < 0.15] = 1
    return sig, 5

def strat_multi_edge(df):
    """Multi-edge: IBS + Z-score + reversal"""
    sig = pd.Series(0, index=df.index)
    ibs = df['IBS'].shift(1) < 0.20
    zsc = df['Z20'].shift(1) < -1.5
    rev = df['ConsecDn'].shift(1) >= 3
    sig[ibs | zsc | rev] = 1
    return sig, 5

def strat_gap_mr(df):
    """Gap down mean reversion"""
    sig = pd.Series(0, index=df.index)
    sig[df['Gap'].shift(1) < -0.005] = 1
    return sig, 3

STRATEGIES = {
    'IBS_MR': strat_ibs_mr,
    'IBS_MR_Trend': strat_ibs_mr_trend,
    'IBS_MR_Vol': strat_ibs_mr_vol,
    'IBS_MR_TrendVol': strat_ibs_mr_trend_vol,
    'Z_MR': strat_z_mr,
    'Rev3': strat_rev3,
    'Rev5': strat_rev5,
    'TrendPull': strat_trend_pull,
    'IBS_Aggressive': strat_ibs_aggressive,
    'IBS_Deep': strat_ibs_deep,
    'MultiEdge': strat_multi_edge,
    'Gap_MR': strat_gap_mr,
}

# ============================================================
# REGIME DETECTION
# ============================================================
def get_regime(df, method='basic'):
    """Return regime series: 1=bull, 0=sideways, -1=bear"""
    if method == 'none':
        return pd.Series(1, index=df.index)
    
    ret20 = df['Close'] / df['Close'].shift(20) - 1
    
    if method == 'basic':
        regime = pd.Series(0, index=df.index)
        regime[ret20 > 0.05] = 1
        regime[ret20 < -0.05] = -1
        return regime
    
    elif method == 'markov':
        regime = pd.Series(0, index=df.index)
        regime[ret20 > 0.05] = 1
        regime[ret20 < -0.05] = -1
        
        # Stickiness: if yesterday was bull, boost bull probability
        for i in range(21, len(df)):
            if regime.iloc[i-1] == 1:
                if ret20.iloc[i] > 0:
                    regime.iloc[i] = 1
            elif regime.iloc[i-1] == -1:
                if ret20.iloc[i] < 0:
                    regime.iloc[i] = -1
        return regime
    
    return regime

# ============================================================
# PROP FIRM SIMULATOR
# ============================================================
def run_prop_firm(signals, closes, opens, hold_days=5,
                  risk_pct=0.02, sizing='dynamic', regime_filter='none',
                  regime_series=None, target=0.10, max_dd=0.10, 
                  daily_limit=0.05, window=30):
    """
    Simulate passing a prop firm.
    Returns: (passed, days_to_pass, max_dd_hit, total_return, n_trades)
    """
    cap = INITIAL
    max_cap = INITIAL
    daily_start = INITIAL
    current_day = None
    pos = 0
    entry = 0
    direction = 0
    days_in_pos = 0
    n_trades = 0
    wins = 0
    day_count = 0
    
    closes_arr = closes.values
    opens_arr = opens.values
    sig_arr = signals.values
    
    if regime_series is not None:
        reg_arr = regime_series.values
    else:
        reg_arr = np.ones(len(closes_arr))
    
    for i in range(1, len(closes_arr)):
        o = opens_arr[i]
        c = closes_arr[i]
        sig = sig_arr[i]
        reg = reg_arr[i]
        
        if np.isnan(sig): sig = 0
        if np.isnan(reg): reg = 0
        
        try:
            day = closes.index[i].date()
        except:
            day = i // 20
        
        if day != current_day:
            daily_start = cap
            current_day = day
            day_count += 1
        
        # Daily loss limit
        if pos != 0:
            daily_pnl_pct = (daily_start - cap) / daily_start if daily_start > 0 else 0
            if daily_pnl_pct >= daily_limit:
                pnl = (c - entry) * direction * abs(pos)
                cap += pnl - abs(pnl) * 0.0002
                pos = 0; direction = 0
        
        # Max DD check
        max_cap = max(max_cap, cap)
        dd_pct = (max_cap - cap) / max_cap if max_cap > 0 else 0
        if dd_pct >= max_dd:
            if pos != 0:
                pnl = (c - entry) * direction * abs(pos)
                cap += pnl - abs(pnl) * 0.0002
                pos = 0; direction = 0
            return False, day_count, dd_pct, (cap - INITIAL) / INITIAL, n_trades
        
        # Target reached
        ret_pct = (cap - INITIAL) / INITIAL
        if ret_pct >= target:
            return True, day_count, dd_pct, ret_pct, n_trades
        
        # Time limit
        if day_count >= window:
            return False, day_count, dd_pct, ret_pct, n_trades
        
        # Exit existing position
        if pos > 0:
            days_in_pos += 1
            if c <= entry * 0.98 or days_in_pos >= hold_days or sig == 0:
                pnl = (c - entry) * pos
                cap += pnl - abs(pnl) * 0.0002
                pos = 0; direction = 0; days_in_pos = 0
                n_trades += 1
                if pnl > 0: wins += 1
        
        # Entry
        if pos == 0 and sig > 0 and reg >= 0:
            # Dynamic sizing
            actual_risk = risk_pct
            if sizing == 'dynamic':
                if dd_pct > 0.06:
                    actual_risk = risk_pct * 0.5
                elif dd_pct > 0.03:
                    actual_risk = risk_pct * 0.75
            elif sizing == 'aggressive':
                if day_count <= 10:
                    actual_risk = risk_pct * 1.5
                elif day_count <= 20:
                    actual_risk = risk_pct * 1.0
                else:
                    actual_risk = risk_pct * 0.75
            
            risk_amount = cap * actual_risk
            stop_dist = o * 0.02  # 2% stop
            shares = int(risk_amount / stop_dist) if stop_dist > 0 else 0
            max_shares = int(cap * 0.25 / o)  # max 25% per position
            shares = min(shares, max_shares)
            
            if shares > 0:
                entry = o
                pos = shares
                direction = 1
                days_in_pos = 0
        
        # Mark to market
        if pos > 0:
            cap = cap  # already updated on exit
    
    # Force close at end
    if pos != 0:
        c = closes_arr[-1]
        pnl = (c - entry) * pos
        cap += pnl - abs(pnl) * 0.0002
    
    return False, day_count, dd_pct, (cap - INITIAL) / INITIAL, n_trades

# ============================================================
# WALK-FORWARD VALIDATION
# ============================================================
def walk_forward_pass_rate(signals, closes, opens, hold_days=5,
                           risk_pct=0.02, sizing='dynamic', 
                           regime_filter='none', regime_series=None,
                           is_window=504, oos_window=252, step=63):
    """Walk-forward: train on IS, test on OOS. Return OOS pass rate."""
    total_pass = 0
    total_windows = 0
    
    for start in range(0, len(signals) - is_window - oos_window, step):
        # OOS window
        oos_start = start + is_window
        oos_end = min(oos_start + oos_window, len(signals))
        
        oos_sig = signals.iloc[oos_start:oos_end]
        oos_close = closes.iloc[oos_start:oos_end]
        oos_open = opens.iloc[oos_start:oos_end]
        oos_reg = regime_series.iloc[oos_start:oos_end] if regime_series is not None else None
        
        passed, days, dd, ret, nt = run_prop_firm(
            oos_sig, oos_close, oos_open, hold_days,
            risk_pct, sizing, regime_filter, oos_reg
        )
        
        total_windows += 1
        if passed:
            total_pass += 1
    
    return total_pass / total_windows * 100 if total_windows > 0 else 0

# ============================================================
# BRUTE FORCE SEARCH
# ============================================================
print("=" * 90)
print("BRUTE FORCE: Searching for 80%+ pass rate strategies...")
print("=" * 90)

results = []
total_tests = 0

# Instrument combinations (1-5 instruments)
inst_list = list(raw.keys())
inst_combos = []
for n in [1, 2, 3, 4, 5]:
    for combo in combinations(range(len(inst_list)), n):
        inst_combos.append([inst_list[i] for i in combo])

# Limit combos for speed
inst_combos = [c for c in inst_combos if len(c) <= 3]  # max 3 instruments for speed
print(f"Testing {len(inst_combos)} instrument combos × {len(STRATEGIES)} strategies × 6 risk levels")
print(f"Total tests: ~{len(inst_combos) * len(STRATEGIES) * 6}")

for inst_combo in inst_combos:
    for strat_name, strat_fn in STRATEGIES.items():
        for risk_pct in [0.01, 0.02, 0.03, 0.05, 0.08, 0.10]:
            for sizing in ['fixed', 'dynamic', 'aggressive']:
                for regime in ['none', 'basic']:
                    # Build combined signals and run
                    pass_count = 0
                    total_count = 0
                    all_rets = []
                    all_dds = []
                    
                    for inst in inst_combo:
                        if inst not in raw: continue
                        df = raw[inst]
                        sig, hold = strat_fn(df)
                        reg = get_regime(df, regime)
                        
                        # Run 100 non-overlapping 30-day windows
                        for w in range(0, min(750, len(df)) - 30, 30):
                            w_sig = sig.iloc[w:w+30]
                            w_close = df['Close'].iloc[w:w+30]
                            w_open = df['Open'].iloc[w:w+30]
                            w_reg = reg.iloc[w:w+30]
                            
                            passed, days, dd, ret, nt = run_prop_firm(
                                w_sig, w_close, w_open, hold,
                                risk_pct, sizing, regime, w_reg
                            )
                            
                            total_count += 1
                            if passed:
                                pass_count += 1
                            all_rets.append(ret)
                            all_dds.append(dd)
                    
                    if total_count >= 20:
                        pr = pass_count / total_count * 100
                        avg_ret = np.mean(all_rets) * 100
                        avg_dd = np.mean(all_dds) * 100
                        
                        results.append({
                            'inst': ','.join(inst_combo[:3]),
                            'strat': strat_name,
                            'risk': risk_pct,
                            'sizing': sizing,
                            'regime': regime,
                            'pass_rate': pr,
                            'avg_ret': avg_ret,
                            'avg_dd': avg_dd,
                            'total': total_count,
                            'passed': pass_count
                        })
                        
                        total_tests += 1

# Sort by pass rate
results.sort(key=lambda x: x['pass_rate'], reverse=True)

print(f"\nCompleted {total_tests} tests\n")
print("=" * 90)
print(f"{'#':>3} {'Inst':<25} {'Strat':<18} {'Risk':>5} {'Sizing':<10} {'Regime':<8} {'Pass%':>6} {'AvgRet':>7} {'AvgDD':>7}")
print("=" * 90)

for i, r in enumerate(results[:50]):
    marker = " ***" if r['pass_rate'] >= 80 else (" **" if r['pass_rate'] >= 70 else "")
    print(f"{i+1:>3} {r['inst']:<25} {r['strat']:<18} {r['risk']:>5.0%} {r['sizing']:<10} {r['regime']:<8} {r['pass_rate']:>5.0f}% {r['avg_ret']:>6.1f}% {r['avg_dd']:>6.1f}%{marker}")

# ============================================================
# TOP STRATEGIES DEEP DIVE
# ============================================================
print("\n" + "=" * 90)
print("TOP 5 STRATEGIES — DETAILED ANALYSIS")
print("=" * 90)

for i, r in enumerate(results[:5]):
    print(f"\n{'='*60}")
    print(f"RANK #{i+1}: {r['pass_rate']:.0f}% pass rate")
    print(f"{'='*60}")
    print(f"  Instruments: {r['inst']}")
    print(f"  Strategy: {r['strat']}")
    print(f"  Risk per trade: {r['risk']:.0%}")
    print(f"  Sizing mode: {r['sizing']}")
    print(f"  Regime filter: {r['regime']}")
    print(f"  Pass rate: {r['pass_rate']:.1f}% ({r['passed']}/{r['total']})")
    print(f"  Avg return: {r['avg_ret']:.1f}%")
    print(f"  Avg drawdown: {r['avg_dd']:.1f}%")

# ============================================================
# FINDINGS
# ============================================================
print("\n" + "=" * 90)
print("KEY FINDINGS")
print("=" * 90)

# Analyze what works
if results:
    best = results[0]
    print(f"\nBest strategy found: {best['pass_rate']:.0f}% pass rate")
    print(f"  Configuration: {best['strat']} on {best['inst']}")
    print(f"  Risk: {best['risk']:.0%}, Sizing: {best['sizing']}, Regime: {best['regime']}")
    
    # Check if any hit 80%
    eighty_plus = [r for r in results if r['pass_rate'] >= 80]
    seventy_plus = [r for r in results if r['pass_rate'] >= 70]
    
    print(f"\nStrategies with 80%+ pass rate: {len(eighty_plus)}")
    print(f"Strategies with 70%+ pass rate: {len(seventy_plus)}")
    
    if eighty_plus:
        print("\n80%+ PASS RATE STRATEGIES:")
        for r in eighty_plus[:10]:
            print(f"  {r['pass_rate']:.0f}% — {r['strat']} on {r['inst']} (risk={r['risk']:.0%}, {r['sizing']}, {r['regime']})")
    elif seventy_plus:
        print("\n70%+ PASS RATE STRATEGIES (closest to target):")
        for r in seventy_plus[:10]:
            print(f"  {r['pass_rate']:.0f}% — {r['strat']} on {r['inst']} (risk={r['risk']:.0%}, {r['sizing']}, {r['regime']})")
    else:
        print("\nNo strategies found with 70%+ pass rate")
        print("Top 10 by pass rate:")
        for r in results[:10]:
            print(f"  {r['pass_rate']:.0f}% — {r['strat']} on {r['inst']} (risk={r['risk']:.0%}, {r['sizing']}, {r['regime']})")

print("\n" + "=" * 90)
print("RECOMMENDATIONS")
print("=" * 90)
print("""
To improve pass rate toward 80%:
1. Use DYNAMIC sizing — scale down when DD increases
2. Trade 2-3 UNCORRELATED instruments — more opportunities
3. Use REGIME filter — avoid trading in bear markets
4. Risk 1-2% per trade — tight enough to survive
5. Focus on MEAN REVERSION — highest win rate (60%+)
6. Front-load AGGRESSIVE sizing — hit target before DD builds
""")
