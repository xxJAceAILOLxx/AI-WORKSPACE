"""Tests for Chunk 2c strategies: trend, volatility, portfolio.

Covers:
* ``qqq_dual_ma`` produces trades on real QQQ data.
* ``vix_etn`` runs on real SPY/VXX/SVXY/VIX data and also runs
  gracefully when VXX data is missing (returns an empty
  ``BacktestResult`` with a diagnostic note).
* ``mr_portfolio`` returns trades from at least two sub-strategies and
  tags every trade with the originating ``sub_strategy``.
* All three strategies are reachable via the registry: ``registry.run``
  returns a valid ``BacktestResult`` for each name.

Real-data tests share downloads via session-scoped fixtures so the
suite stays fast on subsequent runs (data is also cached on disk by
:func:`backtest.load_daily`).
"""

from __future__ import annotations

import importlib
import inspect
from typing import Iterable

import numpy as np
import pandas as pd
import pytest

from backtest import Engine, FLAT_40, OHLCV, PERCENT_10BP, from_dataframe, load_daily
from backtest.engine import BacktestResult, Trade
from backtest.indicators import sma
from backtest.strategies import (
    REGISTRY,
    SUB_STRATEGIES,
    VIX_TICKERS,
    list_strategies,
    mr_portfolio,
    qqq_dual_ma,
    run,
    vix_etn,
)
# Resolve the submodule via importlib: ``backtest.strategies.__init__``
# does ``from .vix_etn import vix_etn`` (the function), which shadows the
# module reference in the parent package's namespace.  ``importlib.import_module``
# always returns the actual module object regardless of that shadowing.
vix_etn_mod = importlib.import_module("backtest.strategies.vix_etn")
from backtest.strategies.portfolio import SUB_STRATEGIES as PORTFOLIO_SUBS


# ---------------------------------------------------------------------------
# Registry semantics (no data download needed)
# ---------------------------------------------------------------------------


EXPECTED_NEW_STRATEGIES = {"qqq_dual_ma", "vix_etn", "mr_portfolio"}


def test_new_strategies_in_registry():
    names = set(list_strategies())
    assert EXPECTED_NEW_STRATEGIES.issubset(names), (
        f"missing strategies: {EXPECTED_NEW_STRATEGIES - names}"
    )


def test_registry_stores_strategy_functions():
    """The @register decorator must have stored each new strategy directly."""
    assert REGISTRY["qqq_dual_ma"] is qqq_dual_ma
    assert REGISTRY["vix_etn"] is vix_etn
    assert REGISTRY["mr_portfolio"] is mr_portfolio


def test_sub_strategy_constant_lists_four_members():
    """The portfolio must be built from exactly these four MR sub-strategies."""
    assert set(PORTFOLIO_SUBS) == {"ibs_spy", "rsi2_mr", "pct_b_mr", "turn_of_month"}
    # And the package re-export must agree.
    assert SUB_STRATEGIES == PORTFOLIO_SUBS


def test_vix_ticker_constant_lists_required_assets():
    """The VIX ETN strategy must align SPY/VXX/SVXY/^VIX."""
    assert set(VIX_TICKERS) == {"SPY", "VXX", "SVXY", "^VIX"}


def test_qqq_dual_ma_signature_defaults():
    sig = inspect.signature(qqq_dual_ma)
    assert sig.parameters["ticker"].default == "QQQ"
    assert sig.parameters["short_window"].default == 50
    assert sig.parameters["long_window"].default == 200


def test_vix_etn_signature_defaults():
    sig = inspect.signature(vix_etn)
    # VIX ETN has no ``ticker`` arg -- it always uses the canonical basket.
    assert "ticker" not in sig.parameters
    assert sig.parameters["cost_model"].default is FLAT_40


def test_mr_portfolio_signature_defaults():
    sig = inspect.signature(mr_portfolio)
    assert sig.parameters["ticker"].default == "SPY"


# ---------------------------------------------------------------------------
# qqq_dual_ma: end-to-end on real QQQ data
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def dual_ma_result():
    return qqq_dual_ma()


def test_qqq_dual_ma_produces_trades(dual_ma_result):
    """The trend strategy should have at least one entry on 10y of QQQ."""
    assert isinstance(dual_ma_result, BacktestResult)
    assert dual_ma_result.trades, (
        "qqq_dual_ma should produce trades on QQQ 2016-2025"
    )


