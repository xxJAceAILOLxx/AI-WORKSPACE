"""Centralized cost models for trades.

Each :class:`CostModel` encapsulates a commission/slippage schedule as a
pure function of ``(shares, entry_price, exit_price)``.  Strategies pick
a model by name and the engine applies the cost on both entry and exit.

The cost callable's signature is intentionally uniform so any new model
can be plugged in without engine changes.  The default cost models are:

* :data:`PERCENT_10BP` — 5 bps per side (``0.0005`` of traded notional on
  entry and again on exit).
* :data:`FLAT_40` — a flat $20 per side, $40 round-trip (typical of VIX
  ETN brokers).
* :data:`PER_SHARE_1C` — $0.005 per share per side, $0.01 round-trip.

Callers can register custom models with :func:`register`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict


CostFn = Callable[[int, float, float], float]


@dataclass(frozen=True)
class CostModel:
    """A named commission/slippage schedule.

    ``cost_fn(shares, entry_price, exit_price)`` returns the *total*
    round-trip cost in dollars.  The engine subtracts the entry and
    exit halves separately from cash so that the equity curve reflects
    the timing of each leg.
    """

    name: str
    cost_fn: CostFn = field(repr=False)

    def cost(self, shares: int, entry_price: float, exit_price: float) -> float:
        """Return the dollar cost for ``shares`` traded at the given prices.

        Negative results are clamped to zero — costs cannot be negative.
        """
        if shares <= 0:
            return 0.0
        try:
            raw = float(self.cost_fn(int(shares), float(entry_price), float(exit_price)))
        except Exception:
            return 0.0
        if raw != raw:  # NaN
            return 0.0
        return max(0.0, raw)


# --- Default cost models ---------------------------------------------------

PERCENT_10BP = CostModel(
    name="etf_0.1pct",
    cost_fn=lambda s, e, x: s * (e + x) * 0.001 / 2,
)

FLAT_40 = CostModel(
    name="vix_etn_40",
    cost_fn=lambda s, e, x: 40.0,
)

PER_SHARE_1C = CostModel(
    name="per_share_0.01",
    cost_fn=lambda s, e, x: s * 0.01,
)

# --- Registry --------------------------------------------------------------

_REGISTRY: Dict[str, CostModel] = {
    PERCENT_10BP.name: PERCENT_10BP,
    FLAT_40.name: FLAT_40,
    PER_SHARE_1C.name: PER_SHARE_1C,
}


def register(model: CostModel) -> CostModel:
    """Register a custom cost model.  Replaces any existing model with the same name."""
    _REGISTRY[model.name] = model
    return model


def get(name: str) -> CostModel:
    """Look up a cost model by name.

    Raises :class:`KeyError` if the name is unknown.  Use :func:`available`
    to inspect the current registry.
    """
    if name in _REGISTRY:
        return _REGISTRY[name]
    # Allow lookup by the model itself for convenience.
    for m in _REGISTRY.values():
        if m is name:
            return m
    raise KeyError(
        f"Unknown cost model {name!r}. Available: {sorted(_REGISTRY)}"
    )


def available() -> list[str]:
    """Sorted list of registered cost model names."""
    return sorted(_REGISTRY)


__all__ = [
    "CostModel",
    "CostFn",
    "PERCENT_10BP",
    "FLAT_40",
    "PER_SHARE_1C",
    "register",
    "get",
    "available",
]
