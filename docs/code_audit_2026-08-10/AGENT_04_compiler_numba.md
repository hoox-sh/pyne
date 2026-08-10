# AGENT 04 — Compiler & Numba Path Audit

**Date:** 2026-08-10 
**Scope:** `src/pynescript/compiler/{engine,compiler,numba_builtins,strategy_broker,__init__}.py` 
**Related tests (read-only):** `tests/test_compiler_*.py`, `tests/test_interp_compile_parity.py` 
**Mode:** Read-only audit (no code changes)

---

## Executive summary

The compile path is a mature **source-to-source** pipeline: Pine AST → Python bar-loop module → optional Numba nopython JIT, with automatic **object-mode** re-emit when features or typing force pure Python. The engine layer (`engine.py`, ~1.4k LOC) is the strongest subsystem: typed errors, dual-key LRU + IR sharing, disk IR + Numba `.nbi`/`.nbc` corruption recovery, prewarm hooks, and careful plot packing.

The emitter (`compiler.py`, ~7.8k LOC) is a single `CompilerVisitor` that both **analyzes** and **emits** via string concatenation. It works and has absorbed many parity fixes (Pine `na` compares, UDF call-site state clones, `request.security` no-invent policy, strategy broker wiring), but remains a **god-object** with fragile string heuristics for numeric safety and mode selection.

`numba_builtins.py` (~5.2k LOC) is a large, well-commented kernel library: full-window + incremental `*_inc` TA, Pine-aware `numba_pine_eq`/`ne`, and object-mode `safe_*`/`na_num`. Constraints for nopython are documented at module top and on hot kernels.

`strategy_broker.py` (~1.1k LOC) is a deliberate **lightweight** compile-path broker aligned with the **interpret oracle**, not full reference-platform (immediate `strategy.exit` fill, simplified supertrend-style dual-host choices elsewhere). Commission, pyramiding, OCA, default qty, and pending OHLC fills are real; **risk.*** is a no-op; trade-query APIs are mostly stubs; **event `bar_time` is never wired** from `time_arr`.

**Bottom line:** Numeric indicators on the nopython path are in good shape for the always-on parity smoke set. Residual risk concentrates on (1) object-mode result packaging edge cases, (2) strategy surface incompleteness vs production expectations, (3) disk-cache invalidation discipline, and (4) long-term maintainability of the monomorphic visitor.

**Overall score: 7.0 / 10**

---

## Critical findings

None that reliably produce silent wrong numeric plots on pure-nopython scripts covered by the smoke harness. Residual issues below are **High** because they either drop series, zero strategy metadata, or leave operators with stale IR.

---

## High findings

### H1 — Object-mode `plot()` does not uniquify titles (series can vanish)

| Field | Detail |
|-------|--------|
| **Where** | `compiler.py:4233–4279` (`plot` emit); contrast `hline`/`fill` at `4202`, `4227` |
| **What** | `_unique_plot_title` is used for `hline`/`fill` but **not** for `plot()`. Numeric path is rescued by engine packing (`engine.py:661–673`, `_pack_plot_sequence` + title uniquify at `_transpile_once` ~946–953). Object mode embeds raw titles into a Python dict literal (`compiler.py:955–964`). Duplicate keys collapse at construction time; `_normalize_result` never sees the dropped series. |
| **Impact** | Strategy / UDT / drawing scripts with two `plot(..., title="x")` keep only the last series — interpret↔compile key MISMATCH or silent loss. Prior R8 handoff (`docs/parity_round8/AGENT_04_compile_engine.md`) already called this out; **plot path still unfixed**. |
| **Fix** | Call `title = self._unique_plot_title(title)` before `self.plots.append` in `plot` (and any other plot-like series collectors). Add object-mode golden with duplicate titles. |

### H2 — Strategy events always get `bar_time=0` on compile path

