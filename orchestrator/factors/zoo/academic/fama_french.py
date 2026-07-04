"""Fama-French and Carhart price-based factor proxies."""

from __future__ import annotations

import pandas as pd

from ...base import BaseAlpha
from ...registry import register_alpha


@register_alpha("momentum_12_1")
class Momentum12_1(BaseAlpha):
    """12-month momentum excluding the most recent month (Jegadeesh & Titman)."""

    name = "momentum_12_1"
    category = "momentum"
    description = "12-month return excluding last month"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        ret_12m = df["Close"].pct_change(252)
        ret_1m = df["Close"].pct_change(21)
        return ret_12m - ret_1m


@register_alpha("reversal_1m")
class Reversal1M(BaseAlpha):
    """1-month short-term reversal."""

    name = "reversal_1m"
    category = "mean_reversion"
    description = "Negative of 1-month return (contrarian)"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return -df["Close"].pct_change(21)


@register_alpha("volatility_20d")
class Volatility20D(BaseAlpha):
    """20-day realized volatility (annualized)."""

    name = "volatility_20d"
    category = "volatility"
    description = "20-day rolling standard deviation of returns, annualized"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        returns = df["Close"].pct_change()
        return returns.rolling(20).std() * (252 ** 0.5)


@register_alpha("volume_price_trend")
class VolumePriceTrend(BaseAlpha):
    """On-Balance Volume (OBV) trend signal."""

    name = "volume_price_trend"
    category = "volume"
    description = "OBV normalized by its 50-day SMA"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        direction = (df["Close"].diff() > 0).astype(int)
        direction = direction.replace(0, -1)
        obv = (direction * df["Volume"]).cumsum()
        obv_sma = obv.rolling(50).mean()
        return obv / obv_sma.replace(0, pd.NA)