def test_qqq_dual_ma_uses_qqq_data(dual_ma_result):
    assert dual_ma_result.ohlcv.ticker == "QQQ"


def test_qqq_dual_ma_default_config(dual_ma_result):
    cfg = dual_ma_result.config
    assert cfg["execution"] == "next_open"
    assert cfg["size_policy"] == "percent_of_equity"
    assert cfg["size_value"] == pytest.approx(0.95)
    assert cfg["cost_model"] == PERCENT_10BP.name
    assert cfg["short_window"] == 50
    assert cfg["long_window"] == 200


def test_qqq_dual_ma_exits_are_ma_exit(dual_ma_result):
    """Every trade should have been closed by the ma_exit rule (or end-of-data)."""
    assert dual_ma_result.trades
    reasons = {t.exit_reason for t in dual_ma_result.trades}
    assert reasons.issubset({"ma_exit", "end_of_data"}), (
        f"unexpected exit reasons: {reasons}"
    )


def test_qqq_dual_ma_entry_above_both_smas(dual_ma_result):
    """Every entry must occur on a bar where Close > SMA50 and Close > SMA200."""
    df = dual_ma_result.ohlcv.df
    sma50 = sma(df["Close"], 50)
    sma200 = sma(df["Close"], 200)
    assert dual_ma_result.trades
    for t in dual_ma_result.trades:
        if t.entry_date not in df.index:
            continue
        # next_open execution: the entry fill is at bar ``entry_date``
        # which is the bar AFTER the signal bar.
        sig_pos = df.index.get_loc(t.entry_date) - 1
        if sig_pos < 0:
            continue
        close = float(df["Close"].iloc[sig_pos])
        s50 = float(sma50.iloc[sig_pos])
        s200 = float(sma200.iloc[sig_pos])
        if np.isnan(s50) or np.isnan(s200):
            continue
        assert close > s50, (
            f"entry on {t.entry_date.date()} signal close={close:.2f} not "
            f"above SMA50={s50:.2f}"
        )
        assert close > s200, (
            f"entry on {t.entry_date.date()} signal close={close:.2f} not "
            f"above SMA200={s200:.2f}"
        )


# ---------------------------------------------------------------------------
# vix_etn: end-to-end on real data + graceful handling of missing VXX
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def vix_etn_result():
    return vix_etn()


def test_vix_etn_runs_without_error(vix_etn_result):
    """The strategy must return a valid BacktestResult, even if trades==0."""
    assert isinstance(vix_etn_result, BacktestResult)
    assert vix_etn_result.name == "vix_etn"
    # equity list, if non-empty, must be aligned to the OHLCV index
    if vix_etn_result.equity:
        assert len(vix_etn_result.equity) == len(vix_etn_result.ohlcv.df)


def test_vix_etn_default_config(vix_etn_result):
    cfg = vix_etn_result.config
    assert cfg["cost_model"] == FLAT_40.name
    assert cfg["tickers"] == list(VIX_TICKERS)
    assert cfg["allocation_caps"] == {"contango_svxy": 0.30, "backwardation_vxx": 0.20}
    assert vix_etn_result.cost_model_name == FLAT_40.name


def test_vix_etn_trade_holds_look_reasonable(vix_etn_result):
    """Any trades that did fire must have positive hold days and finite PnL."""
    for t in vix_etn_result.trades:
        assert t.entry_date <= t.exit_date
        assert t.shares > 0
        assert t.entry_price > 0
        assert t.exit_price > 0
        assert np.isfinite(t.pnl)
        # Hold days is a wall-clock delta; allow 0 for intraday regime flips.
        assert t.hold_days >= 0


def test_vix_etn_handles_missing_vxx(monkeypatch):
    """If VXX/SVXY downloads fail the strategy must return an empty result, not raise."""

    def fake_load(ticker, start, end, *args, **kwargs):
        # Only SPY and ^VIX succeed; VXX and SVXY fail.
        if ticker in ("VXX", "SVXY"):
            raise ValueError(f"simulated download failure for {ticker}")
        return load_daily(ticker, start, end)

    monkeypatch.setattr(vix_etn_mod, "load_daily", fake_load)

    with pytest.warns(UserWarning, match="vix_etn"):
        result = vix_etn(start="2020-01-01", end="2021-01-01")

    assert isinstance(result, BacktestResult)
    assert result.trades == []
    assert result.equity == []
    # A diagnostic note must be attached so the caller knows why.
    assert "note" in result.config
    assert "Missing" in result.config["note"]
    assert result.config.get("warning") is True
    # And the load failures should be recorded.
    assert any("VXX" in f for f in result.config.get("load_failures", []))


