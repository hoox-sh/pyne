# AGENT 04 — Compile engine + IR (Round 8)

**Role / ID:** 04 — Compile engine packing, normalize, object_mode surface, cache recovery  
**Date:** 2026-08-04  
**Owns:** `src/pynescript/compiler/engine.py` (+ `tests/test_compiler_engine_r8.py`)

## What you did (files touched)

| File | Change |
|------|--------|
| `src/pynescript/compiler/engine.py` | Result packing / normalize / coerce fixes; legacy 5-arg execute recovery; title uniquify |
| `tests/test_compiler_engine_r8.py` | **New** goldens (19 cases) for packing, normalize, dup titles, arity, envelopes |

### Bugs fixed

1. **Duplicate plot titles silently dropped series (P1p / structural_only)**  
   Numeric emit returns a tuple of arrays; `_pack_result` previously did `out[title] = …`, so two `plot(..., title="x")` kept only the **last** series. Interpret Runtime uniquifies to `x` / `x_2`.  
   **Fix:** `_pack_plot_sequence` + `_uniquify_series_key` (same `base_2`, `base_3` rule as `backend.runtime`). Titles are also uniquified at transpile collect so `CompiledScript.plot_titles` matches `run()` keys.

2. **Extra plot arrays beyond `plot_titles` were dropped**  
   If tuple arity > title list length, trailing series vanished.  
   **Fix:** emit synthetic `plot_{i}` keys for extras.

3. **List-of-arrays return collapsed to one 2d `"plot"` key**  
   Only `tuple` was treated as multi-plot; a `list` of ndarrays hit `_normalize_result` → `items()` fail → single coerced array.  
   **Fix:** `_is_plot_sequence` treats tuple and list-of-series as multi-plot.

4. **Empty / blank titles became `""` map keys**  
   **Fix:** fall back to `plot_{i}` when title is missing/blank.

5. **`None` cells in list series**  
   Explicit list coerce maps `None` → `nan` (no zero fill). Object string columns that cannot cast stay non-numeric (no silent zeros).

6. **Legacy 5-arg `execute_script_compiled` (no `time_arr`) hard-failed**  
   Stale disk IR from pre-`time_arr` engines raised TypeError on run.  
   **Fix:** `_call_execute_with_recovery` retries without `time` on arity TypeError after Numba cache recovery.

### Not changed (exclusive ownership)

- Compiler visitor emit / `_unique_plot_title` on `plot()` — Agent 03  
- Numba kernels — Agent 02  
- Runtime host JSON packing — Agent 11  
- Plot/fill/hline collectors — Agent 07  

## Before / after (structural proof)

**Minimal repro (duplicate titles):**

```pine
//@version=5
indicator("dup")
plot(close, title="x")
plot(open, title="x")
plot(high, title="y")
```

| Mode | series keys (before) | series keys (after) |
|------|----------------------|---------------------|
| interpret | `x`, `x_2`, `y` | unchanged |
| compile | `x`, `y` (**first series lost**) | `x`, `x_2`, `y` |

Runtime host check: interpret ↔ compile key sets + values match after fix.

## Tests run + pass/fail

```bash
PYTHONPATH=src:. .venv/bin/python -m pytest tests/test_compiler_engine_r8.py -q --tb=short
# 19 passed

PYTHONPATH=src:. .venv/bin/python -m pytest \
  tests/test_compiler_numba.py::TestCompileEngineRound6 -q --tb=line
# 9 passed
```

## Residual / handoff

| Item | Owner |
|------|--------|
| **Object-mode dict emit** still builds `{title: plot_i}` with **raw** visitor titles. If `plot()` does not call `_unique_plot_title`, object-mode Python dict literals collapse duplicates at construction time — engine never sees the dropped array. Numeric path is fixed; object path needs visitor uniquify on `plot()` (and ideally all plot-like collectors). | **03** |
| Value MISMATCH on TA (rsi/hma/supertrend/…) is kernel/visitor, not packing. | **02 / 03 / 05** |
| Fill / bgcolor / hline one-sided keys remain harness structural noise unless collectors align. | **07** |
| Host envelope (`series` JSON, `time_arr`) remains Runtime. | **11** |

## Verdict

**win** — proven structural fix: duplicate-title compile path no longer drops series; list packing and legacy arity recovery hardened; 19 new goldens green; Round 6 engine suite still green.
