# Unified Backtest Framework + Agent Orchestration Plan

## Goal
Replace the scattered, copy-pasted backtest scripts in `Strategies/` with a single reusable backtesting library, fix the documented strategy/logic gaps, add a runnable agent orchestration layer, and clean up obsolete files.

## Decision Log

### Gap 1 — Volume-Scaled IBS threshold direction
**Documented issue:** `Strategies/Volume-Scaled IBS.md` and `Strategies/volume_scaled_ibs.py` state that high volume "confirms conviction" and relaxes the IBS threshold to 0.25, while low volume tightens it to 0.15. However, the same script's volume analysis shows the high-volume bucket is a net loser (33% WR). The `memory.md` TODO explicitly says "Invert volume scaling (demand deeper oversold on high volume)".

**Decision:** Invert the scaling in the framework implementation.
- `vol_ratio >= 1.5` → require `IBS < 0.15` (deeper oversold; institutions are distributing on high volume, not accumulating).
- `vol_ratio <= 0.5` → allow `IBS < 0.25` (weaker threshold is acceptable on quiet volume).
- otherwise → `IBS < 0.20`.

**Consequence:** `Strategies/Volume-Scaled IBS.md` must be updated to match the corrected logic. The acceptance test must assert that the high-volume bucket has a lower win rate than the low-volume bucket.

### Gap 2 — Same-bar vs next-open execution
**Documented issue:** `Strategies/intraday_test.py` demonstrates that same-bar execution on interpolated forex data produced Sharpe 3.80, while next-open execution produced Sharpe −7.81.

**Decision:** The framework defaults to **next-open execution** for every strategy. Close execution must be requested explicitly via `execution="close"`.

### Gap 3 — Inconsistent cost models
**Documented issue:** Scripts use 0.1% round-trip, $40 flat, $0.01/share, and 0.02% inconsistently.

**Decision:** Centralize cost models in `backtest/costs.py`. Strategies reference a named cost model; the default is ETF 0.1% round-trip.

### Gap 4 — Agent prompts exist but no runnable orchestration
**Documented issue:** `agents.md` contains prompt templates only; there is no code that can run the workflow.

**Decision:** Build a lightweight `orchestrator/` package that stores agent definitions, keeps shared memory, and exposes a CLI that prints/executes each workflow stage. This version does **not** call external LLM APIs; it populates prompts, invokes the local backtest runner where applicable, and records results to `memory.md`.

---

## Success Criteria
1. A `backtest/` Python package exists with a clean API that can reproduce every strategy currently in `all_strategies_backtest.py`.
2. Every strategy uses **next-open (honest) execution** by default; close-only execution must be explicit.
3. Volume-Scaled IBS logic is corrected as documented in Gap 1, and `Strategies/Volume-Scaled IBS.md` is updated.
4. A unified cost model registry exists (ETF 0.1%, futures $40, per-share, etc.) and all strategies pull costs from it.
5. An `orchestrator/` Python package exists that exposes the 12 agents from `agents.md` and can run the documented workflow stages end-to-end from a CLI.
6. Legacy scripts are moved to `archive/Strategies/` and the root `Strategies/` directory contains only framework-aware strategy specs/runners.
7. All new code has tests; `pytest` passes with no errors.
8. `agents.md` and `memory.md` are updated to reference the new framework paths.

## Constraints
- Only use libraries already in use: `pandas`, `numpy`, `yfinance`.
- Do not change the mathematical intent of existing strategies unless fixing a documented gap.
- Keep the Obsidian vault structure intact; only reorganize Python scripts and add documentation.
- No live trading or broker integrations.
- No external LLM API calls in the orchestrator.

## Assumptions
- `yfinance` is installed and can download daily data for the tickers used.
- The host runs Python 3.10+.
- Tests can download a small amount of data from Yahoo Finance during test runs (cached).

---

## Chunk 1: Core Backtest Framework

**Complexity:** complex (event-loop correctness, execution semantics, drawdown calculations)

**Files:**
- `backtest/__init__.py`
- `backtest/data.py`
- `backtest/indicators.py`
- `backtest/costs.py`
- `backtest/engine.py`
- `backtest/metrics.py`
- `backtest/validation.py`
- `backtest/reporting.py`
- `backtest/py.typed` (empty marker)
- `tests/test_engine.py`
- `tests/test_metrics.py`
- `tests/test_validation.py`

