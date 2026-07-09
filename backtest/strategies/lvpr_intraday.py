"""Intraday Low-Volume Pullback Reversion (LVPR) on crypto 5m bars.

Same novel edge as :mod:`backtest.strategies.lvpr` -- fade *quiet* pullbacks
(price stretched below its mean on below-average volume) -- but on
Binance 5-minute bars instead of daily ETF bars.  Crypto trades 24/7 and is
retail/algorithm-driven, so the pullback-reversion edge is far more
*frequent* intraday, which is exactly what a 30-day prop challenge needs to
climb +10% inside the window.

Because the engine is bar-agnostic, this reuses the daily LVPR logic on a
5-minute OHLCV.  Two differences tuned for the timeframe:

* ``trend_ma`` (default 200 bars ~ 16.7h) replaces the daily SMA200 filter.
* ``hold`` is in *bars* (default 288 = one 24h session) instead of days.

Volume filter still uses a 20-bar (100-min) average so it adapts to the
faster clock.  Exit: reversion to SMA(``ma_period``), 2x ATR(14) stop, or
``hold``-bar time stop.

.. warning::
   Backtests (2026-07-09, BTCUSDT/ETHUSDT 5m, 2021-2025) show this is a
   **NET LOSER** (PF 0.61-0.71, WR ~50%, eq_dd 80-99%).  The "quiet
   pullback" edge is microstructure-specific to *daily equity ETFs* and
   does not transfer to 24/7 retail crypto.  Kept for documentation;
   do not trade.
"""

from __future__ import annotations

from typing import Tuple

import pandas as pd

from backtest import Engine, PERCENT_10BP
from backtest.data import load_intraday_binance
from backtest.engine import BacktestResult
from backtest.indicators import atr, bollinger, ibs, sma, volume_ratio

from .registry import register


DEFAULT_INTERVAL: str = "5m"
DEFAULT_START: str = "2021-08-01"
DEFAULT_END: str = "2026-05-01"
DEFAULT_MA_PERIOD: int = 20
DEFAULT_TREND_MA: int = 200
DEFAULT_IBS_MAX: float = 0.30
DEFAULT_VOL_MAX: float = 1.00
DEFAULT_HOLD: int = 288
DEFAULT_STOP_MULT: float = 2.0
DEFAULT_RISK_FRACTION: float = 0.10
DEFAULT_INITIAL_CAPITAL: float = 100_000.0


@register("lvpr_intraday")
def lvpr_intraday(
    symbol: str = "BTCUSDT",
    interval: str = DEFAULT_INTERVAL,
    start: str = DEFAULT_START,
    end: str = DEFAULT_END,
    ma_period: int = DEFAULT_MA_PERIOD,
    trend_ma: int = DEFAULT_TREND_MA,
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
    """Intraday LVPR on Binance 5m (or other interval) bars."""
    ohlcv = load_intraday_binance(symbol, interval, start, end)
    df = ohlcv.df

    close = df["Close"].astype(float)
    mean = sma(close, ma_period)
    _, _, lower, _ = bollinger(close, period=ma_period, num_std=2.0)

    ibs_s = ibs(df)
    vol_r = volume_ratio(df)
    trend = sma(close, trend_ma)

    stretched = (ibs_s < ibs_max) | (close <= lower)
    quiet = vol_r <= vol_max
    trend_ok = close > trend

    entry_signal = (stretched & quiet & trend_ok).fillna(False)

    def exit_rule(state) -> Tuple[str, float] | None:
        close_now = float(state.bar["Close"])
        mean_now = float(mean.iloc[state.idx]) if state.idx < len(mean) else float("nan")
        if pd.notna(mean_now) and close_now >= mean_now:
            return ("revert", 0.0)
        return None

    eng = Engine(
        ohlcv,
        name="lvpr_intraday",
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
    "lvpr_intraday",
    "DEFAULT_INTERVAL",
    "DEFAULT_START",
    "DEFAULT_END",
    "DEFAULT_MA_PERIOD",
    "DEFAULT_TREND_MA",
    "DEFAULT_IBS_MAX",
    "DEFAULT_VOL_MAX",
    "DEFAULT_HOLD",
    "DEFAULT_STOP_MULT",
    "DEFAULT_RISK_FRACTION",
    "DEFAULT_INITIAL_CAPITAL",
]
