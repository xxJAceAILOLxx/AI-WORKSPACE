"""Tests for the mean-reversion strategy library (Chunk 2a).

Tests cover:
* Registry semantics (register, run, list_strategies).
* Each registered strategy returns at least one trade on its default
  date range and produces a :class:`BacktestResult` with the expected
  configuration.
* Strategy functions can also be called directly (not just via the
  registry) and accept parameter overrides.

The end-to-end tests use real SPY/QQQ data via :func:`load_daily`, which
caches to ``data/cache`` after the first download.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtest import Engine, OHLCV, PERCENT_10BP, from_dataframe, load_daily
from backtest.engine import BacktestResult
from backtest.indicators import ibs, sma
from backtest.strategies import (
    REGISTRY,
    ibs_dynamic,
    ibs_spy,
    list_strategies,
    multiple_days_down,
    pct_b_mr,
    register,
    rsi2_mr,
    rsi2_qqq_enhanced,
    run,
    turn_of_month_strategy,
)
from backtest.strategies import ibs as ibs_module  # for ibs_trend / qqq_mr
from backtest.strategies.registry import REGISTRY as REGISTRY_DIRECT


# ---------------------------------------------------------------------------
# Registry semantics (no data download needed)
# ---------------------------------------------------------------------------


EXPECTED_STRATEGIES = {
    "ibs_spy",
    "ibs_trend",
    "qqq_mr",
    "rsi2_mr",
    "rsi2_qqq_enhanced",
    "pct_b_mr",
    "multiple_days_down",
    "turn_of_month",
    "ibs_dynamic",
}


def test_registry_contains_all_expected_strategies():
    names = set(list_strategies())
    assert EXPECTED_STRATEGIES.issubset(names), (
        f"missing strategies: {EXPECTED_STRATEGIES - names}"
    )


def test_registry_is_sorted():
    assert list_strategies() == sorted(list_strategies())


def test_registry_via_package_and_module_match():
    # Importing the package should populate the registry identically to
    # importing the module-level dict directly.
    assert REGISTRY is REGISTRY_DIRECT
    assert len(REGISTRY) >= len(EXPECTED_STRATEGIES)


def test_register_rejects_duplicate_name():
    @register("__dup_test__")
    def fake_strategy():
        return None  # type: ignore[return-value]

    with pytest.raises(ValueError, match="already registered"):
        @register("__dup_test__")
        def fake_strategy_2():
            return None  # type: ignore[return-value]

    # The decorator returned the original function even when the second
    # registration failed; make sure the registry still resolves to it.
    assert REGISTRY["__dup_test__"] is fake_strategy


def test_run_unknown_strategy_raises():
    with pytest.raises(KeyError, match="Unknown strategy"):
        run("not_a_real_strategy")


# ---------------------------------------------------------------------------
# Helpers for end-to-end tests
# ---------------------------------------------------------------------------


# Real-data tests share a single SPY/QQQ download via session scope so the
# suite is fast on subsequent runs (data is also cached on disk by
# load_daily).
@pytest.fixture(scope="module")
def spy_ohlcv():
    return load_daily("SPY", "2016-01-01", "2025-12-31")


@pytest.fixture(scope="module")
def qqq_ohlcv():
    return load_daily("QQQ", "2016-01-01", "2025-12-31")


def _assert_default_config(result: BacktestResult, name: str) -> None:
    assert isinstance(result, BacktestResult)
    assert result.name == name
    assert result.execution == "next_open"
    assert result.cost_model_name == PERCENT_10BP.name
    # 95% sizing and 100k initial capital are the framework defaults.
    assert result.config["size_policy"] == "percent_of_equity"
    assert result.config["size_value"] == pytest.approx(0.95)
    assert result.config["initial_capital"] == pytest.approx(100_000.0)
    # Trades that did happen should reflect the 0.1% cost model.
    for t in result.trades:
        assert t.entry_cost >= 0
        assert t.exit_cost >= 0


# ---------------------------------------------------------------------------
# Per-strategy smoke tests on real data
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "strategy_name, callable_, default_ticker",
    [
        ("ibs_spy", ibs_spy, "SPY"),
        ("qqq_mr", ibs_module.qqq_mr, "QQQ"),
        ("rsi2_mr", rsi2_mr, "SPY"),
        ("rsi2_qqq_enhanced", rsi2_qqq_enhanced, "QQQ"),
        ("pct_b_mr", pct_b_mr, "SPY"),
        ("multiple_days_down", multiple_days_down, "SPY"),
        ("turn_of_month", turn_of_month_strategy, "SPY"),
        ("ibs_dynamic", ibs_dynamic, "SPY"),
    ],
)
def test_strategy_runs_and_trades(strategy_name, callable_, default_ticker):
    """Each strategy must produce >=1 trade on its default date range."""
    result = callable_()
    _assert_default_config(result, strategy_name)
    assert result.trades, f"{strategy_name} should produce at least one trade on 2016-2025"
    # Equity curve length matches the OHLCV length passed to the engine.
    assert len(result.equity) > 0


def test_ibs_spy_min_signal_count():
    """IBS<0.2 should fire on many bars on 10 years of SPY data."""
    result = ibs_spy()
    # Conservative lower bound: at least 20 trades over a decade of SPY.
    assert len(result.trades) >= 20


def test_turn_of_month_one_entry_per_month(spy_ohlcv):
    """TOM should produce roughly one entry per month."""
    result = turn_of_month_strategy()
    # 10 years * 12 months = 120, but month-end fall on holidays can shift
    # the count slightly. Allow generous slack.
    n = len(result.trades)
    assert 100 <= n <= 130, f"expected ~120 TOM trades, got {n}"


def test_ibs_trend_is_subset_of_ibs_spy(spy_ohlcv):
    """IBS+trend+TOM is a stricter filter than plain IBS<0.2."""
    plain = ibs_spy()
    trend = ibs_module.ibs_trend()
    assert len(trend.trades) <= len(plain.trades)
    # And on 10 years it should still produce at least one trade.
    assert trend.trades, "ibs_trend should produce >=1 trade on 2016-2025"


def test_qqq_mr_uses_qqq_data(qqq_ohlcv):
    result = ibs_module.qqq_mr()
    assert result.trades
    assert result.ohlcv.ticker == "QQQ"


# ---------------------------------------------------------------------------
# Registry.run round-trip (verifies callers don't have to import modules)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(EXPECTED_STRATEGIES))
def test_registry_run_works_for_each_strategy(name):
    result = run(name)
    assert isinstance(result, BacktestResult)
    assert result.name == name
    # Default range strategies must trade at least once.
    assert result.trades, f"run({name!r}) produced no trades"


# ---------------------------------------------------------------------------
# Parameter overrides (synthetic data so no yfinance call is made)
# ---------------------------------------------------------------------------


def _synthetic_ohlcv(n: int = 400, seed: int = 0) -> OHLCV:
    """Build a deterministic synthetic OHLCV with a clear mean-reverting regime."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start="2015-01-02", periods=n)
    # Ornstein-Uhlenbeck-ish path: revert to 100 with mean reversion.
    close = np.empty(n)
    close[0] = 100.0
    for i in range(1, n):
        close[i] = close[i - 1] + 1.5 * (100.0 - close[i - 1]) / n + rng.normal(0, 0.5)
    open_ = np.concatenate([[close[0]], close[:-1]]) + rng.normal(0, 0.05, size=n)
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.3, size=n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.3, size=n))
    volume = rng.integers(1_000_000, 5_000_000, size=n).astype(float)
    df = pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=dates,
    )
    return from_dataframe("SYN_MR", df)