**Interfaces:**
```python
# backtest/data.py
from dataclasses import dataclass
import pandas as pd

@dataclass(frozen=True)
class OHLCV:
    ticker: str
    df: pd.DataFrame  # columns: Open, High, Low, Close, Volume

    def align_to(self, other: "OHLCV") -> pd.DataFrame: ...

def load_daily(ticker: str, start: str, end: str,
               cache_dir: str = "data/cache") -> OHLCV: ...

# backtest/indicators.py
def ibs(df: pd.DataFrame) -> pd.Series: ...
def rsi(series: pd.Series, period: int = 2) -> pd.Series: ...
def sma(series: pd.Series, period: int) -> pd.Series: ...
def atr(df: pd.DataFrame, period: int = 14) -> pd.Series: ...
def pct_b(df: pd.DataFrame, period: int = 20) -> pd.Series: ...
def down_streak(series: pd.Series) -> pd.Series: ...
def volume_ratio(df: pd.DataFrame, period: int = 20) -> pd.Series: ...
def turn_of_month(index: pd.DatetimeIndex, enter_last_n: int = 1,
                  hold_n: int = 3) -> pd.Series: ...

# backtest/costs.py
from dataclasses import dataclass, field
from typing import Callable

CostFn = Callable[[int, float, float], float]

@dataclass(frozen=True)
class CostModel:
    name: str
    cost_fn: CostFn = field(repr=False)

    def cost(self, shares: int, entry_price: float, exit_price: float) -> float:
        return max(0.0, self.cost_fn(shares, entry_price, exit_price))

PERCENT_10BP = CostModel(
    "etf_0.1pct",
    lambda s, e, x: s * (e + x) * 0.001 / 2
)
FLAT_40 = CostModel(
    "vix_etn_40",
    lambda s, e, x: 40.0
)
PER_SHARE_1C = CostModel(
    "per_share_0.01",
    lambda s, e, x: s * 0.01
)

def get(name: str) -> CostModel: ...

# backtest/engine.py
from dataclasses import dataclass
from typing import Callable, List, Optional
import pandas as pd

@dataclass
class Trade:
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    entry_price: float
    exit_price: float
    shares: int
    pnl: float
    return_pct: float
    hold_days: int
    exit_reason: str

@dataclass
class BacktestResult:
    name: str
    trades: List[Trade]
    equity: List[float]
    ohlcv: OHLCV

class Engine:
    def __init__(self, ohlcv: OHLCV, name: str = "strategy",
                 execution: str = "next_open",  # or "close"
                 cost_model: CostModel = PERCENT_10BP,
                 initial_capital: float = 100_000,
                 size_policy: str = "percent_of_equity",
                 size_value: float = 0.95,
                 stop_mult: float = 0.0): ...

    def set_entry(self, signal: pd.Series) -> "Engine": ...
    def set_exit(self, rule: Callable[["EngineState"], Optional[tuple[str, float]]]) -> "Engine": ...
    def run(self) -> BacktestResult: ...
```

**Engine semantics:**
- Entry signal computed at bar `t` (Close). Order fills at next bar's Open by default.
- Exits are evaluated bar by bar in this order: stop, target/rule, max hold.
- Stop price = `entry_price - stop_mult * ATR` for longs.
- Position sizing uses `size_policy`:
  - `percent_of_equity`: allocate `size_value * equity` to shares.
  - `fixed_risk`: risk `size_value` dollars per trade (shares = risk / (entry_price - stop_price)).
- If an entry signal fires while already in position, ignore it.
- Costs are subtracted from capital on both entry and exit.

**Acceptance criteria:**
- `pytest tests/test_engine.py` passes.
- A simple IBS strategy run through the engine produces non-zero trades on SPY 2020-2023.
- Switching `execution="close"` produces different (earlier/same-bar) entry prices.

---

## Chunk 2a: Mean-Reversion Strategy Library (simple)

**Complexity:** simple

**Files:**
- `backtest/strategies/__init__.py`
- `backtest/strategies/registry.py`
- `backtest/strategies/ibs.py`
- `backtest/strategies/turn_of_month.py`
- `backtest/strategies/rsi2.py`
- `backtest/strategies/pct_b.py`
- `backtest/strategies/multiple_days_down.py`
- `tests/test_strategies_mr.py`

