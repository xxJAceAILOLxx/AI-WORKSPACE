"""Research Autopilot tools — the 5-tool chain bridging Hypothesis → Goal → Backtest.

Tool chain:
1. run_research_autopilot(hypothesis_id) — create goal from hypothesis
2. generate_backtest_config(hypothesis_id, start_date, end_date) — write config.json
3. scaffold_signal_engine(hypothesis_id, run_dir) — write signal_engine.py stub
4. [user edits signal_engine.py, or LLM edits via write_file]
5. link_autopilot_backtest(hypothesis_id, run_dir) — link run_card metrics
"""

from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
from typing import Any

from ..agent.tools import BaseTool
from ..hypotheses.registry import HypothesisRegistry
from ..goal.store import GoalStore

# Hypothesis ID → stable run directory mapping.
_RUN_BASE = Path.home() / ".vibe-trading" / "runs"


def _run_dir_for_hypothesis(hypothesis_id: str) -> Path:
    short_hash = hashlib.sha256(hypothesis_id.encode()).hexdigest()[:12]
    return _RUN_BASE / f"autopilot_{short_hash}"


class RunResearchAutopilotTool(BaseTool):
    name = "run_research_autopilot"
    description = (
        "Initialize the research autopilot for a hypothesis: creates a "
        "research goal and prepares the workflow context."
    )
    is_readonly = False
    repeatable = True
    parameters = {
        "type": "object",
        "properties": {
            "hypothesis_id": {"type": "string", "description": "ID of the hypothesis"},
            "session_id": {"type": "string", "description": "Optional session ID"},
        },
        "required": ["hypothesis_id"],
    }

    def execute(self, **kwargs: Any) -> str:
        h_id = kwargs["hypothesis_id"]
        session_id = kwargs.get("session_id", "default")

        reg = HypothesisRegistry()
        h = reg.get_hypothesis(h_id)
        if h is None:
            return json.dumps({"status": "error", "error": f"hypothesis {h_id!r} not found"})

        criteria = [
            "Backtest produces non-empty trades",
            "Sharpe ratio > 0.5",
            "Max drawdown < 20%",
            "Win rate > 40%",
        ]

        goal_store = GoalStore()
        objective = (
            f"Validate hypothesis '{h.title}': {h.thesis[:200]}\n"
            f"Universe: {h.universe}\nSignal: {h.signal_definition[:200]}"
        )
        goal = goal_store.replace_goal(
            session_id=session_id,
            objective=objective,
            criteria=criteria,
            source="autopilot",
        )

        return json.dumps({
            "status": "ok",
            "hypothesis": {"id": h.hypothesis_id, "title": h.title, "status": h.status},
            "goal": {"id": goal.goal_id, "objective": goal.objective[:200], "criteria": criteria},
            "next_step": "generate_backtest_config",
        })


class GenerateBacktestConfigTool(BaseTool):
    name = "generate_backtest_config"
    description = (
        "Generate a backtest configuration (config.json) for a hypothesis. "
        "Creates the run directory and writes ticker/date/source config."
    )
    is_readonly = False
    parameters = {
        "type": "object",
        "properties": {
            "hypothesis_id": {"type": "string", "description": "ID of the hypothesis"},
            "start_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "End date YYYY-MM-DD"},
        },
        "required": ["hypothesis_id", "start_date", "end_date"],
    }

    def execute(self, **kwargs: Any) -> str:
        h_id = kwargs["hypothesis_id"]
        start_date = kwargs.get("start_date", "2020-01-01")
        end_date = kwargs.get("end_date", "2025-12-31")

        reg = HypothesisRegistry()
        h = reg.get_hypothesis(h_id)
        if h is None:
            return json.dumps({"status": "error", "error": f"hypothesis {h_id!r} not found"})

        # Map universe to ticker(s).
        universe_map = {
            "spy": "SPY", "qqq": "QQQ", "iwm": "IWM", "dia": "DIA",
            "s&p 500": "SPY", "nasdaq": "QQQ", "russell": "IWM",
            "csi 300": "000300.SH", "hang seng": "^HSI",
        }
        ticker = universe_map.get(h.universe.lower(), h.universe.upper() or "SPY")

        run_dir = _run_dir_for_hypothesis(h_id)
        run_dir.mkdir(parents=True, exist_ok=True)

        config = {
            "codes": [ticker],
            "start_date": start_date,
            "end_date": end_date,
            "source": h.data_sources[0] if h.data_sources else "yfinance",
            "interval": "1D",
            "hypothesis_id": h_id,
        }

        config_path = run_dir / "config.json"
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

        code_dir = run_dir / "code"
        code_dir.mkdir(exist_ok=True)

        return json.dumps({
            "status": "ok",
            "run_dir": str(run_dir),
            "config": config,
            "config_path": str(config_path),
            "hypothesis": {"id": h.hypothesis_id, "signal_definition": h.signal_definition[:200]},
            "next_step": "scaffold_signal_engine",
        })


