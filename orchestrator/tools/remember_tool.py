"""Memory tool — persist findings across sessions."""

from __future__ import annotations

import json
from typing import Any

from ..agent.tools import BaseTool


class RememberTool(BaseTool):
    name = "remember"
    description = (
        "Save an important finding, insight, or lesson to persistent memory. "
        "Use this to record backtest results, strategy insights, or mistakes."
    )
    is_readonly = False
    parameters = {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "What to remember"},
            "category": {
                "type": "string",
                "description": "Category: insight, result, mistake, rule, observation",
            },
        },
        "required": ["content"],
    }

    def execute(self, **kwargs: Any) -> str:
        from ..memory import Memory

        content = kwargs.get("content", "")
        category = kwargs.get("category", "insight")

        try:
            memory = Memory(path="memory.md")
            section = f"## Agent Memory"
            bullet = f"- **[{category}]** {content}"
            memory.update_section(section.lstrip("#").strip(), bullet, mode="append")
            return json.dumps({"status": "ok", "saved": True, "category": category})
        except Exception as exc:
            return json.dumps({"status": "error", "error": str(exc)})


class ReadMemoryTool(BaseTool):
    name = "read_memory"
    description = "Read the current contents of persistent memory (memory.md)."
    is_readonly = True
    parameters = {"type": "object", "properties": {}}

    def execute(self, **kwargs: Any) -> str:
        from pathlib import Path

        path = Path("memory.md")
        if not path.exists():
            return json.dumps({"status": "ok", "content": ""})
        content = path.read_text(encoding="utf-8")
        return json.dumps({"status": "ok", "content": content[:8000]})
