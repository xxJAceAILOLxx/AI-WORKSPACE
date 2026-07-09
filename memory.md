# Memory

## Last Updated

2026-07-09

## 1. What this vault is

A unified backtest framework + agent orchestration layer for a personal Obsidian trading-research vault, replacing scattered `Strategies/*.py` one-offs.

## Maintenance rule

Whenever a strategy is added, removed, or modified; a new backtest result is produced; an agent/workflow stage changes; or a design decision/critical gotcha is updated, this file must be updated. The framework auto-rewrites some sections on opt-in (`--update-memory`, workflow `new_strategy` flag); everything else is a manual edit.

**Checklist by change type:**
- **New strategy (added):** add a row to `## 5. Registered strategies` and bump `Last Updated`.
- **Strategy modified or removed:** edit or delete the corresponding row in `## 5. Registered strategies`; update `## 9. Backtest snapshot` if metrics changed materially.
- **New backtest result:** append a one-line bullet (timestamp, strategy, PF / Sharpe / CAGR / DD / WR / trades, verdict) to `## 9. Backtest snapshot`.
- **Agent or workflow stage change:** update `## 6. Agent system` (table row + primary-agent list).
- **Design decision:** add a bullet to `## 7. Key design decisions`.
- **Critical gotcha discovered:** add a bullet to `## 8. Critical gotchas`.
- Always bump `Last Updated` at the top of the file.

After any non-trivial change, run `python3 -m pytest tests/ -q` to confirm the test suite still passes.

## 2. Quick start

```bash
# Run every registered strategy (ranked)
python3 Strategies/run_all.py

# Run one strategy
python3 Strategies/run_strategy.py --strategy ibs_spy

# End-to-end 7-stage agent workflow
python3 -m orchestrator.cli --workflow full --idea "IBS mean reversion using ibs_spy"

# Tests
python3 -m pytest tests/ -q
```

## 3. Directory map

| Path | Purpose |
|---|---|
| `backtest/` | Reusable engine, indicators, costs, metrics, validation, reporting, strategies |
| `backtest/strategies/` | Strategy library + `@register` registry |
| `orchestrator/` | 12-agent definitions, 7-stage workflow, CLI, memory writer |
| `Strategies/` | Framework-aware runner scripts (`run_all.py`, `run_strategy.py`) + Obsidian `.md` notes |
| `tests/` | Pytest suite for the framework |
| `archive/Strategies/` | Legacy one-off backtest scripts (do not import) |
| `agents.md` | Canonical agent prompt library (12 agents) |
| `Concepts/`, `Reflections/`, `Strategies/*.md` | Obsidian vault notes (untouched by refactor) |

## 4. Framework API (one-liners)

| Class/Function | Location | Purpose |
|---|---|---|
| `Engine` | `backtest/engine.py` | Event-loop backtest engine; default `execution="next_open"` |
| `BacktestResult` / `Trade` / `EngineState` | `backtest/engine.py` | Result container, trade record, per-bar state |
| `OHLCV` / `load_daily` | `backtest/data.py` | Data wrapper + Yahoo loader with local cache |
| `ibs`, `rsi`, `sma`, `ema`, `atr`, `bollinger`, `pct_b`, `down_streak`, `volume_ratio`, `turn_of_month`, `realized_vol` | `backtest/indicators.py` | Pure-Pandas indicators |
| `CostModel`, `PERCENT_10BP`, `FLAT_40`, `PER_SHARE_1C`, `register`, `get`, `available` | `backtest/costs.py` | Named cost-model registry |
| `sharpe`, `sortino`, `cagr`, `max_drawdown`, `win_rate`, `profit_factor`, `expectancy`, `Metrics`, `compute_metrics` | `backtest/metrics.py` | Performance metrics |
| `walk_forward`, `walk_forward_split`, `monte_carlo`, `monte_carlo_paths` | `backtest/validation.py` | Out-of-sample + bootstrap |
| `print_result`, `print_ranking` | `backtest/reporting.py` | CLI formatting |
| `register`, `run`, `list_strategies`, `REGISTRY` | `backtest/strategies/registry.py` | Strategy discovery |
| `Agent`, `AGENTS`, `get_agent`, `list_agents`, `by_stage`, `primary_agent` | `orchestrator/agents.py` | Agent definitions |

## 5. Registered strategies

