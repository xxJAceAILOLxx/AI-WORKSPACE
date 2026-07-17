"""Grid-search optimizer for the two-sided ``vp_consolidation_fade`` strategy.

Loads a 5m symbol once, then sweeps a parameter grid and ranks configs by a
composite score (Sharpe, profit factor, drawdown, trade count).

Usage:
    python3 Strategies/optimize_vp_fade_5m.py --symbol BTCUSDT
"""

from __future__ import annotations

import argparse
import itertools
from typing import Dict, List

from backtest import load_intraday_binance
from backtest.metrics import compute_metrics
from backtest.strategies import vp_consolidation_fade


GRID = {
    "va_pct": [0.68, 0.70],
    "n_bins": [24, 48],
    "max_hold_bars": [48, 96, 144],
    "stop_mult": [0.0, 1.5],
}

EOD_EXIT = True
START = "2021-07-01"
END = "2026-05-31"


def score(m) -> float:
    if m.trade_count < 30:
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
        res = vp_consolidation_fade(
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
            f"  [{i:>2}/{len(combos)}] va={params['va_pct']:.2f} bins={params['n_bins']:>2} "
            f"hold={params['max_hold_bars']:>3} stop={params['stop_mult']:.1f} | "
            f"Sharpe={m.sharpe:5.2f} PF={m.profit_factor:5.2f} WR={m.win_rate:4.1%} "
            f"DD={m.max_drawdown:5.1%} n={m.trade_count} (L{n_long}/S{n_short})"
        )

    rows.sort(key=lambda r: r["score"], reverse=True)
    print("\n=== TOP 10 (by score) ===")
    print(
        f"{'va':>4} {'bins':>4} {'hold':>5} {'stop':>5} "
        f"{'Sharpe':>7} {'PF':>6} {'WR':>6} {'DD':>6} {'trades':>7} {'score':>6}"
    )
    for r in rows[:10]:
        print(
            f"{r['va_pct']:4.2f} {r['n_bins']:4d} {r['max_hold_bars']:5d} "
            f"{r['stop_mult']:5.1f} {r['sharpe']:7.2f} {r['pf']:6.2f} "
            f"{r['wr']:6.1%} {r['dd']:6.1%} {r['trades']:7d} {r['score']:6.2f}"
        )


if __name__ == "__main__":
    main()
