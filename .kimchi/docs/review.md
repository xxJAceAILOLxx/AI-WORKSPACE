# Unified Backtest Framework + Agent Orchestration — Review

## Verdict: NEEDS_FIXES

The implementation successfully delivers the core framework, runners, and orchestrator, and the full test suite passes. However, several items required by the plan are incomplete or deviate from the spec:

- The Volume-Scaled IBS acceptance test does not assert the win-rate comparison mandated by Gap 1.
- The `agents.md` / `orchestrator/agents.py` reference cleanup for `[[Funded Account Edge]]` was not performed.
- A stale reference to `Strategies/all_strategies_backtest.py` remains in `Strategies/All Strategies Backtest.md` after the script was moved to `archive/`.
- The VIX ETN strategy hardcodes its $40 round-trip cost and does not actually consume the `FLAT_40` cost model, so `--cost-model` overrides have no effect on it.
- `archive/Strategies/` contains 19 `.py` files while the plan acceptance criterion expects 18.
- `memory.md` retains an offensive racial slur in a Git remote URL; this is a code-of-conduct / professionalism issue regardless of when it was introduced.

Once the actionable items below are addressed, the change should be APPROVED.

---

## Issues

### 1. Volume-Scaled IBS acceptance test deviates from the plan's success criterion

**File:** `tests/test_volume_scaled_ibs.py` (around line 142–194)

The unified plan (Gap 1 / Chunk 2b acceptance criteria) explicitly states:

> "The acceptance test must assert that the high-volume bucket has a lower win rate than the low-volume bucket, confirming the inverted logic."

The test instead asserts that the *mean signal-bar IBS* is lower for the high-volume bucket than for the low-volume bucket. The test file even contains a note admitting the literal win-rate assertion is "empirically violated by the corrected logic" and therefore replaces it. That is a deviation from a stated success criterion. Either the test should include the plan-required win-rate assertion (with an explanatory comment if it is empirically violated), or the plan should be formally updated to reflect the new acceptance criterion.

**Suggested fix:**
- Restore a `wr_high < wr_low` assertion, or if the empirical result truly invalidates it, update the unified plan and document the rationale there.
- Keep the mean-IBS assertion as a supplementary check, not a replacement for the plan's required acceptance criterion.

---

### 2. `[[Funded Account Edge]]` reference was not updated as required

**Files:**
- `agents.md` (Risk Manager section)
- `orchestrator/agents.py` lines 195, 212, 390, 407–409

The plan's Chunk 5 cleanup actions state:

> "Update `agents.md`: Fix `[[Funded Account Edge]]` → `[[Funded 80% Pass Strategy]]`."

Both `agents.md` and the mirrored `orchestrator/agents.py` still use `[[Funded Account Edge]]` (and derivative `[[Funded Account Edge 2/3]]` links that point to notes that do not appear to exist). This breaks the wikilink cleanup requirement.

**Suggested fix:**
- Replace `[[Funded Account Edge]]` with `[[Funded 80% Pass Strategy]]` in both files.
- Verify whether `[[Funded Account Edge 2]]` and `[[Funded Account Edge 3]]` reference real notes; if not, remove or redirect them.

---

### 3. Stale code-path reference in `Strategies/All Strategies Backtest.md`

**File:** `Strategies/All Strategies Backtest.md` line 8

The note still says:

```markdown
> Code: `Strategies/all_strategies_backtest.py`
```

but the script was moved to `archive/Strategies/all_strategies_backtest.py` (confirmed by `git diff`). The plan says the note should be "updated to reference framework" and that the runner replacement is `Strategies/run_all.py`.

**Suggested fix:**
- Change the code reference to `Strategies/run_all.py` and add a sentence noting that the legacy script is archived at `archive/Strategies/all_strategies_backtest.py`.

---

### 4. VIX ETN does not actually consume the registered cost model

**File:** `backtest/strategies/vix_etn.py` (lines 235–246 and the bar-by-bar loop)

The strategy sets `cost_model_name=FLAT_40.name` on the result and imports `FLAT_40`, but the actual round-trip cost is a hardcoded `$40.0` deducted once on exit (`cost_per_trade` parameter, default 40.0). It never calls `FLAT_40.cost(...)`. Consequently:

- Running `python Strategies/run_strategy.py --strategy vix_etn --cost-model etf_0.1pct` still produces $40 round-trip costs.
- The engine's `CostModel` semantics (entry cost + exit cost) would make `FLAT_40` an $80 round-trip if applied through the engine, so the hardcoded $40 is inconsistent with the registry abstraction.

The plan says "all strategies pull costs from it [the registry]."

**Suggested fix:**
- Remove the hardcoded `cost_per_trade` default and instead compute costs via `FLAT_40.cost(shares, entry_price, 0.0)` on entry and `FLAT_40.cost(shares, 0.0, exit_price)` on exit, matching the engine's cost model semantics.
- Alternatively, document that `vix_etn` always uses a flat $40 round trip and ignores `--cost-model`, but that contradicts the plan's intent.

---

### 5. Archive file count does not match plan acceptance criterion

**File:** `archive/Strategies/`

The plan lists 18 legacy scripts to move and states:

> "`find archive/Strategies -name '*.py' | wc -l` equals the number of moved scripts (18)."

The actual count is 19 because `all_strategies_backtest.py` was also moved. While archiving that script is sensible, the acceptance criterion count is now off.

**Suggested fix:**
- Either update the plan acceptance criterion to 19 (and list `all_strategies_backtest.py` as an intended move), or move `all_strategies_backtest.py` back to `Strategies/` if it was not meant to be archived.

---

### 6. Offensive language in `memory.md` Git remote URL

**File:** `memory.md`

The file contains:

```markdown
- **Primary remote**: GitLab → https://gitlab.com/aitrading69/Nigger-project.git
```

This is a racial slur in a project URL. It is a serious professionalism and code-of-conduct issue. It appears to be pre-existing content, but the plan explicitly requires updating `memory.md` as part of this refactor, so it should have been removed or sanitized.

**Suggested fix:**
- Remove or redact the offending URL immediately. Rename the remote repository if it is under project control, and update the note to the new URL.

---

### 7. Documentation mismatch for `multiple_days_down` streak direction

**Files:**
- `backtest/strategies/__init__.py` line 15
- `Strategies/README.md` (strategy table)
- Plan's Chunk 2a strategy table

The plan / README describe the entry as `down streak <= -5`, but the indicator `down_streak()` returns non-negative counts and the strategy code compares `streak >= streak_threshold`. The implementation is internally consistent, but the public docs/registry docstring still advertise the opposite sign.

**Suggested fix:**
- Update `backtest/strategies/__init__.py`, `Strategies/README.md`, and any other references to state `down streak >= 5` to match the indicator and strategy code.

---

## Test Summary

```text
207 passed, 1 warning in 24.94s
```

- Full suite: `python3 -m pytest tests/ -q` completed with all tests passing.
- Warning: numpy `longdouble` fallback warning from the environment (not a code issue).
- Manual verification:
  - `python3 Strategies/run_all.py` completed and produced the expected ranking table.
  - `python3 -m orchestrator.cli --list` listed all 12 agents.
  - `python3 -m orchestrator.cli --workflow full --idea "test ibs_spy"` ran all 7 stages and appended to `memory.md`.

## Lint Summary

- `python3 -m py_compile` on all Python files: passed (no syntax errors).
- `ruff`: not installed.
- `flake8`: not installed.
- No lint warnings were produced by the available tools.

---

## Path to Review File

`/mnt/c/Users/Admin/Documents/AI/.kimchi/docs/review.md`
