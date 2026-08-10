# AGENT 03 — Builtins: TA, Strategy, Plotting/Drawing, Collections, Request

| Field | Value |
| --- | --- |
| **Role / ID** | Agent 03 — Builtins (TA / strategy / plot / collections / request) |
| **Scope** | `src/pynescript/ast/evaluator/builtins/` (+ `technical_submodules/`) |
| **Mode** | READ-ONLY audit (no code changes) |
| **Date** | 2026-08-10 |

---

## Executive summary

The builtins layer is a mature, production-shaped Pine runtime surface: mixin composition, broad `ta.*` / `strategy.*` / `array|map|matrix.*` coverage, incremental TA state machines, OCA/partial-fill plumbing, and deliberate soft-na / mock-request policies tuned for corpus survival. Correctness work has clearly targeted **interpret↔compile dual-host parity** more than pure TradingView numerical fidelity on every kernel.

**Highest-risk gaps vs TradingView Pine:**

1. **`strategy.exit` is an immediate close oracle**, not a pending stop/limit bracket that waits for bar path (fills even when mark is between stop and limit).
2. **`ta.atr` is EMA-of-TR** (shared with compile `numba_atr`), not TV’s documented **`rma(tr)` / Wilder** definition — dual-host OK, TV parity risk High.
3. **`request.security` does not re-evaluate HTF expressions**; pre-eval on chart TF + soft mock/na policy. Complex MTF strategies cannot be trusted without a real multi-TF host path.
4. **EMA seed split**: bar-mode incremental uses SMA seed; full-history `_ema` still first-value seeds (and MACD’s nested `_ema_state_step` uses first-value). Residual dual-path and unit-test drift risk.
5. **Process-level `PlotRegistry` / `DrawingRegistry`** (ClassVar lists) require careful `reset()` between runs — concurrency / host isolation risk.

Overall quality is strong for an open-source Pine host (especially collections, dispatch, incremental TA engineering). Scorecard below: **~7.4 / 10** blended.

---

## Critical

### C1 — `strategy.exit` always closes now (no pending bracket)

**Evidence:** [`strategy.py:1231–1313`](../../src/pynescript/ast/evaluator/builtins/strategy.py)

When both `limit` and `stop` are set and mark is **between** them, the handler still picks a price and calls `_close_position`:

```1268:1294:src/pynescript/ast/evaluator/builtins/strategy.py
        if limit_p is not None and stop_p is not None:
            # Choose the trigger that would hit first based on current price direction
            if is_long:
                if current_p <= stop_p:
                    exit_price = stop_p
                elif current_p >= limit_p:
                    exit_price = limit_p
                else:
                    exit_price = min(limit_p, stop_p) if limit_p < stop_p else limit_p
            ...
        if self._strategy_state.position_direction != "flat":
            if limit_p is None and stop_p is None:
                exit_action = "sell" if is_long else "buy"
                exit_price = self._apply_slippage(exit_price, exit_action)
            self._close_position(exit_price, qty, self._bar_time())
```

Single-sided `limit=` / `stop=` likewise becomes an **immediate** fill at that price even if the bar never trades there.

**TV semantics:** `strategy.exit` places protective orders that fill on subsequent bars when price path hits stop/limit (often with OCA between legs). Instant oracle fill is only valid for unit/parity fixtures that intentionally model “exit called ⇒ closed”.

**Impact:** Backtest equity, hold times, and multi-bar TP/SL strategies diverge from TradingView. Documented as intentional “interpret oracle” in tests ([`tests/test_compiler_strategy.py:309–321`](../../tests/test_compiler_strategy.py)).

**Related gaps in same handler:**

- `from_entry` is documented but **not used** to select which open-trade leg to close.
- `profit` / `loss` kwargs are coerced as **prices** (`limit`/`stop` aliases), not TV tick offsets from entry.
- No trail stop / trail offset / trail price surface in the sampled exit path.

