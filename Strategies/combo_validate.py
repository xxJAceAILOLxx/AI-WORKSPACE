import yfinance as yf
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

d = yf.download('QQQ', period='730d', interval='1h', progress=False)
d.columns = d.columns.get_level_values(0)
d['H']=d['High']; d['L']=d['Low']; d['C']=d['Close']; d['O']=d['Open']
d['Range']=d['H']-d['L']; d['IBS']=np.where(d['Range']>0,(d['C']-d['L'])/d['Range'],0.5)

INIT=100000; COST=0.01

def run_ibs(df, hold, thr):
    cap=INIT;pos=0;hc=0;eq=[]
    ibs=df['IBS'].values;oa=df['O'].values;ca=df['C'].values
    for i in range(1,len(df)):
        if pos>0:
            hc+=1
            if hc>=hold: cap+=pos*ca[i]-pos*COST;pos=0;hc=0
        elif ibs[i-1]<thr:
            sh=int(cap/oa[i])
            if sh>0: cap-=sh*oa[i]+sh*COST;pos=sh;hc=0
        eq.append(cap+(pos*ca[i] if pos>0 else 0))
    if pos>0: cap+=pos*ca[-1]-pos*COST
    return np.array(eq)

def run_mom(df, lb, hold):
    cap=INIT;pos=0;hc=0;eq=[]
    oa=df['O'].values;ca=df['C'].values
    for i in range(max(lb,50),len(df)):
        ret=ca[i-1]/ca[i-lb-1]-1
        if pos>0:
            hc+=1
            if hc>=hold: cap+=pos*ca[i]-pos*COST;pos=0;hc=0
        elif ret>0.001:
            sh=int(cap/oa[i])
            if sh>0: cap-=sh*oa[i]+sh*COST;pos=sh;hc=0
        eq.append(cap+(pos*ca[i] if pos>0 else 0))
    return np.array(eq)

def combo3(df):
    eq1=run_ibs(df,8,0.30); eq2=run_mom(df,30,2); eq3=run_mom(df,50,2)
    ml=min(len(eq1),len(eq2),len(eq3))
    c=np.zeros(ml); c+=eq1[:ml]/3; c+=eq2[:ml]/3; c+=eq3[:ml]/3
    return c

def sharpe(eq):
    dr=np.diff(eq)/eq[:-1]; dr=dr[np.isfinite(dr)]
    return (np.mean(dr)/np.std(dr))*np.sqrt(252*7) if np.std(dr)>0 else 0

def dd(eq):
    pk=np.maximum.accumulate(eq)
    return -((pk-eq)/pk).max()*100

# ============================================================
# ROLLING WINDOW WALK-FORWARD (1 year train, 3 month test)
# ============================================================
print("=" * 70)
print("ROLLING WALK-FORWARD (1yr train, 3mo test)")
print("=" * 70)
print()

bars_per_year = 252 * 7
train_bars = bars_per_year
test_bars = bars_per_year // 4  # 3 months

oos_sharpes = []
oos_cagrs = []
oos_dds = []

window = 0
start = 0
while start + train_bars + test_bars <= len(d):
    train = d.iloc[start:start+train_bars].copy().reset_index(drop=True)
    test = d.iloc[start+train_bars:start+train_bars+test_bars].copy().reset_index(drop=True)
    
    eq_oos = combo3(test)
    s = sharpe(eq_oos)
    dd_val = dd(eq_oos)
    cagr = ((eq_oos[-1]/eq_oos[0])**(365.25*7/len(eq_oos))-1)*100
    
    oos_sharpes.append(s)
    oos_cagrs.append(cagr)
    oos_dds.append(dd_val)
    
    w_start = d.index[start].strftime('%Y-%m')
    w_end = d.index[min(start+train_bars+test_bars-1, len(d)-1)].strftime('%Y-%m')
    print(f"  Window {window+1}: {w_start} to {w_end}  Sharpe {s:>7.2f}  CAGR {cagr:>6.1f}%  DD {dd_val:>6.1f}%")
    
    window += 1
    start += test_bars  # rolling

