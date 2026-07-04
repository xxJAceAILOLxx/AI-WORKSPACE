"""Tests for Chunk 4: orchestrator package.

Covers:

* All 12 agents are loaded and mapped to the expected stages.
* ``python -m orchestrator.cli --list`` lists every agent.
* ``python -m orchestrator.cli --agent backtest_engine --strategy ibs_spy``
  prints a populated prompt and runs the backtest, producing metrics.
* ``python -m orchestrator.cli --workflow full`` runs every stage
  without errors and appends a run entry to ``memory.md`` (test copy).
* ``detect_strategy_names`` correctly tokenises free-text ideas.
* :class:`Memory` round-trips a document and ``append_run`` works.
* :class:`Workflow` can be driven directly without the CLI.

The workflow tests use a temporary ``memory.md`` copy so the vault
note is never modified by the test suite.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import List

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ORCHESTRATOR_PKG = PROJECT_ROOT  # so the package import path resolves

# Ensure the project root is on sys.path for in-process tests.
sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_cli(*args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    """Invoke ``python -m orchestrator.cli`` and capture output."""
    cmd = [sys.executable, "-m", "orchestrator.cli", *args]
    return subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
    )


# ---------------------------------------------------------------------------
# Agent registry
# ---------------------------------------------------------------------------


EXPECTED_AGENTS = [
    "strategy_architect",
    "backtest_engine",
    "risk_manager",
    "market_regime_detector",
    "structure_analyst",
    "order_flow_interpreter",
    "mistake_tracker",
    "knowledge_curator",
    "web_researcher",
    "prop_firm_challenger",
    "neural_network_architect",
    "portfolio_optimizer",
]

# Stage -> expected primary agent(s).  Workflow stages are driven by the
# first agent in the by_stage(stage) ordering.
EXPECTED_STAGE_AGENTS = {
    "research": "web_researcher",
    "design": "strategy_architect",
    "backtest": "backtest_engine",
    "validate": "risk_manager",
    "deploy": "prop_firm_challenger",
    "monitor": "mistake_tracker",
    "learn": "knowledge_curator",
}


def test_all_twelve_agents_loaded():
    from orchestrator.agents import AGENTS, list_agents

    assert len(AGENTS) == 12, f"expected 12 agents, got {len(AGENTS)}: {sorted(AGENTS)}"
    names = set(list_agents())
    assert set(EXPECTED_AGENTS) == names, (
        f"agent name mismatch; missing={set(EXPECTED_AGENTS) - names} "
        f"extra={names - set(EXPECTED_AGENTS)}"
    )


@pytest.mark.parametrize("agent_name", EXPECTED_AGENTS)
def test_each_agent_has_required_fields(agent_name):
    from orchestrator.agents import get_agent

    agent = get_agent(agent_name)
    assert agent.name == agent_name
    assert isinstance(agent.purpose, str) and agent.purpose
    assert isinstance(agent.responsibilities, tuple) and len(agent.responsibilities) >= 1
    assert isinstance(agent.prompt_template, str) and agent.prompt_template
    assert isinstance(agent.references, tuple) and len(agent.references) >= 1
    assert agent.stage in (
        "research",
        "design",
        "backtest",
        "validate",
        "deploy",
        "monitor",
        "learn",
    )


@pytest.mark.parametrize("stage,expected_first", list(EXPECTED_STAGE_AGENTS.items()))
def test_primary_agent_for_stage_matches_agents_md(stage, expected_first):
    """The primary agent per stage must match the agents.md workflow section."""
    from orchestrator.agents import by_stage, primary_agent

    # ``by_stage`` returns every agent mapped to ``stage`` (sorted).
    stage_agents = [a.name for a in by_stage(stage)]
    assert expected_first in stage_agents, (
        f"primary agent {expected_first!r} is not mapped to stage {stage!r}; "
        f"got {stage_agents}"
    )
    # ``primary_agent`` returns the canonical workflow driver for the stage.
    assert primary_agent(stage).name == expected_first


def test_get_agent_unknown_raises():
    from orchestrator.agents import get_agent

    with pytest.raises(KeyError):
        get_agent("not_a_real_agent")


def test_by_stage_unknown_raises():
    from orchestrator.agents import by_stage

    with pytest.raises(ValueError):
        by_stage("not_a_real_stage")


def test_agent_format_prompt_substitutes_placeholders():
    from orchestrator.agents import get_agent

    agent = get_agent("backtest_engine")
    rendered = agent.format_prompt(
        strategy_name="ibs_spy",
        ticker="SPY",
        start="2020-01-01",
        end="2021-01-01",
        execution="next_open",
        cost_model="etf_0.1pct",
    )
    assert "ibs_spy" in rendered
    assert "SPY" in rendered
    assert "2020-01-01" in rendered
    assert "next_open" in rendered


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------


def test_memory_load_returns_dict_with_sections():
    from orchestrator.memory import Memory

    mem = Memory(path="memory.md")
    data = mem.load()
    assert isinstance(data, dict)
    assert "title" in data and "sections" in data
    assert isinstance(data["sections"], list)
    assert data["title"] == "Memory"
    headings = [s["heading"] for s in data["sections"]]
    assert "Last Updated" in headings


def test_memory_roundtrip_is_stable(tmp_path):
    from orchestrator.memory import Memory, parse_markdown, render_markdown

    sample = (
        "# Memory\n\n"
        "## Last Updated\n2026-06-26\n\n---\n\n"
        "## Trading Framework (From Vault)\n- rule 1\n- rule 2\n\n"
        "## Open Questions\n- question?\n"
    )
    path = tmp_path / "memory.md"
    path.write_text(sample, encoding="utf-8")

    mem = Memory(path=str(path))
    data = mem.load()
    assert data["title"] == "Memory"
    headings = [s["heading"] for s in data["sections"]]
    assert headings == ["Last Updated", "Trading Framework (From Vault)", "Open Questions"]

    # Re-render and re-parse must be stable.
    once = render_markdown(data)
    twice = render_markdown(parse_markdown(once))
    assert once == twice


def test_memory_append_run_creates_section(tmp_path):
    from orchestrator.memory import Memory

    path = tmp_path / "memory.md"
    path.write_text("# Memory\n\n## Notes\nhello\n", encoding="utf-8")

    mem = Memory(path=str(path))
    mem.append_run(
        {
            "idea": "IBS mean reversion",
            "strategy_name": "ibs_spy",
            "stages": ["research", "design", "backtest"],
            "metrics": {"profit_factor": 1.77, "sharpe": 0.14},
        }
    )

    after = path.read_text(encoding="utf-8")
    assert "## Framework Runs" in after
    assert "ibs_spy" in after
    assert "IBS mean reversion" in after
    # The metrics dict should be embedded as JSON.
    assert "profit_factor" in after


def test_memory_append_run_appends_to_existing_section(tmp_path):
    from orchestrator.memory import Memory

    initial = (
        "# Memory\n\n"
        "## Notes\nhello\n\n"
        "## Framework Runs\n- **old** legacy entry\n"
    )
    path = tmp_path / "memory.md"
    path.write_text(initial, encoding="utf-8")

    mem = Memory(path=str(path))
    mem.append_run({"idea": "second run", "strategy_name": "rsi2_mr"})

    after = path.read_text(encoding="utf-8")
    # Section preserved and new entry appended (not replacing).
    assert "## Framework Runs" in after
    assert "legacy entry" in after
    assert "rsi2_mr" in after


# ---------------------------------------------------------------------------
# Memory.update_section
# ---------------------------------------------------------------------------


def test_update_section_replace_overwrites_body(tmp_path):
    """update_section with mode='replace' swaps the body and keeps the H2 title."""
    from orchestrator.memory import Memory

    initial = (
        "# Memory\n\n"
        "## 9. Backtest snapshot\nold bullet\n\n"
        "## Notes\nkeep me\n"
    )
    path = tmp_path / "memory.md"
    path.write_text(initial, encoding="utf-8")

    mem = Memory(path=str(path))
    mem.update_section(
        "Backtest snapshot", "fresh content here", mode="replace"
    )

    after = path.read_text(encoding="utf-8")
    # Original H2 title preserved (with numeric prefix).
    assert "## 9. Backtest snapshot" in after
    # Body replaced.
    assert "fresh content here" in after
    assert "old bullet" not in after
    # Surrounding sections untouched.
    assert "keep me" in after
    assert after.index("## 9. Backtest snapshot") < after.index("## Notes")


def test_update_section_append_extends_body(tmp_path):
    """update_section with mode='append' concatenates without dropping content."""
    from orchestrator.memory import Memory

    initial = "# Memory\n\n## 9. Backtest snapshot\nfirst bullet\n"
    path = tmp_path / "memory.md"
    path.write_text(initial, encoding="utf-8")

    mem = Memory(path=str(path))
    mem.update_section("Backtest snapshot", "second bullet", mode="append")
    mem.update_section("Backtest snapshot", "third bullet", mode="append")

    after = path.read_text(encoding="utf-8")
    assert "first bullet" in after
    assert "second bullet" in after
    assert "third bullet" in after
    # All three should appear in order.
    assert (
        after.index("first bullet")
        < after.index("second bullet")
        < after.index("third bullet")
    )


def test_update_section_creates_section_when_missing(tmp_path):
    """A new H2 section is appended when no match is found."""
    from orchestrator.memory import Memory

    path = tmp_path / "memory.md"
    path.write_text("# Memory\n\n## Notes\nhello\n", encoding="utf-8")

    mem = Memory(path=str(path))
    mem.update_section("New Section", "brand new", mode="replace")

    after = path.read_text(encoding="utf-8")
    assert "## New Section" in after
    assert "brand new" in after
    # Existing section preserved.
    assert "hello" in after


def test_update_section_rejects_unknown_mode(tmp_path):
    from orchestrator.memory import Memory

    path = tmp_path / "memory.md"
    path.write_text("# Memory\n\n", encoding="utf-8")

    mem = Memory(path=str(path))
    with pytest.raises(ValueError):
        mem.update_section("Anything", "x", mode="bogus")


def test_update_section_matches_numbered_headings(tmp_path):
    """Heading matching tolerates a leading 'N. ' numeric prefix."""
    from orchestrator.memory import Memory

    initial = (
        "# Memory\n\n"
        "## 5. Registered strategies\n| old | row |\n|---|---|\n"
    )
    path = tmp_path / "memory.md"
    path.write_text(initial, encoding="utf-8")

    mem = Memory(path=str(path))
    mem.update_section(
        "Registered strategies", "| new | row |", mode="replace"
    )

    after = path.read_text(encoding="utf-8")
    assert "| new | row |" in after
    assert "| old | row |" not in after


def test_render_strategy_table_contains_known_strategies():
    from orchestrator.memory import render_strategy_table

    table = render_strategy_table()
    assert "| Name | Ticker | Entry | Exit | Sizing | Cost |" in table
    assert "`ibs_spy`" in table
    assert "`mr_portfolio`" in table


def test_render_snapshot_bullet_formats_metrics():
    from orchestrator.memory import render_snapshot_bullet

    bullet = render_snapshot_bullet(
        "ibs_spy",
        {
            "profit_factor": 1.66,
            "sharpe": 0.7,
            "cagr": 0.0876,
            "max_drawdown": 0.21,
            "win_rate": 0.6435,
            "trade_count": 230,
        },
        verdict="validate OK",
        timestamp="2026-06-28T07:00:13Z",
    )
    assert "2026-06-28T07:00:13Z" in bullet
    assert "`ibs_spy`" in bullet
    assert "PF 1.66" in bullet
    assert "Sharpe 0.70" in bullet
    assert "230 trades" in bullet
    assert "validate OK" in bullet


# ---------------------------------------------------------------------------
# Workflow (in-process)
# ---------------------------------------------------------------------------


def test_workflow_runs_all_stages_without_error(tmp_path):
    """A Workflow with no backtest_fn still completes all 7 stages."""
    from orchestrator.workflow import STAGES, Workflow

    captured: List[str] = []

    def printer(s: str) -> None:
        captured.append(s)

    memory_path = str(tmp_path / "memory.md")
    Path(memory_path).write_text("# Memory\n\n## Notes\nbase\n", encoding="utf-8")

    wf = Workflow(
        stages=list(STAGES),
        memory_path=memory_path,
        print_fn=printer,
        backtest_fn=None,  # explicit None -> default registry
    )
    ctx = {"idea": "noop run", "strategy_name": None}
    result = wf.run(ctx)

    # All 7 stage keys populated on the returned context.
    for stage in STAGES:
        assert stage in result, f"missing stage result for {stage!r}"
    # Backtest stage ran without a strategy -> no metrics, but no crash.
    assert result["backtest"]["ran"] is False
    # Learn stage appended to memory.
    assert result["learn"]["appended"] is True
    assert "Framework Runs" in Path(memory_path).read_text(encoding="utf-8")
    # Validate stage produced sane numbers.
    assert "max_drawdown" in result["validate"]
    # Captured output mentions each stage.
    combined = "\n".join(captured)
    for stage in STAGES:
        assert stage in combined, f"no output for stage {stage!r}"


def test_workflow_runs_real_backtest_and_records_metrics(tmp_path):
    """A Workflow with a real strategy should produce metrics and memory entry."""
    from orchestrator.workflow import STAGES, Workflow

    memory_path = str(tmp_path / "memory.md")
    Path(memory_path).write_text("# Memory\n\n## Notes\nbase\n", encoding="utf-8")

    wf = Workflow(stages=list(STAGES), memory_path=memory_path)
    ctx = {"idea": "run ibs_spy", "strategy_name": "ibs_spy"}
    result = wf.run(ctx)

    assert result["backtest"]["ran"] is True
    assert result["backtest"]["strategy_name"] == "ibs_spy"
    metrics = result["backtest"]["metrics"]
    assert metrics, "expected non-empty metrics dict"
    assert "profit_factor" in metrics
    assert "sharpe" in metrics
    # Memory entry contains the strategy name.
    assert "ibs_spy" in Path(memory_path).read_text(encoding="utf-8")


def test_workflow_unknown_strategy_does_not_crash(tmp_path):
    from orchestrator.workflow import Workflow

    memory_path = str(tmp_path / "memory.md")
    Path(memory_path).write_text("# Memory\n\n", encoding="utf-8")

    wf = Workflow(stages=["backtest"], memory_path=memory_path)
    ctx = {"strategy_name": "definitely_not_a_strategy"}
    result = wf.run(ctx)
    assert result["backtest"]["ran"] is False
    assert "error" in result["backtest"]


def test_workflow_rejects_unknown_stage():
    from orchestrator.workflow import Workflow

    with pytest.raises(ValueError):
        Workflow(stages=["not_a_stage"])


def test_workflow_validate_appends_backtest_snapshot(tmp_path):
    """A workflow run that completes backtest+validate appends a snapshot bullet."""
    from orchestrator.workflow import STAGES, Workflow

    initial = (
        "# Memory\n\n"
        "## 9. Backtest snapshot\n- existing bullet\n"
    )
    memory_path = tmp_path / "memory.md"
    memory_path.write_text(initial, encoding="utf-8")

    wf = Workflow(
        stages=["backtest", "validate"],
        memory_path=str(memory_path),
    )
    ctx = {"idea": "auto-snapshot test", "strategy_name": "ibs_spy"}
    result = wf.run(ctx)

    assert result["backtest"]["ran"] is True
    assert result["validate"]["snapshot_appended"] is True

    after = memory_path.read_text(encoding="utf-8")
    # Existing bullet preserved.
    assert "existing bullet" in after
    # New bullet appended with strategy name and key metrics.
    assert "`ibs_spy`" in after
    assert "PF" in after and "Sharpe" in after
    assert "Verdict:" in after


def test_workflow_validate_skips_snapshot_when_no_backtest_ran(tmp_path):
    """If no backtest ran, no snapshot bullet is appended."""
    from orchestrator.workflow import Workflow

    memory_path = tmp_path / "memory.md"
    memory_path.write_text(
        "# Memory\n\n## 9. Backtest snapshot\n- existing\n",
        encoding="utf-8",
    )

    wf = Workflow(stages=["validate"], memory_path=str(memory_path))
    # No strategy_name -> backtest doesn't run, validate has nothing to append.
    result = wf.run({"idea": "no-strategy"})

    assert result["validate"]["snapshot_appended"] is False
    after = memory_path.read_text(encoding="utf-8")
    assert "- existing" in after


def test_workflow_learn_rewrites_strategies_table_on_new_strategy(tmp_path):
    """Setting ``new_strategy`` in context rewrites the strategies table."""
    from orchestrator.workflow import STAGES, Workflow

    initial = (
        "# Memory\n\n"
        "## 5. Registered strategies\n| OLD | row |\n|---|---|\n"
    )
    memory_path = tmp_path / "memory.md"
    memory_path.write_text(initial, encoding="utf-8")

    wf = Workflow(stages=list(STAGES), memory_path=str(memory_path))
    ctx = {
        "idea": "add a new strat",
        "strategy_name": "my_new_strat",
        "new_strategy": {
            "ticker": "QQQ",
            "entry": "IBS<0.20",
            "exit": "5-day hold",
            "sizing": "95% equity",
            "cost": "etf_0.1pct",
        },
    }
    result = wf.run(ctx)

    assert result["learn"]["strategies_rewritten"] is True
    after = memory_path.read_text(encoding="utf-8")
    assert "| OLD | row |" not in after
    assert "`my_new_strat`" in after
    assert "QQQ" in after
    # Existing strategies should still be in the rewritten table.
    assert "`ibs_spy`" in after


def test_workflow_learn_no_rewrite_without_new_strategy(tmp_path):
    """Without new_strategy, the table is left untouched."""
    from orchestrator.workflow import Workflow

    initial = (
        "# Memory\n\n"
        "## 5. Registered strategies\n| keep | me |\n"
    )
    memory_path = tmp_path / "memory.md"
    memory_path.write_text(initial, encoding="utf-8")

    wf = Workflow(stages=["learn"], memory_path=str(memory_path))
    result = wf.run({"idea": "noop", "strategy_name": "ibs_spy"})

    assert result["learn"]["strategies_rewritten"] is False
    after = memory_path.read_text(encoding="utf-8")
    assert "| keep | me |" in after


def test_workflow_append_run_still_works(tmp_path):
    """``append_run`` (Framework Runs) still appends after the new logic."""
    from orchestrator.workflow import STAGES, Workflow

    initial = "# Memory\n\n## Notes\nbase\n"
    memory_path = tmp_path / "memory.md"
    memory_path.write_text(initial, encoding="utf-8")

    wf = Workflow(stages=list(STAGES), memory_path=str(memory_path))
    result = wf.run({"idea": "ensure runs work", "strategy_name": "ibs_spy"})

    assert result["learn"]["appended"] is True
    after = memory_path.read_text(encoding="utf-8")
    assert "## Framework Runs" in after
    assert "ensure runs work" in after
    assert "ibs_spy" in after


# ---------------------------------------------------------------------------
# detect_strategy_names
# ---------------------------------------------------------------------------


def test_detect_strategy_names_finds_registered_names():
    from orchestrator.cli import detect_strategy_names

    text = "IBS mean reversion using ibs_spy and qqq_mr"
    found = detect_strategy_names(text)
    assert "ibs_spy" in found
    assert "qqq_mr" in found


def test_detect_strategy_names_prefers_longer_match():
    from orchestrator.cli import detect_strategy_names

    text = "let's try ibs_trend today"
    found = detect_strategy_names(text)
    assert "ibs_trend" in found


def test_detect_strategy_names_returns_empty_when_no_match():
    from orchestrator.cli import detect_strategy_names

    text = "this string contains no strategies"
    assert detect_strategy_names(text) == []


# ---------------------------------------------------------------------------
# CLI subprocess tests
# ---------------------------------------------------------------------------


def test_cli_list_lists_all_twelve_agents():
    result = _run_cli("--list", timeout=30)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    for name in EXPECTED_AGENTS:
        assert name in out, f"agent {name!r} missing from --list output"


def test_cli_list_includes_stage_column():
    result = _run_cli("--list", timeout=30)
    assert result.returncode == 0
    out = result.stdout
    # Table header.
    assert "Stage" in out
    for stage in (
        "research",
        "design",
        "backtest",
        "validate",
        "deploy",
        "monitor",
        "learn",
    ):
        assert stage in out


def test_cli_agent_backtest_engine_runs_strategy_and_emits_metrics():
    result = _run_cli(
        "--agent",
        "backtest_engine",
        "--strategy",
        "ibs_spy",
        "--idea",
        "IBS mean reversion on SPY",
        timeout=180,
    )
    assert result.returncode == 0, result.stderr
    out = result.stdout
    # Prompt was printed.
    assert "backtest_engine" in out
    assert "IBS mean reversion on SPY" in out
    # Backtest ran and printed a metrics block.
    assert "ibs_spy" in out
    assert "Profit Factor" in out
    assert "Sharpe" in out


def test_cli_agent_unknown_agent_returns_error():
    result = _run_cli("--agent", "definitely_not_an_agent", timeout=30)
    assert result.returncode != 0


def test_cli_workflow_full_runs_all_stages_and_updates_memory(tmp_path):
    # Use a copy of memory.md so the real vault note is untouched.
    src = PROJECT_ROOT / "memory.md"
    test_memory = tmp_path / "memory.md"
    test_memory.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    result = _run_cli(
        "--workflow",
        "full",
        "--idea",
        "IBS mean reversion using ibs_spy",
        "--memory",
        str(test_memory),
        timeout=240,
    )
    assert result.returncode == 0, result.stderr
    out = result.stdout

    # Every stage emitted at least one heading.
    for stage in (
        "research",
        "design",
        "backtest",
        "validate",
        "deploy",
        "monitor",
        "learn",
    ):
        assert stage in out, f"stage {stage!r} missing from workflow output"

    # Backtest ran for ibs_spy.
    assert "ibs_spy" in out
    assert "Profit Factor" in out

    # Memory was updated.
    after = test_memory.read_text(encoding="utf-8")
    assert "## Framework Runs" in after
    assert "ibs_spy" in after
    assert "IBS mean reversion using ibs_spy" in after


def test_cli_workflow_subset_runs_only_requested_stages(tmp_path):
    test_memory = tmp_path / "memory.md"
    test_memory.write_text("# Memory\n\n", encoding="utf-8")

    result = _run_cli(
        "--workflow",
        "research,design",
        "--idea",
        "exploratory idea",
        "--memory",
        str(test_memory),
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "research" in out
    assert "design" in out
    # Stages not requested should not appear.
    assert "backtest ::" not in out
    assert "validate ::" not in out


def test_cli_workflow_full_without_strategy_in_idea_does_not_crash(tmp_path):
    test_memory = tmp_path / "memory.md"
    test_memory.write_text("# Memory\n\n", encoding="utf-8")

    result = _run_cli(
        "--workflow",
        "full",
        "--idea",
        "just an idea, no concrete strategy yet",
        "--memory",
        str(test_memory),
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    out = result.stdout
    # All 7 stages still ran, but backtest had no strategy.
    for stage in (
        "research",
        "design",
        "backtest",
        "validate",
        "deploy",
        "monitor",
        "learn",
    ):
        assert stage in out


def test_cli_no_mode_reports_error():
    """Calling the CLI with no mode flag should fail with non-zero exit."""
    result = _run_cli(timeout=30)
    assert result.returncode != 0


# ---------------------------------------------------------------------------
# In-process main() entry point
# ---------------------------------------------------------------------------


def test_cli_main_returns_zero_for_list():
    # Import via the package so the relative imports inside cli.py resolve.
    import orchestrator.cli as cli_mod

    rc = cli_mod.main(["--list"])
    assert rc == 0
