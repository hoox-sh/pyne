# Engine review + fine-tuning plan — 2026-11-18

- Date: 2026-11-18
- Repo: `pynescript` @ HEAD `9d6e7dd6` (`915b65ba` plotshape landed; re-measure recorded at `9ce57472`; HEAD later moved to `9d6e7dd6` with docs/tests-only commits)
- Scope: read-only review. This file is the ONLY artifact written. No source, tests, boards, or benchmarks were run or modified for this document.

## 1. Engine map

- `engine.py:1261` `_transpile_once` (parse → CompilerVisitor → `(code, titles, kinds, object_mode, attrs)`); `_DISK_META_VERSION = 62` at `engine.py:182`.
- `compile_script` `engine.py:1766`: memory cache → sanitize → disk-index fast path (`_compile_via_disk_index`, `engine.py:1685`) → `_transpile_once` → IR-share `_IR_CACHE` (max 64) → `_exec_generated` → `_warm_numeric_or_fallback` (`engine.py:1618`); numeric→object fallback also via `_recover_nopython_at_run` (`engine.py:804`).
- Library path `engine.py:1813-1827` (`if libraries:`): transpiles fresh, uses `ir_key=None`, NEVER touches `_COMPILE_CACHE`/`_IR_CACHE`/disk cache. Measured by prior session: `compile_script(src, libraries=[...])` ≈ 1.9 ms vs 0.007 ms warm cache hit (micro-benchmark, best-of-5, `.venv/bin/python`).
- `_object_mode_for_realtime` `engine.py:787-803`: re-transpiles on every `rt_first` call — per-tick cost. Card `pyne-cache-transient-object-mode-7ed4272f` (HQ Todo).
- Bar loop `runtime/host.py:2413`; history = newest-first `deque` (`runtime/series.py`, PineSeries) + chronological `current_series` lists, capped by `PYNE_SERIES_CAP` (default on); ring buffer (RingPineSeries `series.py:225`, `series_buffer.py`) behind `PYNE_SERIES_RING`, default OFF — REVIEW.md "one series representation" item still accurate.
- TA window materialization `technical_submodules/core.py:5482` (`_as_series`, `_SERIES_MAX=256`) with id()-keyed same-bar cache; reversed-list copies at `numeric.py:310,332`, `common.py:606`, `core.py:3098`, `core.py:5534-5545`.
- Parse cache exists (`helper.py:161-215`, `PYNE_PARSE_CACHE`, max 128).
- Library inline allowlist `_library_function_unsupported` `compiler.py:~11268`; `allowed_ta = {"sma","ema"}` `compiler.py:~11308` — all else fail-closed.
- Numeric varip routing: `compiler.py:1393-1397` sends any script with `varip_vars` to object mode (no numeric tick loop) — commit `755b2806` was the routing fix; card `pyne-numeric-varip-tick-loop-cur-3814706c` (Todo).
- `runtime.error`: numeric supports only single literal-string arg (`compiler.py:6528-6544` → `pine_raise_njit`); multi-arg/dynamic → object mode `pine_raise(args[0])` which DROPS `parts[1:]` (`numba_builtins.py:2349`); interpret joins with `format_log_message(*parts)` (`evaluator/builtins/logging.py:118-128,131-134`).

## 2. REVIEW.md / docs triage

STALE:
- "tests/test_set06_*.py raise FileNotFoundError" (all guarded, commit `01a11897`; `9d6e7dd6` fixed a vacuous early return + stale filename).
- "test_set06_pine_int_na.py is the only skip" (all siblings guarded).

STILL VALID (as of read-through):
- mypy `|| true` in `.github/workflows/ci.yml:64`.
- `docs/optimization_notes.md:47,53,296` still says 859 tests.
- Disk IR version mention v55 → now 62 (cosmetic).
- F2 (eager and/or), F3 (round ties).
- F5 (S002 only walks `ast.Name` funcs, `langserver/features/semantic_diagnostics.py:130-140`).
- F-LSP gaps, F-struct two-type-stories.
- Rank 3 (one series representation).
- Rank 2 partial (non-library cache exists; library path bypasses).
- Rank 6 (realtime snapshot costs).

