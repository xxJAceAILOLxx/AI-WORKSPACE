"""Event-driven backtest engine.

The :class:`Engine` consumes a boolean entry signal and an optional
exit-rule callback and produces a list of closed :class:`Trade` records
plus a daily equity curve.

Semantics
---------

* Entries: signals are computed at bar ``t`` close.  With the default
  ``execution="next_open"`` the order fills at bar ``t+1`` open.  With
  ``execution="close"`` the fill happens at bar ``t`` close.  Signals
  that fire while a position is open are ignored.
* Exits: stops trigger intraday if ``Low <= stop_price``; rule-based and
  max-hold exits fill at the same execution price as entries (next bar
  open for ``next_open`` mode, current bar close for ``close`` mode).
* Costs: the configured :class:`~backtest.costs.CostModel` is invoked on
  entry and again on exit.  Both halves are subtracted from cash so the
  equity curve reflects the timing of each leg.
* Sizing: ``percent_of_equity`` allocates ``size_value * cash`` to the
  trade; ``fixed_risk`` sizes shares as ``size_value / (entry - stop)``
  and requires ``stop_mult > 0``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .costs import CostModel, PERCENT_10BP
from .data import OHLCV
from .indicators import atr


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------


@dataclass
class Trade:
    """A single round-trip trade."""

    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    entry_price: float
    exit_price: float
    shares: int
    pnl: float
    return_pct: float
    hold_days: int
    exit_reason: str
    entry_cost: float = 0.0
    exit_cost: float = 0.0


@dataclass
class BacktestResult:
    """Output of an :class:`Engine` run."""

    name: str
    trades: List[Trade]
    equity: List[float]
    ohlcv: OHLCV
    initial_capital: float = 0.0
    execution: str = "next_open"
    cost_model_name: str = ""
    config: Dict[str, object] = field(default_factory=dict)


@dataclass
class EngineState:
    """Snapshot passed to the exit-rule callback.

    The state exposes everything a rule might need to make a decision:
    the current bar's OHLCV, the position's entry details, current
    mark-to-market equity, ATR at entry and now, and the position's
    bar index within the OHLCV.
    """

    date: pd.Timestamp
    bar: pd.Series
    entry_date: pd.Timestamp
    entry_price: float
    shares: int
    days_held: int
    equity: float
    atr_entry: float
    atr_now: float
    stop_price: float
    idx: int


ExitRule = Callable[[EngineState], Optional[Tuple[str, float]]]
EntrySignal = pd.Series


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class Engine:
    """Event-driven backtest engine.

    Construct with an :class:`OHLCV` dataset and configure via the
    setter methods or constructor args.  Call :meth:`run` to execute.
    """

    def __init__(
        self,
        ohlcv: OHLCV,
        name: str = "strategy",
        execution: str = "next_open",
        cost_model: CostModel = PERCENT_10BP,
        initial_capital: float = 100_000.0,
        size_policy: str = "percent_of_equity",
        size_value: float = 0.95,
        stop_mult: float = 0.0,
        max_hold: int = 0,
        atr_period: int = 14,
        vol_series: "pd.Series | None" = None,
        target_vol: float = 0.15,
        max_leverage: float = 3.0,
    ) -> None:
        if execution not in {"next_open", "close"}:
            raise ValueError(f"execution must be 'next_open' or 'close', got {execution!r}")
        if size_policy not in {"percent_of_equity", "fixed_risk", "vol_target"}:
            raise ValueError(
                f"size_policy must be 'percent_of_equity', 'fixed_risk' or "
                f"'vol_target', got {size_policy!r}"
            )
        if size_policy == "fixed_risk" and stop_mult <= 0:
            raise ValueError("fixed_risk sizing requires stop_mult > 0")
        if size_policy == "vol_target" and vol_series is None:
            raise ValueError("vol_target sizing requires a vol_series (forecast vol)")

        self.ohlcv = ohlcv
        self.name = name
        self.execution = execution
        self.cost_model = cost_model
        self.initial_capital = float(initial_capital)
        self.size_policy = size_policy
        self.size_value = float(size_value)
        self.stop_mult = float(stop_mult)
        self.max_hold = int(max_hold)
        self.atr_period = int(atr_period)
        self.vol_series = vol_series
        self.target_vol = float(target_vol)
        self.max_leverage = float(max_leverage)

        self._entry_signal: Optional[pd.Series] = None
        self._exit_rule: Optional[ExitRule] = None

    # -- Configuration ------------------------------------------------------

    def set_entry(self, signal: EntrySignal) -> "Engine":
        """Register the entry signal aligned to the OHLCV index.

        Accepts either:

        * a **boolean** Series (long-only) — ``True`` means enter long, or
        * a **signed integer/float** Series with values in ``{-1, 0, 1}`` —
          ``+1`` enters long, ``-1`` enters short, ``0`` does nothing.

        The raw series is stored as-is so the sign (trade direction) is
        preserved; the engine reads the direction at decision time.
        """
        if not isinstance(signal, pd.Series):
            raise TypeError("entry signal must be a pandas Series")
        self._entry_signal = signal
        return self

    def set_exit(self, rule: ExitRule) -> "Engine":
        """Register the exit rule callback.  See :class:`EngineState`."""
        self._exit_rule = rule
        return self

    # -- Main entry point ---------------------------------------------------

    def run(self) -> BacktestResult:
        if self._entry_signal is None:
            raise RuntimeError(
                "Engine.run() called before set_entry(); supply an entry signal first."
            )

        df = self.ohlcv.df
        n = len(df)
        if n == 0:
            return BacktestResult(
                name=self.name,
                trades=[],
                equity=[],
                ohlcv=self.ohlcv,
                initial_capital=self.initial_capital,
                execution=self.execution,
                cost_model_name=self.cost_model.name,
                config=self._config_dict(),
            )

        signal = self._entry_signal.reindex(df.index, fill_value=0)
        atr_series = atr(df, period=self.atr_period).fillna(0.0)

        # Vol-target forecast (annualized) aligned to the index; looked up
        # per-bar inside _open_position.  Warm-up / missing values become
        # 0.0 so the position simply stays flat until the forecast is live.
        if self.vol_series is not None:
            vol_lookup = self.vol_series.reindex(df.index, fill_value=0.0).fillna(0.0)
        else:
            vol_lookup = None

        cash = self.initial_capital
        position: Optional[dict] = None
        trades: List[Trade] = []
        equity: List[float] = []

        # Pending actions fire at the next bar's open (next_open mode only).
        pending_entry: Optional[dict] = None  # {'exec_idx', 'atr_at_signal'}
        pending_exit: Optional[dict] = None   # {'exec_idx', 'reason'}

        def _build_exit_fill_price(reason: str) -> None:
            """Record an exit that will fill at the next bar's open."""
            nonlocal pending_exit
            pending_exit = {"reason": reason}

        def _close_position(fill_price: float, fill_idx: int, reason: str) -> None:
            nonlocal position, cash
            assert position is not None
            entry_price = position["entry_price"]
            shares = position["shares"]
            pnl_gross = (fill_price - entry_price) * shares
            exit_cost = self.cost_model.cost(abs(shares), 0.0, fill_price)
            pnl_net = pnl_gross - exit_cost
            cash += shares * fill_price - exit_cost
            notional = abs(entry_price * shares)
            trades.append(
                Trade(
                    entry_date=position["entry_date"],
                    exit_date=df.index[fill_idx],
                    entry_price=entry_price,
                    exit_price=fill_price,
                    shares=shares,
                    pnl=pnl_net,
                    return_pct=pnl_net / notional if notional else 0.0,
                    hold_days=max(0, fill_idx - position["entry_idx"]),
                    exit_reason=reason,
                    entry_cost=position.get("entry_cost", 0.0),
                    exit_cost=exit_cost,
                )
            )
            position = None

        def _open_position(
            fill_price: float, fill_idx: int, atr_at_signal: float, side: int
        ) -> None:
            nonlocal position, cash, pending_entry
            side = int(side)
            if self.stop_mult > 0 and atr_at_signal > 0:
                if side > 0:
                    stop_price = fill_price - self.stop_mult * atr_at_signal
                else:
                    stop_price = fill_price + self.stop_mult * atr_at_signal
            else:
                stop_price = 0.0
            fcst_vol = (
                float(vol_lookup.iloc[fill_idx])
                if (self.size_policy == "vol_target" and vol_lookup is not None)
                else 0.0
            )
            shares_base = self._compute_shares(cash, fill_price, stop_price, fcst_vol)
            if shares_base <= 0:
                pending_entry = None
                return
            shares = shares_base * side
            entry_cost = self.cost_model.cost(abs(shares), fill_price, 0.0)
            cash -= entry_cost + shares * fill_price
            position = {
                "entry_idx": fill_idx,
                "entry_date": df.index[fill_idx],
                "entry_price": fill_price,
                "shares": shares,
                "side": side,
                "stop_price": stop_price,
                "atr_entry": atr_at_signal,
                "entry_cost": entry_cost,
            }
            pending_entry = None

        i = 0
        while i < n:
            bar = df.iloc[i]

            # ---- 1. Resolve pending exit at this bar's Open (next_open mode) ----
            if pending_exit is not None and position is not None:
                fill_price = float(bar["Open"])
                _close_position(fill_price, i, pending_exit["reason"])
                pending_exit = None

            # ---- 2. Resolve pending entry at this bar's Open (next_open mode) ----
            if position is None and pending_entry is not None:
                fill_price = float(bar["Open"])
                _open_position(fill_price, i, pending_entry["atr_at_signal"], pending_entry["side"])

            # ---- 3. Decide new entry (only if flat) ----
            if position is None and pending_entry is None and bool(signal.iloc[i]):
                atr_at_signal = float(atr_series.iloc[i])
                raw = signal.iloc[i]
                if isinstance(raw, (bool, np.bool_)):
                    side = 1 if bool(raw) else 0
                else:
                    side = int(np.sign(raw))
                if self.execution == "close":
                    _open_position(float(bar["Close"]), i, atr_at_signal, side)
                else:  # next_open
                    if i + 1 < n:
                        pending_entry = {
                            "exec_idx": i + 1,
                            "atr_at_signal": atr_at_signal,
                            "side": side,
                        }

            # ---- 4. Evaluate exits while in a position ----
            if position is not None:
                # Track holding days (entry bar counts as day 1).
                days_held = max(1, i - position["entry_idx"] + 1)

                stop_price = position["stop_price"]
                side = position.get("side", 1)
                stop_hit = False
                if self.stop_mult > 0 and stop_price > 0:
                    if side > 0:
                        stop_hit = float(bar["Low"]) <= stop_price
                    else:
                        stop_hit = float(bar["High"]) >= stop_price
                rule_exit: Optional[Tuple[str, float]] = None
                if not stop_hit and self._exit_rule is not None:
                    state = EngineState(
                        date=df.index[i],
                        bar=bar,
                        entry_date=position["entry_date"],
                        entry_price=position["entry_price"],
                        shares=position["shares"],
                        days_held=days_held,
                        equity=cash + position["shares"] * float(bar["Close"]),
                        atr_entry=position["atr_entry"],
                        atr_now=float(atr_series.iloc[i]),
                        stop_price=stop_price,
                        idx=i,
                    )
                    rule_out = self._exit_rule(state)
                    if rule_out is not None:
                        rule_exit = rule_out

                if stop_hit:
                    reason = "stop"
                    if self.execution == "next_open":
                        if i + 1 < n:
                            _build_exit_fill_price(reason)
                        else:
                            _close_position(stop_price, i, reason)
                    else:
                        # Close execution: stop fills at the lower of stop / Close
                        # to be conservative about gaps.
                        fill = min(stop_price, float(bar["Close"]))
                        _close_position(fill, i, reason)
                elif rule_exit is not None:
                    reason, _target = rule_exit
                    if self.execution == "next_open":
                        if i + 1 < n:
                            _build_exit_fill_price(reason)
                        else:
                            _close_position(float(bar["Close"]), i, reason)
                    else:
                        _close_position(float(bar["Close"]), i, reason)
                elif self.max_hold > 0 and days_held >= self.max_hold:
                    reason = "max_hold"
                    if self.execution == "next_open":
                        if i + 1 < n:
                            _build_exit_fill_price(reason)
                        else:
                            _close_position(float(bar["Close"]), i, reason)
                    else:
                        _close_position(float(bar["Close"]), i, reason)

            # ---- 5. Record end-of-bar equity ----
            if position is not None:
                mark = position["shares"] * float(bar["Close"])
                equity.append(cash + mark)
            else:
                equity.append(cash)
            i += 1

        # Force-close any open position at the last bar's close.
        if position is not None:
            _close_position(float(df.iloc[-1]["Close"]), n - 1, "end_of_data")
            equity[-1] = cash

        return BacktestResult(
            name=self.name,
            trades=trades,
            equity=equity,
            ohlcv=self.ohlcv,
            initial_capital=self.initial_capital,
            execution=self.execution,
            cost_model_name=self.cost_model.name,
            config=self._config_dict(),
        )

    # -- Helpers ------------------------------------------------------------

    def _compute_shares(
        self, cash: float, entry_price: float, stop_price: float, fcst_vol: float = 0.0
    ) -> int:
        if entry_price <= 0:
            return 0
        if self.size_policy == "percent_of_equity":
            alloc = self.size_value * cash
            if alloc <= 0:
                return 0
            return int(alloc // entry_price)
        if self.size_policy == "vol_target":
            # Inverse-vol sizing: target a constant annualized volatility by
            # scaling notional as target_vol / forecast_vol.  ``size_value``
            # is the full-size equity fraction (e.g. 0.95); the forecast
            # vol is the GARCH/realized series aligned to the entry bar.
            if fcst_vol <= 0:
                return 0
            base_notional = self.size_value * cash
            desired = (self.target_vol / fcst_vol) * base_notional
            # Cap gross notional so calm regimes can't lever astronomically.
            cap = self.max_leverage * cash
            desired = max(-cap, min(cap, desired))
            if desired == 0:
                return 0
            return int(desired // entry_price)
        # fixed_risk
        risk_per_share = abs(entry_price - stop_price)
        if risk_per_share <= 0:
            return 0
        return int(self.size_value // risk_per_share)

    def _config_dict(self) -> Dict[str, object]:
        return {
            "execution": self.execution,
            "cost_model": self.cost_model.name,
            "initial_capital": self.initial_capital,
            "size_policy": self.size_policy,
            "size_value": self.size_value,
            "target_vol": self.target_vol,
            "max_leverage": self.max_leverage,
            "stop_mult": self.stop_mult,
            "max_hold": self.max_hold,
            "atr_period": self.atr_period,
        }


__all__ = [
    "Trade",
    "BacktestResult",
    "EngineState",
    "Engine",
    "ExitRule",
    "EntrySignal",
]
