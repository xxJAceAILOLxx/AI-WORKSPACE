"""VIX ETN volatility strategy (Chunk 2c).

Implements the framework's :data:`vix_etn` strategy (originally
``all_strategies_backtest.py`` strategy 10, the "Concretum-style"
short-vol / long-vol regime switcher).

Inputs
------
* ``SPY``  : used to compute realized volatility.
* ``VXX``  : long-vol instrument (held during backwardation).
* ``SVXY`` : short-vol instrument (held during contango + eVRP).
* ``^VIX`` : VIX index, used both as the regime proxy and as a position
  size scaler.

Regime logic
------------
* **Realized vol** = 10-day rolling stdev of log SPY returns, annualised.
* **eVRP** flag    = ``VIX_close > realized_vol_10``.
* **Term-structure proxy** = 90-day SMA of VIX.  The bar is in
  *contango* (``front < back``) when ``VIX_close < VIX_sma90``;
  otherwise it is in *backwardation*.

Position sizing
---------------
* Contango + eVRP -> long SVXY for ``min(VIX_close / 100, 0.30)`` of
  equity.
* Backwardation    -> long VXX for ``min(VIX_close / 100 * 0.5, 0.20)``
  of equity.
* Exit when the regime flips.

Cost model is :data:`FLAT_40` (the framework's futures-style $40 round
trip cost).

Missing-data handling
---------------------
If either VXX or SVXY cannot be downloaded (or has no rows after date
alignment with SPY/VIX), the function returns an empty
:class:`BacktestResult` with a ``note`` in its ``config`` describing the
problem.  No exception is raised.
"""

from __future__ import annotations

import math
import warnings
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from backtest import FLAT_40, load_daily
from backtest.costs import CostModel
from backtest.data import OHLCV
from backtest.engine import BacktestResult, Trade

from ._common import DEFAULT_END, DEFAULT_INITIAL_CAPITAL, DEFAULT_START
from .registry import register


# Annualisation constant for the realised-vol stdev calculation.  252
# trading days per year is the framework default.
_TRADING_DAYS_PER_YEAR = 252

# Tickers in their canonical order.  Exposed so tests can iterate.
VIX_TICKERS: Tuple[str, ...] = ("SPY", "VXX", "SVXY", "^VIX")


def _align_common(
    frames: Dict[str, pd.DataFrame],
) -> Dict[str, pd.DataFrame]:
    """Reduce a dict of ticker dataframes to the dates all of them share."""
    if not frames:
        return frames
    common_index: pd.DatetimeIndex | None = None
    for df in frames.values():
        idx = df.index
        common_index = idx if common_index is None else common_index.intersection(idx)
    if common_index is None or len(common_index) == 0:
        return {k: df.iloc[0:0].copy() for k, df in frames.items()}
    return {k: df.loc[common_index].copy() for k, df in frames.items()}


def _compute_regime(
    spy_close: pd.Series,
    vix_close: pd.Series,
) -> pd.DataFrame:
    """Build the per-bar regime table used by the position logic.

    Returns a DataFrame with columns ``rv10``, ``vix_sma90`` and
    ``contango`` plus the aligned ``vix`` series.  All columns are
    indexed on the union of ``spy_close`` and ``vix_close`` dates (rows
    with no VIX observation are dropped here so downstream loops only
    see bars with a known VIX).
    """
    # Restrict to dates where we have both SPY and VIX closes.
    common = spy_close.index.intersection(vix_close.index)
    spy = spy_close.loc[common].astype(float)
    vix = vix_close.loc[common].astype(float)

    log_ret = np.log(spy / spy.shift(1))
    # Annualised rolling stdev of log returns (in %, same scale as VIX).
    rv10 = log_ret.rolling(window=10, min_periods=10).std(ddof=0) * math.sqrt(
        _TRADING_DAYS_PER_YEAR
    ) * 100.0

    # 90-day SMA of VIX acts as the back-month proxy.
    vix_sma90 = vix.rolling(window=90, min_periods=90).mean()

    contango = vix < vix_sma90  # front < back => contango

    out = pd.DataFrame(
        {
            "vix": vix,
            "rv10": rv10,
            "vix_sma90": vix_sma90,
            "contango": contango.fillna(False),
        }
    )
    return out


def _empty_result(
    name: str,
    note: str,
    ohlcv: OHLCV | None,
    execution: str = "next_open",
    load_failures: List[str] | None = None,
) -> BacktestResult:
    """Return an empty :class:`BacktestResult` with a diagnostic note."""
    cfg: Dict[str, object] = {"note": note, "warning": True}
    if load_failures is not None:
        cfg["load_failures"] = load_failures
    return BacktestResult(
        name=name,
        trades=[],
        equity=[],
        ohlcv=ohlcv,
        initial_capital=DEFAULT_INITIAL_CAPITAL,
        execution=execution,
        cost_model_name=FLAT_40.name,
        config=cfg,
    )