_SIGNAL_ENGINE_TEMPLATE = '''\
"""Signal engine scaffolded by the Research Autopilot.

Edit the generate() method to implement your trading signal.
The engine is called by the backtest runner with OHLCV data.
"""

import pandas as pd


class SignalEngine:
    """Default signal engine — generates a flat (no-position) signal.

    Edit generate() to implement your entry/exit logic based on the
    hypothesis signal definition.
    """

    def generate(self, data_map: dict[str, pd.DataFrame]) -> dict[str, pd.Series]:
        """Return {ticker: boolean_series} indicating entry signals.

        Parameters
        ----------
        data_map:
            Dict mapping ticker symbols to OHLCV DataFrames with columns
            Open, High, Low, Close, Volume and a DatetimeIndex.

        Returns
        -------
        Dict mapping ticker symbols to boolean Series (True = enter long).
        """
        signals = {}
        for ticker, df in data_map.items():
            # Default: no signal (all False).
            signals[ticker] = pd.Series(False, index=df.index)
        return signals
'''


class ScaffoldSignalEngineTool(BaseTool):
    name = "scaffold_signal_engine"
    description = (
        "Write a stub signal_engine.py file in the run directory. "
        "The LLM or user then edits it to implement the actual signal."
    )
    is_readonly = False
    parameters = {
        "type": "object",
        "properties": {
            "hypothesis_id": {"type": "string", "description": "ID of the hypothesis"},
            "run_dir": {"type": "string", "description": "Path to the run directory"},
            "overwrite": {"type": "boolean", "description": "Overwrite if exists (default false)"},
        },
        "required": ["hypothesis_id", "run_dir"],
    }

    def execute(self, **kwargs: Any) -> str:
        h_id = kwargs["hypothesis_id"]
        run_dir = Path(kwargs["run_dir"])
        overwrite = kwargs.get("overwrite", False)

        reg = HypothesisRegistry()
        h = reg.get_hypothesis(h_id)
        if h is None:
            return json.dumps({"status": "error", "error": f"hypothesis {h_id!r} not found"})

        engine_path = run_dir / "code" / "signal_engine.py"
        if engine_path.exists() and not overwrite:
            return json.dumps({
                "status": "ok",
                "signal_engine_path": str(engine_path),
                "already_exists": True,
                "next_step": "edit signal_engine.py with your signal logic, then run backtest",
            })

        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "code").mkdir(exist_ok=True)

        # Embed hypothesis signal definition as docstring context.
        template = _SIGNAL_ENGINE_TEMPLATE
        if h.signal_definition:
            comment = f"\n# Hypothesis signal: {h.signal_definition[:500]}\n"
            template = template.replace(
                '"""Default signal engine',
                f'{comment}\n"""Default signal engine',
            )

        engine_path.write_text(template, encoding="utf-8")

        return json.dumps({
            "status": "ok",
            "signal_engine_path": str(engine_path),
            "run_dir": str(run_dir),
            "hypothesis_signal": h.signal_definition[:200],
            "next_step": "edit signal_engine.py, then run backtest",
        })


class LinkAutopilotBacktestTool(BaseTool):
    name = "link_autopilot_backtest"
    description = (
        "Link a completed backtest run to the hypothesis. Reads run_card.json "
        "from the run directory and links its metrics."
    )
    is_readonly = False
    parameters = {
        "type": "object",
        "properties": {
            "hypothesis_id": {"type": "string", "description": "ID of the hypothesis"},
            "run_dir": {"type": "string", "description": "Path to the backtest run directory"},
            "notes": {"type": "string", "description": "Optional notes"},
        },
        "required": ["hypothesis_id", "run_dir"],
    }

    def execute(self, **kwargs: Any) -> str:
        h_id = kwargs["hypothesis_id"]
        run_dir = Path(kwargs["run_dir"])
        notes = kwargs.get("notes", "")

        # Try to read run_card.json for metrics.
        metrics = {}
        run_card_path = run_dir / "run_card.json"
        if run_card_path.exists():
            try:
                card = json.loads(run_card_path.read_text(encoding="utf-8"))
                metrics = card.get("metrics", {})
            except Exception:
                pass

        # Fallback: try artifacts/metrics.csv.
        if not metrics:
            metrics_csv = run_dir / "artifacts" / "metrics.csv"
            if metrics_csv.exists():
                try:
                    import csv
                    with open(metrics_csv, "r") as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            for k, v in row.items():
                                try:
                                    metrics[k] = float(v)
                                except (ValueError, TypeError):
                                    pass
                            break  # only read first row
                except Exception:
                    pass

        reg = HypothesisRegistry()
        h = reg.link_backtest(
            hypothesis_id=h_id,
            run_dir=str(run_dir),
            metrics=metrics,
            notes=notes,
        )
        if h is None:
            return json.dumps({"status": "error", "error": f"hypothesis {h_id!r} not found"})

        return json.dumps({
            "status": "ok",
            "metrics": metrics,
            "run_dir": str(run_dir),
            "hypothesis": {
                "id": h.hypothesis_id,
                "status": h.status,
                "run_cards_count": len(h.run_cards),
            },
            "next_step": "evaluate metrics, then add_goal_evidence",
        })