**Recommendation:** Route untriggered exit legs through `pending_orders` + `process_pending_orders` (same OHLC path as `strategy.order` / limit entries). Gate “oracle immediate fill” behind a test/flag if needed for goldens.

---

### C2 — `ta.atr` formula is EMA-of-TR, not Wilder RMA (TV mismatch)

**Evidence:**

- Full path: [`volatility.py:644–671`](../../src/pynescript/ast/evaluator/builtins/technical_submodules/volatility.py) — `return self._ema(tr_values, period)`
- Incremental: [`core.py:480–540`](../../src/pynescript/ast/evaluator/builtins/technical_submodules/core.py) — “EMA of TR after warm-up”
- Compile: [`numba_builtins.py:256–286`](../../src/pynescript/compiler/numba_builtins.py) — documents matching interpret EMA-of-TR

TradingView defines ATR as **`ta.rma(ta.tr(true), length)`** (Wilder smoothing, α = 1/length). ADX/DMI paths in the same codebase correctly use RMA (`_rma_state_step`, `numba` RMA helpers), so the stack **knows** Wilder — ATR simply doesn’t use it.

**Impact:** Supertrend, Keltner, ATR stops, and any script using `ta.atr` will systematically differ from TV charts while still matching interpret↔compile. Residual mismatches noted for Supertrend in parity work ([`docs/parity_round8/AGENT_05_interpret_ta.md`](../parity_round8/AGENT_05_interpret_ta.md)).

**Recommendation:** Switch full + inc + numba ATR to RMA-of-TR (SMA seed of first `period` TR samples, then Wilder). Re-golden Supertrend / KC fixtures.

---

## High

### H1 — `request.security` / MTF: no true HTF re-evaluation; gaps/lookahead unused

**Evidence:** [`request.py:667–799`](../../src/pynescript/ast/evaluator/builtins/request.py)

Documented policy (good): foreign without multi-symbol feed → `na`; same-symbol complex pre-eval on different TF → `na`; HA transform for `ticker.heikinashi`. Signature comments mention `gaps` / `lookahead`, but the handler body does not implement barmerge gaps or lookahead offset semantics on the returned series.

Pre-evaluated expressions are **chart-TF values** already computed by the evaluator. True multi-timeframe security requires either:

- a host data provider with HTF OHLCV + re-run of the expression, or  
- a dedicated security sub-runtime.

**Also:** Fundamentals, dividends, earnings, splits, financial, quandl, economic, currency, footprint are **mock** or soft-fail by design ([`request.py:20–28`](../../src/pynescript/ast/evaluator/builtins/request.py), [`:855+`](../../src/pynescript/ast/evaluator/builtins/request.py)). `request.footprint` generates random volume rows ([`:1091–1131`](../../src/pynescript/ast/evaluator/builtins/request.py)).

**Impact:** SSL/Heikin-Ashi MTF strategies and dividend scripts are known residual MISMATCH drivers (see strategy dual-path notes). Soft mock fallbacks without chart identity can invent prices for demos — intentional but dangerous if hosts forget identity wiring.

---

### H2 — EMA seed inconsistency (full `_ema` vs incremental / MACD)

**Evidence:**

| Path | Seed | Location |
| --- | --- | --- |
| `_ema_inc_update` | SMA of first `period` samples | `core.py:245–297` |
| Full `_ema` | First valid sample | `core.py:3211–3234` |
| MACD `_ema_state_step` | First sample | `core.py:417–435`, used by `_macd_inc_update` |

Incremental EMA docstring claims “matches numba_ema_inc / TV” (SMA seed). Full-history and MACD still use first-value seed. Unit tests that force full recompute (`_pine_ta_incremental=False` or non-bar mode) diverge from bar-mode Runtime.

**Impact:** Dual-host residual on nested-EMA families (Chaikin, etc. already noted historically); MACD warm-up differs from bare `ta.ema`.

**Recommendation:** Unify seed to SMA-window (TV) for `_ema`, `_ema_state_step`, and MACD signal EMA; keep single formula source with numba.

---

