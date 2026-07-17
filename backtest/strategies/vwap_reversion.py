"""Two-sided VWAP mean-reversion on 5m bars (crypto, and equity via HF).

This is the strategy the long-only intraday edges in the vault were missing:
it trades *both* sides of the VWAP, because the prior verdict was that
long-only crypto 5m mean reversion is dominated by trend + fees and is ~random
(WR ~= 50%, PF < 1). Fading a volume-confirmed stretch *above* VWAP (short)
as well as below (long) is what the original Alpha Atlas CS-Rev edge did, and
it requires engine-level shorting, which the framework now supports.

Signal
------
* ``dev = (Close - session_VWAP) / session_VWAP``
* Volume confirmation: ``vol_ratio = Volume / SMA(vol_period)``.  Entries are
  only taken when volume is at/above ``vol_min`` of its rolling average, so the
  stretch is a real move, not noise.
* Long:  ``dev < -entry_dev`` AND ``vol_ratio >= vol_min``
* Short: ``dev > +entry_dev`` AND ``vol_ratio >= vol_min``

Exits
-----
* Reversion: long exits when ``Close >= VWAP``; short exits when ``Close <= VWAP``.
* Hard stop: optional ATR multiple (``stop_mult``; 0 disables).
* Max hold in bars (``max_hold_bars``).
* Optional end-of-session (UTC day) flatten (``eod_exit``).

Data sources
------------
* ``source="binance"`` (default): Binance public 5m klines (BTCUSDT/ETHUSDT),
  already cached in the vault.
* ``source="hf"``: HF Data Library 1m bars resampled to 5m (equity tickers
  like ``SPY``/``QQQ``).  Requires ``HF_DATA_API_KEY`` (register free at
  hfdatalibrary.com).
"""

from __future__ import annotations

from typing import Tuple

import numpy as np
import pandas as pd

from backtest import PERCENT_10BP, load_intraday_binance, load_intraday_hf
from backtest.engine import BacktestResult, Engine, EngineState
from backtest.indicators import volume_ratio, vwap

from ._common import DEFAULT_SIZE_VALUE
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


def _resample_1m_to_5m(df: pd.DataFrame) -> pd.DataFrame:
    """Resample a 1m OHLCV frame to 5m bars (last-close, session-agnostic)."""
    agg = {
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum",
    }
    out = df.resample("5min").agg(agg).dropna(subset=["Open", "High", "Low", "Close"])
    return out[["Open", "High", "Low", "Close", "Volume"]]


def _vwap_exit(vwap_series: pd.Series, max_hold_bars: int, eod: pd.Series, eod_exit: bool):
    """Close on reversion to VWAP, max hold, or end of session."""

    def rule(state: EngineState) -> None | Tuple[str, float]:
        v = float(vwap_series.iloc[state.idx])
        price = float(state.bar["Close"])
        if state.shares > 0:  # long: exit when price reclaims VWAP
            reverted = price >= v
        else:  # short: exit when price falls back to VWAP
            reverted = price <= v
        if reverted:
            return ("revert", 0.0)
        if state.days_held >= max_hold_bars:
            return ("hold", 0.0)
        if eod_exit and bool(eod.iloc[state.idx]):
            return ("eod", 0.0)
        return None

    return rule


@register("vwap_reversion")
def vwap_reversion(
    symbol: str = "BTCUSDT",
    start: str = "2021-07-01",
    end: str = "2026-05-31",
    source: str = "binance",
    entry_dev: float = 0.005,
    vol_min: float = 1.0,
    vol_period: int = 20,
    max_hold_bars: int = 48,
    stop_mult: float = 0.0,
    eod_exit: bool = True,
    execution: str = "next_open",
    size_value: float = DEFAULT_SIZE_VALUE,
    ohlcv=None,
    mode: str = "reversion",
) -> BacktestResult:
    """Two-sided VWAP deviation strategy on 5m bars.

    ``mode="reversion"`` fades a volume-confirmed stretch away from VWAP
    (long when far below, short when far above).  ``mode="momentum"`` trades
    *with* the stretch (long when far above, short when far below) — suited to
    trending markets like crypto.

    ``entry_dev`` is the fractional VWAP distance that triggers an entry
    (e.g. 0.005 = 0.5%).  ``vol_min`` filters entries by relative volume.
    ``stop_mult`` > 0 adds an ATR stop; 0 disables it.  Pass a preloaded
    ``ohlcv`` to skip data loading (used by the optimizer).
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

    vwap_series = vwap(df, daily_reset=True)
    dev = (df["Close"] - vwap_series) / vwap_series.replace(0, np.nan)
    vr = volume_ratio(df, period=vol_period)

    if mode == "reversion":
        long_sig = (dev < -entry_dev) & (vr >= vol_min)
        short_sig = (dev > entry_dev) & (vr >= vol_min)
    elif mode == "momentum":
        long_sig = (dev > entry_dev) & (vr >= vol_min)
        short_sig = (dev < -entry_dev) & (vr >= vol_min)
    else:
        raise ValueError(f"unknown mode {mode!r}; expected 'reversion' or 'momentum'")

    # Signed entry signal: +1 long, -1 short, 0 flat.
    signal = pd.Series(0, index=df.index, dtype=int)
    signal[long_sig] = 1
    signal[short_sig] = -1

    eod = _last_bar_of_day(df.index)
    eng = Engine(
        ohlcv,
        name="vwap_reversion",
        execution=execution,
        cost_model=PERCENT_10BP,
        initial_capital=100_000.0,
        size_policy="percent_of_equity",
        size_value=size_value,
        stop_mult=stop_mult,
        atr_period=14,
    )
    eng.set_entry(signal).set_exit(_vwap_exit(vwap_series, max_hold_bars, eod, eod_exit))
    return eng.run()


__all__ = ["vwap_reversion"]
