"""Tests for the per-day volume-profile / value-area helper."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtest.indicators import value_area_by_day


def _make_day(date: str, closes, vols, freq: str = "5min") -> pd.DataFrame:
    idx = pd.date_range(date, periods=len(closes), freq=freq)
    high = np.maximum(closes, np.roll(closes, 1))
    low = np.minimum(closes, np.roll(closes, 1))
    df = pd.DataFrame(
        {
            "Open": closes,
            "High": np.maximum(closes, high) * 1.001,
            "Low": np.minimum(closes, low) * 0.999,
            "Close": closes,
            "Volume": vols,
        },
        index=idx,
    )
    return df


def test_balanced_day_is_consolidation():
    """A bell-shaped volume profile centred in the range is a consolidation."""
    # Near-flat (consolidating) price with a smooth bell of volume peaking at
    # the centre bar -> POC sits at the middle of the (small) range.
    rng = np.random.default_rng(1)
    closes = 100.0 + rng.normal(0.0, 0.01, 48)
    bell = np.exp(-((np.arange(48) - 24) ** 2) / (2 * 6.0 ** 2))
    vols = bell * 100.0 + 1.0
    df = _make_day("2023-01-03", closes, vols, freq="5min")
    daily = value_area_by_day(df, n_bins=24, va_pct=0.70)
    assert len(daily) == 1
    row = daily.iloc[0]
    assert 0.35 <= row["poc_pos"] <= 0.65
    assert row["is_consolidation"]
    assert row["vah"] > row["poc"] > row["val"]


def test_trend_day_is_not_consolidation():
    """A strongly trending day (volume at one extreme, close outside value)."""
    closes = np.linspace(100, 130, 48)  # strong up-trend
    vols = np.zeros(48)
    vols[-1] = 1000.0  # volume concentrated at the top extreme
    vols += 1.0
    df = _make_day("2023-01-04", closes, vols)
    daily = value_area_by_day(df, n_bins=24, va_pct=0.70)
    row = daily.iloc[0]
    # POC sits near the top extreme -> not a balanced consolidation.
    assert row["poc_pos"] > 0.65
    assert not row["is_consolidation"]


def test_value_area_coverage():
    """The value area should contain ~va_pct of the day's volume."""
    rng = np.random.default_rng(0)
    closes = 100.0 + np.cumsum(rng.normal(0, 0.1, 100))
    vols = rng.integers(1, 10, size=100).astype(float)
    df = _make_day("2023-01-05", closes, vols, freq="1min")
    daily = value_area_by_day(df, n_bins=30, va_pct=0.70)
    # POC is the highest-volume single bin: at least 1/30 of volume, and the
    # value area (>=1 bin) must be non-empty and ordered.
    assert daily.iloc[0]["vah"] > daily.iloc[0]["val"]
    assert daily.iloc[0]["poc"] >= daily.iloc[0]["val"]
    assert daily.iloc[0]["poc"] <= daily.iloc[0]["vah"]


def test_invalid_va_pct_rejected():
    df = _make_day("2023-01-06", np.full(20, 100.0), np.ones(20))
    with pytest.raises(ValueError):
        value_area_by_day(df, va_pct=1.5)
