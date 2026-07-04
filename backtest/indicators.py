"""Technical indicators used by strategies in the framework.

All functions are pure: they accept a :class:`pandas.DataFrame` or
:class:`pandas.Series` and return a :class:`pandas.Series` aligned to the
input index.  No global state, no look-ahead leakage beyond what the
formula dictates (each result at index ``i`` only uses data through ``i``).
"""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


def ibs(df: pd.DataFrame) -> pd.Series:
    """Internal Bar Strength = (Close - Low) / (High - Low).

    Values near 0 mean the close is near the bar's low (oversold); values
    near 1 mean the close is near the high (overbought).  Returns NaN
    when ``High == Low``.
    """
    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    close = df["Close"].astype(float)
    rng = high - low
    out = (close - low) / rng.replace(0, np.nan)
    return out


def rsi(series: pd.Series, period: int = 2) -> pd.Series:
    """Wilder-style RSI on ``series``.

    ``period`` is the look-back for average gains/losses.  Default 2 is
    the common short-term mean-reversion RSI.
    """
    s = series.astype(float)
    delta = s.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    # Wilder smoothing == EMA with alpha = 1 / period
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100.0 - (100.0 / (1.0 + rs))
    return out


def sma(series: pd.Series, period: int) -> pd.Series:
    """Simple moving average with a minimum-periods warm-up."""
    return series.astype(float).rolling(window=period, min_periods=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential moving average (Wilder-style smoothing)."""
    return series.astype(float).ewm(span=period, adjust=False, min_periods=period).mean()


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range using Wilder smoothing."""
    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    close = df["Close"].astype(float)
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


def bollinger(series: pd.Series, period: int = 20, num_std: float = 2.0):
    """Return ``(middle, upper, lower, pct_b)`` Bollinger Bands.

    ``pct_b`` is (Close - lower) / (upper - lower); ``>1`` means above the
    upper band, ``<0`` means below the lower band.
    """
    s = series.astype(float)
    middle = sma(s, period)
    std = s.rolling(window=period, min_periods=period).std(ddof=0)
    upper = middle + num_std * std
    lower = middle - num_std * std
    width = (upper - lower).replace(0, np.nan)
    pct_b = (s - lower) / width
    return middle, upper, lower, pct_b


def pct_b(df: pd.DataFrame, period: int = 20, num_std: float = 2.0) -> pd.Series:
    """``%B`` of the close relative to Bollinger Bands."""
    _, _, _, pb = bollinger(df["Close"], period=period, num_std=num_std)
    return pb


def down_streak(series: pd.Series) -> pd.Series:
    """Running count of consecutive down closes (negative = streak length).

    Reset to 0 on any non-negative change.  ``series`` should be a price
    series; the streak is computed from day-over-day differences.
    """
    s = series.astype(float)
    change = s.diff()
    is_down = (change < 0).astype(int)
    # Group consecutive down days: cumulative sum that resets on up days.
    # Trick: use a running group id that increments only when is_down goes 0->1.
    up = (change >= 0).astype(int)
    group = up.cumsum()
    streak = is_down.groupby(group).cumsum()
    # The bar on which the down move completes is part of the streak; the
    # first down bar (diff < 0) is day 1 of the streak.
    streak = streak.where(is_down == 1, 0).astype(float)
    return streak


def volume_ratio(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Today's volume divided by the simple average of the last ``period`` days.

    Values > 1 indicate above-average volume; values < 1 indicate quiet
    sessions.
    """
    vol = df["Volume"].astype(float)
    avg = sma(vol, period)
    return vol / avg.replace(0, np.nan)


def turn_of_month(
    index: pd.DatetimeIndex,
    enter_last_n: int = 1,
    hold_n: int = 3,
) -> pd.Series:
    """Boolean series that is True during the turn-of-month window.

    The signal is True on the last ``enter_last_n`` trading days of every
    month and the ``hold_n`` trading days that follow, giving a total
    window of ``enter_last_n + hold_n`` bars per month.  ``hold_n`` is the
    *additional* hold period after month-end, so the default of
    ``enter_last_n=1, hold_n=3`` yields a 4-bar window.
    """
    if not isinstance(index, pd.DatetimeIndex):
        raise TypeError("index must be a pandas.DatetimeIndex")
    if enter_last_n < 1 or hold_n < 0:
        raise ValueError("enter_last_n must be >= 1 and hold_n must be >= 0")

    out = pd.Series(False, index=index, dtype=bool)
    if len(index) == 0:
        return out

    # For each month boundary, find the last `enter_last_n` trading days
    # of that month and set the following `hold_n` days True as well.
    months = pd.Series(index.month, index=index)
    month_change = months.ne(months.shift(-1)).values  # True on last bar of month

    # Determine the position of the last `enter_last_n` bars of each month.
    last_n_positions: list[int] = []
    n = len(index)
    for i in range(n):
        if month_change[i]:
            start = max(0, i - enter_last_n + 1)
            last_n_positions.extend(range(start, i + 1))
    out.iloc[last_n_positions] = True

    # Propagate True forward by `hold_n` bars.
    if hold_n > 0:
        out = _propagate_true(out, hold_n)

    return out


def _propagate_true(mask: pd.Series, n: int) -> pd.Series:
    """Extend each True run in ``mask`` by ``n`` additional bars."""
    arr = mask.values.astype(bool).copy()
    n_bars = len(arr)
    new = arr.copy()
    # For each True at i, set True at i+1, i+2, ..., i+n if in bounds.
    # Iterate from right to left so offsets don't get overwritten incorrectly.
    for i in range(n_bars - 1, -1, -1):
        if arr[i]:
            for k in range(1, n + 1):
                j = i + k
                if j < n_bars:
                    new[j] = True
                else:
                    break
    return pd.Series(new, index=mask.index)


def realized_vol(close: pd.Series, period: int = 10) -> pd.Series:
    """Annualized realized volatility from log returns.

    Useful for the VIX ETN strategy: ``sigma * sqrt(252)`` from the rolling
    standard deviation of ``log(close).diff()``.
    """
    log_ret = np.log(close.astype(float) / close.astype(float).shift(1))
    return log_ret.rolling(window=period, min_periods=period).std(ddof=0) * np.sqrt(252)
