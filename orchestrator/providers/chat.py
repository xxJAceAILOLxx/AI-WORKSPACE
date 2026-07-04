"""ChatLLM wrapper around the OpenAI Python SDK.

Any provider that exposes an OpenAI-compatible ``/v1/chat/completions``
endpoint works transparently: OpenCode Zen, OpenAI, Ollama, LM Studio,
vLLM, etc.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ToolCallRequest:
    """A single tool call requested by the LLM."""

    id: str
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    """Normalised response from the LLM."""

    content: str = ""
    tool_calls: List[ToolCallRequest] = field(default_factory=list)
    usage: Dict[str, int] = field(default_factory=dict)
    finish_reason: str = ""


# ---------------------------------------------------------------------------
# ChatLLM
# ---------------------------------------------------------------------------


class ChatLLM:
    """Thin wrapper around ``openai.OpenAI`` chat completions.

    Parameters
    ----------
    client:
        An ``openai.OpenAI`` (or ``openai.AsyncOpenAI`` sync equivalent)
        instance already configured with base_url and api_key.
    model:
        Model identifier sent in the ``model`` field.
    temperature:
        Sampling temperature.  Defaults to ``0`` for deterministic tool
        calling; override for creative / research tasks.
    """

    def __init__(
        self,
        client: Any,
        model: str,
        temperature: float = 0.0,
    ) -> None:
        self._client = client
        self._model = model
        self._temperature = temperature

    # -- public API --------------------------------------------------------

    def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        """Non-streaming chat completion.

        Returns an :class:`LLMResponse` with either ``content`` (text) or
        ``tool_calls`` (one or more tool invocations).
        """
        kwargs: Dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self._temperature,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        raw = self._client.chat.completions.create(**kwargs)
        return self._normalize(raw)

    def stream_chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        on_text_chunk: Optional[Callable[[str], None]] = None,
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        """Streaming chat completion.

        Calls ``on_text_chunk`` for each incremental text token.  Tool
        calls are accumulated and returned in the final
        :class:`LLMResponse`.
        """
        kwargs: Dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self._temperature,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        chunks = self._client.chat.completions.create(**kwargs)
        return self._normalize_stream(chunks, on_text_chunk=on_text_chunk)

    # -- internals ---------------------------------------------------------

    @staticmethod
    def _normalize(raw: Any) -> LLMResponse:
        """Convert a raw ``ChatCompletion`` into :class:`LLMResponse`."""
        choice = raw.choices[0]
        message = choice.message
        content = message.content or ""
        tool_calls: List[ToolCallRequest] = []

        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    args = {}
                tool_calls.append(
                    ToolCallRequest(
                        id=tc.id or "",
                        name=tc.function.name,
                        arguments=args,
                    )
                )

        usage: Dict[str, int] = {}
        if raw.usage:
            usage = {
                "prompt_tokens": getattr(raw.usage, "prompt_tokens", 0),
                "completion_tokens": getattr(raw.usage, "completion_tokens", 0),
                "total_tokens": getattr(raw.usage, "total_tokens", 0),
            }

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=choice.finish_reason or "",
        )

    @staticmethod
    def _normalize_stream(
        chunks: Any,
        on_text_chunk: Optional[Callable[[str], None]] = None,
    ) -> LLMResponse:
        """Accumulate a streaming response into :class:`LLMResponse`."""
        content_parts: List[str] = []
        # Accumulate tool calls by index.
        tool_call_accum: Dict[int, Dict[str, Any]] = {}

        for chunk in chunks:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            finish = chunk.choices[0].finish_reason

            # Text content.
            if delta and delta.content:
                content_parts.append(delta.content)
                if on_text_chunk:
                    on_text_chunk(delta.content)

            # Tool calls arrive as incremental deltas.
            if delta and delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tool_call_accum:
                        tool_call_accum[idx] = {
                            "id": "",
                            "name": "",
                            "arguments": "",
                        }
                    entry = tool_call_accum[idx]
                    if tc_delta.id:
                        entry["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            entry["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            entry["arguments"] += tc_delta.function.arguments

        # Build final tool calls.
        tool_calls: List[ToolCallRequest] = []
        for idx in sorted(tool_call_accum):
            entry = tool_call_accum[idx]
            try:
                args = json.loads(entry["arguments"])
            except (json.JSONDecodeError, TypeError):
                args = {}
            tool_calls.append(
                ToolCallRequest(
                    id=entry["id"],
                    name=entry["name"],
                    arguments=args,
                )
            )

        return LLMResponse(
            content="".join(content_parts),
            tool_calls=tool_calls,
            finish_reason=finish or "",
        )