### H3 — Market `strategy.entry` same-id replace vs average; pyramiding asymmetry

**Evidence:** [`strategy.py:1140–1181`](../../src/pynescript/ast/evaluator/builtins/strategy.py) vs [`_open_position_qty:1789–1856`](../../src/pynescript/ast/evaluator/builtins/strategy.py)

- Market entry with **same id** **replaces** open trades with a single new leg at new fill price (does not VWAP-merge).
- Pending/order path with `pyramiding <= 0` **VWAP-merges** into one leg.
- Opposite-direction market entry reverses then opens new size (good); commission on reverse path is applied via `_close_position` + new entry.

**Impact:** Scripts that re-call `strategy.entry("L", …)` every bar behave like cancel/replace (TV-like for same id) but differ from order-fill averaging — easy to misread. Documented in `_open_position_qty` docstring; still a parity footgun for hybrid entry APIs.

---

### H4 — Process-global plot/drawing registries

**Evidence:**

- [`plotting.py:121–131`](../../src/pynescript/ast/evaluator/builtins/plotting.py) — `PlotRegistry.plots: ClassVar[list[Plot]]`
- [`drawing.py:145–167`](../../src/pynescript/ast/evaluator/builtins/drawing.py) — ClassVar collections + GC caps

**Impact:** Parallel evaluations in one process can cross-contaminate visuals unless `reset()` / per-run isolation is always enforced. Strategy state correctly moved to per-evaluator instances (`StrategyState` docstring `strategy.py:235–240`) — plots/drawings did not get the same treatment.

---

### H5 — Inverse / coin-margined avg price incomplete

**Evidence:** [`strategy.py:75–84`](../../src/pynescript/ast/evaluator/builtins/strategy.py), [`:1823`](../../src/pynescript/ast/evaluator/builtins/strategy.py)

`avg_price_model=inverse` is accepted but “harmonic add blend is phase-2 (add path still arithmetic)”. Futures sticky AEP vs stock reweight on partial close is implemented; coin-m harmonic is not.

---

## Medium

### M1 — Soft-fail culture (corpus resilience vs fail-closed)

Widespread `except Exception: pass` and soft-na coercion:

| Area | Pattern |
| --- | --- |
| `request.py` | Soft data-path failures (documented) |
| `arrays.py` | Soft index / soft size on non-array |
| `strategy.py` | `_soft_int_decl` / `_soft_float_decl` for unresolved names |
| `__init__.py:142–160` | Declaration wiring swallows broad exceptions (strategy TypeError re-raised) |
| `alerts.py`, `strings.py`, `utility.py` | Broad catches |

**Design tradeoff:** Corpus and sanitized scripts keep running. **Risk:** Silent misconfiguration (e.g. commission_value parse fail → 0) and hard-to-debug production runs.

### M2 — Call-site slot TA state (correct but brittle)

Incremental TA keys by **call-site order** (`_ta_next_slot`, `core.py:113–117`). Documented carefully for stoch warm-up ([`oscillators.py:97–102`](../../src/pynescript/ast/evaluator/builtins/technical_submodules/oscillators.py)): early-return without consuming a slot corrupts later EMA/SMA state.

**Risk:** Any new indicator that skips `_ta_next_slot` on warm-up bars reintroduces slot drift. No static enforcement.

### M3 — `_SERIES_MAX = 256` truncation on full-path materialization

[`core.py:78`](../../src/pynescript/ast/evaluator/builtins/technical_submodules/core.py), [`:2905–2925`](../../src/pynescript/ast/evaluator/builtins/technical_submodules/core.py). Safe for pure incremental kernels; full recompute of long-period indicators (e.g. period 300) can be wrong if forced off incremental path or if history is needed beyond the cap.

### M4 — Stoch D-line / smooth forms incomplete

[`oscillators.py:50–87`](../../src/pynescript/ast/evaluator/builtins/technical_submodules/oscillators.py): primary path returns **%K only**; 5-arg legacy smooth uses EMA for %D. TV `ta.stoch` returns single %K (OK); community dual-output forms are partial.

