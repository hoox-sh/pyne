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

# AGENT 12 — Compiler residual + Phase 3 (mypyc / C / auto-route)

**AGENT_ID:** 12  
**ROLE:** Dual — (A) Phase 3 techniques research, (B) one small safe compiler residual win  
**Date:** 2026-08-02  
**BASE_SHA:** `045190203a1991aa683147995b5f42ee71169756`  
**Owns:** research report; residual kernels in `numba_builtins.py` + emit in `compiler.py`  
**Avoided:** Agent 07 prewarm/H2 product path (no engine prewarm rewrite)

---

## 1. Role / ID

Round 7 Agent 12: document **when/how** Phase 3 native compilation (mypyc, Cython, limited C) could help **interpret-path** hot spots (`PineSeries`, `pine_expect_int`), map **numba object-mode gaps** still falling out of nopython, and clarify **auto-route compile** safety — plus ship one residual nopython kernel win that does not thrash engine deploy knobs.

---

## 2. What you did (files touched)

| File | Change |
|------|--------|
| `src/pynescript/compiler/numba_builtins.py` | New nopython kernels: `numba_median`, `numba_wpr`, `numba_cmo`, `numba_bbw`, `numba_bbw_inc` |
| `src/pynescript/compiler/compiler.py` | Emit handlers for `ta_median` / `ta_wpr` / `ta_cmo` / `ta_bbw`; bare aliases in `_BARE_TA` |
| `tests/test_compiler_numba.py` | `TestCompileRound7ResidualKernels` (3 tests) |
| `docs/perf_round7/AGENT_12_compiler_phase3.md` | This report |
| `docs/perf_round7/STATUS.md` | Agent 12 row |

**Not touched:** `engine.py` prewarm list / disk cache / H2 SLOs (Agent 07).

---

## 3. Research — Phase 3 techniques

### 3.1 Current architecture (where Phase 3 would plug in)

| Path | Hot code | Already accelerated? |
|------|----------|----------------------|
| **Compile / numeric** | Bar loop + `numba_*` kernels | **Yes** — `@numba.njit` + `*_inc` state; disk IR + `.nbc` (R6 Agent 06) |
| **Compile / object** | Pure-Python bar loop, `safe_*`, UDT dicts | Partial — no AST walk, still CPython |
| **Interpret** | AST visitor + `PineSeries` deque + TA builtins + `pine_expect_int` | No native layer; incremental TA (T2) is Python |

Phase 3 is **not** a substitute for the Numba compile path. It targets **interpret residual** and **object-mode helpers** that Numba cannot type (deques, mixed `None`/float, unicode, UDT dicts).

### 3.2 mypyc feasibility — `PineSeries` / `expect_int`

**Targets**

1. `backend/series.py` — `PineSeries` (`deque` history, `__getitem__`, arithmetic dunders)
2. `pine_expect_int` / `pine_period_or_none` in `src/pynescript/ast/evaluator/builtins/base.py` (hot every TA call)

**Feasibility assessment**

| Aspect | Finding |
|--------|---------|
| **API shape** | `PineSeries` is small (`__slots__`, explicit dunders) — good mypyc candidate *if* types tighten |
| **`deque`** | mypyc supports many stdlib types; deque of `Any`/`object` often stays boxed → gains limited on history itself |
| **Heterogeneous values** | Series hold `float | None | str | UDT`; arithmetic short-circuits on `None` (na). mypyc wants concrete types; dual typed series (`FloatSeries` vs object series) would be a larger redesign |
| **`pine_expect_int`** | Fast path is already `type(value) is int` (no bool). Remaining work is unwrap (series/list/numpy). Compiling this alone is **low risk**, **moderate gain** only if call volume dominates profile (Agent 02 should confirm) |
| **Tooling / matrix** | Package supports **3.10–3.13** (+ local 3.14). mypy/mypyc not in env; multi-version wheels for optional C extensions raise CI/Nuitka/Cloud Run cost |
| **Nuitka LSP binary** | Separate ship path; mypyc extension modules need coordinated packaging (`[compile]` extra already owns Numba) |
| **Interaction with Numba** | Compile path **does not use** `PineSeries` — flat `float64` arrays. mypyc on series **does not speed numeric compile** |