@register("vix_etn")
def vix_etn(
    start: str = DEFAULT_START,
    end: str = DEFAULT_END,
    execution: str = "next_open",
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    cost_model: CostModel = FLAT_40,
) -> BacktestResult:
    """Run the VIX ETN volatility regime strategy.

    Parameters
    ----------
    start, end : str
        ISO-format date bounds for the data download.
    execution : str
        Kept for parity with the other strategies.  ``vix_etn`` runs its
        own bar-by-bar loop so the value is informational only (it is
        stored on the result and in ``config``).
    initial_capital : float
        Starting equity (default 100,000).
    cost_model : CostModel
        Commission/slippage schedule applied to both the entry and
        exit legs.  Defaults to :data:`FLAT_40` (``vix_etn_40``) so the
        ``--cost-model`` flag on the runner actually takes effect for
        this strategy.  Costs are computed via ``cost_model.cost`` on
        each leg so that swapping in another model changes both legs
        consistently.

    Returns
    -------
    BacktestResult
        Standard result object.  If VXX/SVXY/VIX data cannot be
        obtained, ``result.trades`` and ``result.equity`` are empty and
        ``result.config['note']`` describes the issue.
    """
    # --- 1. Download data, gracefully handling missing tickers ---------
    raw: Dict[str, pd.DataFrame] = {}
    load_failures: List[str] = []
    for tkr in VIX_TICKERS:
        try:
            raw[tkr] = load_daily(tkr, start, end).df
        except Exception as exc:  # noqa: BLE001 - we want to be tolerant
            load_failures.append(f"{tkr}: {exc}")
            warnings.warn(
                f"vix_etn: could not load {tkr}: {exc}", stacklevel=2
            )

    if "VXX" not in raw or "SVXY" not in raw:
        note = (
            "Missing VXX/SVXY data; vix_etn returned no trades. "
            f"Failures: {', '.join(load_failures) or 'none'}"
        )
        # Still attach whatever we did manage to download so callers can
        # inspect the partial dataset.
        ohlcv_for_result = None
        for tkr in ("SVXY", "VXX", "SPY", "^VIX"):
            if tkr in raw:
                ohlcv_for_result = OHLCV(ticker=tkr, df=raw[tkr])
                break
        return _empty_result(
            "vix_etn", note, ohlcv_for_result, execution, load_failures=load_failures
        )

    # --- 2. Align all four tickers to common dates ----------------------
    aligned = _align_common(raw)
    common_index = aligned["VXX"].index
    if len(common_index) == 0:
        note = "VXX/SVXY/VIX have no overlapping dates with SPY"
        return _empty_result("vix_etn", note, OHLCV(ticker="VXX", df=aligned["VXX"]), execution)

    spy_close = aligned["SPY"]["Close"]
    vix_close = aligned["^VIX"]["Close"]
    vxx_close = aligned["VXX"]["Close"]
    svxy_close = aligned["SVXY"]["Close"]

    # Drop any bars whose VIX is NaN; we can't decide a regime without it.
    regime = _compute_regime(spy_close, vix_close).dropna(subset=["vix"])
    # Only consider bars where the regime indicators are valid.
    regime = regime.dropna(subset=["rv10", "vix_sma90"])
    if len(regime) == 0:
        note = "No bars have both rv10 and vix_sma90 defined; vix_etn empty"
        return _empty_result(
            "vix_etn",
            note,
            OHLCV(ticker="VXX", df=aligned["VXX"]),
            execution,
        )

    # Use the intersection of regime dates with the price frame so the
    # price lookups stay in lock-step with the regime signals.
    usable = regime.index.intersection(common_index)
    regime = regime.loc[usable]
    spy_close = spy_close.loc[usable]
    vix_close = vix_close.loc[usable]
    vxx_close = vxx_close.loc[usable]
    svxy_close = svxy_close.loc[usable]

    # --- 3. Bar-by-bar regime-switching event loop ---------------------
    # Position state: 0 = flat, +1 = long SVXY, -1 = long VXX.
    capital = float(initial_capital)
    position = 0
    pos_size = 0
    entry_price = 0.0
    entry_date: pd.Timestamp | None = None
    entry_size_fraction = 0.0  # used to track the entry allocation
    trades: List[Trade] = []
    equity: List[float] = []

    dates = regime.index
    n = len(dates)
    for i in range(n):
        date = dates[i]
        svxy_px = float(svxy_close.iloc[i]) if pd.notna(svxy_close.iloc[i]) else 0.0
        vxx_px = float(vxx_close.iloc[i]) if pd.notna(vxx_close.iloc[i]) else 0.0
        vix_val = float(regime["vix"].iloc[i])
        contango = bool(regime["contango"].iloc[i])
        rv10 = float(regime["rv10"].iloc[i])

        # 3a. Mark-to-market equity.
        if position == 1 and pos_size > 0:
            eq = capital + pos_size * svxy_px
        elif position == -1 and pos_size > 0:
            eq = capital + pos_size * vxx_px
        else:
            eq = capital
        equity.append(eq)

        # 3b. Regime-flip exits (only while in a position).
        if position != 0:
            flip = (position == 1 and not contango) or (position == -1 and contango)
            if flip:
                if position == 1:
                    exit_price = svxy_px
                else:
                    exit_price = vxx_px
                proceeds = pos_size * exit_price
                # Costs come from the registered cost model; entry cost
                # was already deducted on entry, so we only deduct the
                # exit half here (passed as (shares, 0.0, exit_price)).
                exit_cost = cost_model.cost(pos_size, 0.0, exit_price)
                capital += proceeds - exit_cost
                pnl = proceeds - exit_cost - pos_size * entry_price
                trades.append(
                    Trade(
                        entry_date=entry_date,
                        exit_date=date,
                        entry_price=entry_price,
                        exit_price=exit_price,
                        shares=pos_size,
                        pnl=pnl,
                        return_pct=(exit_price / entry_price - 1.0)
                        if entry_price > 0
                        else 0.0,
                        hold_days=(date - entry_date).days if entry_date is not None else 0,
                        exit_reason="regime_flip",
                        entry_cost=0.0,
                        exit_cost=exit_cost,
                    )
                )
                position = 0
                pos_size = 0
                entry_date = None

        # 3c. Entries (only when flat).
        if position == 0:
            if contango and vix_val > rv10:
                # Short vol: long SVXY, capped at 30% of equity.
                alloc_pct = min(max(vix_val / 100.0, 0.0), 0.30)
                if svxy_px > 0:
                    shares = int((capital * alloc_pct) // svxy_px)
                    if shares > 0:
                        # Charge entry cost on the buy leg only;
                        # exit leg will be charged on the way out.
                        entry_cost = cost_model.cost(shares, svxy_px, 0.0)
                        entry_price = svxy_px
                        capital -= shares * svxy_px + entry_cost
                        position = 1
                        pos_size = shares
                        entry_date = date
                        entry_size_fraction = alloc_pct
            elif not contango:
                # Long vol: long VXX, capped at 20% of equity.
                alloc_pct = min(max(vix_val / 100.0 * 0.5, 0.0), 0.20)
                if vxx_px > 0:
                    shares = int((capital * alloc_pct) // vxx_px)
                    if shares > 0:
                        entry_cost = cost_model.cost(shares, vxx_px, 0.0)
                        entry_price = vxx_px
                        capital -= shares * vxx_px + entry_cost
                        position = -1
                        pos_size = shares
                        entry_date = date
                        entry_size_fraction = alloc_pct

    # 3d. Force-close any open position at the last bar.
    if position != 0 and n > 0:
        if position == 1:
            exit_price = float(svxy_close.iloc[-1])
        else:
            exit_price = float(vxx_close.iloc[-1])
        proceeds = pos_size * exit_price
        exit_cost = cost_model.cost(pos_size, 0.0, exit_price)
        capital += proceeds - exit_cost
        pnl = proceeds - exit_cost - pos_size * entry_price
        trades.append(
            Trade(
                entry_date=entry_date,
                exit_date=dates[-1],
                entry_price=entry_price,
                exit_price=exit_price,
                shares=pos_size,
                pnl=pnl,
                return_pct=(exit_price / entry_price - 1.0)
                if entry_price > 0
                else 0.0,
                hold_days=(dates[-1] - entry_date).days if entry_date is not None else 0,
                exit_reason="end_of_data",
                entry_cost=0.0,
                exit_cost=exit_cost,
            )
        )
        position = 0

    # Final mark on the last bar.
    if n > 0 and equity:
        equity[-1] = capital

    # Build a representative OHLCV so downstream metrics have an index.
    ohlcv_for_result = OHLCV(ticker="VXX", df=aligned["VXX"].loc[usable])

    result = BacktestResult(
        name="vix_etn",
        trades=trades,
        equity=equity,
        ohlcv=ohlcv_for_result,
        initial_capital=initial_capital,
        execution=execution,
        cost_model_name=cost_model.name,
        config={
            "start": start,
            "end": end,
            "cost_model": cost_model.name,
            "tickers": list(VIX_TICKERS),
            "allocation_caps": {"contango_svxy": 0.30, "backwardation_vxx": 0.20},
            "n_regime_bars": int(n),
            "load_failures": load_failures,
        },
    )
    return result


__all__ = ["vix_etn", "VIX_TICKERS"]
