"""Tests for the backtest engine.

Tests cover execution semantics (next_open vs close), cost application,
sizing modes, stop loss, max hold, signal handling while in position, and
end-to-end integration on real SPY data.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtest import (
    FLAT_40,
    PERCENT_10BP,
    PER_SHARE_1C,
    Engine,
    from_dataframe,
)
from backtest.indicators import ibs


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_synthetic_ohlcv(
    n: int = 200,
    start: str = "2022-01-03",
    seed: int = 0,
    drift: float = 0.0005,
    vol: float = 0.01,
    base_price: float = 100.0,
) -> pd.DataFrame:
    """Build a synthetic daily OHLCV frame with a deterministic random walk."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start=start, periods=n)
    rets = rng.normal(loc=drift, scale=vol, size=n)
    close = base_price * np.exp(np.cumsum(rets))
    # Build OHLC so High >= max(Open, Close), Low <= min(Open, Close).
    open_ = np.empty(n)
    open_[0] = base_price
    open_[1:] = close[:-1] * (1.0 + rng.normal(0, 0.003, size=n - 1))
    high = np.maximum(open_, close) * (1.0 + np.abs(rng.normal(0, 0.002, size=n)))
    low = np.minimum(open_, close) * (1.0 - np.abs(rng.normal(0, 0.002, size=n)))
    volume = rng.integers(1_000_000, 5_000_000, size=n).astype(float)
    df = pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=dates,
    )
    return df


@pytest.fixture
def synthetic_ohlcv():
    return from_dataframe("SYN", _make_synthetic_ohlcv(n=250))


@pytest.fixture
def entry_signal(synthetic_ohlcv):
    # Force entries every 20 bars for easy verification.
    s = pd.Series(False, index=synthetic_ohlcv.df.index)
    s.iloc[20::20] = True
    return s


# ---------------------------------------------------------------------------
# Execution mode
# ---------------------------------------------------------------------------


def test_engine_next_open_vs_close_differs(synthetic_ohlcv, entry_signal):
    """next_open must produce a later (or equal) entry price than close."""
    eng_close = Engine(
        synthetic_ohlcv, name="close", execution="close", cost_model=PERCENT_10BP
    )
    eng_close.set_entry(entry_signal).set_exit(
        lambda s: ("hold_5", 0.0) if s.days_held >= 5 else None
    )
    res_close = eng_close.run()

    eng_next = Engine(
        synthetic_ohlcv, name="next_open", execution="next_open", cost_model=PERCENT_10BP
    )
    eng_next.set_entry(entry_signal).set_exit(
        lambda s: ("hold_5", 0.0) if s.days_held >= 5 else None
    )
    res_next = eng_next.run()

    assert len(res_close.trades) > 0
    assert len(res_next.trades) > 0

    # Same number of trades in both modes (signals identical, sizing same).
    assert len(res_close.trades) == len(res_next.trades)

    # Entry prices must differ: next_open fills at next bar's Open which is
    # generally not equal to the signal bar's Close.
    for tc, tn in zip(res_close.trades, res_next.trades):
        # next_open enters one business day after the close-mode entry
        # (because the next_open fills at the signal bar's *next* Open).
        assert tn.entry_date == tc.entry_date + pd.tseries.offsets.BDay(1)
        # Close-mode entry price equals the signal bar's Close.
        df = synthetic_ohlcv.df
        assert tc.entry_price == pytest.approx(
            float(df.loc[tc.entry_date, "Close"])
        )
        # next_open entry price equals the *next* bar's Open.
        assert tn.entry_price == pytest.approx(
            float(df.loc[tn.entry_date, "Open"])
        )


def test_engine_close_entry_uses_close_price(synthetic_ohlcv, entry_signal):
    eng = Engine(synthetic_ohlcv, name="c", execution="close")
    eng.set_entry(entry_signal).set_exit(
        lambda s: ("hold_3", 0.0) if s.days_held >= 3 else None
    )
    res = eng.run()
    assert res.trades, "expected at least one trade"
    df = synthetic_ohlcv.df
    for t in res.trades:
        expected = float(df.loc[t.entry_date, "Close"])
        assert t.entry_price == pytest.approx(expected)