**Verdict on mypyc:** **Defer as default.** Revisit only after interpret cProfile shows `PineSeries.__getitem__` / `_binary_op` / `pine_expect_int` in the top ~10% of wall for production scripts. Prefer:

1. Flagged chronological ring / O(1) lookback (Agent 09 / Phase 2.2) over compiling deques  
2. Keep `pine_expect_int` pure-Python micro-opts (already specialized)  
3. Optional later: isolated mypyc module for `pine_expect_int` + pure float helpers under `pynescript._native` with graceful import fallback

### 3.3 Cython / limited C for series kernels

| Approach | Fit | Notes |
|----------|-----|-------|
| **Cython** on rolling median/WPR-style windows for **interpret** | Medium | Duplicates work already in `numba_builtins` for compile; two oracles to maintain |
| **C extension** for ring buffer + period coerce | Medium–High effort | Best if T1/T2/Agent 09 need a single SoT buffer shared by interpret + compile prep |
| **Reuse Numba kernels from interpret** | **Preferred near-term** | Call `numba_*` / `*_inc` from interpret when series are dense float and incremental flags allow — one oracle, optional import |

**Do not** introduce Cython for kernels that already exist under `@numba.njit` unless interpret cannot call Numba (e.g. free-threaded build without Numba). Prefer **one numeric oracle** (`numba_builtins`) shared both ways.

### 3.4 Numba coverage gaps still falling to object mode

**Mechanism:** Unknown / unsupported `ta_*` (or string/UDT/drawing/strategy) → `CompilerVisitor.object_mode = True` and often emit `None` (unknown call stub). Engine may still run object bar loop; nopython is lost.

**Probe (R7, after this agent’s kernels):**

| Construct | object_mode | Notes |
|-----------|:-----------:|-------|
| `ta.sma` / change / roc / mom / swma / percentrank / valuewhen / pivots | False | Already covered R1–R6 |
| **`ta.median` / `ta.wpr` / `ta.cmo` / `ta.bbw`** | **False** | **This agent** |
| `ta.trix` | True | Still stub `None` |
| `ta.aroon` | True | Multi-return; no kernel |
| `ta.kc` | True | Multi-return Keltner |
| String `input.*`, UDT, map/array, drawings, strategy broker | True | Correctly forced |
| Library `import` | Auto ineligible | Host prefilter |

**Other soft object-mode thrash sources (R6 Agent 05 residual):**

- Unsafe stores wrapping `safe_float` / unicode `nz_py`  
- Chart/time still synthetic (not host ms) — numeric but incomplete  
- Engine recovery: nopython `TypingError` → re-emit object + `nopython_fallback_reason`

**Object-mode helpers** (`safe_int`, `safe_float`, matrix/list mutators) are intentionally pure Python; mypyc here is secondary to keeping scripts **out of** object mode via more kernels.

### 3.5 When auto-route compile is safe

Host: `backend/runtime.py` `Runtime._compile_eligible` + `_run_auto`.

| Condition | Safe to try compile? | Behavior |
|-----------|----------------------|----------|
| No top-level `import …` | Required | Else → interpret (`import statements not supported…`) |
| No `request.*` | Required | Else → interpret (data plumbing) |
| Non-empty `inputs` overrides | **No** | Force interpret (`input.* overrides require interpret path`) |
| Numba missing | Still eligible | Object-mode pure-Python bar loop; pure-numeric emit fails → cached failure + interpret |
| Strategy / UDT / drawings | Eligible | Object-mode compile (broker semantics residual; interpret remains parity oracle for complex strategy) |
| Compile/runtime error | Fallback | `auto_backend=interpret`, `compile_fallback_reason` set |
| Deterministic compile failures | Cached | `_HOST_COMPILE_FAIL_CACHE` for source/env failures only — **not** `Compiled Runtime Error` (data-dependent) |

**Safe auto-route policy (product):**

