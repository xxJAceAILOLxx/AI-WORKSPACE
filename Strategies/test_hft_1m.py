"""Empirical test of the three proposed HFT edges on Binance 1m data.

Data is free Binance public klines (spot + USDT perpetual futures).  The three
strategies map to the proposals as follows:

* S1  crypto -> equity lead-lag        -> PROXY: BTC perp leads BTC spot
                                          (same fast-venue-leads-slow-venue
                                           microstructure, tested inside crypto)
* S2  odd-lot flow clustering          -> PROXY: 1m volume-imbalance burst
                                          continuation on the perp (stands in
                                          for the odd-lot flow-burst mechanism;
                                          the EXACT odd-lot signal needs a paid
                                          tick feed with an odd-lot flag)
* S3  perpetual funding-rate microburst -> LITERAL: basis (perp - spot) snap
                                          around the 00/08/16 UTC funding times

Each strategy is vectorized (not the daily Engine) because HFT trade counts
are huge.  Costs are shown under both MAKER and TAKER assumptions.  A strategy
is "works" only if net Sharpe >= 1.5 after costs.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from backtest import load_intraday_binance

SYMBOL = "BTCUSDT"
START = "2024-01-01"
END = "2024-12-31"
INTERVAL = "1m"


def load_pair():
    print(f"Loading {SYMBOL} 1m spot + perp ({START} -> {END}) ...")
    spot = load_intraday_binance(SYMBOL, INTERVAL, START, END, market="spot")
    perp = load_intraday_binance(SYMBOL, INTERVAL, START, END, market="futures")
    s = spot.df
    p = perp.df
    common = s.index.intersection(p.index)
    s = s.loc[common]
    p = p.loc[common]
    print(f"  {len(common):,} aligned 1m bars ({s.index[0]} -> {s.index[-1]})")
    return s, p


def per_trade_metrics(rets: pd.Series, start, end):
    rets = rets.dropna()
    if len(rets) == 0:
        return None
    mean = rets.mean()
    std = rets.std()
    if std == 0 or np.isnan(std):
        return None
    years = (pd.Timestamp(end) - pd.Timestamp(start)).days / 365.25
    tpy = len(rets) / years if years > 0 else len(rets)
    sharpe = (mean / std) * np.sqrt(tpy)
    wins = (rets > 0).sum()
    gross_win = rets[rets > 0].sum()
    gross_loss = -rets[rets < 0].sum()
    pf = gross_win / gross_loss if gross_loss > 0 else float("inf")
    return {
        "n": len(rets),
        "mean_bps": mean * 1e4,
        "std_bps": std * 1e4,
        "sharpe": sharpe,
        "wr": wins / len(rets),
        "pf": pf,
        "tot_ret": rets.sum(),
    }


def events_to_returns(ei, xi, dirs, epx, xpx, cost):
    """Build per-trade net returns from (entry_idx, exit_idx, direction) lists."""
    out = []
    for e, x, d in zip(ei, xi, dirs):
        if e < 0 or x >= len(epx) or e >= len(epx):
            continue
        entry = epx[e]
        exit = xpx[x]
        if entry <= 0 or exit <= 0:
            continue
        gross = d * (exit / entry - 1.0)
        out.append(gross - cost)
    return pd.Series(out)


# --------------------------------------------------------------------------
# S3: perpetual funding-rate basis microburst (LITERAL)
# --------------------------------------------------------------------------

def test_s3(s, p, cost):
    basis = (p["Close"] - s["Close"]) / s["Close"]
    # Funding settles at 00:00, 08:00, 16:00 UTC.
    idx = basis.index
    is_fund = (idx.hour.isin([0, 8, 16])) & (idx.minute == 0)
    fund_times = idx[is_fund]
    ei, xi, dirs = [], [], []
    for ft in fund_times:
        t_entry = ft - pd.Timedelta(minutes=3)
        t_exit = ft + pd.Timedelta(minutes=1)
        if t_entry not in basis.index or t_exit not in basis.index:
            continue
        b_e = basis.loc[t_entry]
        b_x = basis.loc[t_exit]
        # Only trade when there is a meaningful basis to snap.
        if abs(b_e) < 0.0002:  # 2 bps
            continue
        ei.append(basis.index.get_loc(t_entry) + 1)  # enter next bar
        xi.append(basis.index.get_loc(t_exit) + 1)
        # Convergence play: profit = basis_entry - basis_exit regardless of sign.
        dirs.append(1)
    # Net return of the convergence trade = (basis_entry - basis_exit) / spot_entry.
    rets = []
    for e, x, _ in zip(ei, xi, dirs):
        be = basis.iloc[e - 1]
        bx = basis.iloc[x - 1]
        se = s["Close"].iloc[e - 1]
        rets.append((be - bx) / se - cost)
    return pd.Series(rets)


# --------------------------------------------------------------------------
# S1 proxy: perp leads spot (fast venue leads slow venue)
# --------------------------------------------------------------------------

def test_s1(s, p, cost, hold=3):
    rp = p["Close"].pct_change()
    rs = s["Close"].pct_change()
    win = 300
    mu_p = rp.rolling(win).mean().shift(1)
    sd_p = rp.rolling(win).std().shift(1)
    z_p = (rp - mu_p) / sd_p
    ei, xi, dirs = [], [], []
    for t in range(win + 2, len(rp)):
        z = z_p.iloc[t]
        rp_t = rp.iloc[t]
        rs_t = rs.iloc[t]
        if not np.isfinite(z):
            continue
        # Lead-lag condition: perp made a big (2-sigma) move AND spot moved
        # *less* than perp this bar (spot is lagging).  Trade spot to follow.
        if (z > 2.0 or z < -2.0) and abs(rs_t) < abs(rp_t):
            ei.append(t + 1)
            xi.append(min(t + 1 + hold, len(s) - 1))
            dirs.append(1 if z > 0 else -1)
    return events_to_returns(ei, xi, dirs, s["Open"].to_numpy(), s["Open"].to_numpy(), cost)


# --------------------------------------------------------------------------
# S2 proxy: 1m volume-imbalance burst continuation (flow proxy)
# --------------------------------------------------------------------------

def test_s2(p, cost, hold=3):
    close = p["Close"]
    vol = p["Volume"].astype(float)
    d = np.sign(close.diff().fillna(0).to_numpy())
    v = vol.to_numpy()
    up = np.where(d > 0, v, 0.0)
    dn = np.where(d < 0, v, 0.0)
    up_s = pd.Series(up).rolling(10).sum().shift(1)
    dn_s = pd.Series(dn).rolling(10).sum().shift(1)
    tot = pd.Series(v).rolling(10).sum().shift(1)
    daily = tot.rolling(1440).mean()  # ~1 day of 10-min volume sums
    oli = (up_s - dn_s) / (up_s + dn_s).replace(0, np.nan)
    burst = tot > 5 * daily
    ei, xi, dirs = [], [], []
    for t in range(1500, len(p)):
        o = oli.iloc[t]
        b = burst.iloc[t]
        if not np.isfinite(o) or not b:
            continue
        if o > 0.6:
            dirs.append(1); ei.append(t + 1); xi.append(min(t + 1 + hold, len(p) - 1))
        elif o < -0.6:
            dirs.append(-1); ei.append(t + 1); xi.append(min(t + 1 + hold, len(p) - 1))
    return events_to_returns(ei, xi, dirs, p["Open"].to_numpy(), p["Open"].to_numpy(), cost)


def show(name, rets):
    m = per_trade_metrics(rets, START, END)
    if m is None:
        print(f"  {name}: NO TRADES / undefined")
        return
    print(
        f"  {name}: n={m['n']:<6} Sharpe={m['sharpe']:6.2f} PF={m['pf']:5.2f} "
        f"WR={m['wr']:5.1%} mean={m['mean_bps']:+6.2f}bps std={m['std_bps']:6.2f}bps "
        f"tot={m['tot_ret']:+.1%}"
    )


def main():
    s, p = load_pair()

    # Cost assumptions (round-trip fraction of notional).
    S3_MAKER, S3_TAKER = 0.0008, 0.0016   # two-leg basis trade (4 fills)
    S1_MAKER, S1_TAKER = 0.0004, 0.0008   # single-leg spot
    S2_MAKER, S2_TAKER = 0.0004, 0.0008   # single-leg perp

    print("\n=== S3  funding basis microburst (LITERAL) ===")
    show("  maker ", test_s3(s, p, S3_MAKER))
    show("  taker ", test_s3(s, p, S3_TAKER))
    print("  (raw, no-cost convergence edge):")
    show("  raw   ", test_s3(s, p, 0.0))

    print("\n=== S1  perp->spot lead-lag (PROXY) ===")
    show("  maker ", test_s1(s, p, S1_MAKER))
    show("  taker ", test_s1(s, p, S1_TAKER))
    show("  raw   ", test_s1(s, p, 0.0))

    print("\n=== S2  flow-burst continuation (PROXY for odd-lot clustering) ===")
    show("  maker ", test_s2(p, S2_MAKER))
    show("  taker ", test_s2(p, S2_TAKER))
    show("  raw   ", test_s2(p, 0.0))


if __name__ == "__main__":
    main()
