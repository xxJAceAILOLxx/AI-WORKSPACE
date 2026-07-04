"""Tests for the Swarm subsystem — presets, DAG, and runtime."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator.swarm.presets import list_presets, load_preset, inspect_preset
from orchestrator.swarm.models import SwarmAgent, SwarmTask, TaskStatus


def test_list_presets():
    presets = list_presets()
    assert "investment_committee" in presets
    assert "equity_research_team" in presets
    assert len(presets) >= 5


def test_load_preset():
    preset = load_preset("investment_committee")
    assert preset["name"] == "investment_committee"
    assert len(preset["agents"]) == 4
    assert len(preset["tasks"]) == 4


def test_investement_committee_dag():
    info = inspect_preset("investment_committee")
    assert info["valid"]
    assert len(info["errors"]) == 0
    # bull and bear have no deps, risk depends on both, PM depends on risk.
    tasks = {t["id"]: t for t in info["tasks"]}
    assert tasks["task-bull"]["depends_on"] == []
    assert tasks["task-bear"]["depends_on"] == []
    assert set(tasks["task-risk"]["depends_on"]) == {"task-bull", "task-bear"}
    assert tasks["task-decision"]["depends_on"] == ["task-risk"]


def test_inspect_preset_variables():
    info = inspect_preset("investment_committee")
    var_names = [v["name"] for v in info["variables"]]
    assert "target" in var_names


def test_load_preset_with_variables():
    preset = load_preset("investment_committee", user_vars={"target": "SPY", "market": "bullish"})
    # Variables should be substituted in prompt templates.
    for task in preset["tasks"]:
        assert "{target}" not in task.prompt_template
        assert "{market}" not in task.prompt_template


def test_load_preset_nonexistent():
    with pytest.raises(FileNotFoundError):
        load_preset("nonexistent_preset")


def test_swarm_models():
    agent = SwarmAgent(id="a1", role="analyst", tools=["web_search"])
    assert agent.to_dict()["id"] == "a1"

    task = SwarmTask(id="t1", agent_id="a1", depends_on=[])
    assert task.status == TaskStatus.BLOCKED

    task2 = SwarmTask.from_dict({"id": "t2", "agent_id": "a1", "status": "running"})
    assert task2.status == TaskStatus.RUNNING
