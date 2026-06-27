"""
FUNDED ACCOUNT — PASS RATE SEARCH (MINIMAL)
"""
import yfinance as yf
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

print("Downloading...")
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
            df['SMA50'] = df['Close'].rolling(50).mean()
            df['SMA200'] = df['Close'].rolling(200).mean()
            df['Z20'] = (df['Close']-df['Close'].rolling(20).mean())/df['Close'].rolling(20).std()
            df['Ret5'] = df['Close']/df['Close'].shift(5)-1
            raw[n] = df
            print(f"  {n}: {len(df)} bars")
    except: pass
print(f"Loaded {len(raw)}\n")

INITIAL = 100000

def sim(sig, close, opn, risk, hold, sl_pct, tp_pct, maxpos):
    cap=INITIAL; mx=INITIAL; pos=0; ent=0; dh=0; dc=0; cd=None; ds=INITIAL; nt=0; nw=0
    c=close.values; o=opn.values; s=sig.values
    for i in range(1,len(c)):
        if np.isnan(s[i]): s[i]=0
        try: day=close.index[i].date()
        except: day=i
        if day!=cd: ds=cap; cd=day; dc+=1
        if pos!=0 and (ds-cap)/ds>=0.05:
            cap+=(c[i]-ent)*pos-abs((c[i]-ent)*pos)*0.0002; pos=0; nt+=1
        mx=max(mx,cap); dd=(mx-cap)/mx if mx>0 else 0
        if dd>=0.10:
            if pos: cap+=(c[i]-ent)*pos-abs((c[i]-ent)*pos)*0.0002
            return False,dd,(cap-INITIAL)/INITIAL,nt,nw
        if (cap-INITIAL)/INITIAL>=0.10:
            return True,dd,(cap-INITIAL)/INITIAL,nt,nw
        if dc>=30:
            return False,dd,(cap-INITIAL)/INITIAL,nt,nw
        if pos>0:
            dh+=1; pp=(c[i]-ent)/ent
            if pp>=tp_pct or pp<=-sl_pct or dh>=hold or s[i]==0:
                pnl=(c[i]-ent)*pos; cap+=pnl-abs(pnl)*0.0002
                if pnl>0: nw+=1
                pos=0; nt+=1; dh=0
        if pos==0 and s[i]>0 and dc<28:
            sh=int(cap*risk/(o[i]*sl_pct)) if o[i]>0 else 0
            sh=min(sh,int(cap*maxpos/o[i]))
            if sh>0: ent=o[i]; pos=sh; dh=0
    if pos: cap+=(c[-1]-ent)*pos-abs((c[-1]-ent)*pos)*0.0002
    return False,(mx-cap)/mx if mx>0 else 0,(cap-INITIAL)/INITIAL,nt,nw

results = []
for inst, df in raw.items():
    for sn, sig in [
        ('IBS30',(df['IBS'].shift(1)<0.30).astype(int)),
        ('IBS20',(df['IBS'].shift(1)<0.20).astype(int)),
        ('IBS15',(df['IBS'].shift(1)<0.15).astype(int)),
        ('Z15',(df['Z20'].shift(1)<-1.5).astype(int)),
        ('Z20',(df['Z20'].shift(1)<-2.0).astype(int)),
        ('Trend',(df['Close'].shift(1)>df['SMA50'].shift(1)).astype(int)),
        ('Combo',((df['IBS'].shift(1)<0.30)|(df['Z20'].shift(1)<-1.5)).astype(int)),
        ('Rev5',(df['Ret5'].shift(1)<-0.03).astype(int)),
        ('Mom5',(df['Ret5'].shift(1)>0.03).astype(int)),
    ]:
        for risk in [0.05, 0.10, 0.15, 0.20]:
            for hold in [2, 3, 5]:
                for sl in [0.01, 0.02, 0.03]:
                    for tp in [0.01, 0.02, 0.03, 0.05]:
                        for mp in [0.25, 0.50]:
                            p=0; t=0; rs=[]; ds=[]
                            for w in range(0,min(2000,len(df))-30,30):
                                ws=sig.iloc[w:w+30]; wc=df['Close'].iloc[w:w+30]; wo=df['Open'].iloc[w:w+30]
                                passed,dd,ret,nt,nw=sim(ws,wc,wo,risk,hold,sl,tp,mp)
                                t+=1
                                if passed: p+=1
                                rs.append(ret); ds.append(dd)
                            if t>=20:
                                pr=p/t*100
                                results.append((pr,inst,sn,risk,hold,sl,tp,mp,np.mean(rs)*100,np.mean(ds)*100,t,p))

results.sort(key=lambda x: x[0], reverse=True)

print(f"{'#':>3} {'Inst':<5} {'Strat':<7} {'Risk':>5} {'Hold':>4} {'SL':>4} {'TP':>4} {'Pos':>4} {'Pass%':>6} {'Ret%':>6} {'DD%':>6}")
print("-"*75)
for i,r in enumerate(results[:40]):
    pr,inst,sn,risk,hold,sl,tp,mp,ar,ad,t,p=r
    m=" ***" if pr>=80 else (" **" if pr>=70 else "")
    print(f"{i+1:>3} {inst:<5} {sn:<7} {risk:>5.0%} {hold:>4} {sl:>4.0%} {tp:>4.0%} {mp:>4.0%} {pr:>5.0f}% {ar:>5.1f}% {ad:>5.1f}%{m}")

e80=[r for r in results if r[0]>=80]
e70=[r for r in results if r[0]>=70]
e60=[r for r in results if r[0]>=60]
print(f"\n80%+: {len(e80)} | 70%+: {len(e70)} | 60%+: {len(e60)}")
if e80:
    print("\n80%+ PASS RATE:")
    for r in e80[:15]:
        print(f"  {r[0]:.0f}% — {r[2]} on {r[1]} risk={r[3]:.0%} hold={r[4]} SL={r[5]:.0%} TP={r[6]:.0%} pos={r[7]:.0%}")
elif e70:
    print("\n70%+ PASS RATE:")
    for r in e70[:15]:
        print(f"  {r[0]:.0f}% — {r[2]} on {r[1]} risk={r[3]:.0%} hold={r[4]} SL={r[5]:.0%} TP={r[6]:.0%} pos={r[7]:.0%}")
else:
    print("\nTop 15:")
    for r in results[:15]:
        print(f"  {r[0]:.0f}% — {r[2]} on {r[1]} risk={r[3]:.0%} hold={r[4]} SL={r[5]:.0%} TP={r[6]:.0%} pos={r[7]:.0%}")
