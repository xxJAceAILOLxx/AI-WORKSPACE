"""Unified backtest framework.

Chunk 1 of the unified framework plan: the core event-driven engine,
indicators, cost models, metrics, validation, and reporting.

Typical usage:

    >>> from backtest import Engine, load_daily, PERCENT_10BP
    >>> from backtest.indicators import ibs
    >>>
    >>> ohlcv = load_daily("SPY", "2020-01-01", "2023-12-31")
    >>> signal = ibs(ohlcv.df) < 0.2
    >>> engine = Engine(ohlcv, name="ibs_spy")
    >>> engine.set_entry(signal)
    >>> engine.set_exit(lambda s: ("hold_5", 0.0) if s.days_held >= 5 else None)
    >>> result = engine.run()
"""

from .costs import (
    FLAT_40,
    PERCENT_10BP,
    PER_SHARE_1C,
    CostFn,
    CostModel,
    available,
    get,
    register,
)
from .data import OHLCV, from_dataframe, load_daily, load_intraday_binance, load_intraday_hf
from .engine import BacktestResult, Engine, EngineState, Trade
from .indicators import (
    atr,
    bollinger,
    down_streak,
    ema,
    ibs,
    pct_b,
    realized_vol,
    rsi,
    sma,
    turn_of_month,
    volume_ratio,
)
from .metrics import (
    Metrics,
    avg_hold_days,
    avg_loss,
    avg_win,
    cagr,
    compute_metrics,
    expectancy,
    final_equity,
    max_drawdown,
    profit_factor,
    sharpe,
    sortino,
    total_return,
    trade_count,
    win_rate,
)
from .reporting import print_ranking, print_result
from .validation import (
    MonteCarloResult,
    WalkForwardSplit,
    monte_carlo,
    monte_carlo_paths,
    walk_forward,
    walk_forward_run,
)

__all__ = [
    # data
    "OHLCV",
    "load_daily",
    "load_intraday_binance",
    "load_intraday_hf",
    "from_dataframe",
    # engine
    "Engine",
    "EngineState",
    "Trade",
    "BacktestResult",
    # costs
    "CostModel",
    "CostFn",
    "PERCENT_10BP",
    "FLAT_40",
    "PER_SHARE_1C",
    "register",
    "get",
    "available",
    # indicators
    "ibs",
    "rsi",
    "sma",
    "ema",
    "atr",
    "bollinger",
    "pct_b",
    "down_streak",
    "volume_ratio",
    "turn_of_month",
    "realized_vol",
    # metrics
    "Metrics",
    "compute_metrics",
    "final_equity",
    "total_return",
    "cagr",
    "max_drawdown",
    "sharpe",
    "sortino",
    "win_rate",
    "avg_win",
    "avg_loss",
    "profit_factor",
    "expectancy",
    "avg_hold_days",
    "trade_count",
    # reporting
    "print_result",
    "print_ranking",
    # validation
    "WalkForwardSplit",
    "walk_forward",
    "walk_forward_run",
    "MonteCarloResult",
    "monte_carlo",
    "monte_carlo_paths",
]
