"""Loader registry — discover and use data loaders."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import pandas as pd

from .base import BaseLoader

logger = logging.getLogger(__name__)

# Global loader registry.
_LOADERS: Dict[str, BaseLoader] = {}


def _register(loader: BaseLoader) -> None:
    """Register a loader instance."""
    if loader.is_available():
        _LOADERS[loader.source_name] = loader
        logger.debug("Registered loader: %s", loader.source_name)


def _ensure_loaders() -> None:
    """Lazy-load all built-in loaders."""
    if _LOADERS:
        return
    try:
        from .yfinance_loader import YFinanceLoader
        _register(YFinanceLoader())
    except Exception:
        logger.debug("YFinance loader unavailable")
    try:
        from .csv_loader import CSVLoader
        _register(CSVLoader())
    except Exception:
        logger.debug("CSV loader unavailable")


def list_sources() -> List[str]:
    """Return sorted list of available data source names."""
    _ensure_loaders()
    return sorted(_LOADERS.keys())


def load_data(
    source: str,
    codes: List[str],
    start: str = "2020-01-01",
    end: str = "2025-12-31",
    interval: str = "1d",
) -> Dict[str, pd.DataFrame]:
    """Load OHLCV data using the specified source.

    Parameters
    ----------
    source:
        Data source name (e.g. "yfinance", "csv").
    codes:
        List of ticker symbols.
    start / end:
        Date range.
    interval:
        Bar interval.
    """
    _ensure_loaders()
    if source not in _LOADERS:
        available = list_sources()
        raise ValueError(
            f"Unknown data source {source!r}. Available: {available}"
        )
    return _LOADERS[source].load(codes, start=start, end=end, interval=interval)
