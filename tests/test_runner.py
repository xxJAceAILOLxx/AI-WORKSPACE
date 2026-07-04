"""Tests for Chunk 3: Strategies/run_strategy.py and Strategies/run_all.py.

These tests cover:

* Argument parsing for both CLIs (no network access required).
* Subprocess invocation of ``run_strategy.py`` produces a metrics
  table on a small cached data range.
* Subprocess invocation of ``run_all.py`` produces a ranking table.
* Cost-model flag validation.

The tests deliberately use cached data ranges (``2020-01-01`` ->
``2021-01-01`` and ``2023-01-01`` -> ``2023-02-15``) so they run
quickly and offline once the cache is warm.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUN_STRATEGY = PROJECT_ROOT / "Strategies" / "run_strategy.py"
RUN_ALL = PROJECT_ROOT / "Strategies" / "run_all.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_script(
    script: Path,
    *args: str,
    timeout: int = 120,
) -> subprocess.CompletedProcess:
    """Run ``script`` with ``args`` and capture stdout/stderr.

    The subprocess uses the same Python interpreter as the test runner.
    """
    cmd = [sys.executable, str(script), *args]
    return subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
    )


# ---------------------------------------------------------------------------
# Argument parsing (no data download needed)
# ---------------------------------------------------------------------------


def test_run_strategy_list_flag_exits_zero():
    """``--list`` should print registered strategies and exit 0."""
    result = _run_script(RUN_STRATEGY, "--list", timeout=30)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "Registered strategies" in out
    # Spot-check a couple of canonical strategy names from the registry.
    assert "ibs_spy" in out
    assert "vix_etn" in out


def test_run_strategy_unknown_strategy_returns_error_code():
    """An unknown strategy name should produce a non-zero exit code."""
    result = _run_script(
        RUN_STRATEGY,
        "--strategy",
        "definitely_not_a_real_strategy",
        "--start",
        "2020-01-01",
        "--end",
        "2021-01-01",
        timeout=30,
    )
    assert result.returncode != 0
    assert "unknown strategy" in result.stderr.lower()


def test_run_strategy_missing_strategy_arg_errors():
    """Omitting ``--strategy`` should exit non-zero (argparse error)."""
    result = _run_script(RUN_STRATEGY, "--start", "2020-01-01", "--end", "2021-01-01", timeout=30)
    assert result.returncode != 0
    # argparse writes its usage message to stderr.
    combined = result.stdout + result.stderr
    assert "--strategy" in combined or "usage" in combined.lower()


def test_run_strategy_unknown_cost_model_errors():
    """An unknown cost-model name should exit with a clear error."""
    result = _run_script(
        RUN_STRATEGY,
        "--strategy",
        "ibs_spy",
        "--start",
        "2020-01-01",
        "--end",
        "2021-01-01",
        "--cost-model",
        "not_a_real_cost_model",
        timeout=30,
    )
    assert result.returncode != 0
    combined = (result.stdout + result.stderr).lower()
    assert "cost model" in combined


def test_run_strategy_invalid_execution_choice_errors():
    """An invalid ``--execution`` value should be rejected by argparse."""
    result = _run_script(
        RUN_STRATEGY,
        "--strategy",
        "ibs_spy",
        "--execution",
        "tomorrow",
        timeout=30,
    )
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    # argparse prints "invalid choice" for choices=... mismatches.
    assert "invalid choice" in combined.lower()


def test_run_all_sort_by_choices_reject_invalid_value():
    """``run_all.py`` should reject an invalid ``--sort-by`` value."""
    result = _run_script(
        RUN_ALL,
        "--sort-by",
        "made_up_metric",
        "--start",
        "2020-01-01",
        "--end",
        "2021-01-01",
        timeout=30,
    )
    assert result.returncode != 0
    combined = (result.stdout + result.stderr).lower()
    assert "invalid choice" in combined


def test_run_all_include_exclude_filters_run_a_subset():
    """``--include`` should restrict the run to a single named strategy."""
    result = _run_script(
        RUN_ALL,
        "--include",
        "ibs_spy",
        "--start",
        "2020-01-01",
        "--end",
        "2021-01-01",
        "--quiet",
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "ibs_spy" in out
    # No other strategy names should appear in the per-strategy progress
    # lines (we used --quiet so only the ranking table is printed).
    assert "vix_etn" not in out
    assert "Running 1 strategies" in out


# ---------------------------------------------------------------------------
# Subprocess invocation that actually runs the engine
# ---------------------------------------------------------------------------


def test_run_strategy_subprocess_prints_expected_strategy_name():
    """``run_strategy.py`` must produce a table that includes the strategy name."""
    result = _run_script(
        RUN_STRATEGY,
        "--strategy",
        "ibs_spy",
        "--start",
        "2020-01-01",
        "--end",
        "2021-01-01",
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    out = result.stdout
    # Strategy header is rendered as "=== ibs_spy (SPY) ===" by the framework.
    assert "ibs_spy" in out
    assert "SPY" in out
    # Core metrics must be printed.
    assert "Profit Factor" in out
    assert "Win Rate" in out
    assert "Sharpe" in out


def test_run_strategy_close_vs_next_open_produces_different_result():
    """Same-bar execution must produce different metrics than next-open."""
    res_default = _run_script(
        RUN_STRATEGY,
        "--strategy",
        "ibs_spy",
        "--start",
        "2020-01-01",
        "--end",
        "2021-01-01",
        timeout=120,
    )
    res_close = _run_script(
        RUN_STRATEGY,
        "--strategy",
        "ibs_spy",
        "--start",
        "2020-01-01",
        "--end",
        "2021-01-01",
        "--execution",
        "close",
        timeout=120,
    )
    assert res_default.returncode == 0, res_default.stderr
    assert res_close.returncode == 0, res_close.stderr
    # The two outputs must differ in at least the execution line and
    # (very likely) the metric block.
    assert "next_open" in res_default.stdout
    assert "close" in res_close.stdout
    assert res_default.stdout != res_close.stdout


def test_run_strategy_monte_carlo_appends_report():
    """``--monte-carlo`` should append a Monte Carlo block to the output."""
    result = _run_script(
        RUN_STRATEGY,
        "--strategy",
        "ibs_spy",
        "--start",
        "2020-01-01",
        "--end",
        "2021-01-01",
        "--monte-carlo",
        "--monte-carlo-sims",
        "50",
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "Monte Carlo" in out
    assert "Final equity" in out
    assert "Ruin prob" in out


def test_run_all_subprocess_prints_ranking_table():
    """``run_all.py`` on a small cached range must produce a ranking table."""
    # Use a tiny date range to keep the test fast.
    result = _run_script(
        RUN_ALL,
        "--start",
        "2020-01-01",
        "--end",
        "2021-01-01",
        "--quiet",
        "--top",
        "5",
        timeout=180,
    )
    assert result.returncode == 0, result.stderr
    out = result.stdout
    # The ranking table header (per reporting.print_ranking) contains
    # the canonical column labels.
    for col in ("Strategy", "Trades", "CAGR", "MaxDD", "PF"):
        assert col in out, f"missing column {col!r} in ranking table"
    # The "Per-metric winners" summary at the end.
    assert "Per-metric winners" in out


# ---------------------------------------------------------------------------
# In-process CLI invocation (no subprocess overhead)
# ---------------------------------------------------------------------------


def test_run_strategy_main_returns_0_for_valid_invocation():
    """Calling ``main()`` directly should return 0 on success."""
    sys.path.insert(0, str(PROJECT_ROOT / "Strategies"))
    # Avoid the importlib cache pollution from the subprocess tests above
    # by importing fresh in a controlled way.
    import importlib
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "run_strategy", str(RUN_STRATEGY)
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]

    rc = mod.main(["--strategy", "ibs_spy", "--start", "2020-01-01", "--end", "2021-01-01"])
    assert rc == 0


def test_run_all_main_returns_0_for_valid_invocation():
    """Calling ``run_all.main()`` directly should return 0 on success."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "run_all", str(RUN_ALL)
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]

    rc = mod.main(
        [
            "--start",
            "2020-01-01",
            "--end",
            "2021-01-01",
            "--include",
            "ibs_spy",
            "--quiet",
        ]
    )
    assert rc == 0


