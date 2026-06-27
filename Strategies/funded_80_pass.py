"""
FUNDED ACCOUNT — AGGRESSIVE PASS RATE SEARCH
=============================================
Key insight: To pass, you need FREQUENT trades + BIG winners.
Conservative MR strategies don't generate enough return in 30 days.
"""
import yfinance as yf
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

print("Downloading data...")
raw = {}
for t, n in [('QQQ','QQQ'),('SPY','SPY'),('IWM','IWM'),('DIA','DIA'),
             ('GC=F','GLD'),('BTC-USD','BTC'),('ETH-USD','ETH'),
             ('EURUSD=X','EURUSD'),('GBPUSD=X','GBPUSD')]:
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
            df['Z20'] = (df['Close']-df['Close'].rolling(20).mean())/df['Close'].rolling(20).std()
            df['Ret20'] = df['Close']/df['Close'].shift(20)-1
            df['Ret5'] = df['Close']/df['Close'].shift(5)-1
            df['Vol20'] = df['Ret'].rolling(20).std()
            df['ATR'] = (df['High']-df['Low']).rolling(14).mean()
            raw[n] = df
            print(f"  {n}: {len(df)} bars")
    except: pass
print(f"Loaded {len(raw)} instruments\n")

INITIAL = 100000

# ============================================================
# AGGRESSIVE PROP FIRM SIM
# ============================================================
def run_agg(sig, close, opn, hold, risk, sizing, sl_mult, tp_mult, max_pos_pct):
    cap=INITIAL; max_cap=INITIAL; pos=0; entry=0; dh=0; dc=0; cd=None; ds=INITIAL; nt=0; nw=0
    c=close.values; o=opn.values; s=sig.values
    for i in range(1,len(c)):
        if np.isnan(s[i]): s[i]=0
        try: day=close.index[i].date()
        except: day=i
        if day!=cd: ds=cap; cd=day; dc+=1
        # Daily loss limit 5%
        if pos!=0 and (ds-cap)/ds>=0.05:
            pnl=(c[i]-entry)*pos; cap+=pnl-abs(pnl)*0.0002; pos=0; nt+=1
        # Max DD 10%
        max_cap=max(max_cap,cap); dd=(max_cap-cap)/max_cap if max_cap>0 else 0
        if dd>=0.10:
            if pos!=0: pnl=(c[i]-entry)*pos; cap+=pnl-abs(pnl)*0.0002; pos=0
            return False,dd,(cap-INITIAL)/INITIAL,nt,nw
        # Target 10%
        if (cap-INITIAL)/INITIAL>=0.10:
            return True,dd,(cap-INITIAL)/INITIAL,nt,nw
        # Time limit
        if dc>=30:
            return False,dd,(cap-INITIAL)/INITIAL,nt,nw
        # Exit existing
        if pos>0:
            dh+=1; pnl_pct=(c[i]-entry)/entry
            # Take profit / stop loss / time exit
            if pnl_pct>=tp_mult*0.01 or pnl_pct<=-sl_mult*0.01 or dh>=hold or s[i]==0:
                pnl=(c[i]-entry)*pos; cap+=pnl-abs(pnl)*0.0002
                if pnl>0: nw+=1
                pos=0; nt+=1; dh=0
        # Entry
        if pos==0 and s[i]>0 and dc<28:
            ar=risk
            if sizing=='dynamic':
                if dd>0.06: ar=risk*0.5
                elif dd>0.03: ar=risk*0.75
            elif sizing=='aggressive':
                if dc<=10: ar=risk*2.0
                elif dc<=20: ar=risk*1.5
                else: ar=risk*1.0
            sh=int(cap*ar/(o[i]*sl_mult*0.01)) if o[i]>0 else 0
            sh=min(sh,int(cap*max_pos_pct/o[i]))
            if sh>0: entry=o[i]; pos=sh; dh=0
    if pos>0: pnl=(c[-1]-entry)*pos; cap+=pnl-abs(pnl)*0.0002; nt+=1
    return False,(max_cap-cap)/max_cap if max_cap>0 else 0,(cap-INITIAL)/INITIAL,nt,nw

# ============================================================
# STRATEGIES (AGGRESSIVE VERSIONS)
# ============================================================
def sig_ibs_any(df): return (df['IBS'].shift(1)<0.30).astype(int)  # Very active
def sig_ibs_mr(df): return (df['IBS'].shift(1)<0.20).astype(int)
def sig_ibs_deep(df): return (df['IBS'].shift(1)<0.15).astype(int)
def sig_z_any(df): return (df['Z20'].shift(1)<-1.5).astype(int)
def sig_z_deep(df): return (df['Z20'].shift(1)<-2.0).astype(int)
def sig_trend(df): return (df['Close'].shift(1)>df['SMA50'].shift(1)).astype(int)  # Always long uptrend
def sig_trend_pull(df): return ((df['Close'].shift(1)>df['SMA200'].shift(1))&(df['Ret5'].shift(1)<-0.02)).astype(int)
def sig_combo(df): return ((df['IBS'].shift(1)<0.30)|(df['Z20'].shift(1)<-1.5)).astype(int)
def sig_momentum(df): return (df['Ret5'].shift(1)>0.03).astype(int)  # Buy momentum
def sig_reversal(df): return (df['Ret5'].shift(1)<-0.03).astype(int)  # Buy reversal