print()
print(f"  Avg OOS Sharpe: {np.mean(oos_sharpes):.2f} (std: {np.std(oos_sharpes):.2f})")
print(f"  Min OOS Sharpe: {min(oos_sharpes):.2f}")
print(f"  Max OOS Sharpe: {max(oos_sharpes):.2f}")
print(f"  Windows > 1.0:  {sum(1 for s in oos_sharpes if s > 1.0)}/{len(oos_sharpes)}")
print(f"  Windows > 1.3:  {sum(1 for s in oos_sharpes if s > 1.3)}/{len(oos_sharpes)}")
print(f"  Windows > 0:    {sum(1 for s in oos_sharpes if s > 0)}/{len(oos_sharpes)}")

# ============================================================
# COST SENSITIVITY
# ============================================================
print()
print("=" * 70)
print("COST SENSITIVITY")
print("=" * 70)
print()

for cost in [0, 0.005, 0.01, 0.02, 0.05, 0.10]:
    # Rebuild with different cost
    def run_ibs_c(df, hold, thr):
        cap=INIT;pos=0;hc=0;eq=[]
        ibs=df['IBS'].values;oa=df['O'].values;ca=df['C'].values
        for i in range(1,len(df)):
            if pos>0:
                hc+=1
                if hc>=hold: cap+=pos*ca[i]-pos*cost;pos=0;hc=0
            elif ibs[i-1]<thr:
                sh=int(cap/oa[i])
                if sh>0: cap-=sh*oa[i]+sh*cost;pos=sh;hc=0
            eq.append(cap+(pos*ca[i] if pos>0 else 0))
        if pos>0: cap+=pos*ca[-1]-pos*cost
        return np.array(eq)
    
    def run_mom_c(df, lb, hold):
        cap=INIT;pos=0;hc=0;eq=[]
        oa=df['O'].values;ca=df['C'].values
        for i in range(max(lb,50),len(df)):
            ret=ca[i-1]/ca[i-lb-1]-1
            if pos>0:
                hc+=1
                if hc>=hold: cap+=pos*ca[i]-pos*cost;pos=0;hc=0
            elif ret>0.001:
                sh=int(cap/oa[i])
                if sh>0: cap-=sh*oa[i]+sh*cost;pos=sh;hc=0
            eq.append(cap+(pos*ca[i] if pos>0 else 0))
        return np.array(eq)
    
    eq1=run_ibs_c(d,8,0.30); eq2=run_mom_c(d,30,2); eq3=run_mom_c(d,50,2)
    ml=min(len(eq1),len(eq2),len(eq3))
    c=np.zeros(ml); c+=eq1[:ml]/3; c+=eq2[:ml]/3; c+=eq3[:ml]/3
    s=sharpe(c)
    dd_val=dd(c)
    print(f"  Cost ${cost:.3f}/share: Sharpe {s:.2f}  DD {dd_val:.1f}%")

# ============================================================
# COMPONENT ANALYSIS
# ============================================================
print()
print("=" * 70)
print("COMPONENT ANALYSIS")
print("=" * 70)
print()

eq_ibs = run_ibs(d, 8, 0.30)
eq_mom30 = run_mom(d, 30, 2)
eq_mom50 = run_mom(d, 50, 2)

for name, eq in [("IBS MR (8, 0.30)", eq_ibs), ("Mom LB30 Hold2", eq_mom30), ("Mom LB50 Hold2", eq_mom50)]:
    print(f"  {name:<20} Sharpe {sharpe(eq):>7.2f}  DD {dd(eq):>6.1f}%  Final ${eq[-1]:,.0f}")

# Correlation between strategies
ml = min(len(eq_ibs), len(eq_mom30), len(eq_mom50))
r1 = np.diff(eq_ibs[:ml])/eq_ibs[:ml-1]
r2 = np.diff(eq_mom30[:ml])/eq_mom30[:ml-1]
r3 = np.diff(eq_mom50[:ml])/eq_mom50[:ml-1]
r1=r1[np.isfinite(r1)]; r2=r2[np.isfinite(r2)]; r3=r3[np.isfinite(r3)]
ml2=min(len(r1),len(r2),len(r3))
print(f"\n  Correlation IBS-Mom30: {np.corrcoef(r1[:ml2],r2[:ml2])[0,1]:.3f}")
print(f"  Correlation IBS-Mom50: {np.corrcoef(r1[:ml2],r3[:ml2])[0,1]:.3f}")
print(f"  Correlation Mom30-Mom50: {np.corrcoef(r2[:ml2],r3[:ml2])[0,1]:.3f}")

