"""Compare GARCH vol-targeting vs fixed-size across every asset.

Runs the ``garch_ema_<asset>`` and ``ema_fixed_<asset>`` pairs from
``backtest.strategies.garch`` and prints a side-by-side table plus a
roll-up of how often vol-targeting wins each metric.
"""

from __future__ import annotations

import os
import sys

# Make the project importable when run directly.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backtest.metrics import compute_metrics
from backtest.strategies.garch import ASSETS, _run

METRICS = ["cagr", "total_return", "max_drawdown", "sharpe", "profit_factor", "final_equity"]


def _pct(x: float) -> str:
    return f"{x * 100:7.2f}%"


def _num(x: float) -> str:
    return f"{x:>14,.0f}"


def main() -> int:
    start = "2016-01-01"
    end = "2025-12-31"

    print(f"GARCH vol-target (target 15%, cap 3x) vs fixed %-equity EMA cross")
    print(f"Window {start} -> {end}, next-open fills, 10bp costs\n")

    header = (
        f"{'asset':<6}{'GARCH CAGR':>13}{'fixed CAGR':>13}"
        f"{'G dCAGR':>11}{'G MaxDD':>10}{'fx MaxDD':>10}"
        f"{'G Sharpe':>11}{'fx Sharpe':>11}{'G PF':>9}{'fx PF':>9}"
    )
    print(header)
    print("-" * len(header))

    wins = {"cagr": 0, "max_drawdown": 0, "sharpe": 0, "profit_factor": 0}
    n = 0
    for asset in ASSETS:
        try:
            g = _run(asset, "vol_target", start=start, end=end)
            f = _run(asset, "percent_of_equity", start=start, end=end)
        except Exception as e:  # network / data gaps
            print(f"  {asset:<6} skipped: {e}")
            continue
        gm, fm = compute_metrics(g), compute_metrics(f)
        gd, fd = gm.as_dict(), fm.as_dict()
        n += 1
        print(
            f"{asset:<6}{_pct(gd['cagr']):>13}{_pct(fd['cagr']):>13}"
            f"{(gd['cagr'] - fd['cagr']) * 100:>10.2f}%"
            f"{_pct(gd['max_drawdown']):>10}{_pct(fd['max_drawdown']):>10}"
            f"{gd['sharpe']:>11.3f}{fd['sharpe']:>11.3f}"
            f"{gd['profit_factor']:>9.2f}{fd['profit_factor']:>9.2f}"
        )
        if gd["cagr"] > fd["cagr"]:
            wins["cagr"] += 1
        # max_drawdown is stored as a positive magnitude; smaller = better.
        if gd["max_drawdown"] < fd["max_drawdown"]:
            wins["max_drawdown"] += 1
        if gd["sharpe"] > fd["sharpe"]:
            wins["sharpe"] += 1
        if gd["profit_factor"] > fd["profit_factor"]:
            wins["profit_factor"] += 1

    print()
    if n:
        print(f"Vol-targeting won {n} assets on:")
        print(f"  CAGR higher:        {wins['cagr']}/{n}")
        print(f"  Max DD smaller:     {wins['max_drawdown']}/{n}")
        print(f"  Sharpe higher:      {wins['sharpe']}/{n}")
        print(f"  Profit factor higher:{wins['profit_factor']}/{n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
