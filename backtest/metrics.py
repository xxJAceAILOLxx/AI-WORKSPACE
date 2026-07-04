"""Performance metrics for :class:`BacktestResult`.

All metrics are derived from the trade list and the equity curve stored
on the result object.  :func:`compute_metrics` returns a flat dict
suitable for reporting or ranking.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .engine import BacktestResult

TRADING_DAYS = 252


def _equity_series(result: BacktestResult) -> pd.Series:
    if not result.equity:
        return pd.Series(dtype=float)
    return pd.Series(result.equity, dtype=float)


def _daily_returns(result: BacktestResult) -> pd.Series:
    eq = _equity_series(result)
    if eq.empty:
        return eq
    return eq.pct_change().fillna(0.0)


def final_equity(result: BacktestResult) -> float:
    """Equity at the end of the backtest."""
    eq = _equity_series(result)
    if eq.empty:
        return float(result.ohlcv is not None and 0.0 or 0.0)
    return float(eq.iloc[-1])


def total_return(result: BacktestResult) -> float:
    """Cumulative return as a fraction of initial capital."""
    eq = _equity_series(result)
    if eq.empty or eq.iloc[0] == 0:
        return 0.0
    return float(eq.iloc[-1] / eq.iloc[0] - 1.0)


def cagr(result: BacktestResult) -> float:
    """Compound annual growth rate.

    Years are estimated from the equity curve length assuming 252 trading
    days per year.  Returns 0.0 if there is insufficient data.
    """
    eq = _equity_series(result)
    if eq.empty or eq.iloc[0] <= 0 or len(eq) < 2:
        return 0.0
    years = (len(eq) - 1) / TRADING_DAYS
    if years <= 0:
        return 0.0
    ratio = eq.iloc[-1] / eq.iloc[0]
    if ratio <= 0:
        return 0.0
    return float(ratio ** (1.0 / years) - 1.0)


def max_drawdown(result: BacktestResult) -> float:
    """Maximum peak-to-trough drawdown as a positive fraction (0.20 == 20%)."""
    eq = _equity_series(result)
    if eq.empty:
        return 0.0
    peaks = eq.cummax()
    drawdown = (eq - peaks) / peaks.replace(0, np.nan)
    drawdown = drawdown.dropna()
    if drawdown.empty:
        return 0.0
    # Return as a positive fraction (loss).
    return float(-drawdown.min())


def sharpe(result: BacktestResult, risk_free: float = 0.0) -> float:
    """Annualized Sharpe ratio from daily returns."""
    rets = _daily_returns(result)
    if rets.empty or rets.std(ddof=1) == 0:
        return 0.0
    excess = rets - risk_free / TRADING_DAYS
    return float(excess.mean() / excess.std(ddof=1) * math.sqrt(TRADING_DAYS))


def sortino(result: BacktestResult, risk_free: float = 0.0) -> float:
    """Annualized Sortino ratio using downside deviation only."""
    rets = _daily_returns(result)
    if rets.empty:
        return 0.0
    excess = rets - risk_free / TRADING_DAYS
    downside = excess[excess < 0]
    if downside.empty or downside.std(ddof=1) == 0:
        return 0.0
    return float(excess.mean() / downside.std(ddof=1) * math.sqrt(TRADING_DAYS))


def win_rate(result: BacktestResult) -> float:
    """Fraction of trades with positive PnL."""
    if not result.trades:
        return 0.0
    wins = sum(1 for t in result.trades if t.pnl > 0)
    return wins / len(result.trades)


def avg_win(result: BacktestResult) -> float:
    """Mean PnL of winning trades."""
    wins = [t.pnl for t in result.trades if t.pnl > 0]
    return float(np.mean(wins)) if wins else 0.0


def avg_loss(result: BacktestResult) -> float:
    """Mean PnL of losing trades (negative number)."""
    losses = [t.pnl for t in result.trades if t.pnl < 0]
    return float(np.mean(losses)) if losses else 0.0


def profit_factor(result: BacktestResult) -> float:
    """Gross profits divided by |gross losses|.  Inf if no losses; 0 if no wins."""
    gross_win = sum(t.pnl for t in result.trades if t.pnl > 0)
    gross_loss = -sum(t.pnl for t in result.trades if t.pnl < 0)
    if gross_loss == 0:
        return float("inf") if gross_win > 0 else 0.0
    return float(gross_win / gross_loss)


def expectancy(result: BacktestResult) -> float:
    """Expected dollar PnL per trade.

    ``= win_rate * avg_win + loss_rate * avg_loss``
    """
    n = len(result.trades)
    if n == 0:
        return 0.0
    return win_rate(result) * avg_win(result) + (1 - win_rate(result)) * avg_loss(result)


def avg_hold_days(result: BacktestResult) -> float:
    """Average holding period in trading days."""
    if not result.trades:
        return 0.0
    return float(np.mean([t.hold_days for t in result.trades]))


def trade_count(result: BacktestResult) -> int:
    """Number of closed trades."""
    return len(result.trades)


@dataclass
class Metrics:
    """Container for the standard set of performance metrics."""

    final_equity: float
    total_return: float
    cagr: float
    max_drawdown: float
    sharpe: float
    sortino: float
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    expectancy: float
    avg_hold_days: float
    trade_count: int
    extras: Dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, float]:
        d = {
            "final_equity": self.final_equity,
            "total_return": self.total_return,
            "cagr": self.cagr,
            "max_drawdown": self.max_drawdown,
            "sharpe": self.sharpe,
            "sortino": self.sortino,
            "win_rate": self.win_rate,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "profit_factor": self.profit_factor,
            "expectancy": self.expectancy,
            "avg_hold_days": self.avg_hold_days,
            "trade_count": float(self.trade_count),
        }
        d.update(self.extras)
        return d


def compute_metrics(
    result: BacktestResult,
    risk_free: float = 0.0,
    extras: Optional[Dict[str, float]] = None,
) -> Metrics:
    """Compute the standard metrics bundle for a :class:`BacktestResult`."""
    return Metrics(
        final_equity=final_equity(result),
        total_return=total_return(result),
        cagr=cagr(result),
        max_drawdown=max_drawdown(result),
        sharpe=sharpe(result, risk_free=risk_free),
        sortino=sortino(result, risk_free=risk_free),
        win_rate=win_rate(result),
        avg_win=avg_win(result),
        avg_loss=avg_loss(result),
        profit_factor=profit_factor(result),
        expectancy=expectancy(result),
        avg_hold_days=avg_hold_days(result),
        trade_count=trade_count(result),
        extras=dict(extras or {}),
    )


__all__ = [
    "TRADING_DAYS",
    "final_equity",
    "total_return",
    "cagr",
    "max_drawdown",
    "sharpe",
    "sortino",
    "win_rate",
    "avg_win",
    "avg_loss",
    "profit_factor",
    "expectancy",
    "avg_hold_days",
    "trade_count",
    "Metrics",
    "compute_metrics",
]
