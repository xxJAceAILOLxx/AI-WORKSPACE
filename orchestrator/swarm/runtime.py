"""Swarm runtime — schedules and executes tasks layer-by-layer."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from ..agent.tools import ToolRegistry, build_registry
from ..providers.chat import ChatLLM
from .models import SwarmAgent, SwarmRun, SwarmTask, TaskStatus
from .presets import load_preset
from .worker import SwarmWorker

logger = logging.getLogger(__name__)


class SwarmRuntime:
    """Orchestrate a swarm run: schedule tasks, run workers, collect results.

    Parameters
    ----------
    llm:
        The LLM client for worker agents.
    tool_registry:
        The global tool registry.  Workers get a filtered subset.
    on_task_start:
        Optional callback ``(task_id, agent_id)`` when a task starts.
    on_task_end:
        Optional callback ``(task_id, status)`` when a task completes.
    """

    def __init__(
        self,
        llm: ChatLLM,
        tool_registry: Optional[ToolRegistry] = None,
        on_task_start: Optional[Callable[[str, str], None]] = None,
        on_task_end: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        self.llm = llm
        self.tool_registry = tool_registry or build_registry()
        self.on_task_start = on_task_start
        self.on_task_end = on_task_end

    def run(
        self,
        preset_name: str,
        user_vars: Optional[Dict[str, str]] = None,
    ) -> SwarmRun:
        """Execute a swarm preset and return the completed :class:`SwarmRun`."""
        preset = load_preset(preset_name, user_vars=user_vars)

        run = SwarmRun(
            preset_name=preset_name,
            user_vars=user_vars or {},
            agents=preset["agents"],
            tasks=preset["tasks"],
        )
        run.status = "running"

        # Build agent lookup.
        agent_map = {a.id: a for a in run.agents}

        # Execute tasks layer by layer.
        completed_tasks: Dict[str, str] = {}  # task_id -> result

        remaining = list(run.tasks)
        while remaining:
            # Find tasks whose deps are all done.
            ready = [
                t for t in remaining
                if all(d in completed_tasks for d in t.depends_on)
            ]
            if not ready:
                logger.warning("Swarm DAG deadlock — %d tasks remaining", len(remaining))
                for t in remaining:
                    t.status = TaskStatus.FAILED
                    t.error = "DAG deadlock"
                break

            for task in ready:
                agent = agent_map.get(task.agent_id)
                if agent is None:
                    task.status = TaskStatus.FAILED
                    task.error = f"Unknown agent {task.agent_id!r}"
                    continue

                # Build prompt from template + upstream results.
                prompt = task.prompt_template
                for input_key, upstream_id in task.input_from.items():
                    upstream_result = completed_tasks.get(upstream_id, "")
                    prompt = prompt.replace("{" + input_key + "}", upstream_result)

                if self.on_task_start:
                    self.on_task_start(task.id, agent.id)

                task.status = TaskStatus.RUNNING
                worker = SwarmWorker(
                    llm=self.llm,
                    tool_registry=self.tool_registry,
                    agent=agent,
                )
                try:
                    result = worker.run(prompt)
                    task.result = result
                    task.status = TaskStatus.DONE
                    completed_tasks[task.id] = result
                except Exception as exc:
                    task.error = str(exc)
                    task.status = TaskStatus.FAILED
                    logger.exception("Swarm task %s failed", task.id)

                if self.on_task_end:
                    self.on_task_end(task.id, task.status.value)

            # Remove completed/failed tasks from remaining.
            remaining = [t for t in remaining if t.status == TaskStatus.BLOCKED]

        # Determine overall status.
        statuses = {t.status for t in run.tasks}
        if all(s == TaskStatus.DONE for s in statuses):
            run.status = "completed"
        elif any(s == TaskStatus.FAILED for s in statuses):
            run.status = "partial_failure"
        else:
            run.status = "completed"

        return run
