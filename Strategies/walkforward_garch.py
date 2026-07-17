"""Walk-forward / out-of-sample validation of GARCH vol-targeting vs fixed.

Reuses the GARCH EMA-cross machinery but evaluates it on rolling windows so
the "vol-targeting lowers drawdown but never beats Sharpe/CAGR" result can be
checked for stability instead of being a single-period fluke.

For each asset the data is downloaded once, then sliced into overlapping
``WINDOW``-year windows stepped by ``STEP`` year.  On every window we run both
the GARCH-sized and the fixed-size variant and tally how often the GARCH book
wins each metric.
"""

from __future__ import annotations

import contextlib
import io
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pandas as pd
from backtest import OHLCV
from backtest.metrics import compute_metrics
from backtest.strategies.garch import ASSETS, _build, _load, garch_vol

WINDOW_YEARS = 3
STEP_YEARS = 1
WINDOW = pd.DateOffset(years=WINDOW_YEARS)
STEP = pd.DateOffset(years=STEP_YEARS)
MIN_BARS = 250  # need a year-plus of bars for meaningful metrics


def _quiet_load(asset: str, start: str, end: str) -> OHLCV:
    """Load data but swallow the loader's noisy pre-listing skip prints."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        return _load(asset, start, end)


def _windows(index: pd.DatetimeIndex):
    first, last = index.min(), index.max()
    ws = first
    while ws + WINDOW <= last:
        yield ws, ws + WINDOW
        ws = ws + STEP


def _run_window(asset: str, sub: pd.DataFrame, policy: str):
    ohlcv = OHLCV(ticker=asset, df=sub)
    annualize = int(ASSETS[asset]["annualize"])
    vol = garch_vol(sub["Close"], annualize=annualize)
    name = f"garch_{asset}" if policy == "vol_target" else f"fixed_{asset}"
    eng = _build(ohlcv, name, policy,
                 vol_series=vol if policy == "vol_target" else None)
    return compute_metrics(eng.run()).as_dict()


def main() -> int:
    start, end = "2016-01-01", "2025-12-31"
    print(f"Walk-forward: GARCH vol-target vs fixed EMA cross, "
          f"{WINDOW_YEARS}y windows stepped {STEP_YEARS}y")
    print(f"Window {start} -> {end}, next-open, 10bp\n")

    wins = {"cagr": 0, "max_drawdown": 0, "sharpe": 0, "profit_factor": 0}
    total = 0
    per_asset = {}

    for asset in ASSETS:
        full = _quiet_load(asset, start, end)
        df = full.df
        n_win = 0
        aw = {"cagr": 0, "max_drawdown": 0, "sharpe": 0, "profit_factor": 0}
        for ws, we in _windows(df.index):
            sub = df.loc[ws:we]
            if len(sub) < MIN_BARS:
                continue
            g = _run_window(asset, sub, "vol_target")
            f = _run_window(asset, sub, "percent_of_equity")
            n_win += 1
            total += 1
            if g["cagr"] > f["cagr"]:
                wins["cagr"] += 1; aw["cagr"] += 1
            if g["max_drawdown"] < f["max_drawdown"]:
                wins["max_drawdown"] += 1; aw["max_drawdown"] += 1
            if g["sharpe"] > f["sharpe"]:
                wins["sharpe"] += 1; aw["sharpe"] += 1
            if g["profit_factor"] > f["profit_factor"]:
                wins["profit_factor"] += 1; aw["profit_factor"] += 1
        per_asset[asset] = (n_win, aw)
        print(f"{asset:<5} {n_win:>2} windows  "
              f"CAGR {aw['cagr']}/{n_win}  "
              f"MaxDD {aw['max_drawdown']}/{n_win}  "
              f"Sharpe {aw['sharpe']}/{n_win}  "
              f"PF {aw['profit_factor']}/{n_win}")

    print()
    if total:
        print(f"Across {total} asset-windows, GARCH vol-targeting won:")
        print(f"  CAGR higher:         {wins['cagr']}/{total}")
        print(f"  Max DD smaller:      {wins['max_drawdown']}/{total}")
        print(f"  Sharpe higher:       {wins['sharpe']}/{total}")
        print(f"  Profit factor higher:{wins['profit_factor']}/{total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