1. Prefer `mode="auto"` for generic hosts (AXIS / worker) when scripts are indicator-heavy without imports/request.  
2. Prefer `mode="interpret"` when host injects `inputs`, needs full strategy fill order, or `request.*`.  
3. Prefer `mode="compile"` only when caller accepts compile surface + wants max throughput and can tolerate object-mode or nopython fallback metadata.  
4. After cold deploy: Agent 07 H2 prewarm/IR cache; do not skip eligibility checks.

**Correctness bar:** bit-identical vs interpret for compiled numeric scripts covered by goldens; object-mode is “faster interpret shape,” not a second semantic dialect.

---

## 4. Implementation win (residual kernels)

### 4.1 Problem

Common `ta.median` / `ta.wpr` / `ta.cmo` / `ta.bbw` fell through to **unknown call → `None` + object_mode**, so pure-indicator scripts lost nopython for no good reason.

### 4.2 Solution

Nopython kernels matching **interpret oracles**:

| API | Kernel | Warm / edge |
|-----|--------|-------------|
| `ta.median(src, len)` | `numba_median` | nan warm-up; `statistics.median` on valid window (even → mean of mid pair) |
| `ta.wpr(len)` | `numba_wpr` | interpret: **0.0** warm-up / flat range |
| `ta.cmo(src, len)` | `numba_cmo` | needs `len+1` samples; zero denom → 0.0 |
| `ta.bbw(src, len, mult)` | `numba_bbw` / `numba_bbw_inc` | `(upper-lower)/mid`; mid 0/nan → nan; reuses `numba_bb(_inc)` |

Bare v4 aliases wired in `_BARE_TA`.

### 4.3 Benchmarks / structural proof

No claim of ≥10% on full `bench_pipeline` (those scripts do not call these). Structural win:

| Script | Before | After |
|--------|--------|-------|
| `ta.median` + `wpr` + `cmo` + `bbw` plots | `object_mode=True`, plots `safe_float(None)` | **`object_mode=False`**, `@numba.njit` |

Warm micro (qualitative): same order as other single-kernel numeric compiles once JIT warm.

---

## 5. Tests run + pass/fail

```bash
PYTHONPATH=src:. .venv/bin/python -c \
  "from pynescript.compiler.engine import clear_compile_cache, clear_disk_compile_cache; \
   clear_compile_cache(); clear_disk_compile_cache()"

PYTHONPATH=src:. .venv/bin/python -m pytest \
  tests/test_compiler_numba.py::TestCompileRound7ResidualKernels \
  tests/test_compiler_numba.py::TestCompileRound6DmiSupertrendAlma \
  tests/test_compiler_numba.py::TestCompileAndRun -q --tb=line
# → 11 passed
```

New: emit stays numeric; formula/bbw_inc parity; compile vs interpret oracle on random-walk OHLCV.

---

## 6. Residual / follow-ups

1. **Still missing nopython kernels:** `ta.trix`, `ta.aroon` / `aroonosc`, `ta.kc`, `ta.mode`, nested `ta.stoch` multi-smooth variants, full TV supertrend ratchet (product P3 if required).  
2. **Interpret calling numba kernels** for dense float series (shared oracle) — better than Cython duplicates.  
3. **mypyc** only after Agent 02 bottleneck map + optional ring buffer (Agent 09); not for compile path.  
4. **Auto-route docs** for deploy: advertise eligibility table in product docs when H2 lands.  
5. Disk IR staleness after emitter upgrades: clear disk cache or bump meta (R6 known).

---

## 7. Verdict

**win** — residual nopython coverage for four real stubs (median/wpr/cmo/bbw) with interpret-parity tests, **plus** actionable Phase 3 research:

- **mypyc/C:** deferred for `PineSeries`; optional micro-target `pine_expect_int` only if profiled  
- **Numba object gaps:** documented; common residual kernels fixed  
- **Auto-route:** safe when no import/request/inputs; fail open to interpret with reasons  

**Not research-only** because a safe compiler residual was shipped without touching H2 prewarm.