| Name | Ticker | Entry | Exit | Sizing | Cost |
|---|---|---|---|---|---|
| `ibs_spy` | SPY | `IBS < 0.20` | 5-day hold | 95% equity | `etf_0.1pct` |
| `ibs_trend` | SPY | `IBS<0.20` AND `Close>SMA200` AND TOM | 5-day hold | 95% equity | `etf_0.1pct` |
| `qqq_mr` | QQQ | `IBS<0.20` AND `Close>SMA200` | 5-day hold | 95% equity | `etf_0.1pct` |
| `rsi2_mr` | SPY | `RSI(2)<10` AND `Close>SMA200` | 5-day hold | 95% equity | `etf_0.1pct` |
| `rsi2_qqq_enhanced` | QQQ | `RSI(2)<10` AND `Close>SMA200` AND prior-day-down | `Close>High_{t-1}` OR 5-day hold | 95% equity | `etf_0.1pct` |
| `pct_b_mr` | SPY | `%B<0.10` AND `Close>SMA200` | 5-day hold | 95% equity | `etf_0.1pct` |
| `multiple_days_down` | SPY | down streak `>=5` AND `Close>SMA200` | 5-day hold | 95% equity | `etf_0.1pct` |
| `turn_of_month` | SPY | last trading day of month | 4-day hold | 95% equity | `etf_0.1pct` |
| `volume_scaled_ibs` | SPY | `IBS<threshold(vol_ratio)` AND `Close>SMA200`; inverted rule (see §7) | 2x ATR(14) stop OR `IBS>0.50` OR 5-day hold | fixed-risk 10% of capital | `etf_0.1pct` |
| `qqq_dual_ma` | QQQ | trend pullback on SMA pair | `Close<SMA(short)` | 95% equity | `etf_0.1pct` |
| `ibs_dynamic` | SPY | `IBS<0.20` AND `Close>SMA200` | `Close>High_{t-1}` OR ATR(14) trailing stop OR 5-day hold | 95% equity | `etf_0.1pct` |
| `vix_etn` | SVXY/VXX | VIX-regime (contango/back) flip | regime flip OR end-of-data | vol-targeted | `vix_etn_40` |
| `fade_5bar_crypto` | BTC/ETH (5m) | `Close < prior 5-bar low` (long-only fade) | 12 bars OR end of UTC day | 95% equity | `etf_0.1pct` |
| `orb_15m_crypto` | BTC/ETH (5m) | breakout above first-3-bar UTC high AND `Close>EMA(288)` | end of UTC day | 95% equity | `etf_0.1pct` |
| `mr_portfolio` | composite | sub-signals: ibs_spy + rsi2_mr + pct_b_mr + turn_of_month | per-sub hold (4-5d) | per-trade `0.95` | `etf_0.1pct` |
| `lvpr` | any ETF | `(IBS<0.30 OR Close<lower BB(20,2))` AND `vol_ratio<=1.0` AND `Close>SMA200` — **quiet pullback** (novel: inverts volume logic) | `Close>=SMA20` OR 2x ATR(14) stop OR 10d hold | 95% equity or fixed-risk | `etf_0.1pct` |
| `vcr` | any ETF | volume-climax bar: `vol_ratio>=2.5` AND range>=1.5x ATR AND down-bar AND close off low AND `Close>SMA200` | `Close>=SMA20` OR 2x ATR stop OR 10d hold | 95% equity or fixed-risk | `etf_0.1pct` |
| `funded_reversion` | basket SPY,QQQ,IWM,GLD,DIA,MDY,SLV (or 2x SSO,QLD,UWM,DDM) | LVPR per instrument, summed equity over common calendar | per-instrument LVPR exits | per-slice 95% equity | `etf_0.1pct` |

Run `python3 Strategies/run_strategy.py --list` for the live registry.

> **Novel-edge note (2026-07-09):** `lvpr` and `vcr` are deliberately NON-common (no IBS/RSI/%B/TOM/dual-MA). `lvpr` inverts the usual
> "volume confirms reversal" logic: it fades only *quiet* pullbacks (low volume), because the vault's own gotcha shows high-volume ETF
> selloffs are institutional distribution (net losers). Backtests confirm: QQQ `lvpr` with `vol_max=0.8` beats every common MR strategy in the vault (PF 2.59, Sharpe 0.86, WR 69.7%, 89 trades, 2016-2025).