# ============================================================
# BRUTE FORCE
# ============================================================
print("=" * 90)
print("AGGRESSIVE SEARCH — targeting 10% return in 30 days")
print("=" * 90)

results = []
inst_list = list(raw.keys())

for inst in inst_list:
    df = raw[inst]
    for sig_name, sig_fn in [
        ('IBS_Any', sig_ibs_any), ('IBS_MR', sig_ibs_mr), ('IBS_Deep', sig_ibs_deep),
        ('Z_Any', sig_z_any), ('Z_Deep', sig_z_deep),
        ('Trend', sig_trend), ('TrendPull', sig_trend_pull),
        ('Combo', sig_combo), ('Momentum', sig_momentum), ('Reversal', sig_reversal),
    ]:
        sig = sig_fn(df)
        for risk in [0.03, 0.05, 0.08, 0.10, 0.15, 0.20]:
            for sizing in ['fixed', 'dynamic', 'aggressive']:
                for hold in [2, 3, 5, 7]:
                    for sl in [1.5, 2.0, 3.0]:
                        for tp in [1.0, 1.5, 2.0, 3.0]:
                            for mp in [0.20, 0.30, 0.50]:
                                pass_ct=0; total=0; rets=[]; dds=[]
                                for w in range(0, min(2000, len(df))-30, 30):
                                    ws=sig.iloc[w:w+30]; wc=df['Close'].iloc[w:w+30]
                                    wo=df['Open'].iloc[w:w+30]
                                    passed,dd,ret,nt,nw=run_agg(ws,wc,wo,hold,risk,sizing,sl,tp,mp)
                                    total+=1
                                    if passed: pass_ct+=1
                                    rets.append(ret); dds.append(dd)
                                if total>=20:
                                    pr=pass_ct/total*100
                                    results.append((pr, inst, sig_name, risk, sizing, hold, sl, tp, mp,
                                                  np.mean(rets)*100, np.mean(dds)*100, total, pass_ct))

results.sort(key=lambda x: x[0], reverse=True)

print(f"\nCompleted {len(results)} tests\n")
print(f"{'#':>3} {'Inst':<6} {'Strat':<10} {'Risk':>5} {'Size':<10} {'Hold':>4} {'SL':>4} {'TP':>4} {'MaxP':>5} {'Pass%':>6} {'Ret%':>6} {'DD%':>6}")
print("-" * 95)
for i, r in enumerate(results[:50]):
    pr,inst,st,rs,sz,hd,sl,tp,mp,ar,ad,tot,pas = r
    m=" ***" if pr>=80 else (" **" if pr>=70 else "")
    print(f"{i+1:>3} {inst:<6} {st:<10} {rs:>5.0%} {sz:<10} {hd:>4} {sl:>4.1f} {tp:>4.1f} {mp:>5.0%} {pr:>5.0f}% {ar:>5.1f}% {ad:>5.1f}%{m}")

# ============================================================
# FINDINGS
# ============================================================
eighty = [r for r in results if r[0] >= 80]
seventy = [r for r in results if r[0] >= 70]
sixty = [r for r in results if r[0] >= 60]

print(f"\n{'='*90}")
print(f"RESULTS: {len(eighty)} at 80%+ | {len(seventy)} at 70%+ | {len(sixty)} at 60%+")
print(f"{'='*90}")

if eighty:
    print("\n80%+ PASS RATE STRATEGIES:")
    for r in eighty[:20]:
        pr,inst,st,rs,sz,hd,sl,tp,mp,ar,ad,tot,pas = r
        print(f"  {pr:.0f}% — {st} on {inst} risk={rs:.0%} {sz} hold={hd} SL={sl} TP={tp} MaxPos={mp:.0%}")
elif seventy:
    print("\n70%+ PASS RATE:")
    for r in seventy[:20]:
        pr,inst,st,rs,sz,hd,sl,tp,mp,ar,ad,tot,pas = r
        print(f"  {pr:.0f}% — {st} on {inst} risk={rs:.0%} {sz} hold={hd} SL={sl} TP={tp} MaxPos={mp:.0%}")
else:
    print("\nTop 15 by pass rate:")
    for r in results[:15]:
        pr,inst,st,rs,sz,hd,sl,tp,mp,ar,ad,tot,pas = r
        print(f"  {pr:.0f}% — {st} on {inst} risk={rs:.0%} {sz} hold={hd} SL={sl} TP={tp} MaxPos={mp:.0%}")
