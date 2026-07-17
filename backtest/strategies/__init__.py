"""Mean-reversion strategy library (Chunk 2a).

Importing this package registers every strategy listed below in
:data:`backtest.strategies.registry.REGISTRY`.  Use
:func:`backtest.strategies.registry.run` to invoke a strategy by name, or
import the strategy functions directly.

Strategies registered by this package:

* ``ibs_spy``           - IBS < 0.20 on SPY
* ``ibs_trend``         - IBS < 0.20 + Close > 200 SMA + turn-of-month on SPY
* ``qqq_mr``            - IBS < 0.20 + Close > 200 SMA on QQQ
* ``rsi2_mr``           - RSI(2) < 10 + Close > 200 SMA on SPY
* ``pct_b_mr``          - %B < 0.10 + Close > 200 SMA on SPY
* ``multiple_days_down``- down streak >= 5 + Close > 200 SMA on SPY
* ``turn_of_month``     - last trading day of month on SPY

Typical usage::

    from backtest.strategies import run
    result = run("ibs_spy")
"""

from __future__ import annotations

# Importing each strategy module triggers its @register decorator so that
# the registry is fully populated when callers `import backtest.strategies`.
from . import (  # noqa: F401
    dual_ma,
    fade_5bar_crypto,
    funded_reversion,
    ibs,
    ibs_dynamic,
    lvpr,
    lvpr_intraday,
    multiple_days_down,
    orb_15m_crypto,
    pct_b,
    portfolio,
    rsi2,
    rsi2_qqq_enhanced,
    turn_of_month,
    vix_etn,
    vcr,
    volume_scaled_ibs,
    vwap_reversion,
    vp_consolidation_fade,
)
from .dual_ma import qqq_dual_ma
from .fade_5bar_crypto import fade_5bar_crypto
from .orb_15m_crypto import orb_15m_crypto
from .ibs import ibs_spy, ibs_trend, qqq_mr
from .ibs_dynamic import ibs_dynamic
from .lvpr import lvpr
from .lvpr_intraday import lvpr_intraday
from .multiple_days_down import multiple_days_down
from .pct_b import pct_b_mr
from .portfolio import SUB_STRATEGIES, mr_portfolio
from .registry import REGISTRY, list_strategies, register, run
from .rsi2 import rsi2_mr
from .rsi2_qqq_enhanced import rsi2_qqq_enhanced
from .turn_of_month import turn_of_month_strategy
from .vix_etn import VIX_TICKERS, vix_etn
from .vcr import vcr
from .volume_scaled_ibs import trades_with_vol_ratio, volume_scaled_ibs
from .funded_reversion import funded_reversion
from .vwap_reversion import vwap_reversion
from .vp_consolidation_fade import vp_consolidation_fade
from .garch import ASSETS, _run

__all__ = [
    "REGISTRY",
    "register",
    "run",
    "list_strategies",
    "ibs",
    "ibs_dynamic",
    "multiple_days_down",
    "pct_b",
    "rsi2",
    "rsi2_qqq_enhanced",
    "turn_of_month",
    "vix_etn",
    "portfolio",
    "dual_ma",
    "fade_5bar_crypto",
    "orb_15m_crypto",
    "ibs_spy",
    "ibs_trend",
    "qqq_mr",
    "rsi2_mr",
    "rsi2_qqq_enhanced",
    "pct_b_mr",
    "multiple_days_down",
    "turn_of_month_strategy",
    "volume_scaled_ibs",
    "trades_with_vol_ratio",
    "qqq_dual_ma",
    "vix_etn",
    "VIX_TICKERS",
    "mr_portfolio",
    "SUB_STRATEGIES",
    "ibs_dynamic",
    "lvpr",
    "vcr",
    "funded_reversion",
    "lvpr_intraday",
    "vwap_reversion",
    "vp_consolidation_fade",
    "garch_ema_btc",
    "ema_fixed_btc",
    "garch_ema_qqq",
    "ema_fixed_qqq",
    "garch_ema_eth",
    "ema_fixed_eth",
    "garch_ema_sol",
    "ema_fixed_sol",
    "garch_ema_bnb",
    "ema_fixed_bnb",
    "garch_ema_spy",
    "ema_fixed_spy",
    "garch_ema_dia",
    "ema_fixed_dia",
    "garch_ema_iwm",
    "ema_fixed_iwm",
]
