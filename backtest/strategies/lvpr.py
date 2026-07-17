"""Low-Volume Pullback Reversion (LVPR) -- a NON-common mean-reversion edge.

Most "volume-confirmed mean reversion" systems *require* a volume spike on
the reversal bar (effort confirms the turn).  This strategy does the
opposite, on purpose: memory.md's own gotcha shows that **high-volume**
selloffs in broad ETFs are institutional *distribution* and are net losers
(high-volume IBS entries: 33.3% win rate).  So we fade only *quiet*
pullbacks -- where price has stretched well below its rolling mean but
volume is *below* average.  Low effort (volume) vs a stretched result
(price) = exhaustion, not distribution.

Entry (long):
  - Stretch: z = (Close - SMA20) / rolling_std20 <= z_entry (default -2.0)
    OR Close below the lower Bollinger Band (20, 2).
  - Quiet volume: vol_ratio <= vol_max (default 1.00).  This is the novel
    filter that separates a low-effort pullback from a high-volume panic.
  - Trend filter: Close > SMA200 (only fade pullbacks inside an uptrend).

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
from backtest.indicators import atr, bollinger, ibs, sma, volume_ratio

from .registry import register


DEFAULT_START: str = "2016-01-01"
DEFAULT_END: str = "2025-12-31"
DEFAULT_MA_PERIOD: int = 20
DEFAULT_IBS_MAX: float = 0.40
DEFAULT_VOL_MAX: float = 0.80
DEFAULT_HOLD: int = 10
DEFAULT_STOP_MULT: float = 3.0
DEFAULT_RISK_FRACTION: float = 0.10
DEFAULT_INITIAL_CAPITAL: float = 100_000.0


@register("lvpr")
def lvpr(
    ticker: str = "SPY",
    start: str = DEFAULT_START,
    end: str = DEFAULT_END,
    ma_period: int = DEFAULT_MA_PERIOD,
    ibs_max: float = DEFAULT_IBS_MAX,
    vol_max: float = DEFAULT_VOL_MAX,
    hold: int = DEFAULT_HOLD,
    stop_mult: float = DEFAULT_STOP_MULT,
    risk_fraction: float = DEFAULT_RISK_FRACTION,
    size_policy: str = "percent_of_equity",
    size_value: float = 0.95,
    execution: str = "next_open",
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
) -> BacktestResult:
    """Low-Volume Pullback Reversion on daily OHLCV.

    See the module docstring for the rationale.  Parameters are exposed so
    the orchestrator/sweeps can tune the stretch depth, the volume ceiling,
    and the risk budget per trade.
    """
    ohlcv = load_daily(ticker, start, end)
    df = ohlcv.df

    close = df["Close"].astype(float)
    mean = sma(close, ma_period)
    _, _, lower, _ = bollinger(close, period=ma_period, num_std=2.0)

    ibs_s = ibs(df)
    vol_r = volume_ratio(df)
    sma200 = sma(close, 200)

    stretched = (ibs_s < ibs_max) | (close <= lower)
    quiet = vol_r <= vol_max
    trend_ok = close > sma200

    entry_signal = (stretched & quiet & trend_ok).fillna(False)

    def exit_rule(state) -> Tuple[str, float] | None:
        close_now = float(state.bar["Close"])
        mean_now = float(mean.iloc[state.idx]) if state.idx < len(mean) else float("nan")
        if pd.notna(mean_now) and close_now >= mean_now:
            return ("revert", 0.0)
        return None

    eng = Engine(
        ohlcv,
        name="lvpr",
        execution=execution,
        cost_model=PERCENT_10BP,
        initial_capital=initial_capital,
        size_policy=size_policy,
        size_value=risk_fraction * initial_capital if size_policy == "fixed_risk" else size_value,
        stop_mult=stop_mult,
        max_hold=hold,
        atr_period=14,
    )
    eng.set_entry(entry_signal).set_exit(exit_rule)
    result = eng.run()
    result.config["vol_ratio"] = vol_r
    return result


__all__ = [
    "lvpr",
    "DEFAULT_START",
    "DEFAULT_END",
    "DEFAULT_MA_PERIOD",
    "DEFAULT_IBS_MAX",
    "DEFAULT_VOL_MAX",
    "DEFAULT_HOLD",
    "DEFAULT_STOP_MULT",
    "DEFAULT_RISK_FRACTION",
    "DEFAULT_INITIAL_CAPITAL",
]