| Field | Detail |
|-------|--------|
| **Where** | Emit: `compiler.py:929–932` — `__strategy.begin_bar(__bar_idx, o, h, l, c)` with no `bar_time`. Broker: `strategy_broker.py:267–287` defaults `bar_time=0`; events store `self._bar_time` at `659–660`. Engine passes real `time_arr` into execute (`engine.py:650–658`). |
| **What** | Host can supply correct bar-open ms, and bare `time` lowers to `time_arr[__bar_idx]`, but the broker never receives it. |
| **Impact** | Compile `__events` / Runtime `events` from compile mode have `bar_time: 0` for every order — bad for JSON export, multi-script merge, and any consumer keyed by time. Tests assert type is int (`test_compiler_strategy.py:386+`) more than value parity with OHLCV. |
| **Fix** | Emit `begin_bar(..., bar_time=int(time_arr[__bar_idx]))` (or float-safe cast). Add golden that entry event `bar_time` matches bar open ms. |

### H3 — `strategy.risk.*` is a deliberate no-op on compile

| Field | Detail |
|-------|--------|
| **Where** | `compiler.py:5799` — `if method.startswith("risk_"): return ""` |
| **What** | Risk declarations emit nothing; broker has no max drawdown / max position / allow_entry enforcement. |
| **Impact** | Scripts that rely on risk caps appear to “work” in compile mode with **unconstrained** fills vs interpret (if interpret enforces) or vs reference Pine. Backtest equity can be wildly optimistic. |
| **Fix** | Either fail closed (surface `nopython_fallback_reason`-style host warning / refuse compile for risk scripts) or implement risk state on `CompileStrategyBroker` shared with interpret. |

### H4 — Disk IR cache invalidation is manual-only (`_DISK_META_VERSION`)

| Field | Detail |
|-------|--------|
| **Where** | `engine.py:167–171` (`_DISK_META_VERSION = 5`); meta check `1060–1061` |
| **What** | Source→IR index is keyed by source hash + meta version. Compiler **logic** fixes that change generated code for the same Pine source do **not** auto-invalidate disk hits unless version is bumped. |
| **Impact** | Deploy/restart with old disk cache can serve **stale wrong IR** after a compiler bugfix if ops forget to bump version or clear `PYNE_COMPILE_CACHE_DIR`. |
| **Fix** | Include a hash of emitter/builtins module versions (or git SHA / content hash of `compiler.py`+`numba_builtins.py`) in meta `v` or a separate `emit_fingerprint` field. |

### H5 — Strategy trade-query surface is mostly zeros

| Field | Detail |
|-------|--------|
| **Where** | `compiler.py:5871–5900` (`_emit_strategy_trade_query`) |
| **What** | `opentrades.entry_price` / `size` / `entry_id` partially real; most other `opentrades_*` / `closedtrades_*` return `0.0` / `0` / `''`. |
| **Impact** | Compile path for strategies that branch on closed trade stats / entry bar indices will **diverge** from interpret without raising. Silent logic change, not a crash. |
| **Fix** | Track closed-trade list on broker (even simplified) or force host note / expected residual in corpus. |

---

## Medium findings

### M1 — Monolithic `CompilerVisitor` (emit pipeline design)

| Field | Detail |
|-------|--------|
| **Where** | `compiler.py` entire file (~7840 lines); single class from ~392 |
| **What** | Mode selection, UDF free-var analysis, TA lowering, strategy, drawing, security, control flow, and emit all live in one visitor. String-level helpers (`_is_safe_numeric_expr` ~2004–2158, `_looks_like_numeric_expr` ~6141–6168) drive object vs numeric decisions. |
| **Impact** | High regression risk; hard to unit-test lowering in isolation; new APIs tend to copy-paste call handlers. Comment at top admits size by design. |
| **Fix** | Split into analyze phase (typed plan) + emitters per namespace (`ta`, `strategy`, `array`, …). Keep string emit initially if needed. |

### M2 — Non-nopython warm-up failures are deferred