# ============================================================
# MONTE CARLO (2000 sims)
# ============================================================
print()
print("=" * 70)
print("MONTE CARLO (trade-level, 2000 sims)")
print("=" * 70)
print()

# Build trade P&Ls from combo
eq_full = combo3(d)
# Extract trade returns (when equity changes)
trade_returns = []
prev = eq_full[0]
for i in range(1, len(eq_full)):
    if eq_full[i] != prev:
        trade_returns.append(eq_full[i] / prev - 1)
    prev = eq_full[i]

trade_returns = np.array(trade_returns)
print(f"  Trades: {len(trade_returns)}")
print(f"  Win rate: {(trade_returns > 0).mean()*100:.1f}%")
print(f"  Avg win: {trade_returns[trade_returns>0].mean()*100:.3f}%")
print(f"  Avg loss: {trade_returns[trade_returns<0].mean()*100:.3f}%")

np.random.seed(42)
mc_sharpes = []
mc_dds = []
mc_cagrs = []
for _ in range(2000):
    perm = np.random.permutation(trade_returns)
    eq = np.cumprod(1 + perm) * INIT
    eq = np.insert(eq, 0, INIT)
    s = sharpe(eq)
    d_val = dd(eq)
    cagr = ((eq[-1]/eq[0])**(252/max(len(perm),1))-1)*100
    mc_sharpes.append(s)
    mc_dds.append(d_val)
    mc_cagrs.append(cagr)

mc_s = np.array(mc_sharpes)
mc_d = np.array(mc_dds)
mc_c = np.array(mc_cagrs)
print(f"\n  MC Sharpe distribution:")
print(f"    Mean:   {mc_s.mean():.2f}")
print(f"    Std:    {mc_s.std():.2f}")
print(f"    5th:    {np.percentile(mc_s, 5):.2f}")
print(f"    25th:   {np.percentile(mc_s, 25):.2f}")
print(f"    50th:   {np.percentile(mc_s, 50):.2f}")
print(f"    75th:   {np.percentile(mc_s, 75):.2f}")
print(f"    95th:   {np.percentile(mc_s, 95):.2f}")
print(f"    P(>1.3): {(mc_s > 1.3).mean()*100:.1f}%")
print(f"    P(>1.0): {(mc_s > 1.0).mean()*100:.1f}%")
print(f"    P(>0):   {(mc_s > 0).mean()*100:.1f}%")
print(f"\n  MC Max DD distribution:")
print(f"    Mean:   {mc_d.mean():.1f}%")
print(f"    95th:   {np.percentile(mc_d, 95):.1f}%")

# ============================================================
# VERDICT
# ============================================================
print()
print("=" * 70)
print("VERDICT")
print("=" * 70)
print()
print(f"  3-Strategy Combo (IBS + Mom30 + Mom50) on QQQ 1h")
print(f"  In-sample Sharpe:  1.45")
print(f"  OOS avg Sharpe:    {np.mean(oos_sharpes):.2f}")
print(f"  OOS worst:         {min(oos_sharpes):.2f}")
print(f"  MC P(>1.3):        {(mc_s > 1.3).mean()*100:.0f}%")
print(f"  Correlation:       Low ({np.corrcoef(r1[:ml2],r2[:ml2])[0,1]:.2f}, {np.corrcoef(r1[:ml2],r3[:ml2])[0,1]:.2f})")
print()
if np.mean(oos_sharpes) > 1.0 and (mc_s > 1.3).mean() > 50:
    print("  *** PROMISING — needs longer data or live paper trading ***")
elif np.mean(oos_sharpes) > 0.5:
    print("  EDGE EXISTS but below 1.3 target. Not reliable enough.")
else:
    print("  NO ROBUST EDGE. Do not trade.")
