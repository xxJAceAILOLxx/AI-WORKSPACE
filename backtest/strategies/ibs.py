"""IBS-based mean-reversion strategies.

Implements three strategies from the unified framework plan:

* ``ibs_spy``  - plain IBS < 0.20 on SPY.
* ``ibs_trend`` - IBS < 0.20 + Close > 200 SMA + turn-of-month on SPY.
* ``qqq_mr``   - IBS < 0.20 + Close > 200 SMA on QQQ.
"""

from __future__ import annotations

from backtest import load_daily
from backtest.engine import BacktestResult
from backtest.indicators import ibs, sma, turn_of_month

from ._common import DEFAULT_END, DEFAULT_SIZE_VALUE, DEFAULT_START, build_engine, hold_n_exit
from .registry import register


@register("ibs_spy")
def ibs_spy(
    ticker: str = "SPY",
    start: str = DEFAULT_START,
    end: str = DEFAULT_END,
    threshold: float = 0.20,
    hold: int = 5,
    execution: str = "next_open",
    size_value: float = DEFAULT_SIZE_VALUE,
) -> BacktestResult:
    """Buy ``ticker`` when IBS < ``threshold``; hold for ``hold`` days."""
    ohlcv = load_daily(ticker, start, end)
    signal = (ibs(ohlcv.df) < threshold).fillna(False)
    eng = build_engine(ohlcv, name="ibs_spy", execution=execution, size_value=size_value)
    eng.set_entry(signal).set_exit(hold_n_exit(hold))
    return eng.run()


@register("ibs_trend")
def ibs_trend(
    ticker: str = "SPY",
    start: str = DEFAULT_START,
    end: str = DEFAULT_END,
    threshold: float = 0.20,
    hold: int = 5,
    execution: str = "next_open",
    size_value: float = DEFAULT_SIZE_VALUE,
) -> BacktestResult:
    """IBS < ``threshold`` AND Close > 200 SMA AND last trading day of month."""
    ohlcv = load_daily(ticker, start, end)
    df = ohlcv.df
    sma200 = sma(df["Close"], 200)
    tom = turn_of_month(ohlcv.dates, enter_last_n=1, hold_n=0)
    signal = (ibs(df) < threshold) & (df["Close"] > sma200) & tom
    signal = signal.fillna(False)
    eng = build_engine(ohlcv, name="ibs_trend", execution=execution, size_value=size_value)
    eng.set_entry(signal).set_exit(hold_n_exit(hold))
    return eng.run()


@register("qqq_mr")
def qqq_mr(
    ticker: str = "QQQ",
    start: str = DEFAULT_START,
    end: str = DEFAULT_END,
    threshold: float = 0.20,
    hold: int = 5,
    execution: str = "next_open",
    size_value: float = DEFAULT_SIZE_VALUE,
) -> BacktestResult:
    """IBS < ``threshold`` AND Close > 200 SMA on QQQ."""
    ohlcv = load_daily(ticker, start, end)
    df = ohlcv.df
    sma200 = sma(df["Close"], 200)
    signal = (ibs(df) < threshold) & (df["Close"] > sma200)
    signal = signal.fillna(False)
    eng = build_engine(ohlcv, name="qqq_mr", execution=execution, size_value=size_value)
    eng.set_entry(signal).set_exit(hold_n_exit(hold))
    return eng.run()


__all__ = ["ibs_spy", "ibs_trend", "qqq_mr"]
