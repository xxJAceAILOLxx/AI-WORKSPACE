"""Trend-following momentum factors."""

from __future__ import annotations

import pandas as pd

from ...base import BaseAlpha
from ...registry import register_alpha


@register_alpha("trend_strength")
class TrendStrength(BaseAlpha):
    """ADX-based trend strength indicator."""

    name = "trend_strength"
    category = "momentum"
    description = "Average Directional Index (14-period)"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        high, low, close = df["High"], df["Low"], df["Close"]
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0

        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ], axis=1).max(axis=1)

        atr = tr.rolling(14).mean()
        plus_di = 100 * (plus_dm.rolling(14).mean() / atr.replace(0, pd.NA))
        minus_di = 100 * (minus_dm.rolling(14).mean() / atr.replace(0, pd.NA))
        dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, pd.NA))
        return dx.rolling(14).mean()


@register_alpha("ma_crossover")
class MACrossover(BaseAlpha):
    """Moving average crossover signal (50/200 SMA)."""

    name = "ma_crossover"
    category = "momentum"
    description = "50-day SMA minus 200-day SMA, normalized by price"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        sma50 = df["Close"].rolling(50).mean()
        sma200 = df["Close"].rolling(200).mean()
        return (sma50 - sma200) / df["Close"].replace(0, pd.NA)


@register_alpha("rsi_14")
class RSI14(BaseAlpha):
    """Relative Strength Index (14-period)."""

    name = "rsi_14"
    category = "momentum"
    description = "14-period RSI, centered at 50"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        delta = df["Close"].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss.replace(0, pd.NA)
        rsi = 100 - (100 / (1 + rs))
        return rsi - 50  # Center at 0.
