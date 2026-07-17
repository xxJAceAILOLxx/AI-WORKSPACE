"""Parameter optimization for the daily LVPR strategy (the vault's only
validated edge), done with an explicit in-sample / out-of-sample split so we
don't overfit noise.

Discipline (per memory.md gotchas):
  * Optimize params on IS (2016-2022).
  * Validate the single best IS config on OOS (2023-2025).
  * WFR = OOS_PF / IS_PF ; <0.3 = overfit, >0.5 = robust.

The same parameter set is deployed across a basket of liquid ETFs; we rank by
the basket-averaged Sharpe (and report basket-averaged PF).  Sizing is held
constant at 95% equity so params are isolated.
"""

from __future__ import annotations

import argparse
import itertools
from typing import Dict, List

from backtest.metrics import compute_metrics
from backtest.strategies import lvpr

TICKERS = ["SPY", "QQQ", "IWM", "DIA", "MDY", "GLD", "SLV"]
IS_START, IS_END = "2016-01-01", "2022-12-31"
OOS_START, OOS_END = "2023-01-01", "2025-12-31"

GRID = {
    "ibs_max": [0.20, 0.30, 0.40],
    "vol_max": [0.6, 0.8, 1.0],
    "hold": [5, 7, 10],
    "stop_mult": [1.5, 2.0, 3.0],
}


def basket_metrics(tickers, start, end, params) -> Dict:
    pfs, shars, wrs, ns = [], [], [], []
    for t in tickers:
        try:
            r = lvpr(
                ticker=t, start=start, end=end, size_policy="percent_of_equity",
                size_value=0.95, **params,
            )
        except Exception as e:
            print(f"  warn {t}: {e}")
            continue
        m = compute_metrics(r)
        if m.trade_count >= 5:
            pfs.append(m.profit_factor)
            shars.append(m.sharpe)
            wrs.append(m.win_rate)
            ns.append(m.trade_count)
    if not pfs:
        return {"pf": float("nan"), "sharpe": float("nan"), "wr": 0.0, "n": 0}
    return {
        "pf": sum(pfs) / len(pfs),
        "sharpe": sum(shars) / len(shars),
        "wr": sum(wrs) / len(wrs),
        "n": sum(ns),
        "ntick": len(pfs),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", default=",".join(TICKERS))
    args = ap.parse_args()
    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]

    print(f"LVPR optimization | IS {IS_START}->{IS_END} | OOS {OOS_START}->{OOS_END}")
    print(f"Basket: {tickers}\n")

    keys = list(GRID)
    combos = list(itertools.product(*(GRID[k] for k in keys)))
    rows: List[Dict] = []

    for vals in combos:
        params = dict(zip(keys, vals))
        m = basket_metrics(tickers, IS_START, IS_END, params)
        if m["n"] == 0:
            continue
        rows.append({**params, **m})

    rows.sort(key=lambda r: r["sharpe"], reverse=True)
    print(f"=== TOP 8 by IS basket Sharpe ({len(rows)} valid combos) ===")
    print(f"{'ibs':>4} {'vol':>4} {'hold':>4} {'stop':>4} | {'IS_PF':>5} {'IS_Sh':>5} {'IS_WR':>5} {'ntick':>5} {'trades':>6}")
    for r in rows[:8]:
        print(
            f"{r['ibs_max']:4.2f} {r['vol_max']:4.1f} {r['hold']:4d} {r['stop_mult']:4.1f} | "
            f"{r['pf']:5.2f} {r['sharpe']:5.2f} {r['wr']:5.1%} {r['ntick']:5d} {r['n']:6d}"
        )

    best = rows[0]
    best_params = {k: best[k] for k in keys}
    print(f"\nBest IS config: {best_params}")
    oos = basket_metrics(tickers, OOS_START, OOS_END, best_params)
    is_pf, is_sh = best["pf"], best["sharpe"]
    oos_pf, oos_sh = oos["pf"], oos["sharpe"]
    wfr_pf = oos_pf / is_pf if is_pf else float("nan")
    wfr_sh = oos_sh / is_sh if is_sh else float("nan")
    print(f"OOS basket: PF={oos_pf:.2f} Sharpe={oos_sh:.2f} WR={oos['wr']:.1%} trades={oos['n']} ({oos['ntick']} tickers)")
    print(f"WFR (PF)   = {wfr_pf:.2f}   (vault: >0.5 robust, <0.3 overfit)")
    print(f"WFR (Sharpe)= {wfr_sh:.2f}")


if __name__ == "__main__":
    main()
