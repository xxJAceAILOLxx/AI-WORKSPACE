"""Multiple consecutive down-days mean-reversion strategy on SPY.

Enter when the close-down streak reaches 5+ days AND Close > 200 SMA,
hold for 5 days.
"""

from __future__ import annotations

from backtest import load_daily
from backtest.engine import BacktestResult
from backtest.indicators import down_streak, sma

from ._common import DEFAULT_END, DEFAULT_SIZE_VALUE, DEFAULT_START, build_engine, hold_n_exit
from .registry import register


@register("multiple_days_down")
def multiple_days_down(
    ticker: str = "SPY",
    start: str = DEFAULT_START,
    end: str = DEFAULT_END,
    streak_threshold: int = 5,
    hold: int = 5,
    execution: str = "next_open",
    size_value: float = DEFAULT_SIZE_VALUE,
) -> BacktestResult:
    """Enter when down streak reaches ``streak_threshold``+ days AND Close > 200 SMA.

    The framework's :func:`down_streak` returns a non-negative count of
    consecutive down closes, so we compare ``streak >= threshold``.
    """
    ohlcv = load_daily(ticker, start, end)
    df = ohlcv.df
    sma200 = sma(df["Close"], 200)
    streak = down_streak(df["Close"])
    signal = (streak >= streak_threshold) & (df["Close"] > sma200)
    signal = signal.fillna(False)
    eng = build_engine(ohlcv, name="multiple_days_down", execution=execution, size_value=size_value)
    eng.set_entry(signal).set_exit(hold_n_exit(hold))
    return eng.run()


__all__ = ["multiple_days_down"]
