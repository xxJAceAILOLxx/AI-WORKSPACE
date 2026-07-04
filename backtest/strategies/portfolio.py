"""Mean-reversion portfolio strategy (Chunk 2c).

Implements the framework's :data:`mr_portfolio` strategy (originally
``all_strategies_backtest.py`` strategy 15).

The portfolio splits the initial capital into four equal slices and
runs each of four mean-reversion sub-strategies on its own slice using
the framework's event-driven engine:

* ``ibs_spy``        - IBS < 0.20 on SPY, 5-day hold.
* ``rsi2_mr``        - RSI(2) < 10 + Close > 200 SMA on SPY, 5-day hold.
* ``pct_b_mr``       - %B < 0.10 + Close > 200 SMA on SPY, 5-day hold.
* ``turn_of_month``  - last trading day of month on SPY, 4-day hold.

The combined equity curve is the **average of the four daily equity
values** at every bar.  The combined trade list is the union of the
sub-strategy trade lists; each trade is tagged with the
``sub_strategy`` field identifying which sub-strategy produced it.

The trade ``sub_strategy`` tag is attached as an attribute on the
existing :class:`~backtest.engine.Trade` dataclass.  The dataclass is
not frozen, so this does not violate the framework's invariants and is
discoverable from any consumer that iterates ``result.trades``.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import pandas as pd

from backtest import OHLCV, PERCENT_10BP, load_daily
from backtest.engine import BacktestResult, Engine, Trade
from backtest.indicators import ibs, pct_b, rsi, sma, turn_of_month

from ._common import (
    DEFAULT_END,
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_SIZE_VALUE,
    DEFAULT_START,
    hold_n_exit,
)
from .registry import REGISTRY, register


# Sub-strategy definitions: (label, signal_builder, hold_days).  The
# signal builder takes the SPY OHLCV DataFrame and returns a boolean
# Series aligned to its index.  We keep the logic inline (rather than
# invoking the registered strategies with kwargs) so that the per-slice
# ``initial_capital`` can flow into each :class:`Engine` directly -- the
# existing MR strategies only accept the framework-default capital.
_SUB_DEFS: Tuple[Tuple[str, int], ...] = (
    ("ibs_spy", 5),
    ("rsi2_mr", 5),
    ("pct_b_mr", 5),
    ("turn_of_month", 4),
)

SUB_STRATEGIES: Tuple[str, ...] = tuple(name for name, _ in _SUB_DEFS)


def _signal_for(name: str, df: pd.DataFrame, sma200: pd.Series) -> pd.Series:
    """Return the entry signal used by the named MR sub-strategy."""
    if name == "ibs_spy":
        return ibs(df) < 0.20
    if name == "rsi2_mr":
        return (rsi(df["Close"], 2) < 10.0) & (df["Close"] > sma200)
    if name == "pct_b_mr":
        return (pct_b(df) < 0.10) & (df["Close"] > sma200)
    if name == "turn_of_month":
        return turn_of_month(df.index, enter_last_n=1, hold_n=0)
    raise KeyError(f"unknown sub-strategy {name!r}")


def _average_equity_curves(curves: List[List[float]]) -> List[float]:
    """Element-wise mean of equal-length equity curves.

    All sub-strategies use the same SPY data and the same framework
    defaults, so their equity curves are expected to have the same
    length.  If a sub-strategy produced a shorter curve we truncate the
    combined result to the shortest common length to keep the averaging
    honest (rather than padding with zeros).
    """
    if not curves:
        return []
    min_len = min(len(c) for c in curves)
    if min_len == 0:
        return []
    combined: List[float] = []
    for i in range(min_len):
        combined.append(sum(c[i] for c in curves) / len(curves))
    return combined


def _tag_trades(
    trades: List[Trade],
    sub_name: str,
) -> List[Trade]:
    """Return the input trades with ``sub_strategy`` set on each one."""
    for t in trades:
        # Trade is a non-frozen dataclass so we can attach attributes.
        # Falling back to setattr keeps this safe even if a Trade is
        # converted to a dict-like wrapper in the future.
        setattr(t, "sub_strategy", sub_name)
    return trades


@register("mr_portfolio")
def mr_portfolio(
    ticker: str = "SPY",
    start: str = DEFAULT_START,
    end: str = DEFAULT_END,
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    execution: str = "next_open",
    size_value: float = DEFAULT_SIZE_VALUE,
) -> BacktestResult:
    """Run the four MR sub-strategies as an equal-weight portfolio.

    Parameters
    ----------
    ticker : str
        Underlying for every sub-strategy (defaults to ``SPY``; all four
        sub-strategies in this chunk are SPY-only).
    start, end : str
        ISO-format date bounds forwarded to each sub-strategy.
    initial_capital : float
        Total starting equity.  Divided evenly across the four
        sub-strategies.
    execution : str
        Forwarded to every sub-strategy.  All four use next-open
        execution by default.
    size_value : float
        Per-trade sizing fraction (defaults to 0.95).
    """
    ohlcv = load_daily(ticker, start, end)
    df = ohlcv.df
    sma200 = sma(df["Close"], 200)

    n_subs = len(_SUB_DEFS)
    slice_capital = initial_capital / float(n_subs)

    sub_results: Dict[str, BacktestResult] = {}
    missing: List[str] = []
    for sub_name, hold in _SUB_DEFS:
        try:
            signal = _signal_for(sub_name, df, sma200).fillna(False)
        except Exception as exc:  # noqa: BLE001 - defensive
            missing.append(f"{sub_name}: {exc}")
            continue
        eng = Engine(
            ohlcv,
            name=sub_name,
            execution=execution,
            cost_model=PERCENT_10BP,
            initial_capital=slice_capital,
            size_policy="percent_of_equity",
            size_value=size_value,
        )
        eng.set_entry(signal).set_exit(hold_n_exit(hold))
        sub_results[sub_name] = eng.run()

    if not sub_results:
        empty_ohlcv = OHLCV(
            ticker=ticker,
            df=pd.DataFrame(
                columns=["Open", "High", "Low", "Close", "Volume"]
            ).set_index(pd.DatetimeIndex([])),
        )
        return BacktestResult(
            name="mr_portfolio",
            trades=[],
            equity=[],
            ohlcv=empty_ohlcv,
            initial_capital=initial_capital,
            execution=execution,
            cost_model_name=PERCENT_10BP.name,
            config={
                "sub_strategies": list(SUB_STRATEGIES),
                "missing": missing,
                "note": "no sub-strategies produced results",
            },
        )

    combined_equity = _average_equity_curves(
        [r.equity for r in sub_results.values()]
    )

    # Collect tagged trades from every sub-strategy.  Sorting by entry
    # date makes the combined trade list easy to inspect.
    combined_trades: List[Trade] = []
    for sub_name, sub_res in sub_results.items():
        combined_trades.extend(_tag_trades(list(sub_res.trades), sub_name))
    combined_trades.sort(key=lambda t: t.entry_date)

    sub_trade_counts = {
        name: len(res.trades) for name, res in sub_results.items()
    }

    return BacktestResult(
        name="mr_portfolio",
        trades=combined_trades,
        equity=combined_equity,
        ohlcv=ohlcv,
        initial_capital=initial_capital,
        execution=execution,
        cost_model_name=PERCENT_10BP.name,
        config={
            "sub_strategies": list(sub_results.keys()),
            "slice_capital": slice_capital,
            "missing": missing,
            "sub_trade_counts": sub_trade_counts,
            "size_policy": "percent_of_equity",
            "size_value": size_value,
            "cost_model": PERCENT_10BP.name,
        },
    )


__all__ = ["mr_portfolio", "SUB_STRATEGIES"]
