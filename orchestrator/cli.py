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

Run the workflow with LLM agent loop (requires VT_LLM_API_KEY env var)::

    python -m orchestrator.cli --workflow full --idea "IBS mean reversion" --use-llm

Interactive chat with the trading agent::

    python -m orchestrator.cli --chat

Manage hypotheses::

    python -m orchestrator.cli --hypothesis list
    python -m orchestrator.cli --hypothesis create --title "IBS edge" --thesis "Low IBS predicts mean reversion"

Run a swarm team::

    python -m orchestrator.cli --swarm run investment_committee --vars "target=SPY,market=bullish"

List alpha factors::

    python -m orchestrator.cli --alpha list
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
    """Handle ``--workflow {full,NAME,...} [--idea Y] [--use-llm]``."""
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

    # Optionally build LLM + tool registry.
    llm = None
    tool_registry = None
    if getattr(args, "use_llm", False):
        try:
            from .providers.llm import build_llm
            from .agent.tools import build_registry
            llm = build_llm()
            tool_registry = build_registry()
            print("[cli] LLM agent loop enabled")
        except Exception as exc:
            print(f"[cli] LLM unavailable: {exc}", file=sys.stderr)
            return 1

    workflow = Workflow(
        stages=stages,
        memory=memory,
        memory_path=memory_path,
        llm=llm,
        tool_registry=tool_registry,
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
# Chat mode — interactive LLM agent.
# ---------------------------------------------------------------------------


def _run_chat_mode(args: argparse.Namespace) -> int:
    """Handle ``--chat`` — interactive REPL with the trading agent."""
    try:
        from .providers.llm import build_llm
        from .agent.tools import build_registry
        from .agent.loop import AgentLoop
        from .agent.prompt import build_system_prompt
    except ImportError as exc:
        print(f"[chat] required packages missing: {exc}", file=sys.stderr)
        return 1

    try:
        llm = build_llm()
    except Exception as exc:
        print(f"[chat] LLM unavailable: {exc}", file=sys.stderr)
        return 1

    registry = build_registry()
    system_prompt = build_system_prompt(registry)

    loop = AgentLoop(llm=llm, registry=registry, system_prompt=system_prompt)

    print("=== Trading Agent Chat ===")
    print(f"Tools: {', '.join(registry.list_names())}")
    print("Type 'quit' or 'exit' to stop.\n")

    history: list = []
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[chat] exiting.")
            break
        if not user_input or user_input.lower() in ("quit", "exit", "q"):
            print("[chat] bye.")
            break

        result = loop.run(user_input, history=history)
        print(f"\nAgent: {result.content}\n")
        print(f"  [tools: {result.tool_calls_made} calls, {result.iterations} iterations, {result.elapsed_seconds:.1f}s]\n")

        # Append to history for multi-turn.
        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": result.content})

    return 0


# ---------------------------------------------------------------------------
# Hypothesis management mode.
# ---------------------------------------------------------------------------


def _run_hypothesis_mode(args: argparse.Namespace) -> int:
    """Handle ``--hypothesis {list,create,show,search} [--title ...] [--thesis ...]``."""
    from .hypotheses.registry import HypothesisRegistry

    registry = HypothesisRegistry()
    action = args.hypothesis_action or "list"

    if action == "list":
        status_filter = getattr(args, "status", None)
        hypotheses = registry.list_hypotheses(status=status_filter)
        if not hypotheses:
            print("No hypotheses found.")
            return 0
        print(f"{'ID':<14} {'Status':<10} {'Title'}")
        print("-" * 60)
        for h in hypotheses:
            title = h.title[:40] + "..." if len(h.title) > 40 else h.title
            print(f"{h.hypothesis_id:<14} {h.status:<10} {title}")
        return 0

    elif action == "create":
        title = getattr(args, "title", "") or ""
        thesis = getattr(args, "thesis", "") or ""
        universe = getattr(args, "universe", "") or ""
        signal = getattr(args, "signal", "") or ""
        if not title:
            print("[hypothesis] --title is required for create", file=sys.stderr)
            return 2
        h = registry.create_hypothesis(
            title=title, thesis=thesis, universe=universe, signal_definition=signal
        )
        print(f"Created hypothesis {h.hypothesis_id}: {h.title}")
        return 0

    elif action == "show":
        h_id = getattr(args, "hypothesis_id", "") or ""
        h = registry.get_hypothesis(h_id)
        if h is None:
            print(f"[hypothesis] {h_id!r} not found", file=sys.stderr)
            return 2
        print(f"ID: {h.hypothesis_id}")
        print(f"Title: {h.title}")
        print(f"Status: {h.status}")
        print(f"Thesis: {h.thesis}")
        print(f"Universe: {h.universe}")
        print(f"Signal: {h.signal_definition}")
        print(f"Data sources: {h.data_sources}")
        print(f"Run cards: {len(h.run_cards)}")
        for rc in h.run_cards:
            print(f"  - {rc.run_dir}: PF={rc.metrics.get('profit_factor', 0):.2f}")
        return 0

    elif action == "search":
        query = getattr(args, "query", "") or ""
        results = registry.search_hypotheses(query)
        print(f"Found {len(results)} hypotheses matching '{query}':")
        for h in results:
            print(f"  {h.hypothesis_id}: {h.title} [{h.status}]")
        return 0

    print(f"[hypothesis] unknown action: {action}", file=sys.stderr)
    return 2


# ---------------------------------------------------------------------------
# Swarm mode.
# ---------------------------------------------------------------------------


def _run_swarm_mode(args: argparse.Namespace) -> int:
    """Handle ``--swarm {list,run,inspect} [preset]``."""
    action = args.swarm_action or "list"

    if action == "list":
        from .swarm.presets import list_presets
        presets = list_presets()
        if not presets:
            print("No swarm presets found.")
            return 0
        print("Available swarm presets:")
        for p in presets:
            print(f"  - {p}")
        return 0

    elif action == "run":
        preset_name = getattr(args, "swarm_preset", "") or ""
        if not preset_name:
            print("[swarm] preset name required", file=sys.stderr)
            return 2

        # Parse --vars "key=value,key=value"
        user_vars = {}
        vars_str = getattr(args, "swarm_vars", "") or ""
        if vars_str:
            for part in vars_str.split(","):
                if "=" in part:
                    k, v = part.split("=", 1)
                    user_vars[k.strip()] = v.strip()

        try:
            from .providers.llm import build_llm
            from .agent.tools import build_registry
            from .swarm.runtime import SwarmRuntime
        except ImportError as exc:
            print(f"[swarm] required packages missing: {exc}", file=sys.stderr)
            return 1

        llm = build_llm()
        registry = build_registry()
        runtime = SwarmRuntime(llm=llm, tool_registry=registry)

        print(f"[swarm] running preset: {preset_name}")
        run = runtime.run(preset_name, user_vars=user_vars)
        print(f"\n[swarm] status: {run.status}")
        for task in run.tasks:
            status_icon = {"done": "OK", "failed": "FAIL", "pending": "---"}.get(task.status.value, "??")
            print(f"  [{status_icon}] {task.id} ({task.agent_id})")
            if task.result:
                preview = task.result[:200].replace("\n", " ")
                print(f"       {preview}...")
        return 0

    elif action == "inspect":
        preset_name = getattr(args, "swarm_preset", "") or ""
        from .swarm.presets import inspect_preset
        info = inspect_preset(preset_name)
        print(f"Preset: {preset_name}")
        print(f"Valid: {info['valid']}")
        if info["errors"]:
            print("Errors:")
            for e in info["errors"]:
                print(f"  - {e}")
        print(f"Agents: {len(info['agents'])}")
        for a in info["agents"]:
            print(f"  - {a['id']}: {a['role']}")
        print(f"Tasks: {len(info['tasks'])}")
        print(f"DAG layers: {info['layers']}")
        return 0

    print(f"[swarm] unknown action: {action}", file=sys.stderr)
    return 2


# ---------------------------------------------------------------------------
# Alpha factor mode.
# ---------------------------------------------------------------------------


def _run_alpha_mode(args: argparse.Namespace) -> int:
    """Handle ``--alpha {list,bench} [--zoo NAME]``."""
    action = args.alpha_action or "list"

    if action == "list":
        from .factors.registry import list_alphas
        alphas = list_alphas()
        if not alphas:
            print("No alpha factors registered.")
            return 0
        print(f"{'Name':<25} {'Category':<18} Description")
        print("-" * 75)
        for name in alphas:
            from .factors.registry import get_alpha
            a = get_alpha(name)
            desc = a.description[:35] + "..." if len(a.description) > 35 else a.description
            print(f"{name:<25} {a.category:<18} {desc}")
        return 0

    elif action == "bench":
        alpha_name = getattr(args, "alpha_name", "") or ""
        ticker = getattr(args, "ticker", "SPY") or "SPY"
        if not alpha_name:
            print("[alpha] --alpha-name required for bench", file=sys.stderr)
            return 2

        import yfinance as yf
        from .factors.registry import bench_alpha

        print(f"[alpha] benchmarking {alpha_name} on {ticker}...")
        df = yf.Ticker(ticker).history(period="5y", interval="1d")
        if df.empty:
            print("[alpha] no data fetched", file=sys.stderr)
            return 1

        result = bench_alpha(alpha_name, df)
        print(f"  IC mean: {result['ic_mean']:.4f}")
        print(f"  IR: {result['ir']:.4f}")
        print(f"  Positive ratio: {result['positive_ratio']:.2%}")
        print(f"  Samples: {result['samples']}")
        return 0

    print(f"[alpha] unknown action: {action}", file=sys.stderr)
    return 2


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
    group.add_argument(
        "--chat",
        action="store_true",
        help="Interactive chat with the trading agent (requires LLM).",
    )
    group.add_argument(
        "--hypothesis",
        type=str,
        default=None,
        nargs="?",
        const="list",
        help="Hypothesis management: list, create, show, search.",
    )
    group.add_argument(
        "--swarm",
        type=str,
        default=None,
        nargs="?",
        const="list",
        help="Swarm team management: list, run, inspect.",
    )
    group.add_argument(
        "--alpha",
        type=str,
        default=None,
        nargs="?",
        const="list",
        help="Alpha factor management: list, bench.",
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
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Enable LLM agent loop for workflow stages.",
    )

    # Hypothesis sub-args.
    parser.add_argument("--title", type=str, default=None, help="Hypothesis title (for create).")
    parser.add_argument("--thesis", type=str, default=None, help="Hypothesis thesis (for create).")
    parser.add_argument("--universe", type=str, default=None, help="Target universe (for create).")
    parser.add_argument("--signal", type=str, default=None, help="Signal definition (for create).")
    parser.add_argument("--status", type=str, default=None, help="Filter by status (for list).")
    parser.add_argument("--query", type=str, default=None, help="Search query (for search).")
    parser.add_argument("--hypothesis-id", type=str, default=None, dest="hypothesis_id", help="Hypothesis ID (for show).")

    # Swarm sub-args.
    parser.add_argument("--swarm-preset", type=str, default=None, dest="swarm_preset", help="Swarm preset name.")
    parser.add_argument("--swarm-vars", type=str, default=None, dest="swarm_vars", help='Swarm variables: "key=value,key=value".')

    # Alpha sub-args.
    parser.add_argument("--alpha-name", type=str, default=None, dest="alpha_name", help="Alpha factor name (for bench).")
    parser.add_argument("--ticker", type=str, default="SPY", help="Ticker for alpha bench (default: SPY).")

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
    if args.chat:
        return _run_chat_mode(args)
    if args.hypothesis is not None:
        # Store the sub-action.
        args.hypothesis_action = args.hypothesis
        return _run_hypothesis_mode(args)
    if args.swarm is not None:
        args.swarm_action = args.swarm
        return _run_swarm_mode(args)
    if args.alpha is not None:
        args.alpha_action = args.alpha
        return _run_alpha_mode(args)

    parser.print_help()
    return 1


if __name__ == "__main__":  # pragma: no cover - exercised via tests
    raise SystemExit(main())
