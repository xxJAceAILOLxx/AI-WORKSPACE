#!/usr/bin/env python3
"""Single-strategy runner CLI.

Run a single strategy from the unified backtest framework registry and
print a metrics table.  Supports swapping the execution semantics, the
cost model, and optional walk-forward / Monte-Carlo validation.

Usage examples
--------------

List every registered strategy::

    python Strategies/run_strategy.py --list

Run the IBS-on-SPY strategy on the default 2016-2025 window::

    python Strategies/run_strategy.py --strategy ibs_spy

Run with a custom cost model and same-bar (close) execution::

    python Strategies/run_strategy.py \\
        --strategy ibs_spy \\
        --execution close \\
        --cost-model vix_etn_40

Run a 4-fold walk-forward validation plus a 1000-iteration Monte Carlo::

    python Strategies/run_strategy.py \\
        --strategy ibs_spy \\
        --walk-forward --monte-carlo \\
        --walk-forward-splits 4 --monte-carlo-sims 1000
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Iterable, List, Optional, Sequence

# Make the project importable when this file is run directly (e.g.
# ``python Strategies/run_strategy.py``).
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import backtest
import backtest.costs
import backtest.strategies  # noqa: F401  - triggers @register decorators
from backtest import reporting
from backtest.engine import BacktestResult
from backtest.strategies import list_strategies, run as registry_run
from backtest.validation import MonteCarloResult, WalkForwardSplit, monte_carlo, walk_forward

DEFAULT_START: str = "2016-01-01"
DEFAULT_END: str = "2025-12-31"
DEFAULT_EXECUTION: str = "next_open"
DEFAULT_COST_MODEL: str = "etf_0.1pct"
DEFAULT_WF_SPLITS: int = 4
DEFAULT_WF_TRAIN_FRAC: float = 0.7
DEFAULT_MC_SIMS: int = 1000


# ---------------------------------------------------------------------------
# Cost-model patching
# ---------------------------------------------------------------------------


# Modules inside the backtest package whose ``PERCENT_10BP`` / ``FLAT_40`` /
# ``PER_SHARE_1C`` bindings we want to be able to swap out at run time.  We
# skip ``backtest.costs`` itself (it owns the canonical registry) and the
# package ``backtest`` re-exports (we patch those via the strategy modules
# instead, which avoids any confusion with the source-of-truth registry).
_PATCHED_COST_ATTRS: tuple[str, ...] = ("PERCENT_10BP", "FLAT_40", "PER_SHARE_1C")


def _patch_cost_model(model_name: str) -> List["object"]:
    """Return a list of ``mock.patch`` started-patches replacing the named
    cost model wherever the backtest package has imported it.

    The caller is responsible for ``stop()``-ing each returned patcher (use
    ``try/finally``).  When ``model_name`` matches the framework default the
    function returns an empty list and no patching happens.
    """
    from unittest.mock import patch  # local import to avoid hard dep at module load

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
        # Don't patch the registry's source-of-truth module.
        if mod_name == "backtest.costs":
            continue
        # Don't patch the top-level re-export module: strategies get the
        # symbol through their own imports so re-exports are unused, but
        # patching them anyway is harmless and keeps invariants tidy.
        for attr in _PATCHED_COST_ATTRS:
            if hasattr(mod, attr):
                patchers.append(patch.object(mod, attr, new_model))
    return patchers


# ---------------------------------------------------------------------------
# Walk-forward / Monte-Carlo helpers
# ---------------------------------------------------------------------------


def _format_walk_forward(
    splits: Sequence[WalkForwardSplit],
    results: Sequence[BacktestResult],
) -> str:
    """Render a walk-forward report as a multi-line string."""
    from backtest.metrics import compute_metrics

    lines = []
    lines.append(f"Walk-forward validation ({len(splits)} folds)")
    lines.append(
        f"  {'Fold':>4} {'Train Range':<25} {'Test Range':<25} "
        f"{'Trades':>7} {'CAGR':>8} {'MaxDD':>8} {'PF':>7}"
    )
    for split, result in zip(splits, results):
        m = compute_metrics(result)
        train_range = f"{split.train_start.date()} -> {split.train_end.date()}"
        test_range = f"{split.test_start.date()} -> {split.test_end.date()}"
        lines.append(
            f"  {split.fold:>4} {train_range:<25} {test_range:<25} "
            f"{int(m.trade_count):>7d} "
            f"{m.cagr * 100:>7.2f}% "
            f"{m.max_drawdown * 100:>7.2f}% "
            f"{m.profit_factor:>7.2f}"
        )
    return "\n".join(lines)


def _format_monte_carlo(mc: MonteCarloResult) -> str:
    """Render a Monte-Carlo report as a multi-line string."""
    lines = []
    lines.append(f"Monte Carlo ({mc.n_sims} simulations)")
    lines.append(
        f"  Final equity  mean=${mc.final_equity_mean:>12,.0f}  "
        f"median=${mc.final_equity_median:>12,.0f}  "
        f"std=${mc.final_equity_std:>10,.0f}"
    )
    lines.append(
        f"  95% CI        [${mc.final_equity_ci_low:>12,.0f} .. "
        f"${mc.final_equity_ci_high:>12,.0f}]"
    )
    lines.append(
        f"  Max drawdown  mean={mc.max_drawdown_mean * 100:>6.2f}%  "
        f"CI=[{mc.max_drawdown_ci_low * 100:>6.2f}% .. "
        f"{mc.max_drawdown_ci_high * 100:>6.2f}%]"
    )
    lines.append(f"  Ruin prob (50% loss) = {mc.ruin_probability * 100:>6.2f}%")
    return "\n".join(lines)


def _run_walk_forward(
    strategy_name: str,
    ohlcv,
    cost_model_name: str,
    execution: str,
    n_splits: int,
    train_frac: float,
) -> tuple[List[WalkForwardSplit], List[BacktestResult]]:
    """Run a strategy on each walk-forward test fold using a patched
    ``load_daily`` so the strategy receives the test slice."""
    from unittest.mock import patch

    splits = walk_forward(ohlcv, n_splits=n_splits, train_frac=train_frac)
    if not splits:
        return [], []

    # Patch ``load_daily`` in every loaded backtest module so the
    # strategy's internal call to ``load_daily(ticker, start, end)``
    # returns the test-fold OHLCV instead of re-downloading.
    results: List[BacktestResult] = []
    cost_patchers: list = _patch_cost_model(cost_model_name)
    for p in cost_patchers:
        p.start()
    load_patchers: list = []
    try:
        for split in splits:
            test_ohlcv = backtest.OHLCV(ticker=ohlcv.ticker, df=split.test)
            for mod_name, mod in list(sys.modules.items()):
                if mod is None or not isinstance(mod_name, str):
                    continue
                if not mod_name.startswith("backtest"):
                    continue
                if hasattr(mod, "load_daily"):
                    load_patchers.append(
                        patch.object(mod, "load_daily", lambda *a, **kw: test_ohlcv)
                    )
            for p in load_patchers:
                p.start()
            try:
                results.append(registry_run(strategy_name, execution=execution))
            finally:
                for p in load_patchers:
                    p.stop()
                load_patchers = []
    finally:
        for p in cost_patchers:
            p.stop()
    return splits, results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser for ``run_strategy.py``."""
    parser = argparse.ArgumentParser(
        prog="run_strategy",
        description=(
            "Run a single registered backtest strategy and print its metrics."
        ),
    )
    parser.add_argument(
        "--strategy",
        type=str,
        default=None,
        help="Strategy name (use --list to see available names).",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List registered strategies and exit.",
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
        "--walk-forward",
        action="store_true",
        help="Also run walk-forward validation and print per-fold metrics.",
    )
    parser.add_argument(
        "--walk-forward-splits",
        type=int,
        default=DEFAULT_WF_SPLITS,
        help="Number of walk-forward folds (default 4).",
    )
    parser.add_argument(
        "--walk-forward-train-frac",
        type=float,
        default=DEFAULT_WF_TRAIN_FRAC,
        help="Fraction of each fold reserved for training (default 0.7).",
    )
    parser.add_argument(
        "--monte-carlo",
        action="store_true",
        help="Also run a Monte Carlo simulation on the closed trades.",
    )
    parser.add_argument(
        "--monte-carlo-sims",
        type=int,
        default=DEFAULT_MC_SIMS,
        help="Number of Monte Carlo simulations (default 1000).",
    )
    parser.add_argument(
        "--update-memory",
        action="store_true",
        help=(
            "Append a one-line summary of this run to the 'Backtest snapshot' "
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


def _print_strategy_list() -> None:
    print("Registered strategies:")
    for name in list_strategies():
        print(f"  - {name}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list:
        _print_strategy_list()
        return 0

    if not args.strategy:
        parser.error("--strategy is required (or pass --list to see options).")

    if args.strategy not in list_strategies():
        print(
            f"error: unknown strategy {args.strategy!r}. "
            f"Available: {', '.join(list_strategies())}",
            file=sys.stderr,
        )
        return 2

    _resolve_cost_model(args.cost_model)

    # Patch the cost model for the duration of the run.
    cost_patchers = _patch_cost_model(args.cost_model)
    for p in cost_patchers:
        p.start()
    try:
        result = registry_run(
            args.strategy,
            start=args.start,
            end=args.end,
            execution=args.execution,
        )
    finally:
        for p in cost_patchers:
            p.stop()

    # Echo the configuration so the user can verify what was used.
    print(
        f"Strategy: {args.strategy}  Execution: {args.execution}  "
        f"Cost model: {args.cost_model}"
    )
    print(f"Period:   {args.start} -> {args.end}")
    print()
    reporting.print_result(result)

    # Optional: walk-forward
    if args.walk_forward:
        print()
        # Reload the OHLCV used by this strategy (the result already
        # downloaded it; we re-use load_daily here so any cost-model
        # settings are applied consistently across the run).
        from backtest.data import load_daily

        cost_patchers = _patch_cost_model(args.cost_model)
        for p in cost_patchers:
            p.start()
        try:
            ohlcv = load_daily(result.ohlcv.ticker, args.start, args.end)
        finally:
            for p in cost_patchers:
                p.stop()
        splits, wf_results = _run_walk_forward(
            strategy_name=args.strategy,
            ohlcv=ohlcv,
            cost_model_name=args.cost_model,
            execution=args.execution,
            n_splits=args.walk_forward_splits,
            train_frac=args.walk_forward_train_frac,
        )
        if not splits:
            print(
                f"\nwalk-forward: not enough data for "
                f"{args.walk_forward_splits} folds; skipped."
            )
        else:
            print()
            print(_format_walk_forward(splits, wf_results))

    # Optional: Monte Carlo
    if args.monte_carlo:
        if not result.trades:
            print("\nmonte-carlo: no closed trades to simulate; skipped.")
        else:
            mc = monte_carlo(result, n_sims=args.monte_carlo_sims)
            print()
            print(_format_monte_carlo(mc))

    # Optional: append a one-line summary to memory.md 'Backtest snapshot'.
    if args.update_memory:
        try:
            from datetime import datetime, timezone

            from backtest.metrics import compute_metrics
            from orchestrator.memory import Memory, render_snapshot_bullet
        except Exception as exc:  # pragma: no cover - defensive
            print(
                f"\nupdate-memory skipped (imports unavailable): {exc}",
                file=sys.stderr,
            )
        else:
            try:
                metrics = compute_metrics(result).as_dict()
                verdict = f"execution={args.execution}; cost={args.cost_model}"
                bullet = render_snapshot_bullet(
                    strategy_name=args.strategy,
                    metrics=metrics,
                    verdict=verdict,
                    timestamp=datetime.now(timezone.utc).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    ),
                )
                Memory(path=args.memory_path).update_section(
                    "Backtest snapshot", bullet, mode="append"
                )
                print(
                    f"\n[memory] appended 'Backtest snapshot' bullet to "
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
