"""Turn-of-month strategy.

Buy on the last trading day of every month and hold for 4 trading days
(month-end + 3).  Implementation uses the framework's ``turn_of_month``
indicator for the entry signal and a 4-day hold exit rule.
"""

from __future__ import annotations

from backtest import load_daily
from backtest.engine import BacktestResult
from backtest.indicators import turn_of_month

from ._common import DEFAULT_END, DEFAULT_SIZE_VALUE, DEFAULT_START, build_engine, hold_n_exit
from .registry import register


@register("turn_of_month")
def turn_of_month_strategy(
    ticker: str = "SPY",
    start: str = DEFAULT_START,
    end: str = DEFAULT_END,
    hold: int = 4,
    execution: str = "next_open",
    size_value: float = DEFAULT_SIZE_VALUE,
) -> BacktestResult:
    """Buy on the last trading day of each month; hold ``hold`` days."""
    ohlcv = load_daily(ticker, start, end)
    # enter_last_n=1, hold_n=0 -> signal is True only on the last bar of
    # each calendar month.
    signal = turn_of_month(ohlcv.dates, enter_last_n=1, hold_n=0).fillna(False)
    eng = build_engine(ohlcv, name="turn_of_month", execution=execution, size_value=size_value)
    eng.set_entry(signal).set_exit(hold_n_exit(hold))
    return eng.run()


__all__ = ["turn_of_month_strategy"]
