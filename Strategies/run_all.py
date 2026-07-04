#!/usr/bin/env python3
"""All-strategies runner CLI.

Run every strategy registered with the unified backtest framework and
print a ranking table sorted by profit factor (configurable).  The CLI
is the framework-aware replacement for the legacy
``Strategies/all_strategies_backtest.py``.

Usage examples
--------------

Rank every strategy by profit factor on the default 2016-2025 window::

    python Strategies/run_all.py

Same-bar (close) execution and a different cost model::

    python Strategies/run_all.py --execution close --cost-model vix_etn_40

Rank by Sharpe ratio and only print the top 5::

    python Strategies/run_all.py --sort-by sharpe --top 5
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import traceback
from typing import List, Optional, Sequence

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import backtest
import backtest.costs
import backtest.strategies  # noqa: F401  - triggers @register decorators
from backtest import reporting
from backtest.engine import BacktestResult
from backtest.strategies import list_strategies, run as registry_run
from backtest.metrics import compute_metrics

DEFAULT_START: str = "2016-01-01"
DEFAULT_END: str = "2025-12-31"
DEFAULT_EXECUTION: str = "next_open"
DEFAULT_COST_MODEL: str = "etf_0.1pct"
DEFAULT_SORT_BY: str = "profit_factor"
DEFAULT_TOP: Optional[int] = None

# Default ranking keys accepted by ``--sort-by``.  Mirrors the legacy
# ``all_strategies_backtest.py`` ranking axis plus the metric fields
# available on :class:`backtest.metrics.Metrics`.
VALID_SORT_KEYS: tuple[str, ...] = (
    "name",
    "profit_factor",
    "sharpe",
    "sortino",
    "cagr",
    "total_return",
    "max_drawdown",
    "win_rate",
    "expectancy",
    "trade_count",
    "avg_hold_days",
    "final_equity",
)


# ---------------------------------------------------------------------------
# Cost-model patching (same approach as ``run_strategy.py``)
# ---------------------------------------------------------------------------


def _patch_cost_model(model_name: str) -> List["object"]:
    """Return a list of ``mock.patch`` started-patches replacing the named
    cost model in every loaded backtest module."""
    from unittest.mock import patch

    if model_name == DEFAULT_COST_MODEL:
        return []
    try:
        new_model = backtest.costs.get(model_name)
    except KeyError:
        return []
    patchers = []
    for mod_name, mod in list(sys.modules.items()):
        if mod is None or not isinstance(mod_name, str):
            continue
        if not mod_name.startswith("backtest"):
            continue
        if mod_name == "backtest.costs":
            continue
        for attr in ("PERCENT_10BP", "FLAT_40", "PER_SHARE_1C"):
            if hasattr(mod, attr):
                patchers.append(patch.object(mod, attr, new_model))
    return patchers


# ---------------------------------------------------------------------------
# Run helpers
# ---------------------------------------------------------------------------


def _run_one(
    strategy_name: str,
    execution: str,
    start: str,
    end: str,
) -> BacktestResult:
    """Run a single strategy and return the result."""
    return registry_run(
        strategy_name,
        start=start,
        end=end,
        execution=execution,
    )


def _resolve_cost_model(name: str) -> None:
    """Validate ``name`` is a known cost model.  Raise ``SystemExit`` if not."""
    if name == DEFAULT_COST_MODEL:
        return
    try:
        backtest.costs.get(name)
    except KeyError:
        available = ", ".join(backtest.costs.available())
        print(
            f"error: unknown cost model {name!r}. Available: {available}",
            file=sys.stderr,
        )
        raise SystemExit(2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser for ``run_all.py``."""
    parser = argparse.ArgumentParser(
        prog="run_all",
        description=(
            "Run every registered strategy and print a ranking table. "
            "Default sort is profit factor."
        ),
    )
    parser.add_argument(
        "--start", type=str, default=DEFAULT_START, help="ISO start date (default 2016-01-01)."
    )
    parser.add_argument(
        "--end", type=str, default=DEFAULT_END, help="ISO end date (default 2025-12-31)."
    )
    parser.add_argument(
        "--execution",
        type=str,
        choices=("close", "next_open"),
        default=DEFAULT_EXECUTION,
        help="Entry execution semantics (default next_open).",
    )
    parser.add_argument(
        "--cost-model",
        type=str,
        default=DEFAULT_COST_MODEL,
        help=(
            "Cost model name (see backtest.costs.available()). "
            f"Default: {DEFAULT_COST_MODEL}."
        ),
    )
    parser.add_argument(
        "--sort-by",
        type=str,
        default=DEFAULT_SORT_BY,
        choices=VALID_SORT_KEYS,
        help="Metric to rank by (default profit_factor).",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=DEFAULT_TOP,
        help="Only show the top N rows (default: show all).",
    )
    parser.add_argument(
        "--include",
        type=str,
        default=None,
        help="Comma-separated allowlist of strategy names (default: all).",
    )
    parser.add_argument(
        "--exclude",
        type=str,
        default=None,
        help="Comma-separated denylist of strategy names.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-strategy progress output.",
    )
    parser.add_argument(
        "--update-memory",
        action="store_true",
        help=(
            "Append the top-5 ranked strategies to the 'Backtest snapshot' "
            "section of memory.md (opt-in; default off)."
        ),
    )
    parser.add_argument(
        "--memory-path",
        type=str,
        default="memory.md",
        help="Path to memory.md (default: ./memory.md).",
    )
    return parser


