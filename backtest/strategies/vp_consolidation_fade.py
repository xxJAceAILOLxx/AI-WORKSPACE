"""Volume-profile consolidation fade on 5m bars (two-sided).

Thesis (Auction Market Theory / rotation fade)
-----------------------------------------------
When the prior session's volume profile is *balanced* — a "D-shaped"
consolidation where the POC sits near the middle of the range and the day
closed inside its own value area — the market has accepted value and is more
likely to *rotate* than to trend.  So the next session we fade the edges of
that accepted value:

* price tags prior-day **VAH**  -> short (fade the top of value)
* price tags prior-day **VAL**  -> long  (fade the bottom of value)

Exits
-----
* Reversion to the prior-day **POC** (the centre of accepted value).
* Optional ATR stop (``stop_mult``; 0 disables).
* Hard max hold (bars) and optional end-of-session (UTC day) flatten.

This is inherently two-sided, so it requires the engine's short support.

Data sources
------------
* ``source="binance"`` (default): Binance 5m klines (BTCUSDT/ETHUSDT), cached.
* ``source="hf"``: HF Data Library 1m bars resampled to 5m (equity tickers).
  Requires ``HF_DATA_API_KEY``.
"""

from __future__ import annotations

from typing import Tuple

import numpy as np
import pandas as pd

from backtest import PERCENT_10BP, load_intraday_binance, load_intraday_hf
from backtest.engine import BacktestResult, Engine, EngineState
from backtest.indicators import value_area_by_day

from ._common import DEFAULT_SIZE_VALUE
from .registry import register


def _last_bar_of_day(index: pd.DatetimeIndex) -> pd.Series:
    if len(index) <= 1:
        return pd.Series([True] * len(index), index=index)
    dates = np.array([d.date() for d in index])
    is_last = np.zeros(len(index), dtype=bool)
    is_last[:-1] = dates[:-1] != dates[1:]
    is_last[-1] = True
    return pd.Series(is_last, index=index)


def _resample_1m_to_5m(df: pd.DataFrame) -> pd.DataFrame:
    agg = {
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum",
    }
    out = df.resample("5min").agg(agg).dropna(subset=["Open", "High", "Low", "Close"])
    return out[["Open", "High", "Low", "Close", "Volume"]]


def _vp_exit(poc_prev: pd.Series, max_hold_bars: int, eod: pd.Series, eod_exit: bool):
    """Exit on reversion to the prior-day POC (value centre), max hold, or EOD."""

    def rule(state: EngineState) -> None | Tuple[str, float]:
        poc = float(poc_prev.iloc[state.idx])
        price = float(state.bar["Close"])
        if state.shares > 0:  # long (entered at VAL): exit when price returns up to POC
            reverted = price >= poc
        else:  # short (entered at VAH): exit when price returns down to POC
            reverted = price <= poc
        if reverted:
            return ("revert", 0.0)
        if state.days_held >= max_hold_bars:
            return ("hold", 0.0)
        if eod_exit and bool(eod.iloc[state.idx]):
            return ("eod", 0.0)
        return None

    return rule


@register("vp_consolidation_fade")
def vp_consolidation_fade(
    symbol: str = "BTCUSDT",
    start: str = "2021-07-01",
    end: str = "2026-05-31",
    source: str = "binance",
    va_pct: float = 0.70,
    n_bins: int = 24,
    max_hold_bars: int = 96,
    stop_mult: float = 0.0,
    eod_exit: bool = True,
    execution: str = "next_open",
    size_value: float = DEFAULT_SIZE_VALUE,
    ohlcv=None,
) -> BacktestResult:
    """Fade prior-day value-area edges after a balanced/"D-shaped" session.

    Entries fire on a *cross* of the prior-day VAH (short) or VAL (long),
    but only when that prior day was a consolidation (see
    :func:`backtest.indicators.value_area_by_day`).  Exits revert to the
    prior-day POC.
    """
    if ohlcv is None:
        if source == "binance":
            ohlcv = load_intraday_binance(symbol, "5m", start, end)
        elif source == "hf":
            raw = load_intraday_hf(symbol, start, end)
            df = _resample_1m_to_5m(raw.df)
            ohlcv = type(raw)(ticker=symbol, df=df)
        else:
            raise ValueError(f"unknown source {source!r}; expected 'binance' or 'hf'")

    df = ohlcv.df

    daily = value_area_by_day(df, n_bins=n_bins, va_pct=va_pct)

    # Prior day's profile, aligned to every bar by its calendar date.
    prev = daily.shift(1)
    bar_day = df.index.normalize()
    vah_prev = pd.Series(prev["vah"].reindex(bar_day).to_numpy(), index=df.index)
    val_prev = pd.Series(prev["val"].reindex(bar_day).to_numpy(), index=df.index)
    poc_prev = pd.Series(prev["poc"].reindex(bar_day).to_numpy(), index=df.index)
    consol_prev = pd.Series(
        prev["is_consolidation"].reindex(bar_day).fillna(False).to_numpy(), index=df.index
    )

    close = df["Close"].astype(float)
    prev_close = close.shift(1)

    # Crosses of the prior-day value-area edges.
    long_cross = (prev_close > val_prev) & (close <= val_prev)
    short_cross = (prev_close < vah_prev) & (close >= vah_prev)

    long_sig = long_cross & consol_prev
    short_sig = short_cross & consol_prev

    signal = pd.Series(0, index=df.index, dtype=int)
    signal[long_sig] = 1
    signal[short_sig] = -1

    eod = _last_bar_of_day(df.index)
    eng = Engine(
        ohlcv,
        name="vp_consolidation_fade",
        execution=execution,
        cost_model=PERCENT_10BP,
        initial_capital=100_000.0,
        size_policy="percent_of_equity",
        size_value=size_value,
        stop_mult=stop_mult,
        atr_period=14,
    )
    eng.set_entry(signal).set_exit(_vp_exit(poc_prev, max_hold_bars, eod, eod_exit))
    return eng.run()


__all__ = ["vp_consolidation_fade"]
