"""Tests for the metrics module."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from backtest import from_dataframe
from backtest.engine import BacktestResult, Trade
from backtest.metrics import (
    Metrics,
    avg_hold_days,
    avg_loss,
    avg_win,
    cagr,
    compute_metrics,
    expectancy,
    final_equity,
    max_drawdown,
    profit_factor,
    sharpe,
    sortino,
    total_return,
    trade_count,
    win_rate,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result(
    pnls: list[float],
    hold_days: list[int] | None = None,
    initial_capital: float = 100_000.0,
    equity: list[float] | None = None,
) -> BacktestResult:
    """Build a BacktestResult from a list of PnL values."""
    dates = pd.bdate_range("2020-01-01", periods=max(2, len(pnls) + 1))
    trades = []
    for i, pnl in enumerate(pnls):
        entry_date = dates[i]
        exit_date = dates[i + 1] if i + 1 < len(dates) else dates[-1]
        trades.append(
            Trade(
                entry_date=entry_date,
                exit_date=exit_date,
                entry_price=100.0,
                exit_price=100.0 + pnl,
                shares=1,
                pnl=float(pnl),
                return_pct=pnl / 100.0,
                hold_days=(hold_days[i] if hold_days else 1),
                exit_reason="test",
            )
        )
    if equity is None:
        eq = [initial_capital]
        running = initial_capital
        for p in pnls:
            running += p
            eq.append(running)
    else:
        eq = list(equity)

    ohlcv = from_dataframe(
        "TEST",
        pd.DataFrame(
            {
                "Open": [100.0] * len(eq),
                "High": [101.0] * len(eq),
                "Low": [99.0] * len(eq),
                "Close": [100.0] * len(eq),
                "Volume": [1_000_000.0] * len(eq),
            },
            index=pd.bdate_range("2020-01-01", periods=len(eq)),
        ),
    )
    return BacktestResult(
        name="t",
        trades=trades,
        equity=eq,
        ohlcv=ohlcv,
        initial_capital=initial_capital,
    )


# ---------------------------------------------------------------------------
# Trade-based metrics
# ---------------------------------------------------------------------------


def test_win_rate_all_wins():
    res = _make_result([100.0, 50.0, 25.0])
    assert win_rate(res) == 1.0


def test_win_rate_mixed():
    res = _make_result([100.0, -50.0, 25.0, -10.0])
    assert win_rate(res) == 0.5


def test_avg_win_loss():
    res = _make_result([100.0, 50.0, -40.0, -20.0])
    assert avg_win(res) == pytest.approx(75.0)
    assert avg_loss(res) == pytest.approx(-30.0)


def test_profit_factor():
    res = _make_result([100.0, 50.0, -40.0, -10.0])
    assert profit_factor(res) == pytest.approx(150.0 / 50.0)


def test_profit_factor_no_losses_is_inf():
    res = _make_result([10.0, 20.0])
    assert profit_factor(res) == float("inf")


def test_profit_factor_no_wins_is_zero():
    res = _make_result([-10.0, -20.0])
    assert profit_factor(res) == 0.0


def test_expectancy_zero_sum_zero():
    res = _make_result([100.0, -100.0])
    assert expectancy(res) == pytest.approx(0.0)


def test_avg_hold_days():
    res = _make_result([10.0, -5.0, 20.0], hold_days=[1, 2, 3])
    assert avg_hold_days(res) == pytest.approx(2.0)


def test_trade_count():
    res = _make_result([10.0, -5.0, 20.0])
    assert trade_count(res) == 3


# ---------------------------------------------------------------------------
# Equity-based metrics
# ---------------------------------------------------------------------------


def test_final_equity_and_total_return():
    res = _make_result([1000.0, 500.0, -200.0], initial_capital=10_000.0)
    assert final_equity(res) == pytest.approx(11_300.0)
    assert total_return(res) == pytest.approx(0.13)


def test_cagr_one_year():
    # 100k -> 110k over 252 trading days = 10% CAGR
    eq = [100_000.0] + [100_000.0 + (10_000.0 * i / 251.0) for i in range(1, 252)]
    ohlcv = from_dataframe(
        "X",
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
    res = BacktestResult(name="x", trades=[], equity=eq, ohlcv=ohlcv, initial_capital=100_000.0)
    assert cagr(res) == pytest.approx(0.10, abs=1e-3)


def test_max_drawdown_known():
    # Equity: 100, 120, 90, 95 -> peak 120, trough 90 -> DD = (90-120)/120 = -0.25
    res = _make_result([], equity=[100.0, 120.0, 90.0, 95.0])
    assert max_drawdown(res) == pytest.approx(0.25)


def test_max_drawdown_zero_for_monotonic():
    res = _make_result([], equity=[100.0, 110.0, 120.0, 130.0])
    assert max_drawdown(res) == 0.0


def test_sharpe_zero_vol():
    res = _make_result([], equity=[100.0] * 100)
    assert sharpe(res) == 0.0


def test_sharpe_positive_for_uptrend():
    eq = [100_000.0 + 100.0 * i for i in range(252)]
    ohlcv = from_dataframe(
        "X",
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
    res = BacktestResult(name="x", trades=[], equity=eq, ohlcv=ohlcv, initial_capital=100_000.0)
    # Constant uptrend -> high Sharpe, but with tiny variance -> very large number.
    assert sharpe(res) > 5.0


def test_sortino_handles_no_downside():
    # Monotonic uptrend: no negative returns -> Sortino is 0.
    res = _make_result([], equity=[100.0, 110.0, 120.0, 130.0])
    assert sortino(res) == 0.0


# ---------------------------------------------------------------------------
# compute_metrics bundle
# ---------------------------------------------------------------------------


def test_compute_metrics_keys():
    res = _make_result([100.0, -50.0, 25.0])
    m = compute_metrics(res)
    assert isinstance(m, Metrics)
    d = m.as_dict()
    expected_keys = {
        "final_equity", "total_return", "cagr", "max_drawdown",
        "sharpe", "sortino", "win_rate", "avg_win", "avg_loss",
        "profit_factor", "expectancy", "avg_hold_days", "trade_count",
    }
    assert expected_keys.issubset(set(d.keys()))
    assert d["trade_count"] == 3
    assert d["win_rate"] == pytest.approx(2 / 3)


def test_compute_metrics_extras_merge():
    res = _make_result([100.0])
    m = compute_metrics(res, extras={"custom": 42.0})
    assert m.as_dict()["custom"] == 42.0


def test_compute_metrics_empty_result():
    res = _make_result([])
    m = compute_metrics(res)
    assert m.trade_count == 0
    assert m.win_rate == 0.0
    assert m.profit_factor == 0.0
    assert m.avg_hold_days == 0.0