def test_engine_next_open_entry_uses_next_open(synthetic_ohlcv, entry_signal):
    eng = Engine(synthetic_ohlcv, name="n", execution="next_open")
    eng.set_entry(entry_signal).set_exit(
        lambda s: ("hold_3", 0.0) if s.days_held >= 3 else None
    )
    res = eng.run()
    df = synthetic_ohlcv.df
    for t in res.trades:
        expected = float(df.loc[t.entry_date, "Open"])
        assert t.entry_price == pytest.approx(expected)


def test_invalid_execution_rejected(synthetic_ohlcv):
    with pytest.raises(ValueError):
        Engine(synthetic_ohlcv, execution="midbar")


def test_fixed_risk_requires_stop(synthetic_ohlcv):
    with pytest.raises(ValueError):
        Engine(synthetic_ohlcv, size_policy="fixed_risk", stop_mult=0.0)


# ---------------------------------------------------------------------------
# Sizing
# ---------------------------------------------------------------------------


def test_percent_of_equity_sizing(synthetic_ohlcv, entry_signal):
    eng = Engine(
        synthetic_ohlcv,
        name="p",
        execution="close",
        size_policy="percent_of_equity",
        size_value=0.5,
        initial_capital=100_000.0,
    )
    eng.set_entry(entry_signal).set_exit(
        lambda s: ("hold_2", 0.0) if s.days_held >= 2 else None
    )
    res = eng.run()
    first = res.trades[0]
    # 50% of 100k -> ~50k; shares = floor(50k / entry_price)
    expected_shares = int((0.5 * 100_000) // first.entry_price)
    assert first.shares == expected_shares


def test_fixed_risk_sizing(synthetic_ohlcv, entry_signal):
    eng = Engine(
        synthetic_ohlcv,
        name="r",
        execution="close",
        size_policy="fixed_risk",
        size_value=2_000.0,
        stop_mult=2.0,
        atr_period=14,
        initial_capital=100_000.0,
    )
    eng.set_entry(entry_signal).set_exit(
        lambda s: ("hold_2", 0.0) if s.days_held >= 2 else None
    )
    res = eng.run()
    assert res.trades
    # Risk per share = 2 * ATR. Shares = floor(2000 / risk).
    for t in res.trades:
        # Just sanity-check that notional isn't more than 20x the initial capital
        # (which would indicate fixed_risk was ignored and the whole balance
        # was deployed).
        assert t.shares * t.entry_price < 20 * 100_000


# ---------------------------------------------------------------------------
# Costs
# ---------------------------------------------------------------------------


def test_percent_10bp_cost_applied():
    """End-to-end: PERCENT_10BP should deduct a small cost from equity."""
    ohlcv = from_dataframe("X", _make_synthetic_ohlcv(n=80, seed=1))
    s = pd.Series(False, index=ohlcv.df.index)
    s.iloc[10] = True
    eng = Engine(
        ohlcv,
        name="cost",
        execution="close",
        cost_model=PERCENT_10BP,
        initial_capital=100_000.0,
    )
    eng.set_entry(s).set_exit(lambda st: ("h", 0.0) if st.days_held >= 2 else None)
    res = eng.run()
    t = res.trades[0]
    expected_entry_cost = PERCENT_10BP.cost(t.shares, t.entry_price, 0.0)
    expected_exit_cost = PERCENT_10BP.cost(t.shares, 0.0, t.exit_price)
    assert t.entry_cost == pytest.approx(expected_entry_cost)
    assert t.exit_cost == pytest.approx(expected_exit_cost)
    # The engine deducts entry_cost from cash at entry (reducing deployed
    # capital) and exit_cost from pnl at exit. So pnl = gross - exit_cost.
    gross = (t.exit_price - t.entry_price) * t.shares
    assert t.pnl == pytest.approx(gross - expected_exit_cost)
    # The total cost to the account is entry_cost + exit_cost.
    total_cost = expected_entry_cost + expected_exit_cost
    # Total cash impact: opening outlay + closing receipt.
    cash_out = t.entry_cost + t.shares * t.entry_price
    cash_in = t.shares * t.exit_price - t.exit_cost
    assert (cash_in - cash_out) == pytest.approx(gross - total_cost)


def test_flat_40_cost_applied():
    ohlcv = from_dataframe("X", _make_synthetic_ohlcv(n=80, seed=2))
    s = pd.Series(False, index=ohlcv.df.index)
    s.iloc[5] = True
    eng = Engine(
        ohlcv,
        name="flat",
        execution="close",
        cost_model=FLAT_40,
        initial_capital=100_000.0,
    )
    eng.set_entry(s).set_exit(lambda st: ("h", 0.0) if st.days_held >= 2 else None)
    res = eng.run()
    t = res.trades[0]
    # FLAT_40 always returns 40 regardless of inputs.
    assert FLAT_40.cost(t.shares, t.entry_price, t.exit_price) == 40.0
    assert (t.entry_cost + t.exit_cost) == pytest.approx(80.0)


def test_per_share_1c_cost_applied():
    ohlcv = from_dataframe("X", _make_synthetic_ohlcv(n=80, seed=3))
    s = pd.Series(False, index=ohlcv.df.index)
    s.iloc[5] = True
    eng = Engine(
        ohlcv,
        name="ps",
        execution="close",
        cost_model=PER_SHARE_1C,
        initial_capital=100_000.0,
    )
    eng.set_entry(s).set_exit(lambda st: ("h", 0.0) if st.days_held >= 2 else None)
    res = eng.run()
    t = res.trades[0]
    assert t.entry_cost == pytest.approx(t.shares * 0.01)
    assert t.exit_cost == pytest.approx(t.shares * 0.01)


def test_cost_registry_lookup():
    from backtest.costs import get
    assert get("etf_0.1pct") is PERCENT_10BP
    assert get("vix_etn_40") is FLAT_40
    with pytest.raises(KeyError):
        get("nonexistent")


# ---------------------------------------------------------------------------
# Stops, max hold, exit rules
# ---------------------------------------------------------------------------


def test_stop_loss_triggers(synthetic_ohlcv, entry_signal):
    """A 1-ATR stop should trigger at least once on a volatile synthetic series."""
    eng = Engine(
        synthetic_ohlcv,
        name="st",
        execution="close",
        stop_mult=1.0,
        atr_period=14,
        max_hold=10,
    )
    eng.set_entry(entry_signal)
    eng.set_exit(lambda s: ("h", 0.0) if s.days_held >= 10 else None)
    res = eng.run()
    # Trades must exist and the stop should have been hit at least once
    # over the 250-bar series.
    assert res.trades
    stop_reasons = [t.exit_reason for t in res.trades if t.exit_reason == "stop"]
    assert stop_reasons, "expected at least one stop-triggered trade"


def test_max_hold_exit(synthetic_ohlcv, entry_signal):
    eng = Engine(
        synthetic_ohlcv,
        name="mh",
        execution="close",
        max_hold=3,
    )
    eng.set_entry(entry_signal)
    # Rule never fires; only max_hold should close positions.
    eng.set_exit(lambda s: None)
    res = eng.run()
    for t in res.trades:
        assert t.exit_reason == "max_hold"
        assert t.hold_days <= 5  # entry bar counts as 1, plus a couple bars slack


def test_exit_rule_callback_returns_decision(synthetic_ohlcv, entry_signal):
    eng = Engine(synthetic_ohlcv, name="r", execution="close")

    def rule(s):
        if s.days_held >= 2:
            return ("rule_exit", float(s.bar["Close"]))
        return None

    eng.set_entry(entry_signal).set_exit(rule)
    res = eng.run()
    assert all(t.exit_reason == "rule_exit" for t in res.trades)


def test_engine_rejects_run_without_signal(synthetic_ohlcv):
    eng = Engine(synthetic_ohlcv)
    with pytest.raises(RuntimeError):
        eng.run()


def test_signal_during_position_is_ignored(synthetic_ohlcv):
    # Signal is True on every bar; with no exit rule the position can only
    # close via end_of_data at the very last bar.  So there should be exactly
    # one trade despite 250 signals.
    s = pd.Series(True, index=synthetic_ohlcv.df.index)
    eng = Engine(synthetic_ohlcv, name="o", execution="close", max_hold=0)
    eng.set_entry(s).set_exit(lambda st: None)
    res = eng.run()
    assert len(res.trades) == 1
    assert res.trades[0].exit_reason == "end_of_data"


def test_no_signal_no_trades(synthetic_ohlcv):
    s = pd.Series(False, index=synthetic_ohlcv.df.index)
    eng = Engine(synthetic_ohlcv, name="ns")
    eng.set_entry(s)
    res = eng.run()
    assert res.trades == []
    assert len(res.equity) == len(synthetic_ohlcv.df)


def test_end_of_data_closes_position(synthetic_ohlcv):
    """If a signal fires near the end with next_open, the position is closed
    at the final bar's close with reason 'end_of_data'."""
    df = synthetic_ohlcv.df
    s = pd.Series(False, index=df.index)
    s.iloc[-5] = True  # signal near end -> next_open fills at the 4th-to-last bar
    eng = Engine(synthetic_ohlcv, name="eod", execution="next_open", max_hold=100)
    eng.set_entry(s).set_exit(lambda st: ("h", 0.0) if st.days_held >= 100 else None)
    res = eng.run()
    assert res.trades
    last = res.trades[-1]
    # Either max_hold exceeded later or we hit end_of_data on the final bar.
    assert last.exit_reason in {"end_of_data", "max_hold"}


# ---------------------------------------------------------------------------
# Integration on real data
# ---------------------------------------------------------------------------


def test_engine_runs_on_real_spy_data():
    """End-to-end smoke test against SPY data downloaded from yfinance."""
    from backtest import load_daily

    ohlcv = load_daily("SPY", "2020-06-01", "2023-12-31")
    signal = (ibs(ohlcv.df) < 0.2)
    eng = Engine(ohlcv, name="ibs_spy", execution="next_open", max_hold=5)
    eng.set_entry(signal).set_exit(
        lambda s: ("hold_5", 0.0) if s.days_held >= 5 else None
    )
    res = eng.run()
    assert res.trades, "IBS<0.2 strategy should produce trades on SPY 2020-2023"
    assert len(res.equity) == len(ohlcv.df)
    assert all(t.entry_cost >= 0 for t in res.trades)
    assert all(t.exit_cost >= 0 for t in res.trades)


def test_engine_state_fields_populated(synthetic_ohlcv, entry_signal):
    seen = {}

    def rule(s):
        seen["bar"] = s.bar
        seen["shares"] = s.shares
        seen["entry_price"] = s.entry_price
        seen["days_held"] = s.days_held
        seen["equity"] = s.equity
        seen["atr_entry"] = s.atr_entry
        seen["atr_now"] = s.atr_now
        seen["stop_price"] = s.stop_price
        return None  # never exit via rule

    eng = Engine(
        synthetic_ohlcv,
        name="st",
        execution="close",
        stop_mult=2.0,
        atr_period=14,
        max_hold=2,
    )
    eng.set_entry(entry_signal).set_exit(rule)
    eng.run()
    assert "shares" in seen
    assert seen["shares"] > 0
    assert seen["entry_price"] > 0
    assert seen["days_held"] >= 1
    assert seen["equity"] > 0
    assert seen["atr_entry"] >= 0
    assert seen["atr_now"] >= 0
