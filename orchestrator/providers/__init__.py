"""Pluggable LLM provider abstraction.

Supports any OpenAI-compatible API (OpenCode Zen, OpenAI, Ollama, etc.).
Configuration via environment variables or explicit arguments::

    VT_LLM_PROVIDER=opencode-zen
    VT_LLM_MODEL=gpt-5.3-codex
    VT_LLM_API_KEY=sk-...
    VT_LLM_BASE_URL=https://opencode.ai/zen/v1
"""

from __future__ import annotations

from .chat import ChatLLM, LLMResponse, ToolCallRequest
from .llm import build_llm

__all__ = ["ChatLLM", "LLMResponse", "ToolCallRequest", "build_llm"]
