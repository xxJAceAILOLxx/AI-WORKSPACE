"""Goal Store — persistent research goals with evidence tracking."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import Evidence, Goal, _new_id, _now_iso

logger = logging.getLogger(__name__)

_DEFAULT_STORE_DIR = Path(__file__).parent / "store"


class GoalStore:
    """Persistent store for research goals.

    Parameters
    ----------
    store_dir:
        Directory for goal JSON files.
    """

    def __init__(self, store_dir: Optional[Path] = None) -> None:
        self._store_dir = Path(store_dir) if store_dir else _DEFAULT_STORE_DIR
        self._store_dir.mkdir(parents=True, exist_ok=True)

    def create_goal(
        self,
        objective: str,
        session_id: str = "",
        criteria: Optional[List[str]] = None,
        source: str = "manual",
    ) -> Goal:
        """Create and persist a new goal."""
        g = Goal(
            objective=objective,
            session_id=session_id,
            criteria=criteria or [],
            source=source,
        )
        self._save(g)
        logger.info("Created goal %s: %s", g.goal_id, g.objective[:60])
        return g

    def get_goal(self, goal_id: str) -> Optional[Goal]:
        """Load a goal by ID."""
        path = self._path(goal_id)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return Goal.from_dict(json.load(f))

    def list_goals(
        self,
        session_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Goal]:
        """List goals, optionally filtered."""
        items: List[Goal] = []
        for path in sorted(self._store_dir.glob("*.json"), reverse=True):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    g = Goal.from_dict(json.load(f))
                if session_id and g.session_id != session_id:
                    continue
                if status and g.status != status:
                    continue
                items.append(g)
                if len(items) >= limit:
                    break
            except Exception:
                logger.warning("Corrupt goal file: %s", path)
        return items

    def replace_goal(
        self,
        session_id: str,
        objective: str,
        criteria: Optional[List[str]] = None,
        source: str = "autopilot",
    ) -> Goal:
        """Replace any active goal for the session with a new one.

        If an active goal exists, it is marked as cancelled first.
        """
        # Cancel existing active goals for this session.
        for g in self.list_goals(session_id=session_id, status="active"):
            g.status = "cancelled"
            g.updated_at = _now_iso()
            self._save(g)

        return self.create_goal(
            objective=objective,
            session_id=session_id,
            criteria=criteria,
            source=source,
        )

    def add_evidence(
        self,
        goal_id: str,
        claim: str,
        source: str = "",
        status: str = "pending",
    ) -> Optional[Goal]:
        """Add an evidence row to a goal."""
        g = self.get_goal(goal_id)
        if g is None:
            return None
        g.evidence.append(
            Evidence(claim=claim, source=source, status=status)
        )
        g.updated_at = _now_iso()
        self._save(g)
        return g

    def update_status(
        self,
        goal_id: str,
        status: str,
    ) -> Optional[Goal]:
        """Update a goal's status."""
        g = self.get_goal(goal_id)
        if g is None:
            return None
        g.status = status
        g.updated_at = _now_iso()
        self._save(g)
        return g

    def _path(self, goal_id: str) -> Path:
        return self._store_dir / f"{goal_id}.json"

    def _save(self, g: Goal) -> None:
        path = self._path(g.goal_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(g.to_dict(), f, indent=2, ensure_ascii=False)