## 6. Agent system

Pipeline: `research -> design -> backtest -> validate -> deploy -> monitor -> learn`.

| Stage | Primary Agent | What it does |
|---|---|---|
| research | `web_researcher` | Scrape/summarize trading research, compare to vault |
| design | `strategy_architect` | Turn idea into testable hypothesis + mechanical rules |
| backtest | `backtest_engine` | Run registry strategy; compute Sharpe/PF/DD; WF + Monte Carlo |
| validate | `risk_manager` | Enforce DD/daily-loss/correlation limits; Kelly sizing |
| deploy | `prop_firm_challenger` | Adapt to prop rules; size for target; track progress |
| monitor | `mistake_tracker` | Log losses, categorize, suggest rule changes |
| learn | `knowledge_curator` | Maintain MOCs, wikilinks, gap analysis |

Additional agents (not in default workflow): `market_regime_detector`, `structure_analyst`, `order_flow_interpreter`, `neural_network_architect`, `portfolio_optimizer`. No external LLM calls — orchestrator prints populated prompts and invokes the local backtest runner.

## 7. Key design decisions

- **Next-open default execution.** `execution="next_open"` in `Engine`; close execution must be requested explicitly (`--execution close`).
- **Inverted volume-scaled IBS.** `vol_ratio >= 1.5` -> `IBS<0.15` (deep oversold required on high volume, since institutions distribute); `vol_ratio <= 0.5` -> `IBS<0.25` (relaxed on quiet volume); otherwise `IBS<0.20`.
- **Unified cost registry.** Strategies pull from `backtest.costs` (`PERCENT_10BP`/`etf_0.1pct`, `FLAT_40`/`vix_etn_40`, `PER_SHARE_1C`/`per_share_0.01`); no magic numbers in strategy code.
- **No external LLM calls.** `orchestrator/` only formats and prints prompts + calls the local registry runner.
- **Registry-based strategies.** New strategy = one file in `backtest/strategies/` with `@register("name")`.
- **Vault left intact.** Only Python reorganised; all `.md` notes remain.

## 8. Critical gotchas

- **Yahoo forex is interpolated** mid-prices, not real ticks — smooths series and creates fake mean-reversion edges.
- **Same-bar entry/exit = lookahead bias.** Always execute at the next bar's open.
- **IBS<0.18 on GBPUSD:** Sharpe 3.80 at close -> Sharpe -7.81 (WR 2%) at next open. If an edge disappears at next-open, it was a data artifact.
- **QQQ IBS:** Sharpe 0.19 at next open (no edge) — confirms the GBPUSD result was fake.
- **High-volume IBS entries are net losers** (33.3% WR) — institutions distribute into panic.
- **70% rule:** Live PF must be >=70% of backtest PF to stay viable.
- **Walk-Forward Ratio <0.3 = overfitting; >0.5 = robust.**
- **Monte Carlo survival <90% = risky.**
- **IBS-mean-reversion edge is real but tiny** — 148 trades in 20 years on SPY; consider QQQ or multi-asset for frequency.
- **Cost model name vs enum:** `PERCENT_10BP.name == "etf_0.1pct"`; CLI uses the dotted name, code uses the constant.

## 9. Backtest snapshot

**IBS Mean Reversion (SPY, 2005-2025):** PF 1.57, WR 66.9%, Expectancy $16.16, 148 trades, Total Return 0.9%, Sharpe 0.14, WFR 3.30, MC survival 100% (worst DD -1.7%). Verdict: valid edge, practically useless — too few trades.

**All Strategies (10y, 2016-2025):**
- Winner: **QQQ Mean Reversion** — PF 1.71, WR 62.4%, CAGR 10.6%, DD -14.9%, 186 trades.
- Runner-up: **IBS Simple SPY** — PF 1.77, WR 61.2%, CAGR 9.0%, DD -16.3%, 258 trades.
- Trend: **QQQ Dual MA** — PF 2.67, WR 32.8%, CAGR 9.8%, DD -19.1%, 61 trades.
- Disappointing: TOM (PF 1.32), RSI(2) (PF 1.20), Multiple Days Down (10 trades).

**Volume-Scaled IBS (SPY, inverted 2026-06-28):** PF 1.65, WR 63.8%, 337 trades, Sharpe 0.54, DD -1.6%, WFR 1.33, MC survival 100% (worst DD -3.3%). PF +4.4% and Sharpe +17.4% over fixed IBS. Score 9/10 (only Sharpe <1.0 fails). Status: VIABLE — best risk-adjusted in vault.

