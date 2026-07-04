"""Swarm tool — launch multi-agent team runs."""

from __future__ import annotations

import json
from typing import Any

from ..agent.tools import BaseTool


class RunSwarmTool(BaseTool):
    name = "run_swarm"
    description = (
        "Launch a multi-agent swarm team. Available presets: "
        "investment_committee, equity_research_team, quant_strategy_desk, "
        "risk_committee, macro_strategy_forum."
    )
    is_readonly = False
    parameters = {
        "type": "object",
        "properties": {
            "preset_name": {
                "type": "string",
                "description": "Preset name (e.g. investment_committee)",
            },
            "prompt": {
                "type": "string",
                "description": "The task prompt / variables to substitute into presets",
            },
        },
        "required": ["preset_name", "prompt"],
    }

    def execute(self, **kwargs: Any) -> str:
        from ..providers.llm import build_llm
        from ..agent.tools import build_registry
        from ..swarm.runtime import SwarmRuntime
        from ..swarm.presets import list_presets

        preset_name = kwargs.get("preset_name", "")
        prompt = kwargs.get("prompt", "")

        available = list_presets()
        if preset_name not in available:
            return json.dumps({
                "status": "error",
                "error": f"Unknown preset {preset_name!r}. Available: {available}",
            })

        try:
            llm = build_llm()
        except Exception as exc:
            return json.dumps({"status": "error", "error": f"LLM unavailable: {exc}"})

        registry = build_registry()
        runtime = SwarmRuntime(llm=llm, tool_registry=registry)

        # Parse prompt into user_vars.
        user_vars = {"target": prompt}
        if "=" in prompt:
            for part in prompt.split(","):
                if "=" in part:
                    k, v = part.split("=", 1)
                    user_vars[k.strip()] = v.strip()

        try:
            run = runtime.run(preset_name, user_vars=user_vars)
            return json.dumps({
                "status": "ok",
                "run_id": run.id,
                "preset": preset_name,
                "run_status": run.status,
                "tasks": [
                    {
                        "id": t.id,
                        "agent": t.agent_id,
                        "status": t.status.value,
                        "result_preview": t.result[:500] if t.result else "",
                    }
                    for t in run.tasks
                ],
            })
        except Exception as exc:
            return json.dumps({"status": "error", "error": str(exc)})
