"""Base alpha factor interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class BaseAlpha(ABC):
    """Abstract base class for alpha factors.

    Each alpha computes a signal from OHLCV data and returns a
    ``pd.Series`` of alpha values aligned to the input index.
    """

    name: str = ""
    category: str = ""  # e.g. "momentum", "mean_reversion", "value", "volatility"
    description: str = ""

    @abstractmethod
    def compute(self, df: pd.DataFrame) -> pd.Series:
        """Compute the alpha signal from an OHLCV DataFrame.

        Parameters
        ----------
        df:
            DataFrame with columns: Open, High, Low, Close, Volume
            and a DatetimeIndex.

        Returns
        -------
        pd.Series of alpha values (higher = more bullish).
        """
        ...