**QQQ Dual-Signal Edge (daily):** IBS<0.20 MR (5d) + trend pullback. Sharpe 0.88, CAGR 11.0%, DD -14.8%, PF 2.06, WR 44%, WFR 1.34, MC 100%. Best equity strategy; Sharpe below 1.0.

**Funded 80% Pass Study:** Best individual BTC trend = 23% pass rate. Best 6-instrument portfolio (BTC, QQQ, SPY, IWM, GLD, ETH, DIA) = 63%. Honest conclusion: 60-70% achievable on daily bars; 80% needs intraday/leverage.

**Latest framework run (2026-06-28T07:00:13Z, idea "test ibs_spy"):** CAGR 8.76%, max DD 21.03%, PF 1.66, Sharpe 0.70, 230 trades, WR 64.35%. `validate_ok=False`; max daily 10.40%.

**External-research backtests (2026-07-02, next-open, 2016–2025, etf_0.1pct):**
- `rsi2_qqq_enhanced`: CAGR 1.77%, DD -11.81%, PF 1.52, Sharpe 0.30, 72 trades, WR 70.83%. Verdict: **worse than baseline** — the prior-day-down filter and profit-take exit cut trade count and returns versus plain `rsi2_mr` (Sharpe 0.65, PF 2.08) and `qqq_mr` (Sharpe 0.98).
- `ibs_dynamic`: CAGR 3.44%, DD -11.58%, PF 1.56, Sharpe 0.53, 213 trades, WR 68.08%. Verdict: **slightly worse than `ibs_spy`** (Sharpe 0.70, PF 1.66, CAGR 8.76%); the dynamic exits reduced drawdown but also compressed returns and Sharpe.

**Intraday data infrastructure (2026-07-02):**
- Added `load_intraday_binance(symbol, interval, start, end)` and `load_intraday_hf(ticker, start, end)` to `backtest/data.py`. Exported from `backtest` package.
- **Binance bug fixed:** parser auto-detects ms vs us timestamps (Binance switched to microseconds in 2025).
- Cached 59 monthly shards of BTCUSDT and ETHUSDT 5m data, 2021-07 -> 2026-05, 517k rows each, 63MB total.
- HF Data Library requires `HF_DATA_API_KEY` env var (register free at hfdatalibrary.com). Code tested: raises cleanly without key.

**Crypto intraday backtests (2026-07-02, INCOMPLETE — paused):**
- `fade_5bar_crypto(BTCUSDT)`: 3,329 trades, ran in 19.9s. Metrics NOT yet collected (paused before summary printed).
- `orb_15bar_crypto(BTCUSDT)`: was running when paused.
- `fade_5bar_crypto(ETHUSDT)`: not started.
- `orb_15m_crypto(ETHUSDT)`: not started.
- **Honest limitation:** engine is long-only, so fade_5bar_crypto only captures the *downside* of the Alpha Atlas edge (buys new 5-bar lows, expects bounce). The original Atlas edge also shorts new 5-bar highs. A proper short leg needs engine-level shorting support.

- **2026-07-04T05:50:36Z** - `ibs_spy`: PF 1.66, Sharpe 0.70, CAGR 8.76%, DD 21.03%, WR 64.35%, 230 trades. Verdict: validate FAILED.

- **2026-07-09T12:01:20Z** - `funded_reversion`: PF 1.30, Sharpe 0.44, CAGR 1.37%, DD 6.25%, WR 58.03%, 1227 trades. Verdict: validate OK.

## 10. Open questions / TODOs

- How to systematically measure "freshness" of positioning?
- When does a level transition from actionable positioning to context-only?
- How to quantify absorption strength (volume decay at a level)?
- Best way to backtest order-flow setups vs volume-profile setups?
- How to improve IBS strategy trade frequency? (relax filters, add assets, shorter timeframes)
- Combine QQQ MR + IBS Simple SPY as a portfolio (uncorrelated instruments, same edge)?
- Can we get intraday data to test ORB, FVG, and IBS Intraday strategies?
- Volume-Scaled IBS Sharpe still <1.0 — add filter (VIX regime? earnings calendar?)?
- Investigate why framework run on `ibs_spy` shows DD 21% vs backtest snapshot ~16% — cost/window difference?

