"""Swarm data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    BLOCKED = "blocked"
    RETRYING = "retrying"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SwarmAgent:
    """A single agent (worker) in a swarm preset."""

    id: str
    role: str
    system_prompt: str = ""
    tools: List[str] = field(default_factory=list)
    max_iterations: int = 25
    timeout_seconds: int = 300
    model_name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "system_prompt": self.system_prompt,
            "tools": self.tools,
            "max_iterations": self.max_iterations,
            "timeout_seconds": self.timeout_seconds,
            "model_name": self.model_name,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SwarmAgent":
        return cls(
            id=data.get("id", ""),
            role=data.get("role", ""),
            system_prompt=data.get("system_prompt", ""),
            tools=data.get("tools", []),
            max_iterations=data.get("max_iterations", 25),
            timeout_seconds=data.get("timeout_seconds", 300),
            model_name=data.get("model_name"),
        )


@dataclass
class SwarmTask:
    """A task in the swarm DAG."""

    id: str
    agent_id: str
    prompt_template: str = ""
    depends_on: List[str] = field(default_factory=list)
    input_from: Dict[str, str] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.BLOCKED
    result: str = ""
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "prompt_template": self.prompt_template,
            "depends_on": self.depends_on,
            "input_from": self.input_from,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SwarmTask":
        return cls(
            id=data.get("id", ""),
            agent_id=data.get("agent_id", ""),
            prompt_template=data.get("prompt_template", ""),
            depends_on=data.get("depends_on", []),
            input_from=data.get("input_from", {}),
            status=TaskStatus(data.get("status", "blocked")),
            result=data.get("result", ""),
            error=data.get("error", ""),
        )


@dataclass
class SwarmRun:
    """A complete swarm run with its agents, tasks, and DAG."""

    id: str = field(default_factory=lambda: f"swarm-{uuid4().hex[:8]}")
    preset_name: str = ""
    status: str = "pending"
    user_vars: Dict[str, str] = field(default_factory=dict)
    agents: List[SwarmAgent] = field(default_factory=list)
    tasks: List[SwarmTask] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "preset_name": self.preset_name,
            "status": self.status,
            "user_vars": self.user_vars,
            "agents": [a.to_dict() for a in self.agents],
            "tasks": [t.to_dict() for t in self.tasks],
            "created_at": self.created_at,
        }
