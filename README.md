# AI Trading Vault

A unified backtest framework and agent orchestration layer for the trading
research vault. Replaces the scattered, copy-pasted `Strategies/*.py`
scripts with a single reusable library, a runner CLI, and a workflow
orchestrator that mirrors the prompts in `agents.md`.

## Quick Start

Run every registered strategy and print the ranking table:

```bash
python3 Strategies/run_all.py
```

Run a single strategy by name:

```bash
python3 Strategies/run_strategy.py --strategy ibs_spy
```

Run the end-to-end agent workflow (research, design, backtest, validate,
deploy, monitor, learn) for a given idea:

```bash
python3 -m orchestrator.cli --workflow full --idea "IBS mean reversion using ibs_spy"
```

Run the test suite:

```bash
python3 -m pytest tests/ -q
```

## Project Layout

```
.
|-- backtest/                 Reusable backtesting library
|   |-- engine.py             Event-loop engine (next-open by default)
|   |-- costs.py              Named cost-model registry
|   |-- indicators.py         IBS, RSI, SMA, ATR, %B, VolRatio, TOM
|   |-- metrics.py            Sharpe, Sortino, PF, drawdown, expectancy
|   |-- validation.py         Walk-forward + Monte Carlo
|   |-- reporting.py          Ranking table + per-strategy reports
|   `-- strategies/           Strategy library + registry
|-- orchestrator/             Agent orchestration layer
|   |-- agents.py             12 agent definitions from agents.md
|   |-- workflow.py           7-stage workflow runner
|   |-- memory.py             Persists run results to memory.md
|   `-- cli.py                `python -m orchestrator.cli` entry point
|-- Strategies/               Framework-aware strategy specs + runners
|   |-- run_all.py            Runs every registered strategy
|   |-- run_strategy.py       Runs a single strategy by name
|   |-- *.md                  Strategy notes (Obsidian vault)
|-- tests/                    Pytest suite for the framework
|-- archive/Strategies/       Legacy one-off backtest scripts
|-- agents.md                 Agent prompt library (12 agents)
|-- memory.md                 Working memory for runs + open questions
`-- README.md                 This file
```

## Design Principles

1. **Next-open execution by default.** `execution="close"` is explicit,
   never the default. See `Strategies/Volume-Scaled IBS.md` for the
   data-quality reason.
2. **Named cost models.** Strategies pull costs from `backtest.costs`
   (`etf_0.1pct`, `vix_etn_40`, `per_share_0.01`). No magic numbers in
   strategy code.
3. **Registry-based strategies.** Every strategy lives in
   `backtest/strategies/` and self-registers via `@register("name")`.
   Adding a new strategy = one decorator + one function.
4. **Agents without external LLM calls.** The orchestrator prints
   populated prompts and invokes the local backtest runner where
   applicable; it does not hit any external API.
5. **Obsidian vault stays intact.** Only Python scripts are reorganised.
   All `.md` strategy notes, `Concepts/`, and `Reflections/` remain.

## Strategy Notes

For the rationale behind each strategy and the backtest results, see
[`Strategies/README.md`](Strategies/README.md) and the per-strategy
`.md` notes under `Strategies/`.

## Adding a New Strategy

```python
# backtest/strategies/my_edge.py
from backtest.engine import Engine, BacktestResult
from backtest.indicators import ibs, sma
from backtest.strategies.registry import register

@register("my_edge")
def my_edge(start="2016-01-01", end="2025-12-31", execution="next_open"):
    ohlcv = load_daily("SPY", start, end)
    sig = (ibs(ohlcv.df) < 0.20) & (ohlcv.df["Close"] > sma(ohlcv.df["Close"], 200))
    eng = Engine(ohlcv, name="my_edge", execution=execution)
    eng.set_entry(sig.shift(1).fillna(False))
    eng.set_exit(lambda s: ("hold_expired", 0.0) if s.bars_in_trade >= 5 else None)
    return eng.run()
```

Then run it:

```bash
python3 Strategies/run_strategy.py --strategy my_edge
python3 Strategies/run_all.py --include my_edge
```

## Archive

Legacy one-off backtest scripts live in `archive/Strategies/`. They are
preserved for reference but are not used by the framework. New work
should target `backtest/strategies/` and the registry.

## License

Personal research vault.
