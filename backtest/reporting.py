"""Text reporting helpers for backtest results.

This module contains lightweight printers used by CLI runners and tests.
There is no third-party rendering dependency — output is plain text.
"""

from __future__ import annotations

from typing import Iterable, List, Sequence

from .engine import BacktestResult
from .metrics import Metrics, compute_metrics


_METRIC_FIELDS: Sequence[tuple[str, str]] = (
    ("trade_count", "Trades"),
    ("total_return", "Total Return"),
    ("cagr", "CAGR"),
    ("max_drawdown", "Max Drawdown"),
    ("sharpe", "Sharpe"),
    ("sortino", "Sortino"),
    ("win_rate", "Win Rate"),
    ("avg_win", "Avg Win"),
    ("avg_loss", "Avg Loss"),
    ("profit_factor", "Profit Factor"),
    ("expectancy", "Expectancy"),
    ("avg_hold_days", "Avg Hold (d)"),
    ("final_equity", "Final Equity"),
)


def _fmt_pct(x: float) -> str:
    if x is None or (isinstance(x, float) and (x != x)):
        return "nan"
    return f"{x * 100:>9.2f}%"


def _fmt_num(x: float, digits: int = 2) -> str:
    if x is None or (isinstance(x, float) and (x != x)):
        return "nan"
    if abs(x) >= 1e6:
        return f"{x:>12,.0f}"
    if abs(x) >= 1e3:
        return f"{x:>12,.1f}"
    return f"{x:>12.{digits}f}"


def _format(field: str, value: float) -> str:
    if field in {"total_return", "cagr", "max_drawdown", "win_rate"}:
        return _fmt_pct(value)
    if field in {"avg_win", "avg_loss", "expectancy", "final_equity"}:
        return _fmt_num(value, digits=2)
    if field == "trade_count":
        return f"{int(value):>12d}"
    if field == "avg_hold_days":
        return _fmt_num(value, digits=1)
    return _fmt_num(value, digits=3)


def print_result(result: BacktestResult, metrics: Metrics | None = None) -> None:
    """Print a single result as a labeled metrics table."""
    if metrics is None:
        metrics = compute_metrics(result)

    print(f"=== {result.name} ({result.ohlcv.ticker}) ===")
    print(f"Period: {result.ohlcv.dates[0].date()} -> {result.ohlcv.dates[-1].date()}"
          f"  ({len(result.ohlcv.df)} bars)")
    print(f"{'Metric':<20}{'Value':>14}")
    print("-" * 34)
    d = metrics.as_dict()
    for field, label in _METRIC_FIELDS:
        print(f"{label:<20}{_format(field, d[field]):>14}")


def print_ranking(
    results: Iterable[BacktestResult],
    sort_by: str = "profit_factor",
    top: int | None = None,
) -> None:
    """Print a ranked table of multiple results.

    ``sort_by`` accepts any key in :meth:`Metrics.as_dict` or ``"name"``.
    """
    rows: List[tuple[str, Metrics]] = []
    for r in results:
        m = compute_metrics(r)
        rows.append((r.name, m))

    if sort_by != "name":
        rows.sort(
            key=lambda rm: (
                -float("inf") if (rm[1].as_dict().get(sort_by) != rm[1].as_dict().get(sort_by))
                else rm[1].as_dict().get(sort_by, 0.0)
            ),
            reverse=False,
        )
        # Sort by descending value for numeric metrics (higher is better).
        rows.sort(key=lambda rm: rm[1].as_dict().get(sort_by, 0.0), reverse=True)
    else:
        rows.sort(key=lambda rm: rm[0])

    if top is not None:
        rows = rows[:top]

    cols = [
        ("name", "Strategy", 22),
        ("trade_count", "Trades", 7),
        ("total_return", "TotRet", 9),
        ("cagr", "CAGR", 9),
        ("max_drawdown", "MaxDD", 9),
        ("sharpe", "Sharpe", 8),
        ("win_rate", "Win%", 9),
        ("profit_factor", "PF", 8),
        ("avg_hold_days", "Hold", 7),
    ]

    header = " ".join(f"{label:>{w}}" for _, label, w in cols)
    print(header)
    print("-" * len(header))
    for name, m in rows:
        d = m.as_dict()
        line_parts: list[str] = [f"{name[:cols[0][2]-1]:<{cols[0][2]}}"]
        for field, _, w in cols[1:]:
            v = d.get(field, 0.0)
            if field in {"total_return", "cagr", "max_drawdown", "win_rate"}:
                line_parts.append(f"{v*100:>{w}.2f}%")
            elif field == "trade_count":
                line_parts.append(f"{int(v):>{w}d}")
            elif field == "avg_hold_days":
                line_parts.append(f"{v:>{w}.1f}")
            else:
                line_parts.append(f"{v:>{w}.2f}")
        print(" ".join(line_parts))


__all__ = ["print_result", "print_ranking"]
