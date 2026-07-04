"""QQQ dual moving-average trend strategy (Chunk 2c).

Implements the framework's :data:`qqq_dual_ma` strategy (originally
``all_strategies_backtest.py`` strategy 9).

* Entry  : ``Close > 50 SMA`` AND ``Close > 200 SMA``.
* Exit   : ``Close < 50 SMA`` (a single condition; the position is held
  as long as the trend remains intact).
* Sizing : 95% of equity per trade.
* Cost   : 0.1% round-trip (PERCENT_10BP).

The exit is implemented as an engine rule callback so the existing
:class:`backtest.Engine` can drive the backtest end-to-end.  When the
close at bar ``t`` falls below the 50-day SMA the rule returns
``("ma_exit", 0.0)`` and the engine books the trade.
"""

from __future__ import annotations

import pandas as pd

from backtest import load_daily
from backtest.engine import BacktestResult, EngineState
from backtest.indicators import sma

from ._common import DEFAULT_END, DEFAULT_SIZE_VALUE, DEFAULT_START, build_engine
from .registry import register


@register("qqq_dual_ma")
def qqq_dual_ma(
    ticker: str = "QQQ",
    start: str = DEFAULT_START,
    end: str = DEFAULT_END,
    short_window: int = 50,
    long_window: int = 200,
    execution: str = "next_open",
    size_value: float = DEFAULT_SIZE_VALUE,
) -> BacktestResult:
    """Buy ``ticker`` when ``Close > SMA(short)`` AND ``Close > SMA(long)``;
    exit on the first bar where ``Close < SMA(short)``.
    """
    ohlcv = load_daily(ticker, start, end)
    df = ohlcv.df

    sma_short = sma(df["Close"], short_window)
    sma_long = sma(df["Close"], long_window)

    entry_signal = (df["Close"] > sma_short) & (df["Close"] > sma_long)
    # The warm-up region of either SMA is NaN, which is treated as "not
    # above both averages" -> not a valid entry.  fillna(False) makes the
    # signal safe for the engine's boolean checks.
    entry_signal = entry_signal.fillna(False)

    def exit_rule(state: EngineState):
        short_val = sma_short.iloc[state.idx]
        if pd.notna(short_val) and float(state.bar["Close"]) < float(short_val):
            return ("ma_exit", 0.0)
        return None

    eng = build_engine(
        ohlcv,
        name="qqq_dual_ma",
        execution=execution,
        size_value=size_value,
    )
    eng.set_entry(entry_signal).set_exit(exit_rule)
    result = eng.run()
    result.config["short_window"] = short_window
    result.config["long_window"] = long_window
    return result


__all__ = ["qqq_dual_ma"]