def test_run_strategy_parser_default_values():
    """Defaults should match the values documented in the plan."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "run_strategy", str(RUN_STRATEGY)
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]

    parser = mod.build_parser()
    ns = parser.parse_args([])
    assert ns.start == "2016-01-01"
    assert ns.end == "2025-12-31"
    assert ns.execution == "next_open"
    assert ns.cost_model == "etf_0.1pct"
    assert ns.walk_forward is False
    assert ns.monte_carlo is False
    assert ns.monte_carlo_sims == 1000


def test_run_all_parser_default_values():
    """``run_all.py`` defaults should match the documented behaviour."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "run_all", str(RUN_ALL)
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]

    parser = mod.build_parser()
    ns = parser.parse_args([])
    assert ns.start == "2016-01-01"
    assert ns.end == "2025-12-31"
    assert ns.execution == "next_open"
    assert ns.cost_model == "etf_0.1pct"
    assert ns.sort_by == "profit_factor"
    assert ns.top is None
    assert ns.update_memory is False
    assert ns.memory_path == "memory.md"


def test_run_strategy_parser_includes_update_memory_flag():
    """``--update-memory`` and ``--memory-path`` flags exist and default off."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "run_strategy", str(RUN_STRATEGY)
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]

    parser = mod.build_parser()
    ns = parser.parse_args([])
    assert ns.update_memory is False
    assert ns.memory_path == "memory.md"


def test_run_strategy_update_memory_writes_snapshot(tmp_path):
    """``--update-memory`` appends a bullet to the snapshot section."""
    # Pre-seed the test memory.md with a known snapshot section.
    memory_path = tmp_path / "memory.md"
    memory_path.write_text(
        "# Memory\n\n## 9. Backtest snapshot\n- existing bullet\n",
        encoding="utf-8",
    )

    result = _run_script(
        RUN_STRATEGY,
        "--strategy",
        "ibs_spy",
        "--start",
        "2020-01-01",
        "--end",
        "2021-01-01",
        "--update-memory",
        "--memory-path",
        str(memory_path),
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    # The CLI confirms the memory was updated.
    assert "Backtest snapshot" in result.stdout
    assert "appended" in result.stdout.lower()

    after = memory_path.read_text(encoding="utf-8")
    # Existing bullet preserved.
    assert "- existing bullet" in after
    # New bullet appended with strategy name + metric keywords.
    assert "`ibs_spy`" in after
    assert "PF" in after
    assert "Sharpe" in after
    assert "Verdict:" in after


def test_run_strategy_without_update_memory_does_not_modify_memory(tmp_path):
    """Without ``--update-memory`` the runner leaves memory.md alone."""
    memory_path = tmp_path / "memory.md"
    memory_path.write_text(
        "# Memory\n\n## 9. Backtest snapshot\n- existing bullet\n",
        encoding="utf-8",
    )
    before = memory_path.read_text(encoding="utf-8")

    result = _run_script(
        RUN_STRATEGY,
        "--strategy",
        "ibs_spy",
        "--start",
        "2020-01-01",
        "--end",
        "2021-01-01",
        "--memory-path",
        str(memory_path),
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    after = memory_path.read_text(encoding="utf-8")
    # No bullet appended; section unchanged.
    assert after.count("- existing bullet") == 1
    assert "Verdict:" not in after


def test_run_all_update_memory_appends_top_n(tmp_path):
    """``run_all.py --update-memory`` writes the top-5 snapshot block."""
    memory_path = tmp_path / "memory.md"
    memory_path.write_text(
        "# Memory\n\n## 9. Backtest snapshot\n- existing\n",
        encoding="utf-8",
    )

    result = _run_script(
        RUN_ALL,
        "--start",
        "2020-01-01",
        "--end",
        "2021-01-01",
        "--include",
        "ibs_spy",
        "--quiet",
        "--update-memory",
        "--memory-path",
        str(memory_path),
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "appended" in result.stdout.lower()

    after = memory_path.read_text(encoding="utf-8")
    assert "- existing" in after
    assert "Top 5 by profit_factor" in after
    assert "`ibs_spy`" in after