### M5 — `strategy.default_entry_qty` mock price

[`strategy.py:2286–2300`](../../src/pynescript/ast/evaluator/builtins/strategy.py):

```python
allocation = self._strategy_state.risk_free_capital * (percent_equity / 100.0)
return allocation / 100.0  # Assume price around 100
```

Hard-coded mark ≈ 100 — wrong sizing unless price is ~100.

### M6 — OCA reduce quantity accounting

[`strategy.py:1766–1768`](../../src/pynescript/ast/evaluator/builtins/strategy.py): reduce path does `other.quantity -= fill_qty` without adjusting `filled_qty` / remaining semantics carefully for partially filled siblings. Cancel OCA looks correct. Needs fixture coverage for partial multi-leg OCA.

### M7 — Technical submodule README stale

[`technical_submodules/README.md`](../../src/pynescript/ast/evaluator/builtins/technical_submodules/README.md) still says “85% complete / Phase 2 in progress / Last Updated: October 31, 2025” while the tree is largely integrated (`advanced`, economics, synthesizer, full dispatch in `technical.py`). Misleading for contributors.

### M8 — Duplication: full path vs `*_inc_update` formula pairs

`core.py` is a large dual implementation of SMA/EMA/RMA/RSI/ATR/ADX/… (~3.4k lines). Correctness depends on keeping pairs aligned with numba. Incremental path is excellent modern technique; maintenance cost is High without shared pure-Python reference kernels.

### M9 — Collections: solid API, soft edges

**Strengths:** Negative array indices (v6), soft-na get/set, map dict wrap for compile bridges, matrix half-open fill, linear algebra surface (`det`, `inv`, `eigen*`), list-of-lists bridge for matrix.

**Risks:** Array stats skip non-numeric (TV-like); `array.size` soft-na on non-array ([`arrays.py:296–308`](../../src/pynescript/ast/evaluator/builtins/arrays.py)) can hide type bugs; matrix `avg_row` returns 0 on empty numeric filter rather than na.

### M10 — Plotting semantics deliberate but non-obvious

[`plotting.py:188–196`](../../src/pynescript/ast/evaluator/builtins/plotting.py): plotshape/plotchar export `True` or `None`, never hard `False` — documented for dual-host packing. Call-site plot reuse in bar mode is good. Documentation quality here is better than average.

### M11 — Drawing `table.merge_cells` stub

[`drawing.py:1635–1639`](../../src/pynescript/ast/evaluator/builtins/drawing.py): explicit `pass` mock. GC caps and export helpers are real.

---

## Low

### L1 — Community / pseudo-TV `ta.*` surface sprawl

`technical.py` dispatch includes many non-official or tiered helpers (`ta.fear_greed_index`, `ta.kelly_criterion`, …). Good for corpus; blurs “official Pine parity” vs “pynescript extensions”. Prefer a documented extension namespace or metadata flag.

### L2 — `strategy.convert_to_account` passthrough

[`strategy.py:2280–2283`](../../src/pynescript/ast/evaluator/builtins/strategy.py): `return value * 1.0` mock.

### L3 — `color` / `strings` exception soft paths

Defensive `NotImplemented` / bare except for robustness; low severity.

### L4 — Footprint API shape present, data synthetic

API completeness for v6 surface; not a market-data product.

### L5 — Numerical validation report overclaims vs residual ATR/MTF reality

[`docs/numerical_validation_report.md`](../numerical_validation_report.md) claims ~TV identity; dual-host alignment notes are more honest. ATR EMA choice means the report should not be read as ATR TV gold.

---

## Documentation quality

| Area | Assessment |
| --- | --- |
| Module docstrings (`strategy`, `request`, `plotting`, `base`, `arrays`) | **Good** — Pine semantics, soft-fail policy, mixin composition spelled out |
| Incremental TA / slot semantics | **Excellent** — comments on slot corruption, strict windows, NA poison |
| Strategy exit / commission / OCA | **Partial** — OCA and commission comments exist; **exit pending vs oracle** not called out as intentional deviation |
| `technical_submodules/README.md` | **Stale** |
| Per-function TV form variants (arity overloads) | **Good** in oscillators/MAs (stoch, cci, vwma) |
| Non-obvious soft-na rules | **Good** in arrays/map; **scattered** elsewhere |