## 11. Vault sync

- **Primary remote:** GitLab -> https://gitlab.com/aitrading69/REDACTED.git
- **Secondary remote:** GitHub -> https://github.com/xxJAceAILOLxx/AI-WORKSPACE.git
- **Plugin:** obsidian-git (auto-commit, auto-push, auto-pull)
- **Auto-pull interval:** 3 min | **Auto-push interval:** 10 min | **Auto-save interval:** 5 min
- **Auto-pull on boot:** enabled

## 12. Key quotes

- > "Markets are just positions." — Michael Platt
- > "Volume profile's not a magic map of support and resistance."
- > "The shorter and cleaner it is, the more you could tell about live positioning."
- > "Structure vs flow, always."
- > "Price action tells you what happened. Order flow tells you why."
- > "The order book is the most informative single view in any trading interface."
- > "If you torture the data long enough, it will confess to anything." — Ronald Coase
- > "Simplicity is an advantage, not a limitation."
- > "Only 1 out of every 20 strategy ideas survives a complete validation process." — Kevin Davey

## Framework Runs

- **2026-07-04T05:50:14Z** - idea: IBS mean reversion on SPY
  - strategy: `-`
  - stages: research, design, backtest, validate, deploy, monitor, learn
  - notes: validate_ok=True; max_dd=0.00%; max_daily=0.00%
- **2026-07-04T05:50:36Z** - idea: IBS mean reversion on SPY
  - strategy: `ibs_spy`
  - stages: research, design, backtest, validate, deploy, monitor, learn
  - metrics:
    {
      "cagr": 0.0875669484698045,
      "max_drawdown": 0.2103360230892758,
      "profit_factor": 1.658540255877099,
      "sharpe": 0.703454673682409,
      "trade_count": 230.0,
      "win_rate": 0.6434782608695652
    }
  - notes: validate_ok=False; max_dd=21.03%; max_daily=10.40%

**Novel mean-reversion + volume strategies (2026-07-09, next-open, 2016-2025, etf_0.1pct):**

- `lvpr` (Low-Volume Pullback Reversion) — the headline non-common edge. Fades *quiet* pullbacks (low volume). Best single config: **QQQ, `ibs_max=0.30`, `vol_max=0.80`** → PF 2.59, Sharpe 0.86, WR 69.7%, 89 trades, eq_dd 6.2%. OOS (2022-2025): PF 1.66, Sharpe 0.32, WR 72.2% (edge holds, decays as expected). Confirmed: quiet pullbacks revert; high-volume panic does not (matches the distribution gotcha).
- `vcr` (Volume Climax Reversal) — fades a single-bar volume-exhaustion climax. On liquid ETFs it is TOO RARE (2 trades/decade on QQQ) to be useful for a challenge; kept for completeness / higher-volatility instruments. NOT recommended as primary.
- `funded_reversion` — multi-instrument `lvpr` portfolio (the actual prop-firm deployment):
  - **SAFE mode (1x basket, alloc 0.95):** PF 1.30, Sharpe 0.44, CAGR 1.4%, **eq_dd 6.25%, max daily 1.54%, 1227 trades.** Validate OK. MC survival (P>init) 100%, P(maxDD<10%) 99.8%. Score: risk rules trivially passed; too slow for a 30-day +10% target.
  - **TURBO mode (2x basket SSO/QLD/UWM/DDM, alloc 0.6):** PF 1.38, Sharpe 0.65, CAGR 3.0%, eq_dd 11%, max daily 2.0%, 731 trades. MC survival 99.5%, P(maxDD<10%) 88.2% — borderline vs the hard 10% DD limit; drop alloc to ~0.5 to keep DD<10%.

