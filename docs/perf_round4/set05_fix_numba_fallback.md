# set05: Numba nopython → object-mode fallback

**Date:** 2026-07-29  
**Scope:** `src/pynescript/compiler/{compiler,engine,numba_builtins}.py`  
**Goal:** four set05 compile `RUN_FAIL`s that crashed under nopython typing must
complete under `Runtime.run(..., mode="compile")` (object mode OK).

## Corpus fails (before)

| Script | Error class |
| --- | --- |
| `set05/indicators/8109_ind_the_defibrillator_3.pine` | `non-precise type array(pyobject, 1d, C)` |
| `set05/indicators/8245_ind_aapp_with_alerts.pine` | `No implementation of function … isnan(unicode_type)` |
| `set05/indicators/8251_ind_aapp.pine` | same (`isnan(unicode_type)`) |
| `set05/indicators/8288_ind_efficient_trend_step_mod.pine` | same (`isnan(unicode_type)`) |

Repro: synthetic 50-bar OHLCV, `mode=compile`.

## Root causes (by class)

### Class A — `math.avg` mis-emitted as rolling SMA (8109)

**TV semantics:** `math.avg(number0, number1, …)` is the arithmetic mean of its
arguments (same as the interpreter’s `_builtin_math_avg`). Rolling window mean
is `ta.sma` / `math.sum`.

**Bug:** compile emit treated the 2-arg form as `SMA(source, length)`:

```python
# BEFORE (wrong)
numba_sma_inc(_arr(args[0]), period=args[1], …)
```

Defibrillator uses:

```pine
get = array.get(levels, j)           # float level
avg = math.avg(get, array.get(levels, j+1))
```

`get` was tracked as an object-dtype series (line/array handle neighborhood →
`udt_vars`), so the emit became:

```python
numba_sma_inc(get_arr, safe_period(udt_index(levels, j+1), 0), …)
```

`get_arr` is `dtype=object` → Numba `TypingError: non-precise type array(pyobject)`.

Script was already **object_mode=True** (drawings/UDT); the crash was **njit
helpers called from the Python bar loop** with illegal types — not a missed
object-mode decision.

### Class B — `fixnan` on color/string series (8245 / 8251 / 8288)

Pattern (AAPP / efficient trend step):

```pine
c = fixnan(ma > ma[1] ? color.blue : ma < ma[1] ? color.red : na)
plot(…, color=c)
```

**Bug:** `fixnan` always emitted `numba_nz(arg, 0.0)` with **no** string/color
guard (unlike `nz`, which already avoided `numba_nz` for non-numeric exprs):

```python
c_arr[i] = numba_nz(('#2962FF' if … else …), 0.0)
```

`numba_nz` does `np.isnan(val)` under `@njit` → **`isnan(unicode_type)`**.

Again: visitor already selected object mode (`string_series={'c',…}`); failure
is specialization of an njit helper on unicode, not numeric-mode entry.

## Fixes

### 1. `math.avg` → multi-arg mean (`compiler.py`)

- Multi-arg: pure numeric uses `np.add` / `np.divide` so the whole expr stays
  `_is_safe_numeric_expr` (`startswith("np.")`) and keeps the **warm njit** path.
- Object / unsafe args: `safe_float` mean, `object_mode=True`.
- Single arg: pass-through / `safe_float`.
- Rolling mean tests switched to `ta.sma`; multi-arg mean covered separately.

### 2. `fixnan` / `nz` string-safe path (`compiler.py` + `numba_builtins.py`)

- New pure-Python **`nz_py(val, replacement)`** — never calls `isnan` on
  str/dict/list; float NaN / `None` → replacement.
- `fixnan`: if object mode / non-numeric / color-hex ternary / string series →
  `nz_py(arg, None)` (colors) or `nz_py(arg, 0.0)` (numeric object mode).
- `nz`: same guards (plus stringy replacement); object mode always uses `nz_py`.

### 3. Object-dtype series → float materialize before njit TA (`compiler.py`)

`_materialize_series_source`: pure `*_arr` refs that are string/UDT object
series are rewritten through `store_src_py` into a float64 synthetic series so
kernels never see `array(pyobject)`.

### 4. Engine nopython recovery (`engine.py`)

- `CompilerVisitor(force_object_mode=…)` pins final emit to object mode.
- `compile_script`: after numeric emit, warm-up `execute(dummy…)`; on
  `_is_numba_nopython_failure` → **re-transpile with `force_object_mode=True`**.
- Pure numeric scripts that JIT cleanly keep the warm njit path and LRU cache.

## Recovery count

| Script | Before | After | Mode |
| --- | --- | --- | --- |
| 8109 defibrillator | RUN_FAIL pyobject | **OK** | object_mode |
| 8245 aapp+alerts | RUN_FAIL isnan unicode | **OK** | object_mode |
| 8251 aapp | RUN_FAIL isnan unicode | **OK** | object_mode |
| 8288 trend step mod | RUN_FAIL isnan unicode | **OK** | object_mode |

**Recovered: 4 / 4** (Runtime `mode=compile`, 50 bars).

## Tests

```text
PYTHONPATH=src python3 -m pytest \
  tests/test_compiler_numba.py \
  tests/test_compiler_objects.py \
  tests/test_compiler_strategy.py -q
# 167 passed
```

New / updated:

| Test | Intent |
| --- | --- |
| `TestCompileRound4IncKernels::test_hma_math_sum_avg_emit_inc` | `ta.sma` rolling + `math.avg` multi-arg; stays nopython |
| `TestNumbaObjectModeFallback::test_fixnan_color_uses_nz_py_not_numba_nz` | color `fixnan` → `nz_py` |
| `TestNumbaObjectModeFallback::test_math_avg_multi_arg_not_sma_on_handles` | mean of two series under drawings |
| `TestNumbaObjectModeFallback::test_nz_py_unicode_safe` | unit `nz_py` |

## Files changed

| File | Change |
| --- | --- |
| `src/pynescript/compiler/compiler.py` | `force_object_mode`; math.avg mean; fixnan/nz → `nz_py`; object-arr materialize |
| `src/pynescript/compiler/numba_builtins.py` | `nz_py` |
| `src/pynescript/compiler/engine.py` | nopython warm-up → object re-emit |
| `tests/test_compiler_numba.py` | math.avg / sma test split |
| `tests/test_compiler_objects.py` | `TestNumbaObjectModeFallback` |
| `docs/perf_round4/set05_fix_numba_fallback.md` | this report |

## Non-goals

- Full Pine `fixnan` history carry-forward for color series (still “nz stub”;
  no longer crashes).
- Expanding njit surface for unicode/color.
- Interpret-path changes.

## Summary

Failures were **not** “forgot object_mode” — all four scripts already emitted
the Python bar loop — but **njit helpers (`numba_nz`, `numba_sma_inc`) still
ran on unicode / pyobject**. Structural fix: detect object needs at emit
(`nz_py`, multi-arg `math.avg`, float materialize of object series) and a
safety-net re-emit when numeric warm-up hits a nopython TypingError. Warm
compile path for pure-numeric scripts preserved.
