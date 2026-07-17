"""Grid-search optimizer for the two-sided ``vwap_reversion`` strategy.

Loads BTCUSDT / ETHUSDT 5m data once per symbol (Binance cache), then sweeps
a parameter grid and ranks configs by a composite score that rewards a Sharpe
>= 1, profit factor >= 1.5, a reasonable trade count, and a small drawdown.

Usage:
    python3 Strategies/optimize_vwap_5m.py
    python3 Strategies/optimize_vwap_5m.py --symbol ETHUSDT
"""

from __future__ import annotations

import argparse
import itertools
from typing import Dict, List

from backtest import load_intraday_binance
from backtest.metrics import compute_metrics
from backtest.strategies import vwap_reversion


# Parameter grid.  Kept compact so a full sweep finishes in a few minutes.
GRID = {
    "entry_dev": [0.008, 0.015],
    "vol_min": [1.0, 1.5],
    "max_hold_bars": [48, 96],
    "stop_mult": [0.0, 1.5],
    "mode": ["reversion", "momentum"],
}

EOD_EXIT = True
START = "2021-07-01"
END = "2026-05-31"


def score(m) -> float:
    """Higher is better.  Penalize low trade count and large drawdowns."""
    if m.trade_count < 50:
        return -1.0
    s = m.sharpe
    s += (m.profit_factor - 1.0) * 0.5
    s -= max(0.0, m.max_drawdown - 0.20) * 2.0
    return float(s)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--start", default=START)
    ap.add_argument("--end", default=END)
    args = ap.parse_args()

    print(f"Loading {args.symbol} 5m ({args.start} -> {args.end}) ...")
    ohlcv = load_intraday_binance(args.symbol, "5m", args.start, args.end)
    print(f"  {len(ohlcv.df):,} bars loaded.")

    keys = list(GRID)
    combos = list(itertools.product(*(GRID[k] for k in keys)))
    rows: List[Dict] = []

    for i, vals in enumerate(combos, 1):
        params = dict(zip(keys, vals))
        params["eod_exit"] = EOD_EXIT
        res = vwap_reversion(
            symbol=args.symbol, ohlcv=ohlcv, start=args.start, end=args.end, **params
        )
        m = compute_metrics(res)
        n_long = sum(1 for t in res.trades if t.shares > 0)
        n_short = sum(1 for t in res.trades if t.shares < 0)
        rows.append(
            {
                **params,
                "sharpe": m.sharpe,
                "pf": m.profit_factor,
                "cagr": m.cagr,
                "dd": m.max_drawdown,
                "wr": m.win_rate,
                "trades": m.trade_count,
                "n_long": n_long,
                "n_short": n_short,
                "score": score(m),
            }
        )
        print(
            f"  [{i:>2}/{len(combos)}] dev={params['entry_dev']:.3f} "
            f"vol>={params['vol_min']:.1f} hold={params['max_hold_bars']:>3} "
            f"stop={params['stop_mult']:.1f} | Sharpe={m.sharpe:5.2f} "
            f"PF={m.profit_factor:5.2f} WR={m.win_rate:4.1%} "
            f"DD={m.max_drawdown:5.1%} n={m.trade_count} "
            f"(L{n_long}/S{n_short})"
        )

    rows.sort(key=lambda r: r["score"], reverse=True)
    print("\n=== TOP 10 (by score) ===")
    print(
        f"{'dev':>6} {'vol':>4} {'hold':>5} {'stop':>5} "
        f"{'Sharpe':>7} {'PF':>6} {'WR':>6} {'DD':>6} {'trades':>7} {'score':>6}"
    )
    for r in rows[:10]:
        print(
            f"{r['entry_dev']:6.3f} {r['vol_min']:4.1f} {r['max_hold_bars']:5d} "
            f"{r['stop_mult']:5.1f} {r['sharpe']:7.2f} {r['pf']:6.2f} "
            f"{r['wr']:6.1%} {r['dd']:6.1%} {r['trades']:7d} {r['score']:6.2f}"
        )


if __name__ == "__main__":
    main()
