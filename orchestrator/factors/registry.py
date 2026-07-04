"""Alpha factor registry — discover and compute alpha factors."""

from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import Dict, List, Optional, Type

import pandas as pd

from .base import BaseAlpha

logger = logging.getLogger(__name__)

# Global registry: name -> alpha class.
_REGISTRY: Dict[str, Type[BaseAlpha]] = {}


def register_alpha(name: str):
    """Decorator to register an alpha factor class."""
    def decorator(cls: Type[BaseAlpha]):
        cls.name = name
        _REGISTRY[name] = cls
        return cls
    return decorator


def list_alphas() -> List[str]:
    """Return sorted list of registered alpha names."""
    _ensure_loaded()
    return sorted(_REGISTRY.keys())


def get_alpha(name: str) -> BaseAlpha:
    """Instantiate and return an alpha factor by name."""
    _ensure_loaded()
    if name not in _REGISTRY:
        raise KeyError(f"Unknown alpha {name!r}. Available: {sorted(_REGISTRY)}")
    return _REGISTRY[name]()


def compute_alpha(name: str, df: pd.DataFrame) -> pd.Series:
    """Compute an alpha factor and return the signal series."""
    alpha = get_alpha(name)
    return alpha.compute(df)


def bench_alpha(
    name: str,
    data: pd.DataFrame,
    forward_returns: Optional[pd.Series] = None,
) -> Dict[str, float]:
    """Benchmark an alpha factor: IC mean, IC std, IR, positive ratio.

    Parameters
    ----------
    name:
        Alpha factor name.
    data:
        OHLCV DataFrame.
    forward_returns:
        Optional forward return series for IC computation.  If not
        provided, uses 1-day forward returns of Close.
    """
    signal = compute_alpha(name, data)

    if forward_returns is None:
        forward_returns = data["Close"].pct_change().shift(-1)

    # Align.
    aligned = pd.concat([signal, forward_returns], axis=1).dropna()
    if len(aligned) < 10:
        return {"ic_mean": 0.0, "ic_std": 0.0, "ir": 0.0, "positive_ratio": 0.0, "samples": 0}

    aligned.columns = ["signal", "returns"]
    ic = aligned["signal"].corr(aligned["returns"])
    ic_positive = (aligned["signal"] * aligned["returns"] > 0).mean()

    return {
        "ic_mean": float(ic) if pd.notna(ic) else 0.0,
        "ic_std": 0.0,  # Would need rolling IC for std.
        "ir": float(ic) if pd.notna(ic) else 0.0,
        "positive_ratio": float(ic_positive),
        "samples": len(aligned),
    }


def _ensure_loaded() -> None:
    """Auto-discover alpha modules in the zoo/ subdirectories."""
    if _REGISTRY:
        return
    try:
        import orchestrator.factors.zoo as zoo_pkg
    except ImportError:
        return
    package_path = getattr(zoo_pkg, "__path__", None)
    if package_path is None:
        return
    for importer, modname, ispkg in pkgutil.walk_packages(
        package_path, prefix="orchestrator.factors.zoo."
    ):
        try:
            importlib.import_module(modname)
        except Exception:
            logger.debug("Failed to import alpha module %s", modname)
