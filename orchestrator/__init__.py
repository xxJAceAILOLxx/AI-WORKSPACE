"""Agent orchestration layer for the unified backtest framework.

This package wires together the agent prompts defined in ``agents.md``,
the shared vault ``memory.md``, and the backtest registry.  It exposes:

* :mod:`orchestrator.agents` - registry of the 12 agents from ``agents.md``.
* :mod:`orchestrator.memory` - persistent memory backed by ``memory.md``.
* :mod:`orchestrator.workflow` - the 7-stage research -> learn pipeline.
* :mod:`orchestrator.cli` - ``python -m orchestrator.cli`` entry point.
* :mod:`orchestrator.agent` - LLM agent loop (ReAct core + tools).
* :mod:`orchestrator.providers` - pluggable LLM provider abstraction.
* :mod:`orchestrator.hypotheses` - hypothesis registry.
* :mod:`orchestrator.goal` - research goal store.
* :mod:`orchestrator.tools` - agent tool implementations.
* :mod:`orchestrator.swarm` - multi-agent swarm orchestration.
* :mod:`orchestrator.loaders` - data source loaders.
* :mod:`orchestrator.factors` - alpha factor zoo.
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