**Registry interface:**
```python
# backtest/strategies/registry.py
from typing import Dict, Callable
from backtest.engine import BacktestResult

StrategyFn = Callable[..., BacktestResult]

REGISTRY: Dict[str, StrategyFn] = {}

def register(name: str):
    def decorator(fn: StrategyFn) -> StrategyFn:
        REGISTRY[name] = fn
        return fn
    return decorator

def run(name: str, **kwargs) -> BacktestResult: ...

def list_strategies() -> list[str]: ...
```

**Strategies to port (source: `Strategies/all_strategies_backtest.py`):**

| Name | Ticker | Entry | Exit | Sizing | Cost |
|---|---|---|---|---|---|
| `ibs_spy` | SPY | IBS < 0.20 | hold 5 days | 95% of equity | ETF 0.1% |
| `ibs_trend` | SPY | IBS < 0.20 + Close > 200 SMA + TOM | hold 5 days | 95% of equity | ETF 0.1% |
| `qqq_mr` | QQQ | IBS < 0.20 + Close > 200 SMA | hold 5 days | 95% of equity | ETF 0.1% |
| `rsi2_mr` | SPY | RSI(2) < 10 + Close > 200 SMA | hold 5 days | 95% of equity | ETF 0.1% |
| `pct_b_mr` | SPY | %B < 0.10 + Close > 200 SMA | hold 5 days | 95% of equity | ETF 0.1% |
| `multiple_days_down` | SPY | down streak <= -5 + Close > 200 SMA | hold 5 days | 95% of equity | ETF 0.1% |
| `turn_of_month` | SPY | last trading day of month | hold 4 days (month-end + 3) | 95% of equity | ETF 0.1% |

**Acceptance criteria:**
- `pytest tests/test_strategies_mr.py` passes.
- Each strategy returns at least one trade on its default date range.
- `registry.run("ibs_spy")` works without importing the module directly.

---

## Chunk 2b: Volume-Scaled IBS (simple, but includes gap fix)

**Complexity:** simple

**Files:**
- `backtest/strategies/volume_scaled_ibs.py`
- `tests/test_volume_scaled_ibs.py`

**Logic (corrected per Gap 1):**
- Compute `IBS`, `VolRatio` (volume / 20-day average), `SMA200`, `ATR14`.
- Entry threshold scales inversely with volume:
  - `vol_ratio >= 1.5` → require `IBS < 0.15`
  - `vol_ratio <= 0.5` → allow `IBS < 0.25`
  - otherwise → `IBS < 0.20`
- Trend filter: `Close > SMA200`.
- Exit: `IBS > 0.50`, max hold 5 days, or 2x ATR stop.
- Sizing: fixed risk 10% of initial capital per trade (shares = risk / (entry - stop)).
- Tickers: SPY, QQQ, IWM.

**Acceptance criteria:**
- `pytest tests/test_volume_scaled_ibs.py` passes.
- High-volume bucket (`vol_ratio >= 1.5`) has a lower win rate than the low-volume bucket (`vol_ratio <= 0.5`), confirming the inverted logic.
- Default run on SPY returns trades and PF > 1.0.

---

## Chunk 2c: Trend, Volatility, and Portfolio Strategies (medium)

**Complexity:** medium

**Files:**
- `backtest/strategies/dual_ma.py`
- `backtest/strategies/vix_etn.py`
- `backtest/strategies/portfolio.py`
- `tests/test_strategies_advanced.py`

**Strategies:**

| Name | Ticker | Entry | Exit | Sizing | Cost | Source |
|---|---|---|---|---|---|---|
| `qqq_dual_ma` | QQQ | Close > 50 SMA and Close > 200 SMA | Close < 50 SMA | 95% of equity | ETF 0.1% | `all_strategies_backtest.py` Strategy 9 |
| `vix_etn` | SVXY/VXX | contango + eVRP → long SVXY; backwardation → long VXX | regime flip | VIX/100 capped at 30%/20% | FLAT_40 | `all_strategies_backtest.py` Strategy 10 |
| `mr_portfolio` | SPY | equal-weight combination of `ibs_spy`, `rsi2_mr`, `pct_b_mr`, `turn_of_month` | per-sub-strategy | equal capital split | ETF 0.1% | `all_strategies_backtest.py` Strategy 15 |