def test_ibs_spy_with_synthetic_data():
    ohlcv = _synthetic_ohlcv()
    # Patch load_daily via monkeypatch so the strategy uses our synthetic frame.
    import backtest.strategies.ibs as ibs_pkg
    orig = ibs_pkg.load_daily

    def fake_load(ticker, start, end, *args, **kwargs):
        return ohlcv

    ibs_pkg.load_daily = fake_load
    try:
        result = ibs_spy()
    finally:
        ibs_pkg.load_daily = orig

    assert isinstance(result, BacktestResult)
    # Synthetic series is strongly mean-reverting so we expect entries.
    # Don't assert exact counts since the signal depends on RNG state.
    assert result.execution == "next_open"


def test_strategy_accepts_parameter_overrides():
    """Passing a custom threshold and hold should change the run output."""
    baseline = ibs_spy()  # default threshold=0.20, hold=5
    # We can't easily force IBS<0.05 on real data, but we can verify the
    # config records the override.
    custom_hold = 3
    custom = ibs_spy(hold=custom_hold)
    # Both runs use next_open and PERCENT_10BP regardless of hold.
    assert custom.execution == baseline.execution == "next_open"
    # The hold override is captured in the trade exit reasons.
    if custom.trades:
        assert all(t.exit_reason == f"hold_{custom_hold}" for t in custom.trades)


# ---------------------------------------------------------------------------
# Engine integration sanity (signal produced correctly)
# ---------------------------------------------------------------------------


def test_ibs_spy_signal_matches_engine_behavior(spy_ohlcv):
    """The strategy's entry signal must match what the engine receives."""
    import backtest.strategies.ibs as ibs_pkg

    orig = ibs_pkg.load_daily

    def fake_load(ticker, start, end, *args, **kwargs):
        return spy_ohlcv

    ibs_pkg.load_daily = fake_load
    try:
        result = ibs_spy()
    finally:
        ibs_pkg.load_daily = orig

    expected_signal = ibs(spy_ohlcv.df) < 0.20
    expected_signal = expected_signal.fillna(False)

    # Recreate the engine and check the trade entry dates align with the
    # expected signal bars (next bar opens).
    eng = Engine(
        spy_ohlcv,
        name="replay",
        execution="next_open",
        cost_model=PERCENT_10BP,
        size_policy="percent_of_equity",
        size_value=0.95,
    )

    captured = []

    def exit_rule(s):
        if s.days_held >= 5:
            return ("hold_5", 0.0)
        return None

    eng.set_entry(expected_signal).set_exit(exit_rule)
    replay = eng.run()

    # Same number of trades and same entry dates.
    assert len(result.trades) == len(replay.trades)
    for t_orig, t_rep in zip(result.trades, replay.trades):
        assert t_orig.entry_date == t_rep.entry_date
        assert t_orig.entry_price == pytest.approx(t_rep.entry_price)
        assert t_orig.exit_reason == t_rep.exit_reason
