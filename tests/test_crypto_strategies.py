"""Tests for the crypto intraday strategies (fade_5bar_crypto, orb_15m_crypto).

Uses a short recent window from the already-cached Binance 5m data so
the suite stays fast and offline. Real 5-year backtests live in the
``Strategies/run_strategy.py`` CLI and the run_all ranking.
"""

from __future__ import annotations

import pytest

from backtest import PERCENT_10BP
from backtest.engine import BacktestResult
from backtest.strategies import REGISTRY, fade_5bar_crypto, orb_15m_crypto, run


# Short window so tests are fast and rely on cached shards.
TEST_START = "2025-01-01"
TEST_END = "2025-01-31"


def test_fade_5bar_crypto_runs_on_btc():
    result = fade_5bar_crypto(symbol="BTCUSDT", start=TEST_START, end=TEST_END)
    assert isinstance(result, BacktestResult)
    assert result.name == "fade_5bar_crypto"
    assert result.execution == "next_open"
    assert result.cost_model_name == PERCENT_10BP.name
    # Should produce trades on a month of BTC 5m data with default params.
    assert result.trades, "fade_5bar_crypto(BTC) should produce trades on a month of 5m data"
    assert len(result.equity) > 0


def test_fade_5bar_crypto_runs_on_eth():
    result = fade_5bar_crypto(symbol="ETHUSDT", start=TEST_START, end=TEST_END)
    assert isinstance(result, BacktestResult)
    assert result.trades, "fade_5bar_crypto(ETH) should produce trades on a month of 5m data"


def test_orb_15m_crypto_runs_on_btc():
    result = orb_15m_crypto(symbol="BTCUSDT", start=TEST_START, end=TEST_END)
    assert isinstance(result, BacktestResult)
    assert result.name == "orb_15m_crypto"
    assert result.execution == "next_open"
    # ORB fires less frequently (once per breakout day) so trades are
    # expected to be >=1 over a month of BTC data.
    assert result.trades, "orb_15m_crypto(BTC) should produce >=1 trade on a month of 5m data"


def test_orb_15m_crypto_runs_on_eth():
    result = orb_15m_crypto(symbol="ETHUSDT", start=TEST_START, end=TEST_END)
    assert isinstance(result, BacktestResult)
    assert result.trades, "orb_15m_crypto(ETH) should produce >=1 trade on a month of 5m data"


def test_crypto_strategies_in_registry():
    names = set(REGISTRY.keys())
    assert "fade_5bar_crypto" in names
    assert "orb_15m_crypto" in names


def test_registry_run_resolves_crypto_strategies():
    # Smoke-test that the public registry.run entrypoint works for both.
    for name in ("fade_5bar_crypto", "orb_15m_crypto"):
        result = run(name, symbol="BTCUSDT", start=TEST_START, end=TEST_END)
        assert isinstance(result, BacktestResult)
        assert result.name == name


def test_fade_5bar_crypto_accepts_parameter_overrides():
    """Tighter lookback + shorter hold should still produce a valid run."""
    result = fade_5bar_crypto(
        symbol="BTCUSDT",
        start=TEST_START,
        end=TEST_END,
        lookback=3,
        max_hold_bars=6,
    )
    assert isinstance(result, BacktestResult)
    # Whatever the exact counts, the engine must have populated equity.
    assert len(result.equity) > 0


def test_orb_15m_crypto_accepts_parameter_overrides():
    """Shorter opening range + different EMA should still produce a valid run."""
    result = orb_15m_crypto(
        symbol="BTCUSDT",
        start=TEST_START,
        end=TEST_END,
        or_bars=2,
        ema_period=288,
    )
    assert isinstance(result, BacktestResult)
    assert len(result.equity) > 0