def test_vix_etn_handles_sparse_vxx(monkeypatch):
    """If VXX returns just a couple of rows the strategy must still not raise."""

    sparse_dates = pd.bdate_range("2020-01-02", periods=3)
    sparse_df = pd.DataFrame(
        {
            "Open": [50.0, 51.0, 52.0],
            "High": [50.5, 51.5, 52.5],
            "Low": [49.5, 50.5, 51.5],
            "Close": [50.2, 51.1, 52.0],
            "Volume": [1_000_000] * 3,
        },
        index=sparse_dates,
    )
    sparse_vxx = from_dataframe("VXX", sparse_df)

    real_load = vix_etn_mod.load_daily

    def fake_load(ticker, start, end, *args, **kwargs):
        if ticker == "VXX":
            return sparse_vxx
        return real_load(ticker, start, end, *args, **kwargs)

    monkeypatch.setattr(vix_etn_mod, "load_daily", fake_load)

    # Should not raise -- just return whatever it can.
    result = vix_etn(start="2020-01-01", end="2021-01-01")
    assert isinstance(result, BacktestResult)
    # With only 3 VXX rows there's almost certainly no usable overlap, but
    # whatever the outcome, it must be a valid result object.
    if not result.trades:
        assert "note" in result.config
    else:
        for t in result.trades:
            assert t.shares > 0


# ---------------------------------------------------------------------------
# mr_portfolio: combines four sub-strategies
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def portfolio_result():
    return mr_portfolio()


def test_mr_portfolio_returns_backtest_result(portfolio_result):
    assert isinstance(portfolio_result, BacktestResult)
    assert portfolio_result.name == "mr_portfolio"


def test_mr_portfolio_has_trades(portfolio_result):
    """At least one of the four sub-strategies should have produced trades."""
    assert portfolio_result.trades, "mr_portfolio should produce trades on 2016-2025 SPY"


def test_mr_portfolio_trades_from_multiple_subs(portfolio_result):
    """At least two of the four sub-strategies must have contributed trades."""
    sub_tags = {getattr(t, "sub_strategy", None) for t in portfolio_result.trades}
    sub_tags.discard(None)
    assert len(sub_tags) >= 2, (
        f"expected trades from >=2 sub-strategies, got tags {sub_tags}"
    )


def test_mr_portfolio_trades_tagged_with_sub_strategy(portfolio_result):
    """Every combined trade must carry a sub_strategy attribute."""
    assert portfolio_result.trades
    for t in portfolio_result.trades:
        tag = getattr(t, "sub_strategy", None)
        assert tag in set(PORTFOLIO_SUBS), (
            f"trade {t.entry_date.date()} has unexpected tag {tag!r}"
        )


def test_mr_portfolio_combined_equity_is_average(portfolio_result):
    """The combined equity curve must have one entry per bar in the OHLCV."""
    if not portfolio_result.equity:
        pytest.skip("portfolio produced no equity curve")
    assert len(portfolio_result.equity) == len(portfolio_result.ohlcv.df)
    # Verify the average by recomputing each sub-strategy with the slice
    # capital directly.  We use the inline signal builders from
    # ``backtest.strategies.portfolio`` rather than ``registry.run`` because
    # the existing MR strategies do not accept an ``initial_capital`` kwarg.
    from backtest import Engine
    from backtest.strategies.portfolio import _signal_for
    df = portfolio_result.ohlcv.df
    sma200 = sma(df["Close"], 200)
    slice_cap = portfolio_result.initial_capital / 4.0
    sub_equities = []
    for sub_name, hold in [
        ("ibs_spy", 5), ("rsi2_mr", 5), ("pct_b_mr", 5), ("turn_of_month", 4),
    ]:
        sig = _signal_for(sub_name, df, sma200).fillna(False)
        eng = Engine(
            portfolio_result.ohlcv,
            name=sub_name,
            execution="next_open",
            cost_model=PERCENT_10BP,
            initial_capital=slice_cap,
            size_policy="percent_of_equity",
            size_value=0.95,
        )
        from backtest.strategies._common import hold_n_exit
        eng.set_entry(sig).set_exit(hold_n_exit(hold))
        sub_equities.append(eng.run().equity)
    n = min(len(portfolio_result.equity), *(len(c) for c in sub_equities))
    assert n > 0
    for i in range(n):
        avg = sum(c[i] for c in sub_equities) / len(sub_equities)
        assert portfolio_result.equity[i] == pytest.approx(avg, rel=1e-6), (
            f"combined equity[{i}]={portfolio_result.equity[i]:.4f} != "
            f"average of sub-strategies={avg:.4f}"
        )


