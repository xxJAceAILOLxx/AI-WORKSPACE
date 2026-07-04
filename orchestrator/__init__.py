"""Agent orchestration layer for the unified backtest framework.

This package wires together the agent prompts defined in ``agents.md``,
the shared vault ``memory.md``, and the backtest registry.  It exposes:

* :mod:`orchestrator.agents` - registry of the 12 agents from ``agents.md``.
* :mod:`orchestrator.memory` - persistent memory backed by ``memory.md``.
* :mod:`orchestrator.workflow` - the 7-stage research -> learn pipeline.
* :mod:`orchestrator.cli` - ``python -m orchestrator.cli`` entry point.

The orchestrator never calls external LLM APIs.  It populates prompts,
invokes the local backtest runner where applicable, and records results
back into the vault memory.
"""

from __future__ import annotations

from .agents import AGENTS, Agent, by_stage, get_agent, list_agents
from .memory import Memory
from .workflow import STAGES, Workflow

__all__ = [
    "AGENTS",
    "Agent",
    "Memory",
    "STAGES",
    "Workflow",
    "by_stage",
    "get_agent",
    "list_agents",
]
