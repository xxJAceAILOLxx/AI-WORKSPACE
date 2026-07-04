"""5-bar fade-breakdown mean-reversion on crypto (BTC/ETH).

Long-only approximation of the Intraday Alpha Atlas finding that CS-Rev
5-bar was the strongest crypto signal (Sharpe ~4.40 in the 5-min atlas,
Jan 2024 - Feb 2026). The original faded breakouts in both directions;
the current engine is long-only, so this strategy only fades the
*downside* — it buys when close breaks below the prior ``lookback``-bar
low, expecting a bounce. Exit after ``max_hold_bars`` or at end of UTC day.

Honest caveat: a proper short leg would roughly double the edge per the
Atlas findings, but requires engine-level shorting support.
"""

from __future__ import annotations

from typing import Tuple

import numpy as np
import pandas as pd

from backtest import load_intraday_binance
from backtest.engine import BacktestResult, EngineState

from ._common import DEFAULT_SIZE_VALUE, build_engine
from .registry import register


def _last_bar_of_day(index: pd.DatetimeIndex) -> pd.Series:
    """Boolean series: True at the last bar of each UTC day."""
    if len(index) <= 1:
        return pd.Series([True] * len(index), index=index)
    dates = np.array([d.date() for d in index])
    is_last = np.zeros(len(index), dtype=bool)
    is_last[:-1] = dates[:-1] != dates[1:]
    is_last[-1] = True
    return pd.Series(is_last, index=index)


def _fade_exit(max_hold_bars: int, eod: pd.Series):
    """Exit after ``max_hold_bars`` bars or at end of UTC day."""

    def rule(state: EngineState) -> None | Tuple[str, float]:
        if state.days_held >= max_hold_bars:
            return ("hold", 0.0)
        if bool(eod.iloc[state.idx]):
            return ("eod", 0.0)
        return None

    return rule


@register("fade_5bar_crypto")
def fade_5bar_crypto(
    symbol: str = "BTCUSDT",
    start: str = "2021-07-01",
    end: str = "2026-05-31",
    lookback: int = 5,
    max_hold_bars: int = 12,
    ema_filter_period: int = 0,
    execution: str = "next_open",
    size_value: float = DEFAULT_SIZE_VALUE,
) -> BacktestResult:
    """Buy when close breaks below the prior ``lookback``-bar low.

    Optional ``ema_filter_period`` > 0 restricts entries to bars where
    close is above its EMA (trend filter).
    """
    ohlcv = load_intraday_binance(symbol, "5m", start, end)
    df = ohlcv.df
    prior_low = df["Close"].rolling(lookback).min().shift(1)
    signal = df["Close"] < prior_low
    if ema_filter_period > 0:
        from backtest.indicators import ema

        ema_val = ema(df["Close"], ema_filter_period)
        signal = signal & (df["Close"] > ema_val)
    signal = signal.fillna(False)
    eod = _last_bar_of_day(df.index)
    eng = build_engine(
        ohlcv, name="fade_5bar_crypto", execution=execution, size_value=size_value
    )
    eng.set_entry(signal).set_exit(_fade_exit(max_hold_bars, eod))
    return eng.run()


__all__ = ["fade_5bar_crypto"]
