"""15-minute Opening Range Breakout on crypto (BTC/ETH).

Long-only. Computes the opening range from the first ``or_bars`` bars of
each UTC day (default 3 bars * 5m = 15 minutes). Buys when close breaks
above the OR high, filtered by a daily EMA (default 288 * 5m = 24h).
Exits at end of UTC day.

Based on the Stoic Research ORB study that found Sharpe ~1.0 on
BTC/ETH/SOL with a 15-minute opening range and EMA(21) filter.
"""

from __future__ import annotations

from typing import Tuple

import numpy as np
import pandas as pd

from backtest import load_intraday_binance
from backtest.engine import BacktestResult, EngineState
from backtest.indicators import ema

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


def _orb_exit(eod: pd.Series):
    """Exit at end of UTC day."""

    def rule(state: EngineState) -> None | Tuple[str, float]:
        if bool(eod.iloc[state.idx]):
            return ("eod", 0.0)
        return None

    return rule


@register("orb_15m_crypto")
def orb_15m_crypto(
    symbol: str = "BTCUSDT",
    start: str = "2021-07-01",
    end: str = "2026-05-31",
    or_bars: int = 3,
    ema_period: int = 288,
    execution: str = "next_open",
    size_value: float = DEFAULT_SIZE_VALUE,
) -> BacktestResult:
    """Buy breakout above the first ``or_bars`` bars' high, if close > EMA."""
    ohlcv = load_intraday_binance(symbol, "5m", start, end)
    df = ohlcv.df
    dates = df.index.date

    # OR high per day: max of the first ``or_bars`` High values per UTC day.
    # ``transform`` broadcasts the scalar back to every bar in the group.
    or_high_per_date = df.groupby(dates)["High"].transform(
        lambda x: x.head(or_bars).max()
    )
    # Bar position within each UTC day (0, 1, 2, ...).
    bar_pos_in_day = df.groupby(dates).cumcount()

    ema_val = ema(df["Close"], ema_period)
    signal = (
        (df["Close"] > or_high_per_date)
        & (bar_pos_in_day >= or_bars)
        & (df["Close"] > ema_val)
    )
    signal = signal.fillna(False)

    eod = _last_bar_of_day(df.index)
    eng = build_engine(
        ohlcv, name="orb_15m_crypto", execution=execution, size_value=size_value
    )
    eng.set_entry(signal).set_exit(_orb_exit(eod))
    return eng.run()


__all__ = ["orb_15m_crypto"]