**Doc gaps to close:**

1. Explicit “strategy.exit is immediate-fill oracle until pending brackets land”.
2. Explicit “ATR is EMA-of-TR (TV uses RMA)” with dual-host rationale.
3. `request.security` limitations matrix: same-symbol / foreign / HTF / HA / pre-eval.
4. Refresh technical submodule README status and line counts.

---

## Modernization

### What’s modern / strong

- **Incremental TA** with per-call-site state, env kill-switch `PYNE_TA_INCREMENTAL`, cached bar-mode check (`core.py:90–111`).
- **last_sample_ok** + PineSeries reverse avoidance on hot path (`_expect_series`, `_series_last` type fast-paths).
- **O(1) strategy aggregates** (`_netprofit`, win/loss counts) and equity peak/trough tracking.
- **Pending order OHLC fill model** for `strategy.order` / limit entries (`process_pending_orders`, gap open handling).
- **Plot reuse by call-site** in bar mode; `slots=True` Plot dataclass.
- **Drawing GC** with declaration caps (TV-like).
- **Compile bridge** awareness (dict-as-map, list-of-lists matrix, materialize visual series from drawings).
- **Numba parity comments** linking interpret kernels to `numba_*_inc` (boundary clarity is better than average, still dual codebases).

### What’s still legacy / costly

- Dual full-series vs incremental implementations without a single pure reference.
- ClassVar global registries.
- Mock request data mixed into the same handlers as real feed paths.
- Giant mixin MRO (`BuiltinEvaluator` inherits ~15 mixins) — works, hard to navigate; already partially mitigated by submodule split.

### Opportunities

1. Extract pure kernel functions (no `self`) shared by interpret full, interpret inc, and numba (or generate numba from one source).
2. Per-evaluator Plot/Drawing registries (mirror `StrategyState`).
3. True pending `strategy.exit` + trail stops.
4. Optional `strict_request=True` host flag to disable mock prices entirely.
5. ATR → RMA alignment + Supertrend re-golden.

---

## Scorecard

| Dimension | Score (1–10) | Notes |
| --- | --- | --- |
| TA formula correctness vs TV | **6.5** | RSI/RMA/SMA strict-window strong; ATR EMA, EMA seed splits, residual HMA/VWAP |
| TA engineering (inc/caching) | **8.5** | Call-site state, last-sample path, compile alignment effort |
| Strategy broker realism | **6.0** | Entry/OCA/commission/partial solid; exit oracle Critical |
| Request / MTF | **5.0** | Policy clear; HTF re-eval and real fundamentals missing |
| Collections (array/map/matrix) | **8.0** | Broad v6 surface, soft-na, bridges |
| Plot / draw | **7.5** | Real side effects + GC; process-global state |
| Design / duplication | **6.5** | Mixin split good; dual formulas + sprawling advanced ta.* |
| Documentation (inline) | **7.5** | Best files excellent; README/ATR/exit gaps |
| Testability / corpus hardness | **8.0** | Soft paths enable corpus; can hide bugs |
| **Blended** | **~7.4** | Production-capable host, not full TV backtest clone |

---

## Prioritized recommendations