| Field | Detail |
|-------|--------|
| **Where** | `engine.py:1251–1259` |
| **What** | Typing / nopython failures re-emit object mode; **other** exceptions on dummy OHLCV return the numeric dispatcher unchanged. |
| **Impact** | First real run may fail late; rare shape-dependent bugs slip past warm-up. Documented intentionally — still an operational footgun for `mode=auto`. |
| **Fix** | Optionally re-warm with host-provided sample bars; classify more Numba runtime errors as fallback. |

### M3 — `request.security` compile policy is intentionally incomplete

| Field | Detail |
|-------|--------|
| **Where** | Module doc `compiler.py:40–41`; logic `6290–6435`, call site ~4634–4650 |
| **What** | Same-symbol simple OHLCV (and HA transform) passthrough; foreign / complex expr → `na`. |
| **Impact** | Correct non-invention (good), but many multi-TF scripts compile “successfully” with flat na series — easy to mistake for real MTF. |
| **Fix** | Host flag `security_lowered_as_na` or refuse compile when non-passthrough security is detected. |

### M4 — Stop-limit pending fills ignore open-path price quality

| Field | Detail |
|-------|--------|
| **Where** | `strategy_broker.py:397–405` (`_trigger_price` stop-limit returns bare `lim`) |
| **What** | Limit/stop marketable paths use open-aware prices; stop-limit always fills at limit without open gap adjustment. |
| **Impact** | Small PnL divergence vs interpret/reference on gapped bars. |
| **Fix** | Align with interpret `process_pending_orders` fill price helpers. |

### M5 — `qty_percent` / trailing exits not fully applied

| Field | Detail |
|-------|--------|
| **Where** | Exit param map includes `qty_percent` (`compiler.py:5838`); `close()` uses absolute qty / full position (`strategy_broker.py:807–839`). No trail attributes on `PendingOrder`. |
| **Impact** | Partial exits by percent and trailing stops silently wrong or ignored (`**_kwargs`). |
| **Fix** | Resolve percent against position size in `close` / pending exit path. |

### M6 — Object-mode coercion can hide type bugs (`safe_float` / `na_num`)

| Field | Detail |
|-------|--------|
| **Where** | `numba_builtins.py:1465–1539` |
| **What** | Almost anything becomes `nan` rather than raising. |
| **Impact** | Corpus green + wrong zeros/nans vs interpret TypeError or different branch. Tradeoff for resilience; still a correctness risk for UDT mis-stores. |
| **Fix** | Debug flag `PYNE_STRICT_COERCE=1` to raise; or count coerce-to-nan hits in host diagnostics. |

### M7 — Supertrend is dual-host simplified (not reference Pine ratchet)

| Field | Detail |
|-------|--------|
| **Where** | `numba_builtins.py:4880–4912` |
| **What** | Documented: mid ± factor×ATR, direction from close vs mid; no band ratchet. Matches interpret BasicIndicators; not reference Pine. |
| **Impact** | External users comparing to reference charts will mis-trust “parity.” Internal interp↔compile OK (`supertrend.pine` in always-on smoke). |
| **Fix** | Keep dual-host; document in public COMPATIBILITY; optional reference-parity mode later. |

### M8 — Same-id market re-entry overwrites without realizing PnL

| Field | Detail |
|-------|--------|
| **Where** | `strategy_broker.py:495–498`, `529–537` |
| **What** | Intentional interpret oracle: replace open leg without close event / PnL. |
| **Impact** | Equity and trade stats diverge from reference; OK for dual-host if interpret matches. |
| **Fix** | Keep + document; add explicit comment in public strategy broker docs. |

---

## Low findings

### L1 — `from numba_builtins import *` in generated modules

Pollutes generated namespace; name collisions with user series are mitigated by `_safe_ident` / chart mangling but remain a latent footgun (`compiler.py:794`, `840`).

### L2 — `CompileWarmupError` reserved unused

`engine.py:155–156` — dead public surface; either wire forced-fail mode or remove from conceptual API.

### L3 — Market pending fill price is bar **close**

`_trigger_price` market branch `strategy_broker.py:377–378` returns `close`. Fine for next-bar process after `order()`, but diverges from brokers that fill market at open.

