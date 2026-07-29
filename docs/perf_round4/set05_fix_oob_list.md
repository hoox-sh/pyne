# set05: Fix compile-path OOB / list-vs-scalar / list÷int

**Date:** 2026-07-29  
**Scope:** Runtime `mode=compile`, 50 bars  
**Agent:** 3/4 OOB list assignment + series index + array.range

## Remaining fails (before)

| Script | Error |
| --- | --- |
| `set05/indicators/7020_ind_out_of_bounds_index.pine` | `list assignment index out of range` |
| `set05/indicators/7965_ind_out_of_bounds_index_2.pine` | same |
| `set05/indicators/8242_ind_leman_trend_indicator.pine` | `index 50 is out of bounds for axis 0 with size 50` |
| `set05/indicators/7303_ind_function_kernel_density_estimation_kde.pine` | `unsupported operand type(s) for /: 'list' and 'int'` |

## Root causes

### 1. `array.set` → raw `__setitem__` (7020 / 7965)

**Intentional TV docs demos** (source: pinescript-agents `arrays.md` OOB blocks):

```pine
a = array.new<float>(3)
for i = 1 to 3
    array.set(a, i, i)   // index 3 is OOB for size 3 (valid 0..2)
plot(array.pop(a))
```

On TradingView these **raise** a runtime error (documented “out of bounds”).

| Path | Behaviour (before) |
| --- | --- |
| Interpret | `_builtin_array_set` **grows** list to index (soft recovery, cap 1e6) |
| Compile | `a.__setitem__(int(i), i)` → hard `IndexError` |

Product goal for corpus Runtime: **soft-fail, do not crash** (align compile with interpret grow policy).

### 2. Series history upper bound (8242 LeMan)

```pine
high1 = high[-highestbars(high[1], Min)]
```

`highestbars` returns a non-negative lookback; unary minus yields a **negative** history offset (future bar). Emit was:

```python
base[__bar_idx - off] if __bar_idx >= off else np.nan
```

When `off < 0`, the guard is always true for `bar_idx >= 0`, and  
`__bar_idx - off = __bar_idx + |off|` can exceed `len(base)-1` near series end → NumPy OOB.

### 3. `array.range` miscompiled as Python `range` (7303 KDE)

Pine `array.range(id)` = **max − min** of array elements (statistical helper).

Compile emitted:

```python
_range = list(range(int(safe_float(_observations))))  # WRONG → list
_min = ... - _range / 2   # TypeError: list / int
```

Interpret path already implements max−min correctly in `_builtin_array_range`.

## Fixes

### `src/pynescript/compiler/numba_builtins.py`

- **`safe_list_set(arr, index, value)`** — grow undersized lists (same policy as interpret), no-op on negative / bad index / non-list.
- **`array_range(arr)`** — `safe_max(arr) - safe_min(arr)`; empty/na → `np.nan`.

### `src/pynescript/compiler/compiler.py`

| Site | Change |
| --- | --- |
| `array_set` emit | `safe_list_set(id, index, value)` instead of `.__setitem__` (3-arg form) |
| `array_range` emit | `array_range(id)` scalar; **never** `list(range(...))` |
| Fallback `*_range` | same scalar helper |
| `_history_subscript` | also require `(__bar_idx - off) < len(base)` so future refs past series end → na |

## Intentional demos noted

| File | Nature | Product handling |
| --- | --- | --- |
| `7020_ind_out_of_bounds_index.pine` | TV language-doc **error example** (v6) | Soft-grow via `safe_list_set` (matches interpret; no crash) |
| `7965_ind_out_of_bounds_index_2.pine` | Same demo, v5 | same |
| `8242` | Real indicator; uses negative history (lookahead-ish) | Upper clamp → na past last bar |
| `7303` | Real KDE lib demo | Correct `array.range` semantics |

**Note:** Soft-grow diverges from strict TV (which errors on OOB `array.set`). That is deliberate for corpus Runtime resilience and parity with the existing interpret recovery. Strict TV error simulation is not a goal for these demos in compile mode.

## Verification

### Corpus scripts (Runtime mode=compile, 50 bars)

| Script | Result |
| --- | --- |
| 7020 OOB index | OK, 50 bars, plot present |
| 7965 OOB index v5 | OK |
| 8242 LeMan Trend | OK, 4 plots |
| 7303 KDE | OK (`_range = array_range(_observations)`) |

### Tests

```bash
PYTHONPATH=src python -m pytest tests/test_compiler_numba.py::TestSet05OobListArithmetic -q
```

| Test | Intent |
| --- | --- |
| `test_safe_list_set_grows_on_oob` | helper unit |
| `test_array_range_is_max_minus_min_not_python_range` | helper unit |
| `test_array_set_oob_compile_grows_not_crash` | TV OOB demo compiles + runs |
| `test_array_range_compile_scalar_not_list` | KDE-style `_range / n` |
| `test_history_negative_offset_clamps_upper_bound` | LeMan pattern, 50 bars |
| `test_runtime_compile_oob_demos_and_kde` | Runtime host end-to-end |

## Files changed

| File | Change |
| --- | --- |
| `src/pynescript/compiler/numba_builtins.py` | `safe_list_set`, `array_range` |
| `src/pynescript/compiler/compiler.py` | emit + history clamp |
| `tests/test_compiler_numba.py` | `TestSet05OobListArithmetic` |
| `docs/perf_round4/set05_fix_oob_list.md` | this report |

## Non-goals / left alone

- Strict TV runtime.error on intentional OOB demos (soft recovery preferred)
- Matrix 4-arg `array_set` path still uses row `__setitem__` (unchanged)
- Interpret path already correct for set/range
- Grammar / generated ANTLR
