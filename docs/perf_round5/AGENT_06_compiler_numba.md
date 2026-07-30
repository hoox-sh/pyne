# AGENT 06 — Compiler Numba residual + cold JIT UX (Round 5)

**Date:** 2026-07-30  
**BASE_SHA:** ca5215ac33c34f9b60584f8c230bc281dc768782  
**Scope:** `src/pynescript/compiler/{numba_builtins,compiler,engine}.py` + compiler tests  

## 1. Scope & files touched

| File | Change |
|------|--------|
| `src/pynescript/compiler/numba_builtins.py` | `numba_swma`, `numba_dema` / `numba_dema_inc`, `numba_tema` / `numba_tema_inc` |
| `src/pynescript/compiler/compiler.py` | Wire `ta.dema` / `ta.tema` / `ta.swma` (+ bare aliases) to kernels |
| `src/pynescript/compiler/engine.py` | IR-hash secondary cache; once-per-process builtin warm-up |
| `tests/test_compiler_numba.py` | `TestCompileRound5IncKernels` (emit, parity, compiled≡full, IR cache) |

## 2. Bugs found

None severe. Residual **surface gaps** (not crashes):

| Severity | Issue | Resolution |
|----------|-------|------------|
| Medium | `ta.dema` / `ta.tema` / `ta.swma` were not lowered on the compile path (fell through / missing) | New kernels + emit |
| Low | Comment-only source variants re-JIT’d identical IR (cold ~seconds) | Secondary IR cache shares `execute` |

No LRU source-key collisions found (sha256 of sanitized source remains primary).

## 3. Changes (what / why)

### Residual `*_inc` kernels

| Kernel | State | Notes |
|--------|-------|-------|
| `numba_dema_inc` | `[e1, e2, last_i]` + `e1_raw[]` | Nested SMA-seed EMA matching `numba_ema`; valid at `i ≥ 2p−2` |
| `numba_tema_inc` | `[e1, e2, e3, last_i]` + two raw series | Valid at `i ≥ 3p−3` |
| `numba_swma` | none (O(1) formula) | TV 4-period weights `1,2,2,1 / 6` |

Full `numba_dema` / `numba_tema` retained for parity / fallback. Catch-up (gap) and rewind (`i < last_i`) supported on both `*_inc` paths.

**Skipped (same rationale as Round 4):** ALMA (weight shift forces O(length)), percentrank / percentile (order-stat), pivots (tiny window), dynamic `valuewhen` occurrence, real DMI/supertrend (still stubs; interpret residual is Agent 03).

### Cold JIT UX

1. **IR cache** (max 64, LRU): after transpile, `sha256(generated_code)`. Hit → share warm `execute` + titles; still bind a per-source `CompiledScript`. Comment-only edits that drop out of the AST reuse JIT.
2. **Source cache** unchanged (max 128, sha256 sanitized source) — still identity-stable for exact source.
3. **Builtin pre-warm** once per process on first numeric exec: hottest `*_inc` + dema/tema/swma so later distinct scripts do not re-pay first-touch kernel compile.
4. `clear_compile_cache()` clears **both** source and IR maps.

## 4. Benchmarks

Env: Python 3 + Numba 0.65.1, `PYTHONPATH=src`, random-walk `n=5000`, median of 11 after warm.

### Kernel full vs `*_inc`

| Kernel | full (ms) | inc (ms) | Speedup |
|--------|----------:|---------:|--------:|
| dema p=14 | 122.2 | 6.5 | **~19×** |
| dema p=50 | 109.0 | 2.9 | **~37×** |
| dema p=100 | 98.6 | 5.7 | **~17×** |
| tema p=14 | 176.9 | 3.5 | **~50×** |
| tema p=50 | 169.0 | 4.2 | **~40×** |
| tema p=100 | 173.5 | 7.5 | **~23×** |

(Full rebuilds an intermediate series every bar → O(n²); inc is linear.)

### Compiled end-to-end (dema20+tema14+swma @ 5k)

| Path | Time |
|------|-----:|
| Cold compile (first process touch incl. builtin warm) | ~2490 ms |
| Warm `CompiledScript.run` | **0.625 ms** |
| Second source (comment-only), IR cache hit | **~9.8 ms** (parse+transpile only; `execute` shared) |

## 5. Tests run

```bash
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_compiler_numba.py \
  tests/test_compiler_objects.py \
  tests/test_compiler_strategy.py -q --tb=line
# 182 passed in ~46s
```

Correctness:

| Check | Result |
|-------|--------|
| Kernel full vs `*_inc` dema/tema (p=5,14,30; gap+rewind) | max abs ≤ **1e-10** |
| Compiled MULTI vs full kernels (n=200 / 5000) | dema/tema ≤ **1e-10**, swma **0** |
| IR cache share | `execute` identity; plot series allclose |

## 6. Residual risks / follow-ups

1. DEMA/TEMA use **compiler SMA-seed EMA** (`numba_ema`), not interpret’s first-valid seed — intentional compile-family consistency; dual-host numeric drift vs interpret if compared naively.
2. ALMA / percentrank / percentile still full O(period) / O(period log period).
3. `ta.dmi` / `ta.supertrend` remain numeric stubs.
4. IR cache can retain a large njit dispatcher; 64 entries is a soft bound — tune if memory pressure appears in long-lived LSP/API processes.
5. Builtin warm list is a curated subset; first cold script still JITs its full generated entry.

## 7. Out of scope / did not touch

- Interpret-only TA (Agent 03)
- Runtime host packing (Agent 05)
- Strategy broker semantics beyond existing compile wiring (Agent 07)
- Grammar / parser, LSP, matrix object-mode pre-existing failures
- No commit / push
