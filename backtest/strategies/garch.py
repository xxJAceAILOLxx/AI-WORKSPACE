"""GARCH volatility-targeted position sizing (the "Nobel Prize method").

Implements the workflow from the watched video: a directional signal (an
EMA cross, long/short) whose *size* is scaled by a GARCH(1,1)
variance forecast so the book targets a constant annualized volatility.

For every asset in :data:`ASSETS` two strategies are registered:

* ``garch_ema_<asset>`` -- EMA-cross signal sized by the GARCH
  forecast (inverse-vol).  ``target_vol`` is the constant the book
  aims for; when the forecast vol is high the position is cut, when it
  is low the position is levered up (capped by ``max_leverage``).
* ``ema_fixed_<asset>`` -- the identical EMA-cross signal with a
  constant percent-of-equity size (the naive baseline).

Comparing the pairs across many assets shows whether vol-targeting
actually buys a better Sharpe / smaller drawdown, or just costs return.
"""

from __future__ import annotations

from typing import Dict, Tuple

import numpy as np
import pandas as pd

from backtest import Engine, OHLCV, PERCENT_10BP  # noqa: F401  (OHLCV re-exported for callers)
from backtest.indicators import ema, garch_vol

from ._common import DEFAULT_END, DEFAULT_START
from .registry import register

# EMA-cross parameters (daily bars).
FAST = 20
SLOW = 50

# Vol-target defaults: aim for a 15% annualized vol book (the video's
# institutional-desk figure), cap gross notional at 3x equity.
TARGET_VOL = 0.15
MAX_LEVERAGE = 3.0
SIZE_VALUE = 0.95

# Assets to test.  ``source`` selects the loader; ``annualize`` is the
# trading-days factor for the vol forecast.
ASSETS: Dict[str, Dict[str, object]] = {
    "btc": {"symbol": "BTCUSDT", "source": "binance", "annualize": 365},
    "eth": {"symbol": "ETHUSDT", "source": "binance", "annualize": 365},
    "sol": {"symbol": "SOLUSDT", "source": "binance", "annualize": 365},
    "bnb": {"symbol": "BNBUSDT", "source": "binance", "annualize": 365},
    "spy": {"symbol": "SPY", "source": "yfinance", "annualize": 252},
    "qqq": {"symbol": "QQQ", "source": "yfinance", "annualize": 252},
    "dia": {"symbol": "DIA", "source": "yfinance", "annualize": 252},
    "iwm": {"symbol": "IWM", "source": "yfinance", "annualize": 252},
}


def _load(asset: str, start: str, end: str) -> OHLCV:
    cfg = ASSETS[asset]
    if cfg["source"] == "binance":
        from backtest.data import load_intraday_binance

        return load_intraday_binance(
            symbol=str(cfg["symbol"]), interval="1d", start=start, end=end
        )
    from backtest import load_daily

    return load_daily(str(cfg["symbol"]), start, end)


def _ema_cross_signal(df: pd.DataFrame) -> pd.Series:
    """Signed EMA-cross position: +1 fast>slow, -1 fast<slow."""
    fast = ema(df["Close"], FAST)
    slow = ema(df["Close"], SLOW)
    cross = (fast > slow).astype(int) - (fast < slow).astype(int)
    return cross.fillna(0)


def _flip_exit(signal: pd.Series):
    """Exit when the desired side differs from the open position's side."""

    def rule(state) -> None | Tuple[str, float]:
        desired = int(np.sign(signal.iloc[state.idx]))
        if desired != 0 and desired != int(np.sign(state.shares)):
            return ("flip", 0.0)
        return None

    return rule


def _build(
    ohlcv: OHLCV,
    name: str,
    size_policy: str,
    vol_series: pd.Series | None = None,
    execution: str = "next_open",
) -> Engine:
    eng = Engine(
        ohlcv,
        name=name,
        execution=execution,
        cost_model=PERCENT_10BP,
        initial_capital=100_000.0,
        size_policy=size_policy,
        size_value=SIZE_VALUE,
        vol_series=vol_series,
        target_vol=TARGET_VOL,
        max_leverage=MAX_LEVERAGE,
    )
    signal = _ema_cross_signal(ohlcv.df)
    eng.set_entry(signal).set_exit(_flip_exit(signal))
    return eng


def _run(asset: str, policy: str, start: str = DEFAULT_START, end: str = DEFAULT_END,
         execution: str = "next_open", ohlcv: OHLCV | None = None):
    if ohlcv is None:
        ohlcv = _load(asset, start, end)
    vol = garch_vol(ohlcv.df["Close"], annualize=int(ASSETS[asset]["annualize"]))
    if policy == "vol_target":
        return _build(ohlcv, f"garch_ema_{asset}", "vol_target",
                      vol_series=vol, execution=execution).run()
    return _build(ohlcv, f"ema_fixed_{asset}", "percent_of_equity",
                  execution=execution).run()


# ---------------------------------------------------------------------------
# Auto-registered strategy pairs (one GARCH + one fixed per asset).
# ---------------------------------------------------------------------------
def _make_garch(asset: str):
    def fn(start: str = DEFAULT_START, end: str = DEFAULT_END,
            execution: str = "next_open"):
        return _run(asset, "vol_target", start=start, end=end, execution=execution)
    fn.__name__ = f"garch_ema_{asset}"
    return fn


def _make_fixed(asset: str):
    def fn(start: str = DEFAULT_START, end: str = DEFAULT_END,
            execution: str = "next_open"):
        return _run(asset, "percent_of_equity", start=start, end=end, execution=execution)
    fn.__name__ = f"ema_fixed_{asset}"
    return fn


for _asset in ASSETS:
    register(f"garch_ema_{_asset}")(_make_garch(_asset))
    register(f"ema_fixed_{_asset}")(_make_fixed(_asset))


__all__ = [
    "ASSETS",
    "garch_vol",
    *[f"garch_ema_{a}" for a in ASSETS],
    *[f"ema_fixed_{a}" for a in ASSETS],
]
