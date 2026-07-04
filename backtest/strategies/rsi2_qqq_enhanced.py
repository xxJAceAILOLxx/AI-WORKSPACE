"""Enhanced RSI(2) mean-reversion strategy on QQQ.

Adds a prior-day-down confirmation filter and a dynamic profit-taking
exit (Close > previous day's High) to the classic RSI(2) setup.
"""

from __future__ import annotations

from typing import Tuple

import pandas as pd

from backtest import load_daily
from backtest.engine import BacktestResult, EngineState
from backtest.indicators import rsi, sma

from ._common import DEFAULT_END, DEFAULT_SIZE_VALUE, DEFAULT_START, build_engine
from .registry import register


def _rsi2_qqq_exit(hold: int, prior_high: pd.Series):
    """Build exit rule: take profit on Close > prior High, else hold ``hold`` days."""

    def rule(state: EngineState) -> None | Tuple[str, float]:
        if float(state.bar["Close"]) > float(prior_high.iloc[state.idx]):
            return ("profit_take", 0.0)
        if state.days_held >= hold:
            return (f"hold_{hold}", 0.0)
        return None

    return rule


@register("rsi2_qqq_enhanced")
def rsi2_qqq_enhanced(
    ticker: str = "QQQ",
    start: str = DEFAULT_START,
    end: str = DEFAULT_END,
    rsi_threshold: float = 10.0,
    hold: int = 5,
    execution: str = "next_open",
    size_value: float = DEFAULT_SIZE_VALUE,
) -> BacktestResult:
    """RSI(2) < ``rsi_threshold`` AND Close > 200 SMA AND prior-day-down;
    exit on Close > prior High or ``hold`` days.
    """
    ohlcv = load_daily(ticker, start, end)
    df = ohlcv.df
    sma200 = sma(df["Close"], 200)
    rsi2 = rsi(df["Close"], period=2)
    prior_day_down = df["Close"].shift(1) < df["Close"].shift(2)
    signal = (rsi2 < rsi_threshold) & (df["Close"] > sma200) & prior_day_down
    signal = signal.fillna(False)
    prior_high = df["High"].shift(1)
    eng = build_engine(
        ohlcv, name="rsi2_qqq_enhanced", execution=execution, size_value=size_value
    )
    eng.set_entry(signal).set_exit(_rsi2_qqq_exit(hold, prior_high))
    return eng.run()


__all__ = ["rsi2_qqq_enhanced"]
