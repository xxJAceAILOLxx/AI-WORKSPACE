"""Funded Reversion portfolio -- the prop-firm deployment of LVPR.

Runs the low-volume pullback reversion edge (:func:`lvpr`) across a basket
of uncorrelated ETFs, each on its own capital slice with
``percent_of_equity`` sizing (no cross-instrument leverage).  Per-instrument
equity curves are summed over a common trading-day calendar, so the result
is a genuine multi-instrument portfolio rather than an average of copies of
the same instrument.

Why a basket (per the vault's "Funded 80% Pass Study"):
  - A single instrument produces too few trades to climb +10% inside a
    typical 30-day evaluation while staying inside a 10% max-DD / 5% daily
    loss envelope.
  - Spreading the same edge across several loosely-correlated ETFs raises
    trade frequency (smoother equity) and diversifies regime risk.

Entry / exit per instrument: see :mod:`backtest.strategies.lvpr`.
Sizing: ``percent_of_equity`` with ``alloc`` per slice (default 0.95) so
each open trade risks only ``alloc * slice * stop_distance`` of total
capital -- keeps any single-day gap well under the 5% daily-loss limit.
"""

from __future__ import annotations

from typing import List, Tuple

import pandas as pd

from backtest import OHLCV, PERCENT_10BP, load_daily
from backtest.engine import BacktestResult, Trade
from backtest.indicators import sma

from .lvpr import (
    DEFAULT_HOLD,
    DEFAULT_IBS_MAX,
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_MA_PERIOD,
    DEFAULT_STOP_MULT,
    DEFAULT_VOL_MAX,
    lvpr,
)
from .registry import register


DEFAULT_BASKET: Tuple[str, ...] = ("SPY", "QQQ", "IWM", "GLD", "DIA", "MDY", "SLV")
DEFAULT_START: str = "2016-01-01"
DEFAULT_END: str = "2025-12-31"
DEFAULT_ALLOC: float = 0.95


def _tag_trades(trades: List[Trade], ticker: str) -> List[Trade]:
    for t in trades:
        setattr(t, "instrument", ticker)
    return trades


@register("funded_reversion")
def funded_reversion(
    basket: Tuple[str, ...] = DEFAULT_BASKET,
    start: str = DEFAULT_START,
    end: str = DEFAULT_END,
    ma_period: int = DEFAULT_MA_PERIOD,
    ibs_max: float = DEFAULT_IBS_MAX,
    vol_max: float = DEFAULT_VOL_MAX,
    hold: int = DEFAULT_HOLD,
    stop_mult: float = DEFAULT_STOP_MULT,
    alloc: float = DEFAULT_ALLOC,
    execution: str = "next_open",
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
) -> BacktestResult:
    """Multi-instrument Low-Volume Pullback Reversion portfolio.

    Each instrument in ``basket`` receives ``initial_capital / len(basket)``
    and trades LVPR with ``percent_of_equity`` sizing at fraction ``alloc``.
    """
    n = len(basket)
    slice_capital = initial_capital / float(n)

    per_instrument: List[Tuple[str, pd.DatetimeIndex, List[float]]] = []
    all_trades: List[Trade] = []
    missing: List[str] = []

    for ticker in basket:
        try:
            res = lvpr(
                ticker=ticker,
                start=start,
                end=end,
                ma_period=ma_period,
                ibs_max=ibs_max,
                vol_max=vol_max,
                hold=hold,
                stop_mult=stop_mult,
                size_policy="percent_of_equity",
                size_value=alloc,
                execution=execution,
                initial_capital=slice_capital,
            )
        except Exception as exc:  # noqa: BLE001 - defensive
            missing.append(f"{ticker}: {exc}")
            continue
        idx = res.ohlcv.df.index
        per_instrument.append((ticker, idx, res.equity))
        all_trades.extend(_tag_trades(list(res.trades), ticker))

    if not per_instrument:
        empty_ohlcv = OHLCV(
            ticker=",".join(basket),
            df=pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"]).set_index(
                pd.DatetimeIndex([])
            ),
        )
        return BacktestResult(
            name="funded_reversion",
            trades=[],
            equity=[],
            ohlcv=empty_ohlcv,
            initial_capital=initial_capital,
            execution=execution,
            cost_model_name=PERCENT_10BP.name,
            config={"basket": list(basket), "missing": missing, "note": "no instruments produced results"},
        )

    # Combine equity over a common calendar: reindex each curve to the union
    # of dates and forward-fill (carry last equity when an instrument has no
    # bar), then sum.
    common = per_instrument[0][1]
    for _, idx, _ in per_instrument[1:]:
        common = common.union(idx)
    common = common.sort_values()

    combined: List[float] = []
    for i, _ in enumerate(common):
        total = 0.0
        for _, idx, eq in per_instrument:
            s = pd.Series(eq, index=idx)
            # Value at bar i (or last known value before it).
            prior = s[s.index <= common[i]]
            val = float(prior.iloc[-1]) if len(prior) else slice_capital
            total += val
        combined.append(total)

    all_trades.sort(key=lambda t: t.entry_date)

    return BacktestResult(
        name="funded_reversion",
        trades=all_trades,
        equity=combined,
        ohlcv=OHLCV(ticker=",".join(basket), df=pd.DataFrame(index=common)),
        initial_capital=initial_capital,
        execution=execution,
        cost_model_name=PERCENT_10BP.name,
        config={
            "basket": list(basket),
            "slice_capital": slice_capital,
            "alloc": alloc,
            "missing": missing,
            "size_policy": "percent_of_equity",
            "n_instruments": n,
        },
    )


__all__ = ["funded_reversion", "DEFAULT_BASKET", "DEFAULT_START", "DEFAULT_END", "DEFAULT_ALLOC"]
