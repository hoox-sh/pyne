# Copyright (C) 2024-2026 jango_blockchained
#
# SPDX-License-Identifier: AGPL-3.0-or-later

# AGENT 01 — T2 leftover: incremental `ta.nvi` / `ta.pvi`

**AGENT_ID:** 01
**ROLE:** Residual incremental TA — interpret (PERF + CORRECTNESS)
**BASE_SHA:** `ffd43641`
**Date:** 2026-08-16
**Worktree:** `/mnt/data/home/jango/Git/pynescript` (shared workspace)

## 1. Scope & files

| File | Change |
| --- | --- |
| `src/pynescript/ast/evaluator/builtins/technical_submodules/volume.py` | `_nvi_inc_update` / `_pvi_inc_update`; wire `_builtin_ta_nvi` / `_builtin_ta_pvi` behind `_use_incremental_ta` + last-sample |
| `tests/test_ta_incremental.py` | Append nvi/pvi goldens (inc ≡ full last value, dual call-site, Runtime on/off) |
| `docs/gaps_close_2026-08-16/AGENT_01_nvi_pvi.md` | This report |

**Owns (per prompt):** residual T2 `ta.nvi` / `ta.pvi` full-list recompute every bar.  
**Does not:** Flask, pynets, strategy, supertrend, plot keys, `request.*`, compatibility docs.  
**Numba:** skipped — `compiler.py` / `numba_builtins.py` do not emit `nvi`/`pvi` (no `numba_nvi*` / `numba_pvi*`).

## 2. Changes (what / why)

R9 left `ta.nvi` / `ta.pvi` as O(n) prefix rebuilds each bar (O(n²) over a stream). Same call-site pattern as `_obv_inc_update` / `_wad_inc_update`:

- `_use_incremental_ta()` gate (`PYNE_TA_INCREMENTAL=0` keeps the full list path)
- `_ta_next_slot()` + `_ta_state_bucket()`
- last sample via `_series_last` / `_context_source` / `_as_series_or_raw(..., last_sample_ok=True)`
- incremental returns the current **scalar**; full path stays a list (non-bar-mode / flag-off)

| Kernel | State key | Complexity | Semantics (match full last value) |
| --- | --- | --- | --- |
| `_nvi_inc_update` | `("nvi", slot)` | O(1)/bar | Seed `1000.0` on bar 0; later `nvi *= (1 + close_change)` when `vol < prev_vol` |
| `_pvi_inc_update` | `("pvi", slot)` | O(1)/bar | Seed `1000.0` on bar 0; later `pvi *= (1 + close_change)` when `vol > prev_vol` |

`close_change = (c - prev_c) / prev_c` if `prev_c != 0` else `0`. Forms: 0-arg (chart close+volume) or 2-arg series. Empty chart volume → 0 contribution. Missing / non-numeric **close** skips the increment (not coerced to 0).

## 3. Benchmarks

Bar-walk growing prefix, n=2000, median of 3, `PYTHONPATH=src:.`, CPython 3.14.6.

| Kernel | Full recompute | Incremental | Speedup |
| --- | ---: | ---: | ---: |
| `nvi` | 246.3 ms | 14.6 ms | **~16.9×** |
| `pvi` | 256.3 ms | 16.2 ms | **~15.8×** |

## 4. Tests run

```bash
PYTHONPATH=src:. .venv/bin/python -m pytest \
  tests/test_ta_incremental.py tests/test_indicators.py \
  -k "nvi or pvi or obv or wad or Nvi or Pvi" \
  -q --tb=short
# → 17 passed, 121 deselected
```

Prompt command uses two `-k` flags (last wins). Combined single `-k` above is the union of both files.

New cases (appended only):

- `test_incremental_nvi_matches_full`
- `test_incremental_pvi_matches_full`
- `test_incremental_nvi_pvi_dual_call_sites`
- `test_runtime_nvi_pvi_incremental_vs_disabled`

## 5. Residual / follow-ups

1. **Numba `nvi`/`pvi` inc** — not added; compiler has no emit site. Add only if/when `compiler.py` grows nvi/pvi.
2. **`ta.vpt`** — last-bar only (not a true cumulative VPT); not a rebuild of this shape.
3. **`_SERIES_MAX`:** incremental keeps the running index across the cap window. Goldens stay under 256 bars so inc ≡ full.

## 6. Out of scope / did not touch

- Compiler / `numba_builtins.py` (no existing nvi/pvi emit)
- Flask, pynets, strategy, supertrend, plot keys, `request.*`
- `COMPATIBILITY.md` / `compatibility.mdx`
- Grammar / generated ANTLR/ASDL
- Commit / push

## 7. Verdict

**win** — residual T2 `ta.nvi` / `ta.pvi` now O(1)/bar under incremental TA, last-value parity vs the full-list kernels, dual call-site isolation, Runtime on vs `PYNE_TA_INCREMENTAL=0` last-value parity. Flag-gated; full path unchanged for non-bar-mode.
