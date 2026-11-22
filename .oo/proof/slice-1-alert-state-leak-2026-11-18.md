# Slice 1 gate fix — object-mode alert-state cross-run leak (2026-11-18)

Card: slice-1-2-cache-transient-object-63f9d3da (Slice 1/2, oo-spec-2)
Author: oo-spec-2 · Scope: fix gate-review finding only; no commits, no pushes, no touch to library path / ring buffer / numeric routing.

## Finding

Generated object-mode modules carry module-level mutable state `__alerts = []` and
`__alert_fire_bars = {}` (emitted in `_emit_object_mode`, compiler.py). Every
`execute_script_compiled` call appended into the same module-global list, and
`_normalize_result` copies `__alerts` into the result dict. A shared CompiledScript
(in-process `_COMPILE_CACHE` / `_IR_CACHE`, or disk-rehydrated) therefore leaked
run-1 alerts into run-2 results, and `__alert_fire_bars` could suppress a fresh
once-per-bar alert while returning the stale prior event.

Reproduced before the fix (object_mode=True, compile cache warm):

    run1: [(0, 1700000000000)]          # BARS=1, alert("once", alert.freq_once_per_bar)
    run2: [(0, 1700000000000)]          # stale run-1 event returned; run-2 event suppressed
    freq_all repro: run2 returned 2x alerts (run1 + run2) — see test_compiler_alerts.py::TestAlertStateAcrossRuns

## Fix

`src/pynescript/compiler/compiler.py` — in the object-mode prologue of
`execute_script_compiled` (right after `__drawings = []`):

    global __alerts, __alert_fire_bars
    __alerts = []
    __alert_fire_bars = {}

Seam chosen: the emitted per-run prologue, not the caches. It covers in-process
(`_COMPILE_CACHE`, `_IR_CACHE`, `_OBJECT_MODE_RT_CACHE`), disk rehydration, and
one-shot execs alike, and does not change single-run semantics. Mirrors the
existing `_emit_once_flags` pattern for module-level once flags. Rebinding per run
(not mutating in place) so a reference held by an in-flight caller of run N is never
mutated by run N+1.

`src/pynescript/compiler/engine.py` — docstring on `_object_mode_for_realtime`
corrected: cached instance is shared across ticks; per-run mutable state is
re-initialized inside `execute_script_compiled` each call (previously claimed the
instance was "never mutated", which was false). `_object_mode_rt_key`'s docstring
made no such claim; left as-is.

## Verification (all exit 0 unless noted)

- New regression tests tests/test_compiler_alerts.py::TestAlertStateAcrossRuns (3 tests):
  FAIL before fix (accumulation 16 vs 8; stale 1700000000000 returned for t2=1800000000000;
  message list mismatch) — PASS after fix.
- python -m pytest tests/test_engine_realtime_cache.py -q          -> 6 passed
- python -m pytest tests/ -k 'realtime or object_mode' -q          -> 147 passed, 5291 deselected
- python -m pytest tests/test_compiler_engine_r8.py tests/test_compiler_engine_edges_coverage.py tests/test_compiler_numba.py tests/test_compiler_realtime.py -q -> 281 passed
- python -m pytest tests/ -k 'alert' -q                            -> 55 passed
- ruff 0.15.20 check changed files                                 -> All checks passed
- ruff 0.15.20 format --check changed files                        -> 3 files already formatted

## Not done / notes

- `_DISK_META_VERSION` left at 62 (as expected for this slice). Consequence: a warm
  on-disk IR index written before this fix still rehydrates the pre-fix module for
  the same source (guard is `v == _DISK_META_VERSION`), so the leak persists on those
  machines until `clear_disk_compile_cache()` / purge of PYNE_COMPILE_CACHE_DIR, or a
  version bump. The file's own comment says to bump on generated-IR semantics change;
  bump to 63 is the one-line remedy if the lead wants fleet-wide invalidation. Tests
  above pass either way because the test helpers clear the disk cache.
- Slice 2/2 (library-path cache keying) untouched; no commits/pushes made;
  pre-existing dirty files untouched.
