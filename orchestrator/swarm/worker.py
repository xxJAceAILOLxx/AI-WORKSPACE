"""Swarm worker — runs a single task's agent loop."""

from __future__ import annotations

import logging
from typing import Optional

from ..agent.loop import AgentLoop, AgentResult
from ..agent.prompt import build_system_prompt
from ..agent.tools import ToolRegistry
from ..providers.chat import ChatLLM
from .models import SwarmAgent

logger = logging.getLogger(__name__)


class SwarmWorker:
    """Execute a single swarm task using an LLM agent loop.

    Parameters
    ----------
    llm:
        The LLM client.
    tool_registry:
        Global tool registry (filtered to the agent's tool list).
    agent:
        The swarm agent definition.
    """

    def __init__(
        self,
        llm: ChatLLM,
        tool_registry: ToolRegistry,
        agent: SwarmAgent,
    ) -> None:
        self.llm = llm
        self.tool_registry = tool_registry
        self.agent = agent

    def run(self, prompt: str) -> str:
        """Run the agent loop with the given prompt and return the text result."""
        # Filter tools to the agent's allowed list.
        if self.agent.tools:
            from ..agent.tools import ToolRegistry as TR

            filtered = TR()
            for name in self.agent.tools:
                try:
                    filtered.register(self.tool_registry.get(name))
                except KeyError:
                    logger.warning(
                        "Agent %s requests unknown tool %s", self.agent.id, name
                    )
        else:
            filtered = self.tool_registry

        system_prompt = build_system_prompt(filtered)
        if self.agent.system_prompt:
            system_prompt = self.agent.system_prompt + "\n\n" + system_prompt

        loop = AgentLoop(
            llm=self.llm,
            registry=filtered,
            system_prompt=system_prompt,
            max_iterations=self.agent.max_iterations,
        )

        result: AgentResult = loop.run(prompt)
        return result.content
