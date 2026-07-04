"""Hypothesis data model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid4().hex[:12]


@dataclass
class RunCard:
    """A backtest run linked to a hypothesis."""

    run_dir: str = ""
    metrics: Dict[str, float] = field(default_factory=dict)
    notes: str = ""
    linked_at: str = field(default_factory=_now_iso)


@dataclass
class Hypothesis:
    """A trading hypothesis with optional linked backtests.

    Attributes
    ----------
    hypothesis_id:
        Unique identifier (12-char hex).
    title:
        Short human-readable title.
    thesis:
        Detailed thesis statement.
    universe:
        Target universe (e.g. "SPY", "CSI 300", "QQQ").
    signal_definition:
        Description of the entry/exit signal.
    data_sources:
        List of data source names (e.g. ["yfinance", "tushare"]).
    status:
        One of: draft, active, validated, rejected.
    run_cards:
        Linked backtest run cards.
    created_at / updated_at:
        ISO timestamps.
    """

    hypothesis_id: str = field(default_factory=_new_id)
    title: str = ""
    thesis: str = ""
    universe: str = ""
    signal_definition: str = ""
    data_sources: List[str] = field(default_factory=lambda: ["yfinance"])
    status: str = "draft"
    run_cards: List[RunCard] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "title": self.title,
            "thesis": self.thesis,
            "universe": self.universe,
            "signal_definition": self.signal_definition,
            "data_sources": self.data_sources,
            "status": self.status,
            "run_cards": [
                {
                    "run_dir": rc.run_dir,
                    "metrics": rc.metrics,
                    "notes": rc.notes,
                    "linked_at": rc.linked_at,
                }
                for rc in self.run_cards
            ],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Hypothesis":
        run_cards = [
            RunCard(
                run_dir=rc.get("run_dir", ""),
                metrics=rc.get("metrics", {}),
                notes=rc.get("notes", ""),
                linked_at=rc.get("linked_at", ""),
            )
            for rc in data.get("run_cards", [])
        ]
        return cls(
            hypothesis_id=data.get("hypothesis_id", _new_id()),
            title=data.get("title", ""),
            thesis=data.get("thesis", ""),
            universe=data.get("universe", ""),
            signal_definition=data.get("signal_definition", ""),
            data_sources=data.get("data_sources", ["yfinance"]),
            status=data.get("status", "draft"),
            run_cards=run_cards,
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )
