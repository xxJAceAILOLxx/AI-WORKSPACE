"""Agent core — ReAct loop, tool framework, and context builder.

This package provides the LLM-driven agent loop that powers the
workflow's non-backtest stages.  It re-exports the key classes:

* :class:`BaseTool` / :class:`ToolRegistry` — the tool framework.
* :class:`AgentLoop` — the ReAct core loop.
* :class:`ContextBuilder` — system prompt construction.
"""

from __future__ import annotations

from .tools import BaseTool, ToolRegistry, build_registry

__all__ = ["BaseTool", "ToolRegistry", "build_registry"]
