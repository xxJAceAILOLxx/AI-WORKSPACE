"""Swarm run store — persist swarm run state."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Optional

from .models import SwarmRun

logger = logging.getLogger(__name__)

_DEFAULT_STORE_DIR = Path(__file__).parent / "store"


class SwarmStore:
    """Persistent store for swarm run state."""

    def __init__(self, store_dir: Optional[Path] = None) -> None:
        self._store_dir = Path(store_dir) if store_dir else _DEFAULT_STORE_DIR
        self._store_dir.mkdir(parents=True, exist_ok=True)

    def save_run(self, run: SwarmRun) -> None:
        path = self._store_dir / f"{run.id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(run.to_dict(), f, indent=2, ensure_ascii=False)

    def get_run(self, run_id: str) -> Optional[SwarmRun]:
        path = self._store_dir / f"{run_id}.json"
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return SwarmRun(
            id=data.get("id", ""),
            preset_name=data.get("preset_name", ""),
            status=data.get("status", ""),
            user_vars=data.get("user_vars", {}),
            created_at=data.get("created_at", ""),
        )

    def list_runs(self, limit: int = 20) -> List[SwarmRun]:
        runs: List[SwarmRun] = []
        for path in sorted(self._store_dir.glob("*.json"), reverse=True):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                runs.append(SwarmRun(
                    id=data.get("id", ""),
                    preset_name=data.get("preset_name", ""),
                    status=data.get("status", ""),
                    created_at=data.get("created_at", ""),
                ))
                if len(runs) >= limit:
                    break
            except Exception:
                continue
        return runs
