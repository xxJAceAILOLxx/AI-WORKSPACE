"""Goal data model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid4().hex[:12]


@dataclass
class Evidence:
    """A single evidence row attached to a goal."""

    claim: str = ""
    source: str = ""
    status: str = "pending"  # pending | verified | refuted
    added_at: str = field(default_factory=_now_iso)


@dataclass
class Goal:
    """A research goal with claims, criteria, and evidence.

    Attributes
    ----------
    goal_id:
        Unique identifier.
    session_id:
        Session this goal belongs to.
    objective:
        What the goal aims to achieve.
    criteria:
        Acceptance criteria that must be met.
    evidence:
        Evidence rows supporting or refuting claims.
    status:
        One of: active, completed, cancelled.
    source:
        How the goal was created (e.g. "autopilot", "manual").
    """

    goal_id: str = field(default_factory=_new_id)
    session_id: str = ""
    objective: str = ""
    criteria: List[str] = field(default_factory=list)
    evidence: List[Evidence] = field(default_factory=list)
    status: str = "active"
    source: str = "manual"
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "session_id": self.session_id,
            "objective": self.objective,
            "criteria": self.criteria,
            "evidence": [
                {
                    "claim": e.claim,
                    "source": e.source,
                    "status": e.status,
                    "added_at": e.added_at,
                }
                for e in self.evidence
            ],
            "status": self.status,
            "source": self.source,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Goal":
        evidence = [
            Evidence(
                claim=e.get("claim", ""),
                source=e.get("source", ""),
                status=e.get("status", "pending"),
                added_at=e.get("added_at", ""),
            )
            for e in data.get("evidence", [])
        ]
        return cls(
            goal_id=data.get("goal_id", _new_id()),
            session_id=data.get("session_id", ""),
            objective=data.get("objective", ""),
            criteria=data.get("criteria", []),
            evidence=evidence,
            status=data.get("status", "active"),
            source=data.get("source", "manual"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )
