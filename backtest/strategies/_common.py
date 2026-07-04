"""Shared helpers for the mean-reversion strategy library.

Kept module-private (underscore prefix) so the public package surface is
just the registry and the strategy functions themselves.
"""

from __future__ import annotations

from typing import Tuple

from backtest import Engine, OHLCV, PERCENT_10BP


# Default backtest window per the unified framework plan.
DEFAULT_START: str = "2016-01-01"
DEFAULT_END: str = "2025-12-31"

# Default sizing and capital for all MR strategies.
DEFAULT_SIZE_VALUE: float = 0.95
DEFAULT_INITIAL_CAPITAL: float = 100_000.0


def hold_n_exit(n: int):
    """Build an exit-rule callback that closes the position after ``n`` days.

    The reason string is ``"hold_N"`` so tests can distinguish a planned
    time-based exit from a stop or end-of-data close.
    """

    def rule(state) -> None | Tuple[str, float]:
        if state.days_held >= n:
            return (f"hold_{n}", 0.0)
        return None

    return rule


def build_engine(
    ohlcv: OHLCV,
    name: str,
    execution: str = "next_open",
    size_value: float = DEFAULT_SIZE_VALUE,
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
) -> Engine:
    """Construct a fully-configured :class:`Engine` with the framework
    defaults: ``next_open`` execution, 0.95 percent-of-equity sizing, and
    the :data:`PERCENT_10BP` cost model.
    """
    return Engine(
        ohlcv,
        name=name,
        execution=execution,
        cost_model=PERCENT_10BP,
        initial_capital=initial_capital,
        size_policy="percent_of_equity",
        size_value=size_value,
    )


__all__ = [
    "DEFAULT_START",
    "DEFAULT_END",
    "DEFAULT_SIZE_VALUE",
    "DEFAULT_INITIAL_CAPITAL",
    "hold_n_exit",
    "build_engine",
]
