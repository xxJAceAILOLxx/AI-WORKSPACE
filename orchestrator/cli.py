"""Command-line entry point for the orchestrator.

Examples
--------

List all agents::

    python -m orchestrator.cli --list

Print a populated agent prompt and (for the backtest stage) actually
run the strategy::

    python -m orchestrator.cli --agent backtest_engine --strategy ibs_spy

Run the full seven-stage workflow, parsing strategy names from the
free-text idea::

    python -m orchestrator.cli --workflow full --idea "IBS mean reversion using ibs_spy"

The CLI never calls an external LLM API; it prints prompts, invokes
the local backtest registry, and writes results to ``memory.md``.
"""

from __future__ import annotations

import argparse
import re
import sys
from typing import Any, Dict, List, Optional, Sequence

from .agents import AGENTS, list_agents
from .memory import Memory
from .workflow import STAGES, Workflow


# ---------------------------------------------------------------------------
# Strategy-name detection from free-text ideas.
# ---------------------------------------------------------------------------


# Word boundary characters used when tokenizing idea text.  Strategy
# names contain only [a-z0-9_] so this regex is intentionally permissive.
_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def detect_strategy_names(idea: str, candidates: Optional[Sequence[str]] = None) -> List[str]:
    """Return registered strategy names found in ``idea``.

    Matching is case-insensitive and whole-token.  Longer names are
    reported before their substrings so e.g. ``ibs_trend`` wins over
    ``ibs_spy`` when both appear.
    """
    if candidates is None:
        # Import lazily so ``--list`` works even when the backtest
        # package fails to import (e.g. missing optional deps).
        try:
            from backtest.strategies.registry import list_strategies

            candidates = list_strategies()
        except Exception:
            candidates = []

    idea_tokens = {t.lower() for t in _TOKEN_RE.findall(idea or "")}
    found = [c for c in candidates if c.lower() in idea_tokens]
    found.sort(key=len, reverse=True)
    return found


# ---------------------------------------------------------------------------
# Mode handlers.
# ---------------------------------------------------------------------------


def _print_agents_table() -> None:
    """Print all registered agents in a compact table."""
    rows = sorted(AGENTS.values(), key=lambda a: (a.stage, a.name))
    name_w = max(len("Agent"), max(len(a.name) for a in rows))
    stage_w = max(len("Stage"), max(len(a.stage) for a in rows))

    header = f"{'Agent':<{name_w}}  {'Stage':<{stage_w}}  Purpose"
    print(header)
    print("-" * len(header))
    for agent in rows:
        purpose = agent.purpose
        if len(purpose) > 80:
            purpose = purpose[:77] + "..."
        print(f"{agent.name:<{name_w}}  {agent.stage:<{stage_w}}  {purpose}")


def _run_agent_mode(args: argparse.Namespace) -> int:
    """Handle ``--agent NAME [--strategy X] [--idea Y]``."""
    from .agents import get_agent

    agent = get_agent(args.agent)
    idea = args.idea or ""

    # Populate the prompt template.
    format_kwargs: Dict[str, Any] = {
        "idea": idea or "(no idea provided)",
        "strategy_name": args.strategy or "(unspecified)",
        "ticker": "SPY",
        "start": "2016-01-01",
        "end": "2025-12-31",
        "execution": "next_open",
        "cost_model": "etf_0.1pct",
        "phase": "Challenge",
        "account_size": "100,000",
        "max_dd_pct": "10.0",
        "max_dd_abs": "10,000",
        "daily_loss_pct": "5.0",
        "daily_loss_abs": "5,000",
        "target_pct": "10.0",
        "target_abs": "10,000",
        "metrics": "  (no metrics)",
        "summary": "  (no run data)",
    }
    prompt = agent.format_prompt(**format_kwargs)
    print(f"=== {agent.name} ({agent.stage}) ===")
    print(prompt.rstrip())

    # Backtest stage actually runs the strategy.
    if agent.stage == "backtest":
        strategy_name = args.strategy
        if not strategy_name and idea:
            detected = detect_strategy_names(idea)
            if detected:
                strategy_name = detected[0]
                print(f"[cli] detected strategy name from idea: {strategy_name}")

        if strategy_name:
            try:
                from backtest.metrics import compute_metrics
                from backtest.reporting import print_result
                from backtest.strategies.registry import run as registry_run
            except Exception as exc:
                print(f"[cli] backtest runner unavailable: {exc}", file=sys.stderr)
                return 1

            try:
                result = registry_run(strategy_name)
            except KeyError as exc:
                print(f"[cli] {exc}", file=sys.stderr)
                return 2

            metrics = compute_metrics(result)
            print()
            print_result(result, metrics=metrics)
            return 0

        print(
            "[cli] backtest stage requires --strategy STRAT or a strategy name in --idea.",
            file=sys.stderr,
        )
        return 3

    return 0


