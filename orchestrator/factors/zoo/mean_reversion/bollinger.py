"""Bollinger Band and z-score mean reversion factors."""

from __future__ import annotations

import pandas as pd

from ...base import BaseAlpha
from ...registry import register_alpha


@register_alpha("bollinger_pctb")
class BollingerPctB(BaseAlpha):
    """Bollinger Band %B — position within the band."""

    name = "bollinger_pctb"
    category = "mean_reversion"
    description = "Price position within Bollinger Bands (0 = lower, 1 = upper)"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        sma20 = df["Close"].rolling(20).mean()
        std20 = df["Close"].rolling(20).std()
        upper = sma20 + 2 * std20
        lower = sma20 - 2 * std20
        return (df["Close"] - lower) / (upper - lower).replace(0, pd.NA)


@register_alpha("z_score_20d")
class ZScore20D(BaseAlpha):
    """20-day z-score of closing price."""

    name = "z_score_20d"
    category = "mean_reversion"
    description = "Standard deviations from 20-day mean"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        sma = df["Close"].rolling(20).mean()
        std = df["Close"].rolling(20).std()
        return -(df["Close"] - sma) / std.replace(0, pd.NA)  # Negative = mean-reversion signal.


@register_alpha("ibs")
class IBS(BaseAlpha):
    """Internal Bar Strength — position within the daily range."""

    name = "ibs"
    category = "mean_reversion"
    description = "(Close - Low) / (High - Low); low values = oversold"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        rng = (df["High"] - df["Low"]).replace(0, pd.NA)
        return (df["Close"] - df["Low"]) / rng
