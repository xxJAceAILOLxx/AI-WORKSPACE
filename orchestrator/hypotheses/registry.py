"""Hypothesis Registry — CRUD + backtest linking, persisted as JSON."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import Hypothesis, RunCard, _now_iso

logger = logging.getLogger(__name__)

_DEFAULT_STORE_DIR = Path(__file__).parent / "store"


class HypothesisRegistry:
    """Persistent store for trading hypotheses.

    Each hypothesis is stored as a separate JSON file under ``store_dir``.

    Parameters
    ----------
    store_dir:
        Directory for hypothesis JSON files.  Defaults to
        ``orchestrator/hypotheses/store/``.
    """

    def __init__(self, store_dir: Optional[Path] = None) -> None:
        self._store_dir = Path(store_dir) if store_dir else _DEFAULT_STORE_DIR
        self._store_dir.mkdir(parents=True, exist_ok=True)

    # -- CRUD --------------------------------------------------------------

    def create_hypothesis(
        self,
        title: str,
        thesis: str = "",
        universe: str = "",
        signal_definition: str = "",
        data_sources: Optional[List[str]] = None,
    ) -> Hypothesis:
        """Create and persist a new hypothesis."""
        h = Hypothesis(
            title=title,
            thesis=thesis,
            universe=universe,
            signal_definition=signal_definition,
            data_sources=data_sources or ["yfinance"],
        )
        self._save(h)
        logger.info("Created hypothesis %s: %s", h.hypothesis_id, h.title)
        return h

    def get_hypothesis(self, hypothesis_id: str) -> Optional[Hypothesis]:
        """Load a hypothesis by ID, or ``None`` if not found."""
        path = self._path(hypothesis_id)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return Hypothesis.from_dict(json.load(f))

    def list_hypotheses(
        self,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Hypothesis]:
        """List hypotheses, optionally filtered by status."""
        items: List[Hypothesis] = []
        for path in sorted(self._store_dir.glob("*.json"), reverse=True):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    h = Hypothesis.from_dict(json.load(f))
                if status and h.status != status:
                    continue
                items.append(h)
                if len(items) >= limit:
                    break
            except Exception:
                logger.warning("Corrupt hypothesis file: %s", path)
        return items

    def update_hypothesis(
        self,
        hypothesis_id: str,
        **fields: Any,
    ) -> Optional[Hypothesis]:
        """Update fields on an existing hypothesis."""
        h = self.get_hypothesis(hypothesis_id)
        if h is None:
            return None
        for key, value in fields.items():
            if hasattr(h, key):
                setattr(h, key, value)
        h.updated_at = _now_iso()
        self._save(h)
        return h

    def link_backtest(
        self,
        hypothesis_id: str,
        run_dir: str,
        metrics: Dict[str, float],
        notes: str = "",
    ) -> Optional[Hypothesis]:
        """Append a backtest run card to a hypothesis."""
        h = self.get_hypothesis(hypothesis_id)
        if h is None:
            return None
        h.run_cards.append(
            RunCard(run_dir=run_dir, metrics=metrics, notes=notes)
        )
        h.updated_at = _now_iso()
        self._save(h)
        logger.info(
            "Linked backtest to %s: %s (PF=%.2f)",
            hypothesis_id,
            run_dir,
            metrics.get("profit_factor", 0.0),
        )
        return h

    def invalidate_hypothesis(
        self,
        hypothesis_id: str,
        note: str = "",
    ) -> Optional[Hypothesis]:
        """Mark a hypothesis as rejected."""
        return self.update_hypothesis(
            hypothesis_id,
            status="rejected",
            thesis=((self.get_hypothesis(hypothesis_id) or Hypothesis()).thesis + f"\n[REJECTED] {note}").strip(),
        )

    def search_hypotheses(
        self,
        query: str,
        limit: int = 20,
    ) -> List[Hypothesis]:
        """Simple keyword search across title + thesis."""
        query_lower = query.lower()
        results: List[Hypothesis] = []
        for h in self.list_hypotheses(limit=200):
            if (
                query_lower in h.title.lower()
                or query_lower in h.thesis.lower()
                or query_lower in h.signal_definition.lower()
            ):
                results.append(h)
                if len(results) >= limit:
                    break
        return results

    # -- internals ---------------------------------------------------------

    def _path(self, hypothesis_id: str) -> Path:
        return self._store_dir / f"{hypothesis_id}.json"

    def _save(self, h: Hypothesis) -> None:
        path = self._path(h.hypothesis_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(h.to_dict(), f, indent=2, ensure_ascii=False)
