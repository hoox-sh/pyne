# Copyright (C) 2024-2026 jango_blockchained
#
# SPDX-License-Identifier: AGPL-3.0-or-later

# Agent 02 — F1 Supertrend goldens (TV ratchet out of scope)

**Role / ID:** 02 — residual F1 optional TV supertrend ratchet goldens  
**Date:** 2026-08-16  
**BASE_SHA:** `ffd43641ae9e492a1b0a93f1127af1ebeaf69c66`  
**Owns:** `tests/test_first_party_ta_goldens.py` (append), `tests/test_parity_r9_kernels.py` (Supertrend/F1 only), `tests/fixtures/first_party/README.md`, this report  
**Verdict:** **closed**

## Goal

1. Strengthen dual-host goldens so interpret ≡ compile ≡ incremental ≡ numba for factor/period **3.0/5** and **3.0/10**.
2. Explicit formula golden: after ATR warmup, `st == mid ± factor * atr`.
3. README: TradingView final-band ratchet is **out of scope**, not a residual hole.

Did **not** change Supertrend math. Did **not** implement TV ratchet. Did **not** touch volume.py, Flask, pynets, trail, plot keys, `request.*`, or `COMPATIBILITY.md`.

## Contract (already implemented; locked by goldens)

`src/pynescript/ast/evaluator/builtins/technical_submodules/advanced.py` + Numba:

- `mid = (high + low) / 2`
- `direction = -1` if `close >= mid` else `+1`
- `supertrend = mid - factor * ATR` on up, `mid + factor * ATR` on down
- na ATR → `0.0` (warmup band collapses to mid)
- Shared by interpret full, interpret inc, compile nopython, `numba_supertrend` / `numba_supertrend_inc`
- **Not** the TV final-band ratchet

## What we did

### `tests/test_first_party_ta_goldens.py`

Appended (kept existing 3.0/10 fixture golden):

| Test | What it locks |
| --- | --- |
| `test_supertrend_dual_host_factor_period` | Runtime interpret ≈ compile + simplified contract for **3.0/5** and **3.0/10** |
| `test_supertrend_formula_after_atr_warmup` | After first finite ATR (`>= period`), `st == mid ± factor * atr` on both hosts |
| `test_supertrend_interpret_compile_inc_numba` | interpret-inc (`PYNE_TA_INCREMENTAL` default) ≡ interpret-full (`=0`) ≡ compile nopython ≡ `numba_supertrend` ≡ `numba_supertrend_inc` ≡ evaluator `_builtin_ta_supertrend` ≡ `_supertrend_inc_update` |

Existing `test_supertrend_dual_host` now also calls the explicit post-warmup formula helper.

### `tests/test_parity_r9_kernels.py` (F1 class only)

- `test_interpret_and_numba_kernels_match` parametrized over **3.0/5** and **3.0/10**; each bar checks four-way kernel equality **and** the mid±factor·ATR formula.
- `test_runtime_dual_host_fixture_contract` parametrized the same pair.
- New `test_formula_after_atr_warmup_four_host`: Runtime interpret + compile + eval full/inc + Numba full/inc, formula after ATR warmup.

### `tests/fixtures/first_party/README.md`

Table row + short note: TV band ratchet is **out of scope**, not a missing golden / residual fidelity hole. First-party + F1 tests lock the shipped simplified contract only.

## Verify

```
PYTHONPATH=src:. .venv/bin/python -m pytest \
  tests/test_first_party_ta_goldens.py \
  tests/test_parity_r9_kernels.py -k "supertrend or Supertrend or F1" \
  -q --tb=short
```

**Result:** **14 passed**, 16 deselected, **1 failed** (pre-existing, not F1).

| Slice | Result |
| --- | --- |
| `tests/test_first_party_ta_goldens.py` (whole file) | **11 passed** |
| F1 / Supertrend goldens (new + strengthened) | **all passed** |
| `TestStochRsiSupertrendCorpus.test_strategy_073_parity` | **MISMATCH** — pre-existing P1p, not introduced |

073 (`set01/strategies/073_str_stochrsi_plus_supertrend_strategy.pine`) still disagrees on `Up Trend 2` / `Down Trend 2` (~5 pt) and `Tendence MA` (interpret `None` vs compile `149.7475` at bar 199). That is corpus plot-parity (P1p / EMA-200 na policy), **not** a Supertrend kernel split: the four-host formula goldens prove interpret/compile/inc/numba share mid±factor·ATR. Out of scope to implement TV ratchet or retune 073. Test body was not edited.

No interpret/compile/inc/numba disagreement on the locked contract, so compile/Numba math was left untouched.

## Residual / not in this close

- **TV ratchet** remains unimplemented **by design**. Reclassify COMPATIBILITY.md F1 row as out-of-scope (owned by parent / compatibility docs; this agent must not edit that file).
- **073** corpus MISMATCH stays on the P1p tail.
- `ta.nvi` / `ta.pvi` full-list leftovers (T2) unchanged.

## Verdict

**closed** — F1 optional TV-ratchet goldens are not a hole. Dual-host + four-host goldens lock 3.0/5 and 3.0/10 to `st == mid ± factor * atr` after ATR warmup. TV ratchet documented out of scope.
