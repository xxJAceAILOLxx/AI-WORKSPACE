"""Backtest tool — run strategies from the local registry."""

from __future__ import annotations

import json
from typing import Any

from ..agent.tools import BaseTool


class BacktestTool(BaseTool):
    name = "run_backtest"
    description = (
        "Run a backtest for a registered strategy. Returns metrics "
        "(sharpe, profit_factor, max_drawdown, win_rate, etc.) and trade count."
    )
    is_readonly = False
    parameters = {
        "type": "object",
        "properties": {
            "strategy_name": {
                "type": "string",
                "description": "Name of the registered strategy (e.g. ibs_spy, rsi2_mr)",
            },
            "ticker": {"type": "string", "description": "Ticker symbol (default: SPY)"},
            "start": {"type": "string", "description": "Start date YYYY-MM-DD (default: 2016-01-01)"},
            "end": {"type": "string", "description": "End date YYYY-MM-DD (default: 2025-12-31)"},
            "execution": {"type": "string", "description": "next_open or close (default: next_open)"},
        },
        "required": ["strategy_name"],
    }

    def execute(self, **kwargs: Any) -> str:
        try:
            from backtest.metrics import compute_metrics
            from backtest.strategies.registry import list_strategies, run as registry_run
        except ImportError as exc:
            return json.dumps({"status": "error", "error": f"backtest package unavailable: {exc}"})

        strategy_name = kwargs.get("strategy_name", "")
        available = list_strategies()
        if strategy_name not in available:
            return json.dumps({
                "status": "error",
                "error": f"Unknown strategy {strategy_name!r}. Available: {available}",
            })

        params = {}
        for key in ("ticker", "start", "end", "execution"):
            if key in kwargs and kwargs[key] is not None:
                params[key] = kwargs[key]

        try:
            result = registry_run(strategy_name, **params)
            metrics = compute_metrics(result).as_dict()
            return json.dumps({
                "status": "ok",
                "strategy_name": strategy_name,
                "metrics": metrics,
                "trade_count": len(result.trades),
                "config": result.config,
            })
        except Exception as exc:
            return json.dumps({"status": "error", "error": str(exc)})


class ListStrategiesTool(BaseTool):
    name = "list_strategies"
    description = "List all registered backtest strategies."
    is_readonly = True
    parameters = {"type": "object", "properties": {}}

    def execute(self, **kwargs: Any) -> str:
        try:
            from backtest.strategies.registry import list_strategies
        except ImportError:
            return json.dumps({"status": "ok", "strategies": []})
        return json.dumps({"status": "ok", "strategies": list_strategies()})