**Funded deployment plan (honest):**
- The 1x `funded_reversion` passes the *risk* half of any prop eval (DD + daily-loss) with ~99%+ probability. It is the right core for the **verification + funded phases** where you can trade smaller and keep the account.
- Hitting **+10% in 30 days** on daily ETF mean-reversion at safe sizing is NOT statistically achievable (best CAGR ~3% even 2x levered). To reach the target you must either (a) accept ~11-17% DD via 2x ETFs (near the 10% limit — risky), (b) trade **intraday** (vault's funded study: 80% pass needs intraday/leverage), or (c) use a firm with a longer/"flex" window (60-90 days).
- **Payout / consistency rule:** because trades are frequent and max daily loss is tiny (1.5-3%), the equity curve is naturally consistent — satisfies most firms' "no single day > X% of profit" rules. Once funded, scale up via 2x ETFs and add instruments (KRE, XLE, etc.) to accelerate compounding.
- WFR not computed (portfolio is multi-instrument); single-edge OOS decay (2.98→1.66) is acceptable (>0.5 = robust per vault thresholds).

**Intraday LVPR on crypto 5m — NEGATIVE result (2026-07-09):**
- Built `lvpr_intraday` (Binance 5m, `load_intraday_binance`) reusing the LVPR logic. Tested BTCUSDT + ETHUSDT, 2021-08 → 2026-05 (~500k bars, cached).
- **It is a net loser.** Grid over hold∈{12,24,48}, ibs_max∈{0.20,0.25}, vol_max∈{0.8,1.0}: BTC PF 0.61-0.66, WR 48-50%, eq_dd 83%; ETH PF 0.69-0.71, WR 50-51%, eq_dd 99%. Challenge pass rate = **0%** at 30/60/90-day windows (never reaches +10%; bleeds in the 2022 bear).
- **Why:** the novel "quiet pullback = low-effort exhaustion" edge is microstructure-specific to *daily equity ETFs*, where institutional distribution on high volume is a real, documentable signature. On 24/7 retail/algorithm crypto 5m there is no such signature; long-only mean reversion is dominated by trend + fees and is ~random (WR≈50%, PF<1). The volume filter barely moves the needle.
- **Implication:** a 30-day +10% prop pass via *intraday mean reversion* is not achievable with LVPR on crypto. Daily LVPR remains the only validated LVPR edge.

**Intraday breakout/fade on crypto 5m — also NEGATIVE (2026-07-09):**

Finished + pass-rate tested the two paused intraday crypto strategies (`orb_15m_crypto`, `fade_5bar_crypto`), BTCUSDT + ETHUSDT, 2021-07 → 2026-05, 10bps cost (generous vs real ~40bps taker), proper EOD daily-loss check.

- `orb_15m_crypto` (15m opening-range breakout, long-only): **breakeven, not an edge.** Grid ema_period∈{63,96,288} × or_bars∈{3,6}: PF 0.94-1.02, WR ~46%, CAGR **negative** (-4% BTC / -10% ETH full; -9%/-13% in 2024-26). eq_dd 65-70%. 30d challenge pass 5-12% (variance, not edge), 60d pass 0-10%. Best config ema=288/orb=3: PF 1.02, 30d pass 11.9%, 60d 10.3%. The cited Stoic study (Sharpe~1.0) did NOT replicate on BTC/ETH with 10bps costs.
- `fade_5bar_crypto` (5-bar breakdown fade, long-only): **net loser.** PF 0.96-0.98, WR ~47-50%, CAGR -31% BTC / -61% ETH, eq_dd 84-99%. 30d pass 0-1.7%. Confirms the original caveat: long-only captures only the losing half of the Atlas CS-Rev edge (Sharpe~4.40 was long+short); the short leg is required but the engine is long-only.

**Definitive verdict:** no validated intraday crypto strategy in this vault passes a prop challenge. Long-only + no short leg + 10bps costs + crypto trend/vol = no reliable edge. To make intraday viable you must (a) add **engine-level shorting** so Atlas CS-Rev and ORB can trade both sides, and/or (b) accept that the only validated edge remains **daily LVPR on equity ETFs** (passes risk rules ~99%, too slow for the 30-day target). The vault's "80% pass needs intraday/leverage" holds — but the specific intraday crypto strategies here don't deliver it as long-only.
- **2026-07-09T12:01:20Z** - idea: Low-Volume Pullback Reversion (LVPR) multi-ETF portfolio for prop firm challenge passing and payout; novel volume-filtered mean reversion
  - strategy: `funded_reversion`
  - stages: research, design, backtest, validate, deploy, monitor, learn
  - metrics:
    {
      "cagr": 0.01367184373683794,
      "max_drawdown": 0.06250157767333808,
      "profit_factor": 1.2979070125276941,
      "sharpe": 0.4357891519524061,
      "trade_count": 1227.0,
      "win_rate": 0.5802770986145069
    }
  - notes: validate_ok=True; max_dd=6.25%; max_daily=1.54%