def _filter_strategies(
    names: Sequence[str],
    include: Optional[str],
    exclude: Optional[str],
) -> List[str]:
    """Apply include/exclude filters to the strategy name list."""
    include_set = {n.strip() for n in include.split(",") if n.strip()} if include else None
    exclude_set = {n.strip() for n in exclude.split(",") if n.strip()} if exclude else set()
    out: List[str] = []
    for n in names:
        if include_set is not None and n not in include_set:
            continue
        if n in exclude_set:
            continue
        out.append(n)
    return out


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    _resolve_cost_model(args.cost_model)

    all_names = list_strategies()
    names = _filter_strategies(all_names, args.include, args.exclude)
    if not names:
        print("error: no strategies to run after applying --include/--exclude filters.", file=sys.stderr)
        return 2

    print(f"Running {len(names)} strategies from {args.start} to {args.end}")
    print(f"  execution = {args.execution}")
    print(f"  cost model = {args.cost_model}")
    print(f"  sort by = {args.sort_by}")
    print()

    # Patch cost model across the whole run.
    cost_patchers = _patch_cost_model(args.cost_model)
    for p in cost_patchers:
        p.start()

    results: List[BacktestResult] = []
    timings: List[tuple[str, float]] = []
    try:
        for name in names:
            if not args.quiet:
                print(f"  [{len(results) + 1}/{len(names)}] {name} ...", end="", flush=True)
            t0 = time.time()
            try:
                result = _run_one(name, args.execution, args.start, args.end)
                results.append(result)
                elapsed = time.time() - t0
                timings.append((name, elapsed))
                if not args.quiet:
                    trades = len(result.trades)
                    print(f" {trades} trades ({elapsed:5.1f}s)")
            except Exception as exc:  # noqa: BLE001 - top-level error trap
                elapsed = time.time() - t0
                timings.append((name, elapsed))
                if not args.quiet:
                    print(f" FAILED ({elapsed:5.1f}s): {exc}")
                else:
                    print(f"  [{name}] FAILED: {exc}", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
    finally:
        for p in cost_patchers:
            p.stop()

    if not results:
        print("\nNo strategies produced results; nothing to rank.", file=sys.stderr)
        return 1

    # Header
    print()
    print("=" * 80)
    print("RANKING TABLE")
    print("=" * 80)
    print(f"Sort key: {args.sort_by}")
    print()

    # Use the framework's ranking printer.
    reporting.print_ranking(results, sort_by=args.sort_by, top=args.top)

    # Follow-up summary: count of strategies that traded, profit-factor wins.
    traded = [r for r in results if r.trades]
    print()
    print(
        f"Summary: {len(traded)}/{len(results)} strategies produced trades."
    )

    # Best by each major metric for at-a-glance comparison.
    print()
    print("Per-metric winners:")
    for metric in ("profit_factor", "sharpe", "cagr", "win_rate", "expectancy"):
        winner = None
        best = None
        for r in results:
            m = compute_metrics(r)
            v = m.as_dict().get(metric)
            if v is None or v != v:  # skip NaN
                continue
            if best is None or v > best:
                best = v
                winner = r
        if winner is not None:
            m = compute_metrics(winner).as_dict()
            print(
                f"  best {metric:<14} = {winner.name:<22} "
                f"({m[metric]:.3f})"
            )

    # Optional: append the top-5 by profit factor to memory.md
    # 'Backtest snapshot' section.
    if args.update_memory and results:
        try:
            from datetime import datetime, timezone

            from orchestrator.memory import Memory
        except Exception as exc:  # pragma: no cover - defensive
            print(
                f"\nupdate-memory skipped (imports unavailable): {exc}",
                file=sys.stderr,
            )
        else:
            try:
                timestamp = datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
                ranked = sorted(
                    results,
                    key=lambda r: (
                        compute_metrics(r).as_dict().get(
                            args.sort_by, 0.0
                        )
                        if args.sort_by != "name"
                        else r.name
                    ),
                    reverse=(args.sort_by != "name"),
                )[:5]
                lines = [f"**Top 5 by {args.sort_by} (run {timestamp}):**"]
                for r in ranked:
                    m = compute_metrics(r).as_dict()
                    lines.append(
                        f"- `{r.name}`: PF {m.get('profit_factor', 0.0):.2f}, "
                        f"Sharpe {m.get('sharpe', 0.0):.2f}, "
                        f"CAGR {m.get('cagr', 0.0):.2%}, "
                        f"DD {m.get('max_drawdown', 0.0):.2%}, "
                        f"WR {m.get('win_rate', 0.0):.2%}, "
                        f"{int(m.get('trade_count', 0))} trades."
                    )
                Memory(path=args.memory_path).update_section(
                    "Backtest snapshot", "\n".join(lines), mode="append"
                )
                print(
                    f"\n[memory] appended top-5 snapshot to "
                    f"{args.memory_path}."
                )
            except Exception as exc:  # pragma: no cover - defensive
                print(
                    f"\n[memory] failed to update {args.memory_path}: {exc}",
                    file=sys.stderr,
                )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
