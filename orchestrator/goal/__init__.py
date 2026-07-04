"""Research Goal Store — session-scoped goals with evidence tracking."""

from __future__ import annotations

from .models import Goal
from .store import GoalStore

__all__ = ["Goal", "GoalStore"]