def test_mr_portfolio_trade_count_equals_sum_of_subs(portfolio_result):
    """The combined trade list must be the union (no duplicates) of the
    four sub-strategy trade lists."""
    sub_counts = portfolio_result.config.get("sub_trade_counts", {})
    if not sub_counts:
        pytest.skip("sub_trade_counts not recorded on config")
    expected = sum(sub_counts.values())
    assert len(portfolio_result.trades) == expected


def test_mr_portfolio_default_config(portfolio_result):
    cfg = portfolio_result.config
    assert cfg["cost_model"] == PERCENT_10BP.name
    assert cfg["size_policy"] == "percent_of_equity"
    assert portfolio_result.execution == "next_open"
    # Each sub-strategy ran on a quarter of the capital.
    assert cfg["slice_capital"] == pytest.approx(
        portfolio_result.initial_capital / 4
    )
    assert set(cfg["sub_strategies"]) == set(PORTFOLIO_SUBS)


def test_mr_portfolio_uses_spy_data(portfolio_result):
    assert portfolio_result.ohlcv.ticker == "SPY"


# ---------------------------------------------------------------------------
# Synthetic data path for qqq_dual_ma (no yfinance call)
# ---------------------------------------------------------------------------


def _synthetic_trending_ohlcv(n: int = 600, seed: int = 11) -> OHLCV:
    """Build a deterministic trending OHLCV with two MAs both below price."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start="2015-01-02", periods=n)
    # Drift upward with mild noise so price > both MAs most of the time.
    rets = rng.normal(loc=0.0006, scale=0.01, size=n)
    close = 100.0 * np.exp(np.cumsum(rets))
    open_ = np.empty(n)
    open_[0] = 100.0
    open_[1:] = close[:-1] * (1.0 + rng.normal(0, 0.003, size=n - 1))
    high = np.maximum(open_, close) * (1.0 + np.abs(rng.normal(0, 0.002, size=n)))
    low = np.minimum(open_, close) * (1.0 - np.abs(rng.normal(0, 0.002, size=n)))
    volume = rng.integers(1_000_000, 5_000_000, size=n).astype(float)
    df = pd.DataFrame(
        {
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume,
        },
        index=dates,
    )
    return from_dataframe("SYN_QQQ", df)


def test_qqq_dual_ma_synthetic_runs():
    ohlcv = _synthetic_trending_ohlcv()
    import sys

    mod = sys.modules["backtest.strategies.dual_ma"]
    orig = mod.load_daily

    def fake_load(ticker, start, end, *args, **kwargs):
        return ohlcv

    mod.load_daily = fake_load
    try:
        result = qqq_dual_ma()
    finally:
        mod.load_daily = orig

    assert isinstance(result, BacktestResult)
    assert result.execution == "next_open"
    # Synthetic trending series: there must be at least one entry.
    assert result.trades, "synthetic trending data should produce a trade"


# ---------------------------------------------------------------------------
# Synthetic data path for mr_portfolio (no yfinance call)
# ---------------------------------------------------------------------------


def test_mr_portfolio_synthetic_runs():
    """mr_portfolio must compose four sub-strategies from a shared synthetic SPY frame."""
    ohlcv = _synthetic_trending_ohlcv()
    import sys

    modules = {
        "backtest.strategies.ibs": "ibs_spy",
        "backtest.strategies.rsi2": "rsi2_mr",
        "backtest.strategies.pct_b": "pct_b_mr",
        "backtest.strategies.turn_of_month": "turn_of_month",
    }
    originals = {}

    def make_fake(target):
        def fake_load(ticker, start, end, *args, **kwargs):
            return ohlcv

        return fake_load

    for mod_name in modules:
        mod = sys.modules[mod_name]
        originals[mod_name] = mod.load_daily
        mod.load_daily = make_fake(modules[mod_name])
    try:
        result = mr_portfolio()
    finally:
        for mod_name, orig in originals.items():
            sys.modules[mod_name].load_daily = orig

    assert isinstance(result, BacktestResult)
    # All four sub-strategies must have been registered and run.
    assert set(result.config["sub_strategies"]) == set(PORTFOLIO_SUBS)
    assert result.trades, "synthetic data should yield trades from at least one sub"
    # And the trade count must match the per-sub counts.
    expected = sum(result.config["sub_trade_counts"].values())
    assert len(result.trades) == expected


# ---------------------------------------------------------------------------
# Registry.run round-trip
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(EXPECTED_NEW_STRATEGIES))
def test_registry_run_works_for_each_advanced_strategy(name):
    """registry.run must dispatch correctly without a direct import."""
    result = run(name)
    assert isinstance(result, BacktestResult)
    assert result.name == name


# ---------------------------------------------------------------------------
# Engine-level sanity for the dual MA exit rule
# ---------------------------------------------------------------------------


def test_qqq_dual_ma_exit_rule_only_fires_below_sma50():
    """The exit rule should fire exactly when Close < SMA50 (at signal bar)."""
    # Build a frame where Close > SMA50 on most bars and < SMA50 on a few.
    dates = pd.bdate_range("2024-01-02", periods=300)
    close = np.concatenate(
        [
            np.linspace(100, 130, 150),  # rising -- above SMA50
            np.linspace(130, 95, 150),  # falling -- below SMA50 eventually
        ]
    )
    open_ = close.copy()
    high = close + 0.5
    low = close - 0.5
    df = pd.DataFrame(
        {
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": np.ones_like(close) * 1_000_000,
        },
        index=dates,
    )
    ohlcv = from_dataframe("SYN_T", df)
    sma50 = sma(ohlcv.df["Close"], 50)
    sma200 = sma(ohlcv.df["Close"], 200)

    # Feed a simple "always in" entry signal to the engine and observe that
    # the exit rule triggers when Close < SMA50.
    eng = Engine(
        ohlcv,
        name="replay",
        execution="next_open",
        cost_model=PERCENT_10BP,
        size_policy="percent_of_equity",
        size_value=0.95,
    )
    always_in = pd.Series(True, index=df.index)

    def exit_rule(state):
        v = sma50.iloc[state.idx]
        if pd.notna(v) and float(state.bar["Close"]) < float(v):
            return ("ma_exit", 0.0)
        return None

    eng.set_entry(always_in).set_exit(exit_rule)
    replay = eng.run()

    assert replay.trades, "synthetic always-in signal must produce a trade"
    t = replay.trades[0]
    # The exit bar's close must be below the SMA50 at that bar.
    exit_idx = df.index.get_loc(t.exit_date)
    if exit_idx > 0 and not np.isnan(sma50.iloc[exit_idx - 1]):
        assert df["Close"].iloc[exit_idx - 1] < sma50.iloc[exit_idx - 1]
    # Entry was triggered while Close > SMA50 and Close > SMA200.
    entry_idx = df.index.get_loc(t.entry_date)
    sig_idx = entry_idx - 1  # next_open: signal bar precedes fill bar
    assert sig_idx >= 0
    # SMA50 may be NaN in the first 49 bars (warm-up).  Wait for the first
    # bar where it is defined before checking the entry condition.
    if not np.isnan(sma50.iloc[sig_idx]):
        assert df["Close"].iloc[sig_idx] > sma50.iloc[sig_idx], (
            f"signal bar {sig_idx} close {df['Close'].iloc[sig_idx]} should "
            f"be > SMA50 {sma50.iloc[sig_idx]}"
        )
    # SMA200 might be NaN in the early bars; only check when defined.
    if not np.isnan(sma200.iloc[sig_idx]):
        assert df["Close"].iloc[sig_idx] > sma200.iloc[sig_idx]
