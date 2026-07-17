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


def garch_vol(
    close: pd.Series,
    alpha: float = 0.15,
    beta: float = 0.85,
    annualize: int = 365,
    min_periods: int = 30,
) -> pd.Series:
    """Annualized GARCH(1,1) volatility forecast (IGARCH when alpha+beta=1).

    Uses the integrated form favoured by the "Nobel Prize method" framing::

        sigma_t^2 = alpha * r_{t-1}^2 + beta * sigma_{t-1}^2

    with ``alpha`` the shock weight and ``beta`` the memory weight.  The
    video fits these to Bitcoin as 0.15 / 0.85 (sum = 1.0), which
    reduces to a RiskMetrics EWMA with ``lambda = beta``.  The forecast
    at bar ``t`` is the variance expected for bar ``t+1`` (no look-ahead:
    it only uses returns through ``t-1``), annualized by ``sqrt(annualize)``.

    Returns NaN until ``min_periods`` of returns are available so the
    warm-up does not leak future information.
    """
    if not (0.0 <= alpha <= 1.0 and 0.0 <= beta <= 1.0):
        raise ValueError("garch_vol requires 0 <= alpha, beta <= 1")
    s = close.astype(float)
    log_ret = np.log(s / s.shift(1))
    sq = (log_ret ** 2).fillna(0.0).to_numpy()

    n = len(sq)
    var = np.zeros(n, dtype=float)
    # Seed with the sample variance of the first `min_periods` returns.
    seed = float(np.mean(sq[:max(min_periods, 1)])) if n else 0.0
    var[0] = seed
    for i in range(1, n):
        var[i] = alpha * sq[i - 1] + beta * var[i - 1]
    # Replace any non-finite seed/early values with the long-run EWMA.
    var = np.where(np.isfinite(var), var, seed)

    daily = np.sqrt(np.clip(var, 0.0, None))
    ann = daily * np.sqrt(float(annualize))
    out = pd.Series(ann, index=close.index, dtype=float)
    out.iloc[:min_periods] = np.nan
    return out


def realized_vol(close: pd.Series, period: int = 10) -> pd.Series:
    """Annualized realized volatility from log returns.

    Useful for the VIX ETN strategy: ``sigma * sqrt(252)`` from the rolling
    standard deviation of ``log(close).diff()``.
    """
    log_ret = np.log(close.astype(float) / close.astype(float).shift(1))
    return log_ret.rolling(window=period, min_periods=period).std(ddof=0) * np.sqrt(252)


def vwap(df: pd.DataFrame, daily_reset: bool = True) -> pd.Series:
    """Volume-Weighted Average Price.

    Uses the typical price ``(High + Low + Close) / 3`` as the price weight.
    By default the cumulative VWAP resets at the start of each calendar day
    (``daily_reset=True``), which is the meaningful session VWAP for
    intraday strategies on 24/7 markets.  Pass ``daily_reset=False`` for a
    single cumulative VWAP across the whole series.
    """
    typical = (df["High"] + df["Low"] + df["Close"]).astype(float) / 3.0
    pv = typical * df["Volume"].astype(float)
    if daily_reset:
        grp = df.index.normalize()
        cum_pv = pv.groupby(grp).cumsum()
        cum_v = df["Volume"].astype(float).groupby(grp).cumsum()
    else:
        cum_pv = pv.cumsum()
        cum_v = df["Volume"].astype(float).cumsum()
    return cum_pv / cum_v.replace(0, np.nan)


def session_vwap(df: pd.DataFrame) -> pd.Series:
    """Alias for :func:`vwap` with a daily (session) reset — the common case."""
    return vwap(df, daily_reset=True)


def vwap_deviation(df: pd.DataFrame, daily_reset: bool = True) -> pd.Series:
    """Percent deviation of Close from VWAP: ``(Close - VWAP) / VWAP``.

    Positive values mean price is above the session VWAP (overbought-ish);
    negative values mean below (oversold-ish).  Useful directly as a
    mean-reversion signal.
    """
    v = vwap(df, daily_reset=daily_reset)
    return (df["Close"].astype(float) - v) / v.replace(0, np.nan)


def value_area_by_day(
    df: pd.DataFrame,
    n_bins: int = 24,
    va_pct: float = 0.70,
) -> pd.DataFrame:
    """Per-day volume profile: POC, Value-Area High/Low, and shape flags.

    For each calendar day the bars are binned by price and the volume per bin
    is summed.  The Point of Control (``poc``) is the highest-volume bin; the
    Value Area (``vah``/``val``) is expanded from the POC until cumulative
    volume reaches ``va_pct`` of the day's total.

    Returns a DataFrame indexed by the day's first timestamp with columns:
    ``poc``, ``vah``, ``val``, ``poc_pos`` (POC position in the day's range,
    0=low, 1=high), ``close`` and ``close_in_va`` (whether the day closed
    inside its own value area), and ``is_consolidation`` (a balanced/"D-shaped"
    profile: POC near the range middle and the close inside value).
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("value_area_by_day requires a DatetimeIndex")
    if not 0.0 < va_pct <= 1.0:
        raise ValueError("va_pct must be in (0, 1]")

    days = df.groupby(df.index.date)
    records = []
    for day, g in days:
        if len(g) == 0:
            continue
        lo = float(g["Low"].min())
        hi = float(g["High"].max())
        if hi <= lo:
            continue
        edges = np.linspace(lo, hi, n_bins + 1)
        close = g["Close"].to_numpy(dtype=float)
        vol = g["Volume"].to_numpy(dtype=float)
        bin_idx = np.clip(np.digitize(close, edges) - 1, 0, n_bins - 1)
        hist = np.zeros(n_bins, dtype=float)
        np.add.at(hist, bin_idx, vol)

        poc_i = int(np.argmax(hist))
        poc = float((edges[poc_i] + edges[poc_i + 1]) / 2.0)
        total = float(hist.sum())
        if total <= 0:
            continue

        # Expand the value area outward from the POC until coverage reached.
        cum = hist[poc_i]
        lo_i, hi_i = poc_i, poc_i
        while cum < va_pct * total and (lo_i > 0 or hi_i < n_bins - 1):
            left = hist[lo_i - 1] if lo_i > 0 else -1.0
            right = hist[hi_i + 1] if hi_i < n_bins - 1 else -1.0
            if left >= right:
                lo_i -= 1
                cum += hist[lo_i]
            else:
                hi_i += 1
                cum += hist[hi_i]
        val = float(edges[lo_i])
        vah = float(edges[hi_i + 1])

        day_close = float(g["Close"].iloc[-1])
        poc_pos = (poc - lo) / (hi - lo) if hi > lo else 0.5
        close_in_va = bool(val <= day_close <= vah)
        is_consolidation = bool((0.35 <= poc_pos <= 0.65) and close_in_va)

        records.append(
            {
                "poc": poc,
                "vah": vah,
                "val": val,
                "poc_pos": poc_pos,
                "close": day_close,
                "close_in_va": close_in_va,
                "is_consolidation": is_consolidation,
            }
        )

    if not records:
        return pd.DataFrame(
            columns=["poc", "vah", "val", "poc_pos", "close", "close_in_va", "is_consolidation"]
        )
    out = pd.DataFrame(records)
    out.index = pd.to_datetime([d for d in days.groups.keys()])
    return out
