"""Bollinger %B mean-reversion strategy on SPY.

Enter when %B < 0.10 AND Close > 200 SMA, hold for 5 days.
"""

from __future__ import annotations

from backtest import load_daily
from backtest.engine import BacktestResult
from backtest.indicators import pct_b, sma

from ._common import DEFAULT_END, DEFAULT_SIZE_VALUE, DEFAULT_START, build_engine, hold_n_exit
from .registry import register


@register("pct_b_mr")
def pct_b_mr(
    ticker: str = "SPY",
    start: str = DEFAULT_START,
    end: str = DEFAULT_END,
    pct_b_threshold: float = 0.10,
    bb_period: int = 20,
    bb_std: float = 2.0,
    hold: int = 5,
    execution: str = "next_open",
    size_value: float = DEFAULT_SIZE_VALUE,
) -> BacktestResult:
    """%B < ``pct_b_threshold`` AND Close > 200 SMA; hold ``hold`` days."""
    ohlcv = load_daily(ticker, start, end)
    df = ohlcv.df
    sma200 = sma(df["Close"], 200)
    pb = pct_b(df, period=bb_period, num_std=bb_std)
    signal = (pb < pct_b_threshold) & (df["Close"] > sma200)
    signal = signal.fillna(False)
    eng = build_engine(ohlcv, name="pct_b_mr", execution=execution, size_value=size_value)
    eng.set_entry(signal).set_exit(hold_n_exit(hold))
    return eng.run()


__all__ = ["pct_b_mr"]
