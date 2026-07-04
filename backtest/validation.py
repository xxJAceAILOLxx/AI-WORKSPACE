"""Walk-forward validation and Monte Carlo helpers.

These utilities let the framework check whether a backtest is robust
without leaking look-ahead bias:

* :func:`walk_forward` splits the OHLCV into rolling train/test windows
  and yields each pair along with the indices.
* :func:`monte_carlo` shuffles the trade list to estimate the
  distribution of equity-curve outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterator, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from .data import OHLCV
from .engine import BacktestResult


# ---------------------------------------------------------------------------
# Walk-forward
# ---------------------------------------------------------------------------


@dataclass
class WalkForwardSplit:
    """A single train/test window from a walk-forward run."""

    fold: int
    train: pd.DataFrame
    test: pd.DataFrame
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


def walk_forward(
    ohlcv: OHLCV,
    n_splits: int = 4,
    train_frac: float = 0.7,
    min_train_bars: int = 60,
    anchored: bool = False,
) -> List[WalkForwardSplit]:
    """Split ``ohlcv`` into sequential train/test windows.

    Parameters
    ----------
    n_splits:
        Number of test windows to produce.
    train_frac:
        Fraction of the (expanding) history allocated to training at each
        fold.  ``0.7`` is a sensible default that gives the test window
        roughly 30 % of the remaining bars.
    min_train_bars:
        Skip folds where the training window would have fewer than this
        many bars.
    anchored:
        If ``True`` the training window always starts at the first bar of
        the series (expanding window).  If ``False`` (default) each fold
        uses a rolling window of fixed length ``train_frac`` of the
        current history.

    Returns
    -------
    list[WalkForwardSplit]
        Empty list if the data is too small to produce ``n_splits`` folds.
    """
    df = ohlcv.df
    n = len(df)
    if n < min_train_bars + n_splits:
        return []

    splits: List[WalkForwardSplit] = []
    # Reserve the last `n_splits` chunks for test, distributed across the data.
    test_size = (n - min_train_bars) // n_splits
    if test_size < 1:
        return []

    if anchored:
        # Expanding window: each fold's training starts at 0.
        train_start_idx = 0
    else:
        # Rolling window of fixed length.
        train_start_idx = max(0, min_train_bars - int(min_train_bars * train_frac))

    cursor = min_train_bars
    for fold in range(n_splits):
        train_end_idx = cursor
        test_end_idx = min(n, train_end_idx + test_size)
        if test_end_idx <= train_end_idx:
            break

        if not anchored:
            train_start_idx = max(0, train_end_idx - int(min_train_bars * train_frac))
            # Ensure the rolling window has a minimum size.
            train_start_idx = min(train_start_idx, train_end_idx - min_train_bars)

        train = df.iloc[train_start_idx:train_end_idx].copy()
        test = df.iloc[train_end_idx:test_end_idx].copy()

        splits.append(
            WalkForwardSplit(
                fold=fold,
                train=train,
                test=test,
                train_start=df.index[train_start_idx],
                train_end=df.index[train_end_idx - 1],
                test_start=df.index[train_end_idx],
                test_end=df.index[test_end_idx - 1],
            )
        )
        cursor = test_end_idx

    return splits


def walk_forward_run(
    ohlcv: OHLCV,
    runner: Callable[[pd.DataFrame, pd.DataFrame], BacktestResult],
    n_splits: int = 4,
    train_frac: float = 0.7,
    min_train_bars: int = 60,
    anchored: bool = False,
) -> List[Tuple[WalkForwardSplit, BacktestResult]]:
    """Run :func:`walk_forward` and execute ``runner`` on each split.

    ``runner(train_df, test_df)`` should return a :class:`BacktestResult`
    constructed from the test fold (it can use the train fold for any
    parameter estimation it needs).
    """
    splits = walk_forward(
        ohlcv,
        n_splits=n_splits,
        train_frac=train_frac,
        min_train_bars=min_train_bars,
        anchored=anchored,
    )
    out: List[Tuple[WalkForwardSplit, BacktestResult]] = []
    for split in splits:
        result = runner(split.train, split.test)
        out.append((split, result))
    return out


# ---------------------------------------------------------------------------
# Monte Carlo
# ---------------------------------------------------------------------------


@dataclass
class MonteCarloResult:
    """Summary statistics of a Monte Carlo simulation."""

    n_sims: int
    final_equity_mean: float
    final_equity_median: float
    final_equity_std: float
    final_equity_ci_low: float
    final_equity_ci_high: float
    max_drawdown_mean: float
    max_drawdown_ci_low: float
    max_drawdown_ci_high: float
    ruin_probability: float
    sample_final_equities: List[float] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "n_sims": self.n_sims,
            "final_equity_mean": self.final_equity_mean,
            "final_equity_median": self.final_equity_median,
            "final_equity_std": self.final_equity_std,
            "final_equity_ci_low": self.final_equity_ci_low,
            "final_equity_ci_high": self.final_equity_ci_high,
            "max_drawdown_mean": self.max_drawdown_mean,
            "max_drawdown_ci_low": self.max_drawdown_ci_low,
            "max_drawdown_ci_high": self.max_drawdown_ci_high,
            "ruin_probability": self.ruin_probability,
        }


def _equity_curve_from_pnls(
    pnls: Sequence[float], initial_capital: float
) -> np.ndarray:
    curve = np.empty(len(pnls) + 1, dtype=float)
    curve[0] = initial_capital
    for i, p in enumerate(pnls):
        curve[i + 1] = curve[i] + p
    return curve


def _curve_drawdown(curve: np.ndarray) -> float:
    if len(curve) == 0:
        return 0.0
    peaks = np.maximum.accumulate(curve)
    dd = (curve - peaks) / np.where(peaks == 0, 1, peaks)
    return float(-dd.min()) if len(dd) else 0.0


def monte_carlo(
    result: BacktestResult,
    n_sims: int = 1000,
    initial_capital: float = 100_000.0,
    seed: Optional[int] = 42,
    ruin_fraction: float = 0.5,
) -> MonteCarloResult:
    """Bootstrap the trade list to estimate outcome robustness.

    The function samples ``trades`` with replacement ``n_sims`` times,
    reconstructs an equity curve from each sample, and reports summary
    statistics on the final equity and the maximum drawdown.
    """
    pnls = np.array([t.pnl for t in result.trades], dtype=float)
    n_trades = len(pnls)
    if n_trades == 0:
        return MonteCarloResult(
            n_sims=n_sims,
            final_equity_mean=initial_capital,
            final_equity_median=initial_capital,
            final_equity_std=0.0,
            final_equity_ci_low=initial_capital,
            final_equity_ci_high=initial_capital,
            max_drawdown_mean=0.0,
            max_drawdown_ci_low=0.0,
            max_drawdown_ci_high=0.0,
            ruin_probability=0.0,
        )

    rng = np.random.default_rng(seed)
    finals = np.empty(n_sims, dtype=float)
    drawdowns = np.empty(n_sims, dtype=float)
    ruin_threshold = initial_capital * (1.0 - ruin_fraction)
    ruin_count = 0

    for i in range(n_sims):
        sample = rng.choice(pnls, size=n_trades, replace=True)
        curve = _equity_curve_from_pnls(sample, initial_capital)
        finals[i] = curve[-1]
        drawdowns[i] = _curve_drawdown(curve)
        if curve[-1] <= ruin_threshold:
            ruin_count += 1

    ci_low, ci_high = np.percentile(finals, [2.5, 97.5])
    dd_low, dd_high = np.percentile(drawdowns, [2.5, 97.5])

    return MonteCarloResult(
        n_sims=n_sims,
        final_equity_mean=float(finals.mean()),
        final_equity_median=float(np.median(finals)),
        final_equity_std=float(finals.std(ddof=1)),
        final_equity_ci_low=float(ci_low),
        final_equity_ci_high=float(ci_high),
        max_drawdown_mean=float(drawdowns.mean()),
        max_drawdown_ci_low=float(dd_low),
        max_drawdown_ci_high=float(dd_high),
        ruin_probability=ruin_count / n_sims,
        sample_final_equities=finals[: min(50, n_sims)].tolist(),
    )


def monte_carlo_paths(
    result: BacktestResult,
    n_sims: int = 1000,
    initial_capital: float = 100_000.0,
    seed: Optional[int] = 42,
) -> np.ndarray:
    """Return the full ``(n_sims, n_trades + 1)`` array of simulated equity paths."""
    pnls = np.array([t.pnl for t in result.trades], dtype=float)
    n_trades = len(pnls)
    if n_trades == 0:
        return np.empty((n_sims, 1), dtype=float)
    rng = np.random.default_rng(seed)
    paths = np.empty((n_sims, n_trades + 1), dtype=float)
    paths[:, 0] = initial_capital
    for i in range(n_sims):
        sample = rng.choice(pnls, size=n_trades, replace=True)
        paths[i, 1:] = np.cumsum(sample) + initial_capital
    return paths


__all__ = [
    "WalkForwardSplit",
    "walk_forward",
    "walk_forward_run",
    "MonteCarloResult",
    "monte_carlo",
    "monte_carlo_paths",
]
