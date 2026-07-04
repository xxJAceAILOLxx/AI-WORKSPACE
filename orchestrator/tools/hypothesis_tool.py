"""Hypothesis management tools — create, update, link, search."""

from __future__ import annotations

import json
from typing import Any

from ..agent.tools import BaseTool
from ..hypotheses.registry import HypothesisRegistry


class CreateHypothesisTool(BaseTool):
    name = "create_hypothesis"
    description = "Create a new trading hypothesis with title, thesis, universe, and signal definition."
    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Short title for the hypothesis"},
            "thesis": {"type": "string", "description": "Detailed thesis statement"},
            "universe": {"type": "string", "description": "Target universe (e.g. SPY, QQQ, CSI 300)"},
            "signal_definition": {"type": "string", "description": "Description of the entry/exit signal"},
            "data_sources": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Data sources to use (default: yfinance)",
            },
        },
        "required": ["title"],
    }

    def execute(self, **kwargs: Any) -> str:
        registry = HypothesisRegistry()
        h = registry.create_hypothesis(
            title=kwargs.get("title", ""),
            thesis=kwargs.get("thesis", ""),
            universe=kwargs.get("universe", ""),
            signal_definition=kwargs.get("signal_definition", ""),
            data_sources=kwargs.get("data_sources"),
        )
        return json.dumps({"status": "ok", "hypothesis": h.to_dict()})


class UpdateHypothesisTool(BaseTool):
    name = "update_hypothesis"
    description = "Update fields on an existing hypothesis."
    parameters = {
        "type": "object",
        "properties": {
            "hypothesis_id": {"type": "string", "description": "ID of the hypothesis to update"},
            "title": {"type": "string"},
            "thesis": {"type": "string"},
            "universe": {"type": "string"},
            "signal_definition": {"type": "string"},
            "status": {"type": "string", "description": "draft | active | validated | rejected"},
        },
        "required": ["hypothesis_id"],
    }

    def execute(self, **kwargs: Any) -> str:
        registry = HypothesisRegistry()
        h = registry.update_hypothesis(
            kwargs.pop("hypothesis_id"),
            **{k: v for k, v in kwargs.items() if v is not None},
        )
        if h is None:
            return json.dumps({"status": "error", "error": "hypothesis not found"})
        return json.dumps({"status": "ok", "hypothesis": h.to_dict()})


class LinkBacktestTool(BaseTool):
    name = "link_backtest"
    description = "Link a backtest run to a hypothesis with its metrics."
    parameters = {
        "type": "object",
        "properties": {
            "hypothesis_id": {"type": "string", "description": "ID of the hypothesis"},
            "run_dir": {"type": "string", "description": "Path to the backtest run directory"},
            "metrics": {
                "type": "object",
                "description": "Backtest metrics dict (sharpe, profit_factor, etc.)",
            },
            "notes": {"type": "string", "description": "Optional notes about this run"},
        },
        "required": ["hypothesis_id", "run_dir", "metrics"],
    }

    def execute(self, **kwargs: Any) -> str:
        registry = HypothesisRegistry()
        h = registry.link_backtest(
            hypothesis_id=kwargs["hypothesis_id"],
            run_dir=kwargs["run_dir"],
            metrics=kwargs.get("metrics", {}),
            notes=kwargs.get("notes", ""),
        )
        if h is None:
            return json.dumps({"status": "error", "error": "hypothesis not found"})
        return json.dumps({"status": "ok", "hypothesis": h.to_dict()})


class SearchHypothesesTool(BaseTool):
    name = "search_hypotheses"
    description = "Search hypotheses by keyword across title, thesis, and signal definition."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search keyword"},
            "limit": {"type": "integer", "description": "Max results (default 20)"},
        },
        "required": ["query"],
    }

    def execute(self, **kwargs: Any) -> str:
        registry = HypothesisRegistry()
        results = registry.search_hypotheses(
            query=kwargs.get("query", ""),
            limit=kwargs.get("limit", 20),
        )
        return json.dumps({
            "status": "ok",
            "count": len(results),
            "hypotheses": [h.to_dict() for h in results],
        })


class ListHypothesesTool(BaseTool):
    name = "list_hypotheses"
    description = "List all hypotheses, optionally filtered by status."
    is_readonly = True
    parameters = {
        "type": "object",
        "properties": {
            "status": {"type": "string", "description": "Filter by status: draft, active, validated, rejected"},
            "limit": {"type": "integer", "description": "Max results (default 50)"},
        },
    }

    def execute(self, **kwargs: Any) -> str:
        registry = HypothesisRegistry()
        results = registry.list_hypotheses(
            status=kwargs.get("status"),
            limit=kwargs.get("limit", 50),
        )
        return json.dumps({
            "status": "ok",
            "count": len(results),
            "hypotheses": [h.to_dict() for h in results],
        })