### L4 — Prewarm sets `_BUILTINS_WARMED` before success path completes

`engine.py:468–478` marks warmed True then best-effort warm; transient failure skips retry until process restart / force. Acceptable; document for ops.

### L5 — `run_script` annotation understates object extras

`engine.py:1412` return type `dict[str, np.ndarray]` but object mode adds lists/scalars.

### L6 — Heuristic `_looks_like_numeric_expr` treats any bare name as numeric

`compiler.py:6166–6167` — can keep stringy paths from flipping to object early, partially offset by other checks.

---

## Documentation

| Area | Assessment |
|------|------------|
| Package / engine module docs | **Excellent** — pipeline diagram, cache layers, error contract, env knobs (`engine.py:20–97`, `__init__.py:20–50`). |
| `CompilerVisitor` class doc | **Good** — responsibilities, force_object_mode, key attributes (`compiler.py:392–422`). |
| Emit leaf methods | **Uneven** — complex helpers (`_materialize_series_source`, `_clone_state_arg_for_call`, `_history_subscript`, security, pine eq) are well commented; many `visit_*` / namespace stubs are one-liners. |
| Numba constraints | **Strong** at module top and on EMA/RSI/ATR/inc kernels; dual-host notes present. |
| Strategy broker | **Good** event shape, commission model, pyramiding notes. |
| Gap | No single “when does force_object_mode fire?” decision table in-repo beyond scattered comments. Missing inline note on **plot title uniquify asymmetry** (hline/fill vs plot). |

**Doc score: 7.5 / 10**

---

## Modernization opportunities

1. **Phased compilation** 
 - Phase A: typed feature analysis (object required? strategy? security?) without emit. 
 - Phase B: lower to a small IR (series load/store, call, branch). 
 - Phase C: backend emit (numeric njit / object / future). 
 Enables cheaper nopython fallback (re-emit without full re-parse) and testable analysis.

2. **Structured codegen** 
 Replace string glue with `ast` builders or a tiny SSA of Python statements; validate syntax before `exec`.

3. **Shared strategy core** 
 Factor fill/PnL into one module used by interpret and compile to prevent dual-path drift (risk, exits, trade lists).

4. **Caching** 
 - Emit fingerprint in disk meta (H4). 
 - Consider content-addressed IR only (already partly via `ir_key`) and drop source meta when fingerprint mismatches. 
 - Optional: `numba.core.caching` location under deploy volume only (already env-driven).

5. **Object-mode speed** 
 For hot numeric islands inside object scripts, emit nested `@njit` helper functions for pure float loops (hybrid), or vectorize TA outside bar loop when dependency DAG allows.

6. **Parallel bars** 
 Generally unsafe (series state); only for independent pure functions / multi-symbol batch — low priority.

7. **mypyc / Cython** 
 Better spent on **interpret** `PineSeries` / dispatch (see prior R7 phase-3 notes) than on already-Numba’d kernels.

---

## Scorecard

| Dimension | Score (1–10) | Notes |
|-----------|--------------|-------|
| Correctness (numeric nopython) | **8** | Smoke TA parity + pine eq/div/history hardening |
| Correctness (object / strategy) | **6** | Title collapse, risk no-op, trade stubs, bar_time |
| Interp ↔ compile divergence control | **7** | Explicit oracle alignment; security na policy; residual stubs |
| Numba safety / object-mode traps | **7.5** | Warm fallback, cache purge, safe_*; silent nan coerce |
| Engine / cache design | **8.5** | LRU + IR + disk + prewarm + recovery |
| Emit pipeline maintainability | **5** | Monolith visitor, string heuristics |
| Broker fill fidelity | **7** | Solid market/limit/stop/OCA; exit = interpret immediate |
| Inline documentation | **7.5** | Module-level excellent; leaf gaps |
| Test coverage (compiler surface) | **7.5** | engine R8, numba, strategy, objects, parity smoke |
| **Overall** | **7.0** | Production-usable for indicators; strategy/object caveats |