LANDED (rank 1 numeric compile largely delivered):
- `885dc745` (input.* tokens), `a3c73539` (runtime.error numeric), `e342328b` (nz), `bc3e3012` (assigned hline/bgcolor), `0968048c` (bgcolor const-condition), `915b65ba` (plotshape numeric).

## 3. Fine-tuning candidates

Each item: what / where / why / cost / risk / verify.

### (a) Per-tick re-transpile in `_object_mode_for_realtime`
- Where: `engine.py:787-803`.
- What: cache the transpile for the `rt_first` path (mirror `_IR_CACHE` semantics).
- Why: re-transpiles on every realtime first tick — per-tick cost.
- Cost: S.
- Risk: low.
- Verify: targeted realtime test + before/after wall-time on a realtime tick-loop micro-bench.
- Card: `pyne-cache-transient-object-mode-7ed4272f`.

### (b) Library-path cache bypass
- Where: `engine.py:1813`.
- What: key `_IR_CACHE`/`_COMPILE_CACHE` on canonical library source identity (hash of normalized `(source, exports)`).
- Why: unlocks prewarm for library-heavy graphs; library path currently never touches caches.
- Cost: S/M.
- Risk: low-moderate (cache-key correctness — must include library source, not just main source).
- Verify: 1.9 ms → warm measurement + library inline tests (`tests/test_compiler_library_inline.py`) + IR-cache hit counter.

### (c) Numeric/object/error transpile scan of the four populations
- What: scan plotshape (3234 files) / input.* (1993) / runtime.error (752) / hline (527) with the bgcolor-scan method `_transpile_once`; re-measure harness exists at `.oo/proof/numeric-mode-remeasure-2026-11-17/scan_numeric_mode.py`.
- Why: answers "what unlocks numeric next".
- Cost: S (mechanical, ~8x bgcolor cost).
- Risk: low (read-only scan).
- Verify: scan report committed under `.oo/proof/`; counts per population.
- HQ card `pyne-numeric-object-error-transp-fa4960d2` already filed.

### (d) Interpret UDT-method-named-like-builtin misdispatch — REPRODUCED
- What: lib exports `method plot(Box this)`; `b.plot()` yields interpret series `{}` vs compile `[101.5, 102.5, …]` (venv, exit 0; compile side pinned by `tests/test_compiler_library_inline.py::test_library_udt_method_named_like_builtin_dispatches`).
- Dispatch sites: interpret `expressions.py:1436-1452` (`_method_call`), `expressions.py:1741` (`_invoke_method`), `names.py:170-260`.
- Fix: dispatch UDT-method lookup before builtin-name fallback (or qualify by receiver type).
- Cost: S/M. Correctness.
- Risk: moderate (dispatch-order change; must not break builtin fallback for genuine builtins).
- Verify: the repro plus existing library inline tests.
- Card: `pyne-interpret-side-builtin-name-19a9a794`.

### (e) Event-shape parity — raw `strategy.order` cover
- Compile `strategy_broker.py:744-852`: non-entry cover path calls `self.close(...)` AND emits trailing `"order"` fill event.
- Interpret `_fill_order` (`evaluator/builtins/strategy.py:2338+`) + `_close_position` (`:2757+`) emits `"close"` only on the is_entry reverse branch, NOT on raw-order cover → compile emits close, interpret doesn't.
- Cost: M.
- Risk: moderate (event stream is user-visible; parity tests needed both sides).
- Verify: compile-vs-interpret event-shape parity test on raw `strategy.order` cover scenario.
- Card: `pyne-compile-interpret-event-sha-b4da807f`.

