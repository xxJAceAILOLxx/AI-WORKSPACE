"""Swarm preset loader — reads YAML preset files from the presets/ directory."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .models import SwarmAgent, SwarmTask, TaskStatus

_PRESETS_DIR = Path(__file__).parent / "presets"


def list_presets() -> List[str]:
    """Return sorted list of available preset names."""
    if not _PRESETS_DIR.exists():
        return []
    return sorted(p.stem for p in _PRESETS_DIR.glob("*.yaml"))


def load_preset(
    name: str,
    user_vars: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Load a YAML preset and return parsed dict with agents + tasks.

    Parameters
    ----------
    name:
        Preset name (filename without .yaml).
    user_vars:
        Variable values to substitute into prompt templates.
    """
    path = _PRESETS_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Preset {name!r} not found in {_PRESETS_DIR}")

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    # Parse agents.
    agents = [
        SwarmAgent.from_dict(a) for a in raw.get("agents", [])
    ]

    # Parse tasks.
    tasks = []
    for t in raw.get("tasks", []):
        task = SwarmTask.from_dict(t)
        # Tasks without depends_on start as pending.
        if not task.depends_on:
            task.status = TaskStatus.PENDING
        tasks.append(task)

    # Substitute variables into prompt templates.
    if user_vars:
        for task in tasks:
            try:
                task.prompt_template = task.prompt_template.format(**user_vars)
            except KeyError:
                pass  # Leave unresolved placeholders.

    return {
        "name": raw.get("name", name),
        "title": raw.get("title", ""),
        "description": raw.get("description", ""),
        "variables": raw.get("variables", []),
        "agents": agents,
        "tasks": tasks,
    }


def inspect_preset(name: str) -> Dict[str, Any]:
    """Dry-run a preset: validate DAG, list agents/tasks, no LLM calls."""
    try:
        preset = load_preset(name)
    except Exception as exc:
        return {"valid": False, "errors": [str(exc)]}

    errors: List[str] = []
    warnings: List[str] = []

    # Validate task dependencies.
    task_ids = {t.id for t in preset["tasks"]}
    agent_ids = {a.id for a in preset["agents"]}

    for task in preset["tasks"]:
        if task.agent_id not in agent_ids:
            errors.append(f"Task {task.id!r} references unknown agent {task.agent_id!r}")
        for dep in task.depends_on:
            if dep not in task_ids:
                errors.append(f"Task {task.id!r} depends on unknown task {dep!r}")

    # Compute topological layers.
    layers = _topological_layers(preset["tasks"])

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "variables": preset["variables"],
        "agents": [a.to_dict() for a in preset["agents"]],
        "tasks": [t.to_dict() for t in preset["tasks"]],
        "layers": layers,
    }


def _topological_layers(tasks: List[SwarmTask]) -> List[List[str]]:
    """Compute topological ordering of tasks into layers."""
    task_map = {t.id: t for t in tasks}
    completed: set = set()
    layers: List[List[str]] = []

    remaining = list(tasks)
    while remaining:
        # Find tasks whose deps are all completed.
        ready = [t for t in remaining if all(d in completed for d in t.depends_on)]
        if not ready:
            # Circular dependency — break by taking remaining.
            layers.append([t.id for t in remaining])
            break
        layers.append([t.id for t in ready])
        for t in ready:
            completed.add(t.id)
        remaining = [t for t in remaining if t.id not in completed]

    return layers
