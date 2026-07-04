"""CSV/Parquet local file loader."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import pandas as pd

from .base import BaseLoader


class CSVLoader(BaseLoader):
    """Load OHLCV data from local CSV or Parquet files.

    Files should be named ``{CODE}.csv`` or ``{CODE}.parquet`` in the
    configured directory.  The CSV must have columns: Date, Open, High,
    Low, Close, Volume (case-insensitive).
    """

    source_name = "csv"

    def __init__(self, data_dir: str = "data") -> None:
        self._data_dir = Path(data_dir)

    def is_available(self) -> bool:
        return True

    def load(
        self,
        codes: List[str],
        start: str = "2020-01-01",
        end: str = "2025-12-31",
        interval: str = "1d",
    ) -> Dict[str, pd.DataFrame]:
        result: Dict[str, pd.DataFrame] = {}
        for code in codes:
            # Try CSV first, then Parquet.
            for ext in (".csv", ".parquet"):
                path = self._data_dir / f"{code}{ext}"
                if path.exists():
                    try:
                        if ext == ".csv":
                            df = pd.read_csv(path, parse_dates=["Date"], index_col="Date")
                        else:
                            df = pd.read_parquet(path)
                        # Filter by date range.
                        df = df.loc[start:end]
                        df.columns = [c.capitalize() for c in df.columns]
                        result[code] = df
                    except Exception as exc:
                        import logging
                        logging.getLogger(__name__).warning("Failed to load %s: %s", path, exc)
                    break
        return result