def _run_workflow_mode(args: argparse.Namespace) -> int:
    """Handle ``--workflow {full,NAME,...} [--idea Y]``."""
    if args.workflow == "full":
        stages = list(STAGES)
    else:
        # Comma-separated subset, e.g. "research,design,backtest".
        requested = [s.strip() for s in args.workflow.split(",") if s.strip()]
        unknown = [s for s in requested if s not in STAGES]
        if unknown:
            print(
                f"[cli] unknown stage(s): {unknown}. Valid: {STAGES}",
                file=sys.stderr,
            )
            return 2
        stages = requested

    idea = args.idea or ""

    # Try to discover a strategy name from the idea text.
    strategy_name = args.strategy
    if not strategy_name and idea:
        detected = detect_strategy_names(idea)
        if detected:
            strategy_name = detected[0]
            print(f"[cli] using strategy {strategy_name!r} from idea text")

    memory_path = args.memory or "memory.md"
    memory = Memory(path=memory_path)

    workflow = Workflow(
        stages=stages,
        memory=memory,
        memory_path=memory_path,
    )

    context: Dict[str, Any] = {
        "idea": idea,
        "strategy_name": strategy_name,
    }
    result = workflow.run(context)
    print()
    print("=== workflow summary ===")
    print(f"stages run: {stages}")
    print(f"strategy: {result.get('backtest', {}).get('strategy_name') or '(none)'}")
    ran = result.get("backtest", {}).get("ran", False)
    print(f"backtest ran: {ran}")
    if ran:
        m = result["backtest"].get("metrics", {})
        print(
            f"metrics: PF={m.get('profit_factor', 0.0):.2f}, "
            f"Sharpe={m.get('sharpe', 0.0):.2f}, "
            f"MaxDD={m.get('max_drawdown', 0.0):.2%}"
        )
    validate = result.get("validate", {})
    if validate:
        print(f"validate ok: {validate.get('checks_ok')}")
    learn = result.get("learn", {})
    if learn:
        print(f"memory updated: {learn.get('appended')} ({learn.get('memory_path')})")
    return 0


# ---------------------------------------------------------------------------
# Argparse plumbing.
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m orchestrator.cli",
        description="Orchestrate the unified backtest framework agents.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--list",
        action="store_true",
        help="List all registered agents.",
    )
    group.add_argument(
        "--agent",
        type=str,
        default=None,
        help="Run a single agent by name (e.g. backtest_engine).",
    )
    group.add_argument(
        "--workflow",
        type=str,
        default=None,
        help=(
            "Run a workflow. Use 'full' for all seven stages or a "
            "comma-separated subset, e.g. 'research,design,backtest'."
        ),
    )

    parser.add_argument(
        "--strategy",
        type=str,
        default=None,
        help="Strategy name to use with --agent or --workflow.",
    )
    parser.add_argument(
        "--idea",
        type=str,
        default=None,
        help="Free-text idea describing the strategy under test.",
    )
    parser.add_argument(
        "--memory",
        type=str,
        default=None,
        help="Path to memory.md (default: memory.md).",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point.  Returns a shell exit code (0 == success)."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list:
        _print_agents_table()
        return 0
    if args.agent:
        return _run_agent_mode(args)
    if args.workflow:
        return _run_workflow_mode(args)

    parser.print_help()
    return 1


if __name__ == "__main__":  # pragma: no cover - exercised via tests
    raise SystemExit(main())