---

## Prioritized recommendations

| Priority | Item | Effort | Payoff |
|----------|------|--------|--------|
| **P0** | H1: `_unique_plot_title` on `plot()` (+ test object-mode dups) | S | Stops silent series loss |
| **P0** | H2: pass `time_arr[__bar_idx]` into `begin_bar` | S | Event time correctness |
| **P1** | H4: emit fingerprint in disk meta / auto-invalidate | M | Safe deploys after compiler fixes |
| **P1** | H3: fail closed or implement `strategy.risk` | M | Avoid false-confidence backtests |
| **P1** | H5: closed/open trade list (minimal) for query APIs | M | Strategy logic parity |
| **P2** | M1: split visitor by namespace + analyze phase | L | Maintainability |
| **P2** | M2: broader warm-up fallback classification | S | Fewer late compile failures |
| **P2** | M3: surface security-as-na to host | S | Operator clarity |
| **P3** | M4–M6, L* polish | S–M | Edge fidelity |
| **P3** | Hybrid njit islands in object mode | L | Perf without full numeric eligibility |

---

## Architecture snapshot (reference)

```
source
 → sanitize (cache miss)
 → parse + CompilerVisitor
 ├─ numeric: @njit execute_script_compiled → plot tuple
 └─ object: Python loop + optional CompileStrategyBroker → dict
 → exec / disk import
 → warm njit; TypingError → force_object_mode re-emit
 → CompiledScript.run → _pack_result / _normalize_result
```

**Key files (absolute paths):**

- `/mnt/data/home/jango/Git/pynescript/src/pynescript/compiler/engine.py`
- `/mnt/data/home/jango/Git/pynescript/src/pynescript/compiler/compiler.py`
- `/mnt/data/home/jango/Git/pynescript/src/pynescript/compiler/numba_builtins.py`
- `/mnt/data/home/jango/Git/pynescript/src/pynescript/compiler/strategy_broker.py`
- `/mnt/data/home/jango/Git/pynescript/src/pynescript/compiler/__init__.py`

**Evidence anchors (selected):**

```4233:4279:src/pynescript/compiler/compiler.py
 if func_name == "plot":
 # Match Runtime interpret packaging: untitled plots use plot_0, plot_1, …
 title = f"plot_{len(self.plots)}"
 ...
 self.plots.append({"expr": series_expr, "title": title})
```

```929:932:src/pynescript/compiler/compiler.py
 lines.append(
 " __strategy.begin_bar("
 "__bar_idx, "
 "open_arr[__bar_idx], high_arr[__bar_idx], "
 "low_arr[__bar_idx], close_arr[__bar_idx])"
 )
```

```1222:1282:src/pynescript/compiler/engine.py
def _warm_numeric_or_fallback(...):
 ...
 # nopython → object re-emit; non-nopython errors deferred
```

```2527:2543:src/pynescript/compiler/numba_builtins.py
def numba_pine_eq(a, b):
 """Pine ``==``: ``na==na`` is True; any other comparison with ``na`` is False."""
```

```5799:5818:src/pynescript/compiler/compiler.py
 if method.startswith("risk_"):
 return "" # risk.* declaration no-op in compile path for now
 ...
 "exit": "close", # simplify exit → close
```

---

## Test context (expected behavior)

| Suite | Role |
|-------|------|
| `tests/test_compiler_numba.py` | Transpile/run TA under njit; Runtime `mode=compile` |
| `tests/test_compiler_engine_r8.py` | Packing, uniquify, coerce, arity recovery, cache corruption |
| `tests/test_compiler_strategy.py` | Broker events, limit fills, exit fill price vs interpret oracle |
| `tests/test_compiler_objects.py` | Object-mode UDT/map/drawing surface |
| `tests/test_interp_compile_parity.py` | Always-on smoke set (SMA/EMA/RSI/ATR/BB/supertrend/…) |

---

*End of AGENT_04 compiler/numba audit.*
