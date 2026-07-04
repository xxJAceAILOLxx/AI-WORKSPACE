"""Seven-stage workflow orchestration.

The workflow runs the stages documented in ``agents.md``::

    research -> design -> backtest -> validate -> deploy -> monitor -> learn

Each stage prints the prompt of the corresponding agent (with context
substituted) and, where applicable, invokes the local backtest engine
or sanity checks the equity curve.

When an ``llm`` is provided, non-backtest stages (research, design,
deploy, monitor, learn) run through the LLM agent loop with tool
execution instead of just printing prompts.  The backtest stage always
uses the local registry.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from .agents import (
    AGENTS,
    Agent,
    by_stage,
    get_agent,
    primary_agent,
)
from .memory import (
    Memory,
    STRATEGY_MANIFEST,
    _now_iso,
    render_snapshot_bullet,
    render_strategy_table,
)

logger = logging.getLogger(__name__)


# Canonical stage ordering, mirrored by ``agents.ALL_STAGES``.
STAGES: List[str] = [
    "research",
    "design",
    "backtest",
    "validate",
    "deploy",
    "monitor",
    "learn",
]


# Default backtest callable used when the workflow is constructed without
# an explicit ``backtest_fn``.  Resolved lazily so importing this module
# does not require the backtest package to be importable for purely
# prompt-only workflows.
def _default_backtest_fn(name: str, **kwargs: Any):  # pragma: no cover - thin shim
    from backtest.strategies.registry import run as registry_run

    return registry_run(name, **kwargs)


def _default_memory_factory(path: str) -> Memory:
    return Memory(path=path)


def _compute_max_dd(equity: List[float]) -> float:
    """Maximum peak-to-trough drawdown of an equity curve as a positive fraction."""
    if not equity:
        return 0.0
    eq = np.asarray(equity, dtype=float)
    if eq.size == 0 or np.isnan(eq).all():
        return 0.0
    peaks = np.maximum.accumulate(eq)
    with np.errstate(divide="ignore", invalid="ignore"):
        drawdown = (eq - peaks) / np.where(peaks == 0, np.nan, peaks)
    drawdown = np.nan_to_num(drawdown, nan=0.0, posinf=0.0, neginf=0.0)
    return float(-drawdown.min()) if drawdown.size else 0.0


def _compute_max_daily_loss(equity: List[float]) -> float:
    """Largest single-day equity loss as a positive fraction of starting equity."""
    if len(equity) < 2:
        return 0.0
    eq = np.asarray(equity, dtype=float)
    rets = np.diff(eq) / np.where(eq[:-1] == 0, np.nan, eq[:-1])
    rets = np.nan_to_num(rets, nan=0.0, posinf=0.0, neginf=0.0)
    if rets.size == 0:
        return 0.0
    return float(-rets.min())


class Workflow:
    """Drive the seven-stage research -> learn pipeline.

    Parameters
    ----------
    stages:
        Ordered list of stage names to run.  Defaults to :data:`STAGES`
        (all seven).  Unknown stage names raise :class:`ValueError`.
    backtest_fn:
        Callable with signature ``(name, **kwargs) -> BacktestResult``.
        Defaults to :func:`backtest.strategies.registry.run`.
    memory:
        A pre-built :class:`~orchestrator.memory.Memory` instance, or
        ``None`` to construct one lazily from ``memory_path``.
    memory_path:
        Filesystem path passed to :class:`Memory` when ``memory`` is not
        supplied.  Defaults to ``"memory.md"``.
    print_fn:
        Callable used to emit stage output.  Defaults to the builtin
        :func:`print`.  Override in tests to capture output.
    account_size:
        Default account size used by Risk Manager / Prop Firm prompts.
    max_dd_pct / daily_loss_pct / target_pct:
        Default prop firm rule percentages used in prompts.
    llm:
        Optional :class:`~orchestrator.providers.chat.ChatLLM` instance.
        When provided, non-backtest stages run through the LLM agent
        loop with tool execution.  When ``None`` (default), stages
        print prompts only (backward-compatible behavior).
    tool_registry:
        Optional :class:`~orchestrator.agent.tools.ToolRegistry`.
        When ``llm`` is provided but ``tool_registry`` is not, a
        default registry is built via :func:`~orchestrator.agent.tools.build_registry`.
    """

    def __init__(
        self,
        stages: Optional[List[str]] = None,
        backtest_fn: Optional[Callable[..., Any]] = None,
        memory: Optional[Memory] = None,
        memory_path: str = "memory.md",
        print_fn: Callable[[str], None] = print,
        account_size: float = 100_000.0,
        max_dd_pct: float = 10.0,
        daily_loss_pct: float = 5.0,
        target_pct: float = 10.0,
        llm: Optional[Any] = None,
        tool_registry: Optional[Any] = None,
    ) -> None:
        if stages is None:
            stages = list(STAGES)
        unknown = [s for s in stages if s not in STAGES]
        if unknown:
            raise ValueError(
                f"Unknown workflow stage(s): {unknown}. Expected subset of {STAGES}"
            )
        self.stages = list(stages)
        self.backtest_fn = backtest_fn or _default_backtest_fn
        self._memory_provided = memory is not None
        self.memory_path = memory_path
        self._memory_instance = memory
        self.print_fn = print_fn
        self.account_size = float(account_size)
        self.max_dd_pct = float(max_dd_pct)
        self.daily_loss_pct = float(daily_loss_pct)
        self.target_pct = float(target_pct)
        self._llm = llm
        self._tool_registry = tool_registry

    # -- Helpers ----------------------------------------------------------

    @property
    def memory(self) -> Memory:
        """Lazily construct the :class:`Memory` instance on first access."""
        if self._memory_instance is None:
            self._memory_instance = _default_memory_factory(self.memory_path)
        return self._memory_instance

    def _emit(self, heading: str, body: str) -> None:
        """Print ``heading`` + ``body`` with a blank line separator."""
        self.print_fn("")
        self.print_fn(f"=== {heading} ===")
        self.print_fn(body.rstrip())

    def _agent_for(self, stage: str) -> Agent:
        """Return the primary agent for ``stage`` (the one whose prompt drives the stage)."""
        try:
            return primary_agent(stage)
        except (KeyError, ValueError) as exc:
            raise RuntimeError(f"No primary agent registered for stage {stage!r}") from exc

    def _run_with_llm(self, stage: str, user_message: str) -> str:
        """Run a stage through the LLM agent loop and return the text result.

        Falls back to prompt-only mode if the LLM is not available.
        """
        if self._llm is None:
            return ""

        try:
            from .agent.loop import AgentLoop
            from .agent.prompt import build_system_prompt

            agent = self._agent_for(stage)
            registry = self._tool_registry
            if registry is None:
                from .agent.tools import build_registry
                registry = build_registry()

            system_prompt = build_system_prompt(registry)
            # Prepend the agent's role-specific instructions.
            full_prompt = (
                f"You are {agent.name.replace('_', ' ').title()}. "
                f"{agent.purpose}\n\n"
                f"{system_prompt}"
            )

            loop = AgentLoop(
                llm=self._llm,
                registry=registry,
                system_prompt=full_prompt,
                max_iterations=15,
            )
            result = loop.run(user_message)
            return result.content
        except Exception as exc:
            logger.exception("LLM agent loop failed for stage %s", stage)
            return f"(LLM unavailable: {exc})"

    # -- Stage implementations -------------------------------------------

    def _stage_research(self, context: Dict[str, Any]) -> Dict[str, Any]:
        agent = self._agent_for("research")
        idea = str(context.get("idea", ""))
        prompt = agent.format_prompt(idea=idea or "(no idea provided)")
        self._emit(f"research :: {agent.name}", prompt)

        llm_response = ""
        if self._llm is not None:
            self.print_fn("  [research] running LLM agent with tools...")
            llm_response = self._run_with_llm(
                "research",
                f"Research this trading idea: {idea}",
            )
            if llm_response:
                self.print_fn(f"  [research] LLM response:\n{llm_response}")

        return {
            "agent": agent.name,
            "prompt": prompt,
            "idea": idea,
            "llm_response": llm_response,
        }

    def _stage_design(self, context: Dict[str, Any]) -> Dict[str, Any]:
        agent = self._agent_for("design")
        strategy_name = context.get("strategy_name") or ""
        idea = str(context.get("idea", ""))
        prompt = agent.format_prompt(
            idea=idea or "(no idea provided)",
            strategy_name=strategy_name or "(unspecified)",
        )
        self._emit(f"design :: {agent.name}", prompt)

        llm_response = ""
        if self._llm is not None:
            self.print_fn("  [design] running LLM agent with tools...")
            llm_response = self._run_with_llm(
                "design",
                f"Design a trading strategy for this idea: {idea}. "
                f"Strategy name hint: {strategy_name}",
            )
            if llm_response:
                self.print_fn(f"  [design] LLM response:\n{llm_response}")

        return {
            "agent": agent.name,
            "prompt": prompt,
            "strategy_name": strategy_name,
            "llm_response": llm_response,
        }

    def _stage_backtest(self, context: Dict[str, Any]) -> Dict[str, Any]:
        agent = self._agent_for("backtest")
        strategy_name = context.get("strategy_name")
        params: Dict[str, Any] = dict(context.get("params") or {})
        result_summary: Dict[str, Any] = {
            "agent": agent.name,
            "strategy_name": strategy_name,
            "ran": False,
            "metrics": {},
        }

        prompt = agent.format_prompt(
            strategy_name=strategy_name or "(unspecified)",
            ticker=params.get("ticker", "SPY"),
            start=params.get("start", "2016-01-01"),
            end=params.get("end", "2025-12-31"),
            execution=params.get("execution", "next_open"),
            cost_model=params.get("cost_model", "etf_0.1pct"),
        )
        self._emit(f"backtest :: {agent.name}", prompt)

        if strategy_name:
            try:
                bt_result = self.backtest_fn(strategy_name, **params)
            except KeyError as exc:
                self.print_fn(f"  [backtest] unknown strategy: {exc}")
                result_summary["error"] = f"unknown strategy {strategy_name!r}"
                return result_summary

            metrics: Dict[str, float] = {}
            try:
                # Lazy import keeps this module importable in prompt-only tests.
                from backtest.metrics import compute_metrics

                m = compute_metrics(bt_result)
                metrics = m.as_dict()
            except Exception as exc:  # pragma: no cover - defensive
                self.print_fn(f"  [backtest] metrics computation failed: {exc}")
                metrics = {}

            result_summary["ran"] = True
            result_summary["metrics"] = metrics
            result_summary["trades"] = len(getattr(bt_result, "trades", []))
            result_summary["equity"] = list(getattr(bt_result, "equity", []))
            result_summary["config"] = dict(getattr(bt_result, "config", {}) or {})

            self.print_fn(
                f"  [backtest] {strategy_name}: "
                f"trades={result_summary['trades']}, "
                f"PF={metrics.get('profit_factor', 0.0):.2f}, "
                f"Sharpe={metrics.get('sharpe', 0.0):.2f}, "
                f"MaxDD={metrics.get('max_drawdown', 0.0):.2%}"
            )

            # Render the full metrics table so the workflow output
            # matches what ``Strategies/run_strategy.py`` produces.
            try:
                from backtest.reporting import print_result

                print_result(bt_result, metrics=m)
            except Exception as exc:  # pragma: no cover - defensive
                self.print_fn(f"  [backtest] reporting failed: {exc}")

        return result_summary

    def _stage_validate(self, context: Dict[str, Any]) -> Dict[str, Any]:
        agent = self._agent_for("validate")
        backtest_summary = context.get("backtest") or {}
        metrics = backtest_summary.get("metrics") or {}
        equity: List[float] = backtest_summary.get("equity") or []

        max_dd = _compute_max_dd(equity) if equity else float(metrics.get("max_drawdown", 0.0))
        max_daily = _compute_max_daily_loss(equity) if equity else 0.0

        max_dd_breach = max_dd * 100.0 > self.max_dd_pct
        daily_breach = max_daily * 100.0 > self.daily_loss_pct
        checks_ok = (not max_dd_breach) and (not daily_breach)

        metrics_lines: List[str] = []
        if metrics:
            for key in (
                "trade_count",
                "profit_factor",
                "sharpe",
                "max_drawdown",
                "win_rate",
                "cagr",
            ):
                if key in metrics:
                    metrics_lines.append(f"  - {key}: {metrics[key]}")
        metrics_block = "\n".join(metrics_lines) if metrics_lines else "  (no metrics)"

        prompt = agent.format_prompt(
            account_size=f"{self.account_size:,.0f}",
            max_dd_pct=f"{self.max_dd_pct:.1f}",
            max_dd_abs=f"{self.account_size * self.max_dd_pct / 100:,.0f}",
            daily_loss_pct=f"{self.daily_loss_pct:.1f}",
            daily_loss_abs=f"{self.account_size * self.daily_loss_pct / 100:,.0f}",
            target_pct=f"{self.target_pct:.1f}",
            target_abs=f"{self.account_size * self.target_pct / 100:,.0f}",
            metrics=metrics_block,
        )
        self._emit(f"validate :: {agent.name}", prompt)

        # Sanity checks.
        check_lines = [
            f"  - max drawdown: {max_dd:.2%} "
            f"({'BREACH' if max_dd_breach else 'ok'} vs {self.max_dd_pct:.1f}%)",
            f"  - max daily loss: {max_daily:.2%} "
            f"({'BREACH' if daily_breach else 'ok'} vs {self.daily_loss_pct:.1f}%)",
        ]
        self.print_fn("  [validate] sanity checks:")
        for line in check_lines:
            self.print_fn(line)

        # After both backtest and validate complete successfully, append a
        # concise bullet to the ``Backtest snapshot`` section of memory.md.
        # We only do this when backtest actually produced a result.
        snapshot_appended = False
        snapshot_error: Optional[str] = None
        if backtest_summary.get("ran") and backtest_summary.get("strategy_name"):
            try:
                verdict = "validate OK" if checks_ok else "validate FAILED"
                bullet = render_snapshot_bullet(
                    strategy_name=str(backtest_summary.get("strategy_name")),
                    metrics=metrics,
                    verdict=verdict,
                    timestamp=_now_iso(),
                )
                self.memory.update_section(
                    "Backtest snapshot", bullet, mode="append"
                )
                snapshot_appended = True
                self.print_fn("  [validate] appended Backtest snapshot bullet.")
            except OSError as exc:
                snapshot_error = str(exc)
                self.print_fn(f"  [validate] failed to append snapshot: {exc}")

        return {
            "agent": agent.name,
            "prompt": prompt,
            "max_drawdown": max_dd,
            "max_daily_loss": max_daily,
            "max_dd_breach": max_dd_breach,
            "daily_loss_breach": daily_breach,
            "checks_ok": checks_ok,
            "snapshot_appended": snapshot_appended,
            "snapshot_error": snapshot_error,
        }

    def _stage_deploy(self, context: Dict[str, Any]) -> Dict[str, Any]:
        agent = self._agent_for("deploy")
        backtest_summary = context.get("backtest") or {}
        metrics = backtest_summary.get("metrics") or {}

        metrics_lines: List[str] = []
        for key in (
            "trade_count",
            "profit_factor",
            "sharpe",
            "max_drawdown",
            "win_rate",
            "cagr",
            "expectancy",
        ):
            if key in metrics:
                metrics_lines.append(f"  - {key}: {metrics[key]}")
        metrics_block = "\n".join(metrics_lines) if metrics_lines else "  (no metrics)"

        phase = context.get("phase") or "Challenge"
        prompt = agent.format_prompt(
            phase=str(phase),
            account_size=f"{self.account_size:,.0f}",
            target_pct=f"{self.target_pct:.1f}",
            max_dd_pct=f"{self.max_dd_pct:.1f}",
            daily_loss_pct=f"{self.daily_loss_pct:.1f}",
            metrics=metrics_block,
        )
        self._emit(f"deploy :: {agent.name}", prompt)

        llm_response = ""
        if self._llm is not None:
            self.print_fn("  [deploy] running LLM agent with tools...")
            llm_response = self._run_with_llm(
                "deploy",
                f"Prop firm challenge phase: {phase}. "
                f"Account: ${self.account_size:,.0f}. "
                f"Rules: target {self.target_pct}%, max DD {self.max_dd_pct}%, "
                f"daily loss {self.daily_loss_pct}%.\n"
                f"Metrics:\n{metrics_block}",
            )
            if llm_response:
                self.print_fn(f"  [deploy] LLM response:\n{llm_response}")

        return {"agent": agent.name, "prompt": prompt, "phase": phase, "llm_response": llm_response}

    def _stage_monitor(self, context: Dict[str, Any]) -> Dict[str, Any]:
        agent = self._agent_for("monitor")
        summary_lines: List[str] = []
        idea = context.get("idea")
        if idea:
            summary_lines.append(f"  - idea: {idea}")
        backtest_summary = context.get("backtest") or {}
        if backtest_summary.get("ran"):
            summary_lines.append(
                f"  - strategy: {backtest_summary.get('strategy_name')}"
            )
            summary_lines.append(f"  - trades: {backtest_summary.get('trades', 0)}")
            metrics = backtest_summary.get("metrics") or {}
            for key in ("profit_factor", "win_rate", "sharpe", "max_drawdown"):
                if key in metrics:
                    summary_lines.append(f"  - {key}: {metrics[key]}")
        validate_summary = context.get("validate") or {}
        if validate_summary:
            summary_lines.append(
                f"  - validation checks ok: {validate_summary.get('checks_ok')}"
            )
            summary_lines.append(
                f"  - max drawdown: {validate_summary.get('max_drawdown', 0.0):.2%}"
            )
        summary = "\n".join(summary_lines) if summary_lines else "  (no run data)"

        prompt = agent.format_prompt(summary=summary)
        self._emit(f"monitor :: {agent.name}", prompt)

        llm_response = ""
        if self._llm is not None:
            self.print_fn("  [monitor] running LLM agent with tools...")
            llm_response = self._run_with_llm(
                "monitor",
                f"Review this trading run and identify mistakes:\n{summary}",
            )
            if llm_response:
                self.print_fn(f"  [monitor] LLM response:\n{llm_response}")

        return {"agent": agent.name, "prompt": prompt, "summary": summary, "llm_response": llm_response}

    def _stage_learn(self, context: Dict[str, Any]) -> Dict[str, Any]:
        agent = self._agent_for("learn")
        # Knowledge Curator's prompt is static; just print it so the stage
        # is observable end-to-end.
        self._emit(f"learn :: {agent.name}", agent.format_prompt())

        # Build a compact run summary and append to memory.md.
        backtest_summary = context.get("backtest") or {}
        validate_summary = context.get("validate") or {}

        run_entry: Dict[str, Any] = {
            "idea": context.get("idea", ""),
            "strategy_name": backtest_summary.get("strategy_name") or "",
            "stages": list(self.stages),
            "metrics": {
                k: backtest_summary.get("metrics", {}).get(k)
                for k in (
                    "trade_count",
                    "profit_factor",
                    "sharpe",
                    "max_drawdown",
                    "win_rate",
                    "cagr",
                )
                if k in backtest_summary.get("metrics", {})
            },
            "notes": (
                f"validate_ok={validate_summary.get('checks_ok')}; "
                f"max_dd={validate_summary.get('max_drawdown', 0.0):.2%}; "
                f"max_daily={validate_summary.get('max_daily_loss', 0.0):.2%}"
            ),
        }

        appended = False
        try:
            self.memory.append_run(run_entry)
            appended = True
        except OSError as exc:
            self.print_fn(f"  [learn] failed to append run: {exc}")

        # If the caller flagged a new strategy being added, rewrite the
        # ``Registered strategies`` table from the (extended) manifest.
        strategies_rewritten = False
        strategies_error: Optional[str] = None
        new_strategy = context.get("new_strategy")
        strategy_name = backtest_summary.get("strategy_name") or context.get("strategy_name")
        if new_strategy and strategy_name:
            try:
                manifest: Dict[str, Dict[str, str]] = {k: dict(v) for k, v in STRATEGY_MANIFEST.items()}
                if isinstance(new_strategy, dict):
                    meta = dict(new_strategy)
                    meta.setdefault("ticker", "?")
                    meta.setdefault("entry", "?")
                    meta.setdefault("exit", "?")
                    meta.setdefault("sizing", "?")
                    meta.setdefault("cost", "?")
                    manifest[strategy_name] = meta
                elif strategy_name not in manifest:
                    manifest[strategy_name] = {
                        "ticker": "?",
                        "entry": "?",
                        "exit": "?",
                        "sizing": "?",
                        "cost": "?",
                    }
                table = render_strategy_table(manifest)
                self.memory.update_section(
                    "Registered strategies", table, mode="replace"
                )
                strategies_rewritten = True
                self.print_fn(
                    f"  [learn] rewrote 'Registered strategies' table "
                    f"(now {len(manifest)} entries)."
                )
            except OSError as exc:
                strategies_error = str(exc)
                self.print_fn(
                    f"  [learn] failed to rewrite strategies table: {exc}"
                )

        return {
            "agent": agent.name,
            "appended": appended,
            "run_entry": run_entry,
            "memory_path": self.memory.path,
            "strategies_rewritten": strategies_rewritten,
            "strategies_error": strategies_error,
        }

    # -- Public entry point ----------------------------------------------

    def run(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute the configured stages and return a context dict.

        ``context`` may contain ``idea``, ``strategy_name``, ``params``,
        ``phase``, and the workflow will populate ``backtest``,
        ``validate``, ``deploy``, ``monitor``, ``learn`` keys as each
        stage runs.  The same dict is returned for caller inspection.
        """
        ctx: Dict[str, Any] = dict(context or {})

        handlers = {
            "research": self._stage_research,
            "design": self._stage_design,
            "backtest": self._stage_backtest,
            "validate": self._stage_validate,
            "deploy": self._stage_deploy,
            "monitor": self._stage_monitor,
            "learn": self._stage_learn,
        }

        for stage in self.stages:
            result = handlers[stage](ctx)
            ctx[stage] = result

        return ctx


__all__ = ["STAGES", "Workflow"]