| Priority | Item | Effort | Rationale |
| --- | --- | --- | --- |
| **P0** | Pending `strategy.exit` (stop/limit/OCA); stop immediate close when not triggered | L | Critical TV/backtest correctness |
| **P0** | ATR → Wilder RMA in interpret + numba + Supertrend/KC dependents | M | Formula bug vs TV; dual-host can stay locked |
| **P1** | Unify EMA seed (SMA window) across full, inc, MACD, numba | M | Closes residual dual-path drift |
| **P1** | Document + optionally flag exit-oracle and ATR-EMA for hosts | S | Honesty / support |
| **P1** | Instance-scoped PlotRegistry / DrawingRegistry | M | Concurrency / multi-run isolation |
| **P2** | HTF `request.security` re-eval path or hard-na always without provider | L | MTF strategy truth |
| **P2** | `from_entry` leg selection; profit/loss as ticks; trail_* | M–L | Exit surface parity |
| **P2** | `strategy.default_entry_qty` use mark price | S | Sizing correctness |
| **P3** | Single pure-kernel module for TA shared by hosts | L | Maintainability |
| **P3** | Refresh `technical_submodules/README.md`; tag extension indicators | S | Contributor DX |
| **P3** | Fail-closed mode for soft-int strategy decl / request mocks | S–M | Production hosts |
| **P3** | OCA partial-fill reduce fixtures; inverse harmonic AEP phase-2 | M | Completeness |

---

## Evidence index (key files)

| Path | Role |
| --- | --- |
| [`…/builtins/strategy.py`](../../src/pynescript/ast/evaluator/builtins/strategy.py) | Broker, exit oracle, OCA, commission, pending fills (~2484 lines) |
| [`…/technical.py`](../../src/pynescript/ast/evaluator/builtins/technical.py) | Dispatch map for `ta.*` |
| [`…/technical_submodules/core.py`](../../src/pynescript/ast/evaluator/builtins/technical_submodules/core.py) | Inc kernels, helpers, EMA/RMA/RSI/ATR/ADX |
| [`…/technical_submodules/moving_averages.py`](../../src/pynescript/ast/evaluator/builtins/technical_submodules/moving_averages.py) | SMA/EMA/RMA/HMA/KAMA/… |
| [`…/technical_submodules/oscillators.py`](../../src/pynescript/ast/evaluator/builtins/technical_submodules/oscillators.py) | RSI/MACD/Stoch/CCI |
| [`…/technical_submodules/volatility.py`](../../src/pynescript/ast/evaluator/builtins/technical_submodules/volatility.py) | ATR full path EMA |
| [`…/request.py`](../../src/pynescript/ast/evaluator/builtins/request.py) | security policy, mocks, footprint |
| [`…/plotting.py`](../../src/pynescript/ast/evaluator/builtins/plotting.py) | PlotRegistry, visual packing |
| [`…/drawing.py`](../../src/pynescript/ast/evaluator/builtins/drawing.py) | DrawingRegistry GC, table merge stub |
| [`…/arrays.py`](../../src/pynescript/ast/evaluator/builtins/arrays.py) | Array soft-na / negative index |
| [`…/map.py`](../../src/pynescript/ast/evaluator/builtins/map.py) + [`map_evaluator.py`](../../src/pynescript/ast/evaluator/builtins/map_evaluator.py) | Map type + dispatch |
| [`…/matrix.py`](../../src/pynescript/ast/evaluator/builtins/matrix.py) + [`matrix_evaluator.py`](../../src/pynescript/ast/evaluator/builtins/matrix_evaluator.py) | Matrix type + v6 surface |
| [`…/base.py`](../../src/pynescript/ast/evaluator/builtins/base.py) | Dispatch, period coercion, na |
| [`…/__init__.py`](../../src/pynescript/ast/evaluator/builtins/__init__.py) | Mixin aggregate |
| [`compiler/numba_builtins.py`](../../src/pynescript/compiler/numba_builtins.py) | Dual-host formula mirror (ATR EMA) |

---

## Sampling method notes

- Deep read: strategy fill/exit/OCA, core incremental TA, oscillators, moving averages, ATR, request.security, arrays soft paths, map/matrix, plotting/drawing registries.
- Grep: `TODO|FIXME|pass|except Exception` under builtins; `process_pending_orders` / OCA / commission; numba ATR.
- Cross-check: parity_round8 strategy + interpret TA notes; missing_features; numerical_validation_report claims vs code.

---

*End of AGENT_03 audit.*
