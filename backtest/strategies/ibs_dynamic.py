"""IBS mean-reversion strategy on SPY with dynamic exits.

Entry: IBS < 0.20 AND Close > 200 SMA.
Exit: first to fire of
  1. Close > previous day's High (profit take)
  2. Trailing ATR(14) stop: Close < highest_close_since_entry - 2 * ATR(14)_entry
  3. 5-day max hold
"""

from __future__ import annotations

from typing import Tuple

import pandas as pd

from backtest import load_daily
from backtest.engine import BacktestResult, EngineState
from backtest.indicators import atr, ibs, sma

from ._common import DEFAULT_END, DEFAULT_SIZE_VALUE, DEFAULT_START, build_engine
from .registry import register


def _ibs_dynamic_exit(
    hold: int, prior_high: pd.Series, stop_mult: float = 2.0
):
    """Build dynamic exit rule with profit-take, trailing ATR stop, and max hold."""
    high_water: list[float] = [0.0]

    def rule(state: EngineState) -> None | Tuple[str, float]:
        close = float(state.bar["Close"])

        # Reset high-water on the first day of a new position.
        if state.days_held <= 1:
            high_water[0] = max(state.entry_price, close)
        else:
            high_water[0] = max(high_water[0], close)

        # 1. Profit take on close above prior day's high.
        if close > float(prior_high.iloc[state.idx]):
            return ("profit_take", 0.0)

        # 2. Trailing ATR stop.
        atr_entry = state.atr_entry
        if stop_mult > 0 and atr_entry > 0:
            stop_price = high_water[0] - stop_mult * atr_entry
            if close < stop_price:
                return ("atr_stop", 0.0)

        # 3. Max hold.
        if state.days_held >= hold:
            return (f"hold_{hold}", 0.0)

        return None

    return rule


@register("ibs_dynamic")
def ibs_dynamic(
    ticker: str = "SPY",
    start: str = DEFAULT_START,
    end: str = DEFAULT_END,
    threshold: float = 0.20,
    hold: int = 5,
    atr_stop_mult: float = 2.0,
    execution: str = "next_open",
    size_value: float = DEFAULT_SIZE_VALUE,
) -> BacktestResult:
    """IBS < ``threshold`` AND Close > 200 SMA; dynamic profit/ATR/hold exit."""
    ohlcv = load_daily(ticker, start, end)
    df = ohlcv.df
    sma200 = sma(df["Close"], 200)
    signal = (ibs(df) < threshold) & (df["Close"] > sma200)
    signal = signal.fillna(False)
    prior_high = df["High"].shift(1)
    # Pre-compute ATR so the engine has it available via EngineState.
    _ = atr(df, period=14)
    eng = build_engine(
        ohlcv, name="ibs_dynamic", execution=execution, size_value=size_value
    )
    eng.set_entry(signal).set_exit(
        _ibs_dynamic_exit(hold, prior_high, stop_mult=atr_stop_mult)
    )
    return eng.run()


__all__ = ["ibs_dynamic"]
