"""ReAct agent loop — the core reasoning-and-acting cycle.

The :class:`AgentLoop` sends a user message plus tool definitions to an
LLM, executes any tool calls the model returns, feeds the results back,
and repeats until the model produces a final text answer (or the
iteration budget is exhausted).

This is a simplified port of Vibe-Trading's ``AgentLoop``
(``agent/src/agent/loop.py``), adapted for the vault's orchestrator.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from ..providers.chat import ChatLLM, LLMResponse, ToolCallRequest
from .tools import ToolRegistry

logger = logging.getLogger(__name__)

# Default iteration budget.
MAX_ITERATIONS = 30


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass
class AgentResult:
    """Final result returned by :meth:`AgentLoop.run`."""

    content: str = ""
    iterations: int = 0
    tool_calls_made: int = 0
    total_usage: Dict[str, int] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)
    elapsed_seconds: float = 0.0


# ---------------------------------------------------------------------------
# AgentLoop
# ---------------------------------------------------------------------------


class AgentLoop:
    """ReAct core loop: think → act → observe → repeat.

    Parameters
    ----------
    llm:
        The LLM client used for chat completions.
    registry:
        Tool registry providing callable tools.
    system_prompt:
        System message prepended to every LLM call.
    max_iterations:
        Maximum think-act cycles before forcing a final answer.
    on_tool_start:
        Optional callback ``(tool_name, args_dict)`` fired before each
        tool execution.
    on_tool_end:
        Optional callback ``(tool_name, result_str)`` fired after each
        tool execution.
    on_text_chunk:
        Optional callback for streaming text chunks.
    """

    def __init__(
        self,
        llm: ChatLLM,
        registry: ToolRegistry,
        system_prompt: str = "",
        max_iterations: int = MAX_ITERATIONS,
        on_tool_start: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        on_tool_end: Optional[Callable[[str, str], None]] = None,
        on_text_chunk: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.llm = llm
        self.registry = registry
        self.system_prompt = system_prompt
        self.max_iterations = max_iterations
        self.on_tool_start = on_tool_start
        self.on_tool_end = on_tool_end
        self.on_text_chunk = on_text_chunk
        self._cancel_event = threading.Event()

    # -- public API --------------------------------------------------------

    def run(
        self,
        user_message: str,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> AgentResult:
        """Execute the ReAct loop and return the final :class:`AgentResult`.

        Parameters
        ----------
        user_message:
            The user's input for this turn.
        history:
            Optional prior conversation turns (OpenAI message format).
        """
        t0 = time.monotonic()
        messages: List[Dict[str, Any]] = self._build_messages(user_message, history)
        tools = self.registry.get_definitions()

        result = AgentResult()
        result.history = messages

        for iteration in range(1, self.max_iterations + 1):
            if self._cancel_event.is_set():
                result.content = "(cancelled by user)"
                break

            # Drop tools on the last iteration to force a text answer.
            call_tools = tools if iteration < self.max_iterations else None

            response: LLMResponse = self.llm.chat(messages, tools=call_tools)

            # Accumulate usage.
            for key, val in response.usage.items():
                result.total_usage[key] = result.total_usage.get(key, 0) + val

            # No tool calls → final text answer.
            if not response.tool_calls:
                result.content = response.content
                result.iterations = iteration
                break

            # Process tool calls.
            assistant_msg: Dict[str, Any] = {"role": "assistant", "content": response.content or ""}
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                }
                for tc in response.tool_calls
            ]
            messages.append(assistant_msg)

            # Execute tools and collect results.
            for tc in response.tool_calls:
                if self._cancel_event.is_set():
                    break

                result.tool_calls_made += 1
                if self.on_tool_start:
                    self.on_tool_start(tc.name, tc.arguments)

                tool_result = self.registry.execute(tc.name, tc.arguments)

                if self.on_tool_end:
                    self.on_tool_end(tc.name, tool_result)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": tool_result,
                    }
                )

            # Inject wrap-up nudge at 80% budget.
            if iteration == int(self.max_iterations * 0.8):
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"[SYSTEM] You have {self.max_iterations - iteration} "
                            f"iterations remaining. Please provide your final answer."
                        ),
                    }
                )

        else:
            # Exhausted iterations — force a final text answer.
            messages.append({"role": "user", "content": "[SYSTEM] Please provide your final answer now."})
            response = self.llm.chat(messages, tools=None)
            result.content = response.content
            result.iterations = self.max_iterations

        result.elapsed_seconds = time.monotonic() - t0
        result.history = messages
        return result

    def cancel(self) -> None:
        """Signal the loop to stop after the current iteration."""
        self._cancel_event.set()

    # -- internals ---------------------------------------------------------

    def _build_messages(
        self,
        user_message: str,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Construct the initial message list."""
        messages: List[Dict[str, Any]] = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})
        return messages
