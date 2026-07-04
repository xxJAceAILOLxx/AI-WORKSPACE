"""Strategy registry for the mean-reversion strategy library.

Strategies are registered via the :func:`register` decorator and discovered
through :func:`list_strategies`.  Use :func:`run` to invoke a strategy by
name without importing its module directly.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List

from backtest.engine import BacktestResult


# A strategy function takes arbitrary kwargs and returns a BacktestResult.
StrategyFn = Callable[..., BacktestResult]


# The global registry.  Populated by @register decorators when each
# strategy module is imported (the package __init__ imports them all).
REGISTRY: Dict[str, StrategyFn] = {}


def register(name: str) -> Callable[[StrategyFn], StrategyFn]:
    """Decorator that registers ``fn`` under ``name`` in :data:`REGISTRY`."""

    def decorator(fn: StrategyFn) -> StrategyFn:
        if name in REGISTRY and REGISTRY[name] is not fn:
            # Re-registration of the same name with a different function is
            # almost certainly a bug; surface it loudly instead of silently
            # overwriting.
            raise ValueError(
                f"Strategy name {name!r} already registered to "
                f"{REGISTRY[name].__module__}.{REGISTRY[name].__qualname__}; "
                f"refusing to overwrite with {fn.__module__}.{fn.__qualname__}"
            )
        REGISTRY[name] = fn
        return fn

    return decorator


def run(name: str, **kwargs: Any) -> BacktestResult:
    """Invoke the strategy registered as ``name`` with ``kwargs``.

    Raises :class:`KeyError` if the strategy is not registered.  Use
    :func:`list_strategies` to enumerate the available names.
    """
    if name not in REGISTRY:
        raise KeyError(
            f"Unknown strategy {name!r}. Available: {sorted(REGISTRY)}"
        )
    return REGISTRY[name](**kwargs)


def list_strategies() -> List[str]:
    """Return a sorted list of registered strategy names."""
    return sorted(REGISTRY)


__all__ = ["REGISTRY", "StrategyFn", "register", "run", "list_strategies"]
