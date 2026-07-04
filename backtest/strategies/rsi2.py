"""RSI(2) mean-reversion strategy on SPY.

Enter when RSI(2) < 10 AND Close > 200 SMA, hold for 5 days.
"""

from __future__ import annotations

from backtest import load_daily
from backtest.engine import BacktestResult
from backtest.indicators import rsi, sma

from ._common import DEFAULT_END, DEFAULT_SIZE_VALUE, DEFAULT_START, build_engine, hold_n_exit
from .registry import register


@register("rsi2_mr")
def rsi2_mr(
    ticker: str = "SPY",
    start: str = DEFAULT_START,
    end: str = DEFAULT_END,
    rsi_threshold: float = 10.0,
    hold: int = 5,
    execution: str = "next_open",
    size_value: float = DEFAULT_SIZE_VALUE,
) -> BacktestResult:
    """RSI(2) < ``rsi_threshold`` AND Close > 200 SMA; hold ``hold`` days."""
    ohlcv = load_daily(ticker, start, end)
    df = ohlcv.df
    sma200 = sma(df["Close"], 200)
    rsi2 = rsi(df["Close"], period=2)
    signal = (rsi2 < rsi_threshold) & (df["Close"] > sma200)
    signal = signal.fillna(False)
    eng = build_engine(ohlcv, name="rsi2_mr", execution=execution, size_value=size_value)
    eng.set_entry(signal).set_exit(hold_n_exit(hold))
    return eng.run()


__all__ = ["rsi2_mr"]
