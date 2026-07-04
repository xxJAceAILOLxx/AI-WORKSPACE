"""LLM factory — builds a :class:`ChatLLM` from environment or arguments.

Defaults target OpenCode Zen (OpenAI-compatible endpoint)::

    VT_LLM_PROVIDER=opencode-zen
    VT_LLM_MODEL=gpt-5.3-codex
    VT_LLM_API_KEY=sk-...
    VT_LLM_BASE_URL=https://opencode.ai/zen/v1

Any OpenAI-compatible provider works by overriding the env vars (e.g.
``VT_LLM_BASE_URL=http://localhost:11434/v1`` for Ollama).
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Defaults for OpenCode Zen.
_DEFAULT_BASE_URL = "https://opencode.ai/zen/v1"
_DEFAULT_MODEL = "deepseek-v4-flash-free"
_DEFAULT_TEMPERATURE = 0.0


def build_llm(
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: float = _DEFAULT_TEMPERATURE,
) -> "ChatLLM":
    """Construct a :class:`ChatLLM` from arguments or environment variables.

    Priority: explicit arguments > env vars > defaults.

    Parameters
    ----------
    provider:
        Logical provider name (currently unused; reserved for future
        provider-specific quirks).  Read from ``VT_LLM_PROVIDER``.
    model:
        Model identifier.  Read from ``VT_LLM_MODEL``.
    api_key:
        API key.  Read from ``VT_LLM_API_KEY``.  If still the placeholder
        value, a warning is logged.
    base_url:
        OpenAI-compatible base URL.  Read from ``VT_LLM_BASE_URL``.
    temperature:
        Sampling temperature.  Defaults to 0 for deterministic tool use.
    """
    # Lazy-load .env so python-dotenv is optional.
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    provider = provider or os.getenv("VT_LLM_PROVIDER", "opencode-zen")
    model = model or os.getenv("VT_LLM_MODEL", _DEFAULT_MODEL)
    api_key = api_key or os.getenv("VT_LLM_API_KEY", "")
    base_url = base_url or os.getenv("VT_LLM_BASE_URL", _DEFAULT_BASE_URL)

    if not api_key or api_key.startswith("sk-your-"):
        logger.warning(
            "No valid VT_LLM_API_KEY set. LLM calls will fail. "
            "Set it in .env or export VT_LLM_API_KEY."
        )

    # Import openai lazily so the module loads even when the dep is missing.
    try:
        import openai
    except ImportError as exc:
        raise ImportError(
            "The 'openai' package is required for LLM integration. "
            "Install it with: pip install openai"
        ) from exc

    client = openai.OpenAI(api_key=api_key, base_url=base_url)

    from .chat import ChatLLM

    return ChatLLM(client=client, model=model, temperature=temperature)
