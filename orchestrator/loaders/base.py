"""Base loader interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

import pandas as pd


class BaseLoader(ABC):
    """Abstract base class for data loaders.

    Subclasses implement :meth:`load` to fetch OHLCV data for one or
    more tickers from a specific data source.
    """

    source_name: str = ""

    @abstractmethod
    def load(
        self,
        codes: List[str],
        start: str = "2020-01-01",
        end: str = "2025-12-31",
        interval: str = "1d",
    ) -> Dict[str, pd.DataFrame]:
        """Fetch OHLCV data for the given codes.

        Parameters
        ----------
        codes:
            List of ticker symbols.
        start / end:
            Date range in YYYY-MM-DD format.
        interval:
            Bar interval (1d, 1wk, 1mo, etc.).

        Returns
        -------
        Dict mapping each code to a DataFrame with columns
        Open, High, Low, Close, Volume and a DatetimeIndex.
        """
        ...

    def is_available(self) -> bool:
        """Return True if this loader's dependencies are installed."""
        return True