**VIX ETN details:**
- Align SPY, VXX, SVXY, VIX daily close dates.
- Realized vol: 10-day rolling stdev of log SPY returns, annualized.
- eVRP: `VIX_close > realized_vol_10`.
- Term structure proxy: 90-day SMA of VIX. Contango = `VIX_close < VIX_sma90`.
- If contango + eVRP: long SVXY (short vol). Allocation = `min(VIX_close / 100, 0.30)` of capital.
- If backwardation: long VXX (long vol). Allocation = `min(VIX_close / 100 * 0.5, 0.20)` of capital.
- Exit when contango/backwardation condition flips.

**Portfolio details:**
- Divide initial capital by 4.
- Run each MR sub-strategy on its own capital slice using the framework engine.
- Combine the four equity curves by averaging daily equity values.
- Trades are the union of all sub-strategy trades with `sub_strategy` tag.

**Acceptance criteria:**
- `pytest tests/test_strategies_advanced.py` passes.
- `qqq_dual_ma` produces trades when QQQ trends.
- `vix_etn` runs even if VXX data is missing (returns empty result with a warning).
- `mr_portfolio` returns trades from at least two sub-strategies.

---

## Chunk 3: Runner, Validation, and Replication CLI

**Complexity:** medium

**Files:**
- `Strategies/run_strategy.py`
- `Strategies/run_all.py`
- `tests/test_runner.py`

**Behavior:**
- `python Strategies/run_strategy.py --strategy ibs_spy --start 2016-01-01 --end 2025-12-31` prints a metrics table.
- `python Strategies/run_all.py` runs every registered strategy and prints the ranking table from the original `all_strategies_backtest.py`.
- Both support `--execution close|next_open` and `--cost-model NAME`.
- Walk-forward and Monte Carlo are available via flags `--walk-forward` and `--monte-carlo`.

**Acceptance criteria:**
- `python Strategies/run_all.py` completes without errors and produces a ranking table.
- `pytest tests/test_runner.py` passes.
- Reproducing the original `all_strategies_backtest.py` with next-open execution produces a similar rank order (PF rank correlation ≥ 0.5, acknowledging sizing/cost changes).

---

## Chunk 4: Agent Orchestration Layer

**Complexity:** simple (boilerplate + prompts; no external LLM calls)

**Files:**
- `orchestrator/__init__.py`
- `orchestrator/agents.py`
- `orchestrator/memory.py`
- `orchestrator/workflow.py`
- `orchestrator/cli.py`
- `tests/test_orchestrator.py`

**Agent model:**
```python
# orchestrator/agents.py
from dataclasses import dataclass

@dataclass(frozen=True)
class Agent:
    name: str
    purpose: str
    responsibilities: tuple[str, ...]
    prompt_template: str
    references: tuple[str, ...]
    stage: str  # research|design|backtest|validate|deploy|monitor|learn

AGENTS: dict[str, Agent] = { ... }  # all 12 agents

def get_agent(name: str) -> Agent: ...
def by_stage(stage: str) -> list[Agent]: ...
```

**Memory model:**
```python
# orchestrator/memory.py
class Memory:
    def __init__(self, path: str = "memory.md"): ...
    def load(self) -> dict: ...
    def save(self, data: dict) -> None: ...
    def append_run(self, run: dict) -> None: ...
```

**Workflow model:**
```python
# orchestrator/workflow.py
STAGES = ["research", "design", "backtest", "validate", "deploy", "monitor", "learn"]

class Workflow:
    def __init__(self, stages: list[str] | None = None,
                 backtest_fn: Callable | None = None): ...

    def run(self, context: dict) -> dict: ...
```

**Stage actions (no LLM API calls):**
- `research`: print the Web Researcher prompt populated with the idea.
- `design`: print the Strategy Architect prompt; parse any `strategy_name`/`params` from context if provided.
- `backtest`: if `strategy_name` is in the registry, call `registry.run(strategy_name, **params)` and attach the metrics.
- `validate`: print the Risk Manager prompt and run a max-drawdown / daily-loss check on the backtest equity.
- `deploy`: print the Prop Firm Challenger prompt with the backtest metrics.
- `monitor`: print the Mistake Tracker prompt.
- `learn`: update `memory.md` with the run result via `Memory.append_run`.

**CLI behavior:**
- `python -m orchestrator.cli --list` lists all 12 agents.
- `python -m orchestrator.cli --agent backtest_engine --strategy ibs_spy` prints the populated agent prompt and, because the stage is `backtest`, actually runs the strategy and prints metrics.
- `python -m orchestrator.cli --workflow full --idea "IBS mean reversion on QQQ"` runs all seven stages, invoking the backtest runner if a valid strategy name appears in the idea or context.

