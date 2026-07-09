"""Volume Climax Reversal (VCR) -- a NON-common exhaustion-fade edge.

A volume climax occurs when a down-leg ends on a volume spike of several
standard deviations above its mean *combined with* range expansion and a
close off the bar's low.  The "smart money" has finished distributing and
the move is exhausted.  This strategy fades the direction of that climax
bar (long-only here: we fade down-climaxes).

This is distinct from the vault's existing ``volume_scaled_ibs``, which
scales an IBS threshold by volume.  Here the entry is a *single-bar
exhaustion signature*: volume spike + range expansion + close off the low
(settled in the upper half of the bar).  We keep the ``Close > SMA200``
trend filter so we fade climaxes inside uptrends, not distribution tops in
downtrends (per memory.md's distribution gotcha).

Entry (long) -- all must hold on the signal bar:
  - volume spike: vol_ratio >= vol_mult (default 2.5)
  - range expansion: (High - Low) >= range_mult * ATR(14) (default 1.5)
  - down bar: Close <= Open
  - rejection / exhaustion: Close >= Low + wick_frac * (High - Low)
    (default 0.35 -> close in the upper 65% of the bar's range)
  - trend filter: Close > SMA200

Exit (priority order):
  - Mean reversion achieved: Close >= SMA20.
  - ATR(14) protective stop at stop_mult x ATR below entry.
  - max_hold day time stop.

Sizing: fixed risk of a fraction of initial capital per trade.
"""

from __future__ import annotations

from typing import Tuple

import pandas as pd

from backtest import Engine, PERCENT_10BP, load_daily
from backtest.engine import BacktestResult
from backtest.indicators import atr, sma, volume_ratio

from .registry import register


DEFAULT_START: str = "2016-01-01"
DEFAULT_END: str = "2025-12-31"
DEFAULT_VOL_MULT: float = 2.5
DEFAULT_RANGE_MULT: float = 1.5
DEFAULT_WICK_FRAC: float = 0.35
DEFAULT_MA_PERIOD: int = 20
DEFAULT_HOLD: int = 10
DEFAULT_STOP_MULT: float = 2.0
DEFAULT_RISK_FRACTION: float = 0.10
DEFAULT_INITIAL_CAPITAL: float = 100_000.0


@register("vcr")
def vcr(
    ticker: str = "SPY",
    start: str = DEFAULT_START,
    end: str = DEFAULT_END,
    vol_mult: float = DEFAULT_VOL_MULT,
    range_mult: float = DEFAULT_RANGE_MULT,
    wick_frac: float = DEFAULT_WICK_FRAC,
    ma_period: int = DEFAULT_MA_PERIOD,
    hold: int = DEFAULT_HOLD,
    stop_mult: float = DEFAULT_STOP_MULT,
    risk_fraction: float = DEFAULT_RISK_FRACTION,
    execution: str = "next_open",
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
) -> BacktestResult:
    """Volume Climax Reversal on daily OHLCV (long-only)."""
    ohlcv = load_daily(ticker, start, end)
    df = ohlcv.df

    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    close = df["Close"].astype(float)
    open_ = df["Open"].astype(float)

    atr14 = atr(df, period=14)
    bar_range = (high - low)
    vol_r = volume_ratio(df)
    sma20 = sma(close, ma_period)
    sma200 = sma(close, 200)

    vol_spike = vol_r >= vol_mult
    range_exp = bar_range >= range_mult * atr14
    down_bar = close <= open_
    # Close in the upper portion of the bar's range => buyers rejected the low.
    upper_close = (close - low) >= wick_frac * bar_range.replace(0, pd.NA)
    trend_ok = close > sma200

    entry_signal = (
        vol_spike & range_exp & down_bar & upper_close.fillna(False) & trend_ok
    ).fillna(False)

    def exit_rule(state) -> Tuple[str, float] | None:
        close_now = float(state.bar["Close"])
        sma_now = float(sma20.iloc[state.idx]) if state.idx < len(sma20) else float("nan")
        if pd.notna(sma_now) and close_now >= sma_now:
            return ("revert", 0.0)
        return None

    eng = Engine(
        ohlcv,
        name="vcr",
        execution=execution,
        cost_model=PERCENT_10BP,
        initial_capital=initial_capital,
        size_policy="fixed_risk",
        size_value=risk_fraction * initial_capital,
        stop_mult=stop_mult,
        max_hold=hold,
        atr_period=14,
    )
    eng.set_entry(entry_signal).set_exit(exit_rule)
    result = eng.run()
    result.config["vol_ratio"] = vol_r
    return result


__all__ = [
    "vcr",
    "DEFAULT_START",
    "DEFAULT_END",
    "DEFAULT_VOL_MULT",
    "DEFAULT_RANGE_MULT",
    "DEFAULT_WICK_FRAC",
    "DEFAULT_MA_PERIOD",
    "DEFAULT_HOLD",
    "DEFAULT_STOP_MULT",
    "DEFAULT_RISK_FRACTION",
    "DEFAULT_INITIAL_CAPITAL",
]
