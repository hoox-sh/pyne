# Copyright (C) 2024-2026 jango_blockchained
#
# This file is part of pynescript.
#
# pynescript is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pynescript is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: AGPL-3.0-or-later

# Object-mode compiled execution — Round 3

**Date:** 2026-07-28  
**Scope:** object-mode bar loop + `CompileStrategyBroker` hot path  
**Goal:** speed up UDT / map / drawing / strategy compile runs without semantic loss  

## Environment

- Python: repo `.venv` (NumPy 2.x)
- Workload: synthetic random-walk OHLCV, `n ∈ {1000, 5000}`
- Method: warm `CompiledScript.run` median of 21 reps after 5 warm-ups
- Scripts: UDT field plot, map put/get, market strategy entry/close, limit-entry strategy, label drawing

## Baseline (before)

| Script | n | Run median (ms) |
|--------|---:|----------------:|
| UDT | 1000 | 1.334 |
| MAP | 1000 | 1.060 |
| STRAT (market) | 1000 | 5.679 |
| STRAT_LIMIT | 1000 | 3.540 |
| DRAW | 1000 | 0.577 |
| UDT | 5000 | 7.137 |
| MAP | 5000 | 5.463 |
| STRAT (market) | 5000 | **71.3** |
| STRAT_LIMIT | 5000 | **41.9** |
| DRAW | 5000 | 3.123 |

### Profile notes (STRAT n=5000 × 10 runs)

1. `set_bar` + `process_pending_orders` every bar with **9× `float(arr[i])`**
2. `process_pending_orders` always walked pending keys even when empty
3. Market `entry` always ran `_classify_order_type` / `_opt_float` / `_is_na`
4. `_norm_dir` / `_emit` on every fill
5. Generated code always allocated `__drawings = []` and used `numba_store` for plots
6. UDT series used `np.empty(..., dtype=object)` (slower stores than Python lists)

## After

| Script | n | After (ms) | Before (ms) | Speedup |
|--------|---:|-----------:|------------:|--------:|
| UDT | 1000 | 0.520 | 1.334 | **2.6×** |
| MAP | 1000 | 0.773 | 1.060 | **1.4×** |
| STRAT | 1000 | 3.028 | 5.679 | **1.9×** |
| STRAT_LIMIT | 1000 | 1.459 | 3.540 | **2.4×** |
| DRAW | 1000 | 0.243 | 0.577 | **2.4×** |
| UDT | 5000 | 2.838 | 7.137 | **2.5×** |
| MAP | 5000 | 3.797 | 5.463 | **1.4×** |
| STRAT | 5000 | **15.9** | 71.3 | **4.5×** |
| STRAT_LIMIT | 5000 | **7.0** | 41.9 | **6.0×** |
| DRAW | 5000 | 1.226 | 3.123 | **2.5×** |

cProfile STRAT n=5000 × 10: **~2.0 s → ~0.40 s** wall (≈5×).

## Changes

### Files

| File | Change |
|------|--------|
| `src/pynescript/compiler/compiler.py` | `_emit_object_mode`: contiguity-checked asarray; `begin_bar`; UDT list series; skip `__drawings` when unused; bare `plot_i[i] =` rewrite; drop default `price=float(close)`; `uses_drawing` flag |
| `src/pynescript/compiler/strategy_broker.py` | `begin_bar`; empty-pending fast path; market entry/close fast paths; cheaper `_norm_dir` / `_is_na` / `_opt_float` / `_open_or_add` / `_commission`; no-copy `to_events` |
| `docs/perf_agent_objectmode_round3.md` | This report |

### Compiler object-mode emission

1. **`__strategy.begin_bar(i, o, h, l, c)`** — one call per bar instead of `set_bar` + `process_pending_orders` with repeated `float(...)`.
2. **No default `price=float(close_arr[i])`** on entry/close — broker uses `_mark` (close) set by `begin_bar`.
3. **Skip `__drawings` list** when no drawing APIs (`uses_drawing`); return `'__drawings': []` once.
4. **UDT series as `[None] * n_bars`** (string/color series stay `dtype=object` for unicode safety + existing tests).
5. **Bare plot stores** rewritten from `numba_store(plot_i, i, expr)` → `plot_i[i] = expr` (expression form kept for `fill(plot(...), ...)`).
6. **asarray only when not already C-contiguous float64** (engine path skips copy).

### Strategy broker hot path

1. **`begin_bar`** — direct float assign + conditional pending process.
2. **`process_pending_orders`** early-return when `pending_orders` empty.
3. **Market `entry`** skips classify/opt_float when `limit is None and stop is None`.
4. **`_norm_dir` / direction checks** short-circuit on `"long"` / `"short"`.
5. **`_is_na` / `_opt_float`** cheaper for None / float / int.
6. **`to_events()`** returns the live list (broker is single-use per run).

## Correctness

```text
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_compiler_objects.py \
  tests/test_compiler_strategy.py \
  tests/test_compiler_numba.py -q --tb=line
# 110 passed
```

Semantics preserved: UDT field plots, map put/get, strategy entry/close/order/cancel/limit/stop fills, drawing events, numeric mode still njit.

## Residuals / next opportunities

1. **`_emit` still dominates strategy** (~half remaining time): full event dict per fill. Compact internal tuples expanded in `to_events()` could help when event volume is huge.
2. **Market strategies that trade every bar** still allocate ~1 event dict/bar — fundamental Python cost.
3. **Object-mode still `import *` from `numba_builtins`** even without TA — selective imports would cut cold path slightly.
4. **UDT field plot double-lookup** (`p_arr[i]['x']` after assign) — local binding pass could shave more.
5. No Cython / numba object-mode hybrid attempted (out of scope).

## Summary

Largest wins on **strategy object mode (~4.5–6× @ 5000 bars)** via `begin_bar`, market-entry fast path, and skipping empty pending work. **UDT / drawing ~2.5×** from list series, direct plot stores, and lighter prolog. Public APIs unchanged; 110 compiler tests green.
