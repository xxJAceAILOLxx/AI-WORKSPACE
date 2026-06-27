"""
FUNDED PASS — MINIMAL BRUTE FORCE
"""
import yfinance as yf
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

print("Downloading...")
raw = {}
for t, n in [('QQQ','QQQ'),('SPY','SPY'),('BTC-USD','BTC'),('GC=F','GLD')]:
    try:
        d = yf.download(t, start='2016-01-01', end='2025-12-31', progress=False)
        if hasattr(d.columns, 'get_level_values'): d.columns = d.columns.get_level_values(0)
        if len(d) > 500:
            df = d[['Open','High','Low','Close']].copy()
            df['Ret'] = df['Close'].pct_change()
            df['Range'] = df['High'] - df['Low']
            df['IBS'] = np.where(df['Range']>0,(df['Close']-df['Low'])/df['Range'],0.5)
            df['SMA50'] = df['Close'].rolling(50).mean()
            df['SMA200'] = df['Close'].rolling(200).mean()
            df['Z20'] = (df['Close']-df['Close'].rolling(20).mean())/df['Close'].rolling(20).std()
            df['Ret5'] = df['Close']/df['Close'].shift(5)-1
            raw[n] = df
            print(f"  {n}: {len(df)} bars")
    except: pass
print(f"Loaded {len(raw)}\n")

INITIAL = 100000

def sim(sig, close, opn, risk, hold, sl, tp):
    cap=INITIAL; mx=INITIAL; pos=0; ent=0; dh=0; dc=0
    c=close.values; o=opn.values; s=sig.values
    for i in range(1,len(c)):
        if np.isnan(s[i]): s[i]=0
        dc+=1; mx=max(mx,cap); dd=(mx-cap)/mx if mx>0 else 0
        if dd>=0.10: return False,dd,(cap-INITIAL)/INITIAL
        if (cap-INITIAL)/INITIAL>=0.10: return True,dd,(cap-INITIAL)/INITIAL
        if dc>=30: return False,dd,(cap-INITIAL)/INITIAL
        if pos>0:
            dh+=1; pp=(c[i]-ent)/ent
            if pp>=tp or pp<=-sl or dh>=hold or s[i]==0:
                pnl=(c[i]-ent)*pos; cap+=pnl-abs(pnl)*0.0002; pos=0; dh=0
        if pos==0 and s[i]>0 and dc<28:
            sh=int(cap*risk/(o[i]*sl)) if o[i]>0 else 0
            sh=min(sh,int(cap*0.25/o[i]))
            if sh>0: ent=o[i]; pos=sh; dh=0
    if pos: cap+=(c[-1]-ent)*pos-abs((c[-1]-ent)*pos)*0.0002
    return False,(mx-cap)/mx if mx>0 else 0,(cap-INITIAL)/INITIAL

results = []
for inst, df in raw.items():
    for sn, sig in [
        ('IBS30',(df['IBS'].shift(1)<0.30).astype(int)),
        ('IBS20',(df['IBS'].shift(1)<0.20).astype(int)),
        ('Z15',(df['Z20'].shift(1)<-1.5).astype(int)),
        ('Trend',(df['Close'].shift(1)>df['SMA50'].shift(1)).astype(int)),
        ('Combo',((df['IBS'].shift(1)<0.30)|(df['Z20'].shift(1)<-1.5)).astype(int)),
        ('Rev5',(df['Ret5'].shift(1)<-0.03).astype(int)),
    ]:
        for risk in [0.10, 0.15, 0.20, 0.25]:
            for hold in [2, 3, 5]:
                for sl in [0.02, 0.03]:
                    for tp in [0.02, 0.03, 0.05]:
                        p=0; t=0
                        for w in range(0,min(2000,len(df))-30,30):
                            passed,dd,ret=sim(sig.iloc[w:w+30],df['Close'].iloc[w:w+30],df['Open'].iloc[w:w+30],risk,hold,sl,tp)
                            t+=1
                            if passed: p+=1
                        if t>=15:
                            results.append((p/t*100,inst,sn,risk,hold,sl,tp,t,p))

results.sort(key=lambda x: x[0], reverse=True)

print(f"{'#':>3} {'Inst':<5} {'Strat':<8} {'Risk':>5} {'Hold':>4} {'SL':>4} {'TP':>4} {'Pass%':>6}")
print("-"*55)
for i,r in enumerate(results[:40]):
    pr,inst,sn,risk,hold,sl,tp,tot,pas=r
    m=" ***" if pr>=80 else (" **" if pr>=70 else (" *" if pr>=60 else ""))
    print(f"{i+1:>3} {inst:<5} {sn:<8} {risk:>5.0%} {hold:>4} {sl:>4.0%} {tp:>4.0%} {pr:>5.0f}%{m}")

e80=[r for r in results if r[0]>=80]; e70=[r for r in results if r[0]>=70]; e60=[r for r in results if r[0]>=60]
print(f"\n80%+: {len(e80)} | 70%+: {len(e70)} | 60%+: {len(e60)}")
for label,lst in [("80%+",e80),("70%+",e70),("60%+",e60)]:
    if lst:
        print(f"\n{label} PASS RATE:")
        for r in lst[:10]:
            print(f"  {r[0]:.0f}% — {r[2]} on {r[1]} risk={r[3]:.0%} hold={r[4]} SL={r[5]:.0%} TP={r[6]:.0%}")
        break
else:
    print("\nTop 10:")
    for r in results[:10]:
        print(f"  {r[0]:.0f}% — {r[2]} on {r[1]} risk={r[3]:.0%} hold={r[4]} SL={r[5]:.0%} TP={r[6]:.0%}")
