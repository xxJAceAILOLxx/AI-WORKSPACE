"""Research goal tools — create, query, add evidence, update status."""

from __future__ import annotations

import json
from typing import Any

from ..agent.tools import BaseTool
from ..goal.store import GoalStore


class StartResearchGoalTool(BaseTool):
    name = "start_research_goal"
    description = "Create a new research goal with objective and acceptance criteria."
    parameters = {
        "type": "object",
        "properties": {
            "objective": {"type": "string", "description": "What the goal aims to achieve"},
            "session_id": {"type": "string", "description": "Session ID to bind the goal to"},
            "criteria": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Acceptance criteria",
            },
        },
        "required": ["objective"],
    }

    def execute(self, **kwargs: Any) -> str:
        store = GoalStore()
        g = store.create_goal(
            objective=kwargs.get("objective", ""),
            session_id=kwargs.get("session_id", ""),
            criteria=kwargs.get("criteria", []),
            source="manual",
        )
        return json.dumps({"status": "ok", "goal": g.to_dict()})


class GetResearchGoalTool(BaseTool):
    name = "get_research_goal"
    description = "Get a research goal by ID."
    is_readonly = True
    parameters = {
        "type": "object",
        "properties": {
            "goal_id": {"type": "string", "description": "Goal ID"},
        },
        "required": ["goal_id"],
    }

    def execute(self, **kwargs: Any) -> str:
        store = GoalStore()
        g = store.get_goal(kwargs["goal_id"])
        if g is None:
            return json.dumps({"status": "error", "error": "goal not found"})
        return json.dumps({"status": "ok", "goal": g.to_dict()})


class AddGoalEvidenceTool(BaseTool):
    name = "add_goal_evidence"
    description = "Add an evidence row to a research goal."
    parameters = {
        "type": "object",
        "properties": {
            "goal_id": {"type": "string", "description": "Goal ID"},
            "claim": {"type": "string", "description": "The evidence claim"},
            "source": {"type": "string", "description": "Source of the evidence"},
            "status": {
                "type": "string",
                "description": "pending | verified | refuted",
            },
        },
        "required": ["goal_id", "claim"],
    }

    def execute(self, **kwargs: Any) -> str:
        store = GoalStore()
        g = store.add_evidence(
            goal_id=kwargs["goal_id"],
            claim=kwargs.get("claim", ""),
            source=kwargs.get("source", ""),
            status=kwargs.get("status", "pending"),
        )
        if g is None:
            return json.dumps({"status": "error", "error": "goal not found"})
        return json.dumps({"status": "ok", "goal": g.to_dict()})


class UpdateGoalStatusTool(BaseTool):
    name = "update_goal_status"
    description = "Update a research goal's status (active, completed, cancelled)."
    parameters = {
        "type": "object",
        "properties": {
            "goal_id": {"type": "string", "description": "Goal ID"},
            "status": {"type": "string", "description": "active | completed | cancelled"},
        },
        "required": ["goal_id", "status"],
    }

    def execute(self, **kwargs: Any) -> str:
        store = GoalStore()
        g = store.update_status(
            goal_id=kwargs["goal_id"],
            status=kwargs.get("status", "active"),
        )
        if g is None:
            return json.dumps({"status": "error", "error": "goal not found"})
        return json.dumps({"status": "ok", "goal": g.to_dict()})