### (f) Library kwargs + non-literal defaults (both currently fail-closed)
- Cards: `pyne-library-call-keyword-args-s-949224d4` / `pyne-library-non-literal-paramet-05c5d55b`.
- Cost: S each.
- Risk: low-moderate.
- Verify: library inline tests covering kwargs call and non-literal default cases.

### (g) Widen library `ta.*` allowlist beyond `{sma, ema}`
- Where: `compiler.py:~11308`.
- Cost: M.
- Risk: bounded by inline-safety audit of each `ta.*` kernel before admission.
- Verify: per-kernel inline-safety audit notes + library inline tests per admitted builtin.

### (h) Numeric varip tick loop
- Where: routing at `compiler.py:1393-1397` forces object mode for any script with `varip_vars`.
- Cost: L. Needs design.
- Risk: high (tick-loop semantics with varip state).
- Card: `pyne-numeric-varip-tick-loop-cur-3814706c`.

### (i) `_is_safe_numeric_expr` string/regex heuristic per emission
- Where: `compiler.py:3611`.
- What: candidate repeated-work hotspot — unmeasured.
- Cost: unknown (profile first). Do NOT touch before profiling.
- Risk: low if profiled first; unknown if guessed.
- Verify: profile before/after; only then consider caching the decision.

### (j) `PYNE_SERIES_RING` still default off
- What: flipping needs goldens re-run.
- Cost: L.
- Risk: high until goldens pass.
- Do NOT flip unverified.

### (k) Full-corpus nz unlock measurement — 0/200 transitions
- Result: full-corpus nz unlock measurement showed 0/200 transitions → likely descope card `pyne-full-corpus-nz-numeric-unlo-7cc4d5ef` instead of pursuing.

## 4. Ranked top-5 + recommendation

1. **(a) Transient object-mode realtime re-transpile cache** — small, contained, measurable, mirrors existing `_IR_CACHE`. **RECOMMENDED FIRST SLICE.**
2. **(b) Library-path IR cache key** — biggest lever for library-heavy compile latency.
3. **(c) Numeric/object/error scan of the four populations** — cheap, tells us where the remaining numeric unlocks are (executes an existing HQ card).
4. **(d) Interpret UDT builtin-name misdispatch** — correctness, repro in hand.
5. **(e) Event-shape parity for raw `strategy.order` cover**, or **(g) `ta.*` allowlist widening** — pick at slice time; both M.

**Recommendation — why (a) first:** it is the only candidate that is simultaneously small (S), low-risk, locally measurable (before/after wall-time on a realtime tick-loop micro-bench plus a targeted realtime test), and structurally guaranteed not to change semantics — it reuses the already-proven `_IR_CACHE` pattern rather than inventing a new mechanism. (b) is the biggest lever but touches cache-key correctness across the library path and needs IR-cache hit-rate instrumentation to prove out; (c) is cheap but is measurement, not a fix; (d) and (e) are correctness work that should land with their repro tests, not as a perf slice. Sequencing (a) first banks a low-risk win and builds the measurement habit (counter + micro-bench) that (b) then reuses.

On **(k)**: recommend descoping the nz full-corpus measurement card (`pyne-full-corpus-nz-numeric-unlo-7cc4d5ef`) — 0/200 observed transitions means the expected payoff does not exist; pursuing it would spend corpus-run budget to re-confirm a negative.

## 5. Not verified (verbatim)

- no corpus runs
- no pytest run
- both micro-benchmarks are single sessions (1.9ms/0.007ms)
- 1.13ms transient figure quoted from HQ card, not re-measured
- PYNE_SERIES_RING=1 untested against goldens
- disk-cache hit rate unmeasured (no instrumentation)
- _is_safe_numeric_expr cost unprofiled
- REVIEW.md F2/F3 confirmed by reading only
- whether the compile cache covers library IR after (b) lands is projected, not measured
- re-measure 2026-11-17/18 figures (29/1516/1124 all-six; 23651 corpus) taken from proof REPORT.md, not re-run

## Footer

State: read-only review; no source/boards modified; only artifact = this file.