**Acceptance criteria:**
- `pytest tests/test_orchestrator.py` passes.
- `python -m orchestrator.cli --list` lists all 12 agents.
- `python -m orchestrator.cli --workflow full --idea "test ibs_spy"` runs all stages without errors and updates `memory.md`.

---

## Chunk 5: Cleanup, Docs, and Migration

**Complexity:** simple

**Files:**
- `archive/Strategies/*` (moved legacy scripts)
- `README.md`
- `Strategies/README.md`
- Updated `Strategies/Volume-Scaled IBS.md`
- Updated `agents.md`
- Updated `memory.md`
- Deleted: `test.md`, `Untitled.canvas`

**Cleanup actions:**
1. Create `archive/Strategies/`.
2. Move these legacy scripts to `archive/Strategies/`:
   - `brute_force.py`, `brute_force2.py`, `brute_force3.py`
   - `combine_test.py`, `combo_validate.py`
   - `find_sharpe13.py`
   - `funded_80_pass.py`, `funded_edge.py`, `funded_edge2.py`, `funded_edge3.py`
   - `honest_scan.py`
   - `ibs_backtest.py`
   - `intraday_1h_test.py`, `intraday_test.py`
   - `qqq_regime_edge.py`
   - `rotation_validate.py`
   - `unique_edge.py`
   - `volume_scaled_ibs.py`
   - `all_strategies_backtest.py` (intended archive; the original
     multi-strategy driver, superseded by `Strategies/run_all.py`)
3. Keep in `Strategies/`:
   - `All Strategies Backtest.md` (update to reference framework)
   - `IBS Mean Reversion.md`, `QQQ Dual-Signal Edge.md`, etc.
   - `run_strategy.py`, `run_all.py`
4. Delete `test.md` and `Untitled.canvas` if they exist.
5. Update `Strategies/Volume-Scaled IBS.md`:
   - Replace the old volume-scaling rule with the corrected inverted rule.
   - Explain that high-volume IBS entries were net losers in the original test, so the framework demands deeper oversold on high volume.
6. Update `agents.md`:
   - Fix `[[Funded Account Edge]]` → `[[Funded 80% Pass Strategy]]`.
   - Reference `Strategies/run_all.py` and `python -m orchestrator.cli --workflow full`.
   - Update Backtest Engine references from `all_strategies_backtest.py` to the new registry/runner.
7. Update `memory.md`:
   - Note that the unified framework exists.
   - Mark the volume-scaling inversion as done.
   - Mark next-open-by-default and cost-model consolidation as done.
8. Write `README.md`:
   - Quick-start: `python Strategies/run_all.py`
   - Run a single strategy: `python Strategies/run_strategy.py --strategy ibs_spy`
   - Run agent workflow: `python -m orchestrator.cli --workflow full --idea "..."`
   - Run tests: `pytest tests/ -q`
   - Link to `Strategies/README.md` for strategy details.

**Acceptance criteria:**
- `find archive/Strategies -name '*.py' | wc -l` equals the number of moved scripts (19, including `all_strategies_backtest.py`).
- `find Strategies -maxdepth 1 -name '*.py' | wc -l` equals 2 (`run_strategy.py`, `run_all.py`).
- `test.md` and `Untitled.canvas` no longer exist.
- `README.md` exists and contains the quick-start instructions above.
- `Strategies/Volume-Scaled IBS.md` matches the corrected logic.

---

## Chunk 6: End-to-End Integration Test

**Complexity:** medium

**Files:**
- `tests/test_integration.py`

**Behavior:**
- Runs `ibs_spy`, `qqq_dual_ma`, and `volume_scaled_ibs` end-to-end.
- Asserts each produces trades, positive PF (where expected), and max DD < 50%.
- Verifies that next-open execution produces a later entry price than close execution for the same signal bar.
- Verifies the orchestrator can run a full workflow without raising.

**Acceptance criteria:**
- `pytest tests/test_integration.py` passes.

---

## Verification

After all chunks:
1. `python -m pytest tests/ -q` passes.
2. `python Strategies/run_all.py` produces the expected ranking table.
3. `python -m orchestrator.cli --workflow full --idea "QQQ mean reversion using ibs_spy"` runs end-to-end.
