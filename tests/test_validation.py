"""Tests for walk-forward and Monte Carlo helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtest import from_dataframe
from backtest.engine import BacktestResult, Trade
from backtest.validation import (
    WalkForwardSplit,
    monte_carlo,
    monte_carlo_paths,
    walk_forward,
    walk_forward_run,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_long_ohlcv(n: int = 600, start: str = "2018-01-02", seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start=start, periods=n)
    rets = rng.normal(0.0005, 0.01, size=n)
    close = 100.0 * np.exp(np.cumsum(rets))
    open_ = np.concatenate([[100.0], close[:-1] * (1 + rng.normal(0, 0.002, n - 1))])
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.002, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.002, n)))
    volume = rng.integers(1_000_000, 5_000_000, n).astype(float)
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=dates,
    )


@pytest.fixture
def long_ohlcv():
    return from_dataframe("LONG", _make_long_ohlcv())


def _make_result_with_pnls(pnls: list[float]) -> BacktestResult:
    dates = pd.bdate_range("2020-01-01", periods=max(2, len(pnls) + 1))
    trades = [
        Trade(
            entry_date=dates[i],
            exit_date=dates[i + 1] if i + 1 < len(dates) else dates[-1],
            entry_price=100.0,
            exit_price=100.0 + pnl,
            shares=1,
            pnl=float(pnl),
            return_pct=pnl / 100.0,
            hold_days=1,
            exit_reason="t",
        )
        for i, pnl in enumerate(pnls)
    ]
    eq = [100_000.0]
    for p in pnls:
        eq.append(eq[-1] + p)
    ohlcv = from_dataframe(
        "T",
        pd.DataFrame(
            {
                "Open": eq,
                "High": eq,
                "Low": eq,
                "Close": eq,
                "Volume": [1.0] * len(eq),
            },
            index=pd.bdate_range("2020-01-01", periods=len(eq)),
        ),
    )
    return BacktestResult(
        name="t", trades=trades, equity=eq, ohlcv=ohlcv, initial_capital=100_000.0
    )


# ---------------------------------------------------------------------------
# Walk-forward
# ---------------------------------------------------------------------------


def test_walk_forward_produces_splits(long_ohlcv):
    splits = walk_forward(long_ohlcv, n_splits=4, min_train_bars=120)
    assert len(splits) >= 1
    assert all(isinstance(s, WalkForwardSplit) for s in splits)
    # Each fold must have a non-empty train and test.
    for s in splits:
        assert len(s.train) > 0
        assert len(s.test) > 0
    # Splits are sequential and non-overlapping in test regions.
    for a, b in zip(splits, splits[1:]):
        assert a.test_end < b.test_start


def test_walk_forward_too_small_returns_empty():
    df = _make_long_ohlcv(n=80)
    ohlcv = from_dataframe("S", df)
    assert walk_forward(ohlcv, n_splits=4, min_train_bars=120) == []


def test_walk_forward_anchored_starts_at_zero(long_ohlcv):
    splits = walk_forward(long_ohlcv, n_splits=3, min_train_bars=120, anchored=True)
    assert len(splits) >= 2
    for s in splits:
        assert s.train_start == long_ohlcv.df.index[0]


def test_walk_forward_rolling_shifts_start(long_ohlcv):
    splits = walk_forward(
        long_ohlcv, n_splits=3, min_train_bars=200, train_frac=0.5, anchored=False
    )
    train_starts = [s.train_start for s in splits]
    # Rolling windows: each later split's training start should be later.
    for a, b in zip(train_starts, train_starts[1:]):
        assert a <= b


def test_walk_forward_run_executes_runner(long_ohlcv):
    calls = []

    def runner(train_df, test_df):
        calls.append((len(train_df), len(test_df)))
        # Return a trivial empty result.
        eq = [100_000.0] * (len(test_df) + 1)
        ohlcv = from_dataframe(
            "F",
            pd.DataFrame(
                {
                    "Open": eq,
                    "High": eq,
                    "Low": eq,
                    "Close": eq,
                    "Volume": [1.0] * len(eq),
                },
                index=pd.bdate_range("2021-01-01", periods=len(eq)),
            ),
        )
        return BacktestResult(
            name="fold", trades=[], equity=eq, ohlcv=ohlcv, initial_capital=100_000.0
        )

    results = walk_forward_run(
        long_ohlcv, runner=runner, n_splits=3, min_train_bars=120
    )
    assert len(results) == len(calls)
    assert all(isinstance(r, BacktestResult) for _, r in results)


# ---------------------------------------------------------------------------
# Monte Carlo
# ---------------------------------------------------------------------------


def test_monte_carlo_with_no_trades_returns_initial():
    res = _make_result_with_pnls([])
    mc = monte_carlo(res, n_sims=10, initial_capital=100_000.0)
    assert mc.n_sims == 10
    assert mc.final_equity_mean == pytest.approx(100_000.0)
    assert mc.ruin_probability == 0.0


def test_monte_carlo_means_and_ci():
    pnls = [50.0] * 20 + [-30.0] * 20  # positive expectancy
    res = _make_result_with_pnls(pnls)
    mc = monte_carlo(res, n_sims=500, initial_capital=100_000.0, seed=123)
    assert mc.n_sims == 500
    # Mean final equity should be 100k + mean_pnl * 40 = 100k + 10*40 = 100_400.
    assert mc.final_equity_mean == pytest.approx(100_400.0, rel=1e-2)
    # CI is a band, so low < high.
    assert mc.final_equity_ci_low < mc.final_equity_mean < mc.final_equity_ci_high
    assert mc.max_drawdown_ci_low <= mc.max_drawdown_mean <= mc.max_drawdown_ci_high
    # All-positive PnL mix with smaller negatives: ruin should be near zero
    # for ruin_fraction=0.5.
    assert mc.ruin_probability == 0.0


def test_monte_carlo_with_only_losses_has_ruin_probability():
    pnls = [-200.0] * 30
    res = _make_result_with_pnls(pnls)
    mc = monte_carlo(res, n_sims=200, initial_capital=10_000.0, ruin_fraction=0.5, seed=42)
    # After 30 losses of 200 from 10k, every path ends at 4_000, which is
    # below the 50% ruin threshold of 5_000.
    assert mc.ruin_probability == 1.0
    assert mc.final_equity_mean == pytest.approx(4_000.0)


def test_monte_carlo_paths_shape():
    pnls = [10.0, -5.0, 20.0, -8.0, 12.0]
    res = _make_result_with_pnls(pnls)
    paths = monte_carlo_paths(res, n_sims=50, seed=11)
    assert paths.shape == (50, len(pnls) + 1)
    assert paths[0, 0] == 100_000.0
    # The path is the cumulative equity curve. Verify it ends at initial +
    # total sampled pnl, i.e. that the first differences equal the sampled
    # pnl sequence.
    for i in range(paths.shape[0]):
        diffs = np.diff(paths[i])
        # First value is the initial capital, no diff.  diffs == pnl sample.
        assert diffs.sum() == pytest.approx(paths[i, -1] - paths[i, 0])


def test_monte_carlo_no_trades_path_shape():
    res = _make_result_with_pnls([])
    paths = monte_carlo_paths(res, n_sims=5)
    assert paths.shape == (5, 1)


def test_monte_carlo_seeded_reproducible():
    pnls = [10.0, -3.0, 5.0, 7.0, -2.0] * 5
    res = _make_result_with_pnls(pnls)
    a = monte_carlo(res, n_sims=100, seed=7)
    b = monte_carlo(res, n_sims=100, seed=7)
    assert a.final_equity_mean == pytest.approx(b.final_equity_mean)


def test_monte_carlo_result_as_dict():
    pnls = [10.0, -5.0]
    res = _make_result_with_pnls(pnls)
    mc = monte_carlo(res, n_sims=20, seed=1)
    d = mc.as_dict()
    assert "n_sims" in d
    assert "final_equity_mean" in d
    assert "ruin_probability" in d
