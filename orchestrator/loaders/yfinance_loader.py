"""YFinance data loader — wraps the existing backtest/data.py load_daily."""

from __future__ import annotations

from typing import Dict, List

import pandas as pd

from .base import BaseLoader


class YFinanceLoader(BaseLoader):
    """Load OHLCV data via yfinance."""

    source_name = "yfinance"

    def is_available(self) -> bool:
        try:
            import yfinance  # noqa: F401
            return True
        except ImportError:
            return False

    def load(
        self,
        codes: List[str],
        start: str = "2020-01-01",
        end: str = "2025-12-31",
        interval: str = "1d",
    ) -> Dict[str, pd.DataFrame]:
        import yfinance as yf

        result: Dict[str, pd.DataFrame] = {}
        for code in codes:
            try:
                ticker = yf.Ticker(code)
                df = ticker.history(start=start, end=end, interval=interval)
                if not df.empty:
                    # Standardize columns.
                    df.columns = [c.capitalize() for c in df.columns]
                    if "Adj close" in df.columns:
                        df = df.drop(columns=["Adj close"], errors="ignore")
                    result[code] = df
            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning("Failed to load %s: %s", code, exc)
        return result
