"""System prompt construction for the agent loop.

The system prompt tells the LLM what tools are available, how to use
them, and what the current context is (date, memory, etc.).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from .tools import ToolRegistry

# ---------------------------------------------------------------------------
# System prompt template
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_TEMPLATE = """\
You are an AI trading research agent for a quantitative trading vault.

## Your role
You help traders research, design, backtest, and validate trading strategies.
You have access to {tool_count} tools. Use them to gather data, create hypotheses,
run backtests, and manage research goals.

## Capabilities
- Search the web for trading research and market data
- Create and manage trading hypotheses
- Generate backtest configurations and scaffold signal engines
- Run backtests against the local strategy registry
- Track research goals with evidence and acceptance criteria
- Manage persistent memory across sessions

## Workflow
When given a trading idea or research task:
1. **Research**: Use web_search and market data tools to gather information
2. **Design**: Create a hypothesis with create_hypothesis, define the signal
3. **Backtest**: Use generate_backtest_config → scaffold_signal_engine → run backtest
4. **Validate**: Check metrics (Sharpe, drawdown, win rate) against criteria
5. **Learn**: Record findings in memory with remember

## Rules
- Always use tools for data gathering; do not fabricate prices or metrics
- When running backtests, use the existing strategy registry when possible
- For new strategies, scaffold the signal engine code and let the user review
- Record important findings with the remember tool
- Be honest about backtest results — no sugarcoating losses

## Current context
- Date: {current_date}
- Available tools: {tool_descriptions}
"""


def build_system_prompt(
    registry: ToolRegistry,
    extra_context: Optional[Dict[str, str]] = None,
) -> str:
    """Build the system prompt with current tool and context info.

    Parameters
    ----------
    registry:
        The tool registry to describe in the prompt.
    extra_context:
        Additional key-value pairs to interpolate into the prompt.
    """
    tool_descs: List[str] = []
    for name in registry.list_names():
        tool = registry.get(name)
        tool_descs.append(f"- {name}: {tool.description[:120]}")

    prompt = _SYSTEM_PROMPT_TEMPLATE.format(
        tool_count=len(registry),
        current_date=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        tool_descriptions="\n".join(tool_descs) if tool_descs else "(none)",
    )

    if extra_context:
        for key, value in extra_context.items():
            prompt = prompt.replace("{" + key + "}", value)

    return prompt
