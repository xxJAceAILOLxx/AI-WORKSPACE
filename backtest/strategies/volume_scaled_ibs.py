"""Volume-Scaled IBS mean-reversion strategy (Chunk 2b).

Implements the CORRECTED volume-scaling logic per Gap 1 of the unified
framework plan.  High volume now demands a *deeper* oversold bar because
high-volume sell-offs in broad equity ETFs are typically institutional
distribution rather than accumulation; the deeper oversold filter
excludes the marginal cases while still letting the most extreme
capitulation bottoms through.  Low volume accepts a *weaker* oversold
bar because quiet pullbacks within an uptrend are usually noise.

Entry thresholds (inverse scaling):

* ``vol_ratio >= 1.5``  ->  require ``IBS < 0.15`` (deepest oversold)
* ``vol_ratio <= 0.5``  ->  allow   ``IBS < 0.25`` (weakest oversold OK)
* otherwise             ->  require ``IBS < 0.20`` (baseline)

All entries require ``Close > 200 SMA`` (trend filter).

Exit, in priority order: 2x ATR(14) stop, ``IBS > 0.50``, 5-day max hold.
Sizing: fixed risk 10% of initial capital per trade.
"""

from __future__ import annotations

from typing import List, Tuple

import pandas as pd

from backtest import Engine, PERCENT_10BP, load_daily
from backtest.engine import BacktestResult, Trade
from backtest.indicators import ibs, sma, volume_ratio

from .registry import register


# Framework defaults aligned with the plan.
DEFAULT_START: str = "2016-01-01"
DEFAULT_END: str = "2025-12-31"
DEFAULT_HOLD: int = 5
DEFAULT_STOP_MULT: float = 2.0
DEFAULT_RISK_FRACTION: float = 0.10
DEFAULT_INITIAL_CAPITAL: float = 100_000.0


def _vol_to_threshold(vol_r: pd.Series) -> pd.Series:
    """Map a ``vol_ratio`` series to the per-bar IBS threshold.

    Inverse scaling:

    >>> import pandas as pd
    >>> s = pd.Series([0.3, 0.5, 1.0, 1.5, 2.0])
    >>> list(_vol_to_threshold(s))
    [0.25, 0.25, 0.2, 0.15, 0.15]

    ``NaN`` volume ratios fall through to the baseline ``0.20``.
    """
    threshold = pd.Series(0.20, index=vol_r.index)
    # High volume -> deepest oversold (most restrictive).
    threshold = threshold.mask(vol_r >= 1.5, 0.15)
    # Low volume -> weakest oversold (most permissive).
    threshold = threshold.mask(vol_r <= 0.5, 0.25)
    return threshold


@register("volume_scaled_ibs")
def volume_scaled_ibs(
    ticker: str = "SPY",
    start: str = DEFAULT_START,
    end: str = DEFAULT_END,
    hold: int = DEFAULT_HOLD,
    stop_mult: float = DEFAULT_STOP_MULT,
    risk_fraction: float = DEFAULT_RISK_FRACTION,
    execution: str = "next_open",
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
) -> BacktestResult:
    """Volume-scaled IBS mean-reversion on daily OHLCV.

    Parameters
    ----------
    ticker : str
        Ticker to download via :func:`backtest.load_daily` (default ``SPY``).
    start, end : str
        ISO-format date bounds for the download (defaults ``2016-01-01`` to
        ``2025-12-31`` per the unified plan).
    hold : int
        Maximum holding period in trading days before the engine forces
        an exit (default 5).
    stop_mult : float
        Stop distance as a multiple of ATR(14) from the entry price
        (default 2.0).
    risk_fraction : float
        Fraction of ``initial_capital`` risked per trade; combined with
        ``fixed_risk`` sizing this is the dollar amount at risk
        (default 0.10 -> $10,000 on $100k capital).
    execution : str
        ``"next_open"`` (default) or ``"close"``; see :class:`Engine`.
    initial_capital : float
        Starting equity (default 100,000).
    """
    ohlcv = load_daily(ticker, start, end)
    df = ohlcv.df

    ibs_s = ibs(df)
    vol_r = volume_ratio(df)
    sma200 = sma(df["Close"], 200)

    trend_ok = df["Close"] > sma200
    threshold = _vol_to_threshold(vol_r)

    entry_signal = (ibs_s < threshold) & trend_ok
    entry_signal = entry_signal.fillna(False)

    def exit_rule(state) -> Tuple[str, float] | None:
        # Look up the IBS at the current bar (state.idx is the bar index
        # passed to the exit callback by the engine).
        ibs_val = ibs_s.iloc[state.idx]
        if pd.notna(ibs_val) and ibs_val > 0.50:
            return ("ibs_exit", 0.0)
        return None

    eng = Engine(
        ohlcv,
        name="volume_scaled_ibs",
        execution=execution,
        cost_model=PERCENT_10BP,
        initial_capital=initial_capital,
        size_policy="fixed_risk",
        size_value=risk_fraction * initial_capital,
        stop_mult=stop_mult,
        max_hold=hold,
        atr_period=14,
    )
    eng.set_entry(entry_signal).set_exit(exit_rule)
    result = eng.run()
    # Stash the signal-bar vol_ratio so callers can bucket trades by
    # entry-time volume (used by tests and reporting).
    result.config["vol_ratio"] = vol_r
    return result


def trades_with_vol_ratio(
    result: BacktestResult,
) -> List[Tuple[Trade, float]]:
    """Return ``(trade, vol_ratio_at_signal)`` pairs for a ``volume_scaled_ibs`` run.

    The vol_ratio that determined the entry is the value at the SIGNAL
    bar -- one bar before the entry fill for ``next_open`` execution and
    the same bar for ``close`` execution.  ``NaN`` ratios are skipped.
    Raises :class:`ValueError` if the result was not produced by
    :func:`volume_scaled_ibs` (no ``vol_ratio`` attached).
    """
    if "vol_ratio" not in result.config:
        raise ValueError(
            "BacktestResult has no 'vol_ratio' attached; this helper is "
            "only valid for volume_scaled_ibs output."
        )
    vol_r: pd.Series = result.config["vol_ratio"]
    df_index = result.ohlcv.df.index
    pairs: List[Tuple[Trade, float]] = []
    for t in result.trades:
        if t.entry_date not in df_index:
            continue
        fill_pos = df_index.get_loc(t.entry_date)
        sig_pos = fill_pos - 1 if result.execution == "next_open" else fill_pos
        if sig_pos < 0 or sig_pos >= len(vol_r):
            continue
        vr = float(vol_r.iloc[sig_pos])
        if pd.isna(vr):
            continue
        pairs.append((t, vr))
    return pairs


__all__ = [
    "volume_scaled_ibs",
    "trades_with_vol_ratio",
    "_vol_to_threshold",
    "DEFAULT_START",
    "DEFAULT_END",
    "DEFAULT_HOLD",
    "DEFAULT_STOP_MULT",
    "DEFAULT_RISK_FRACTION",
    "DEFAULT_INITIAL_CAPITAL",
]
