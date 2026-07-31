# AGENT 06 — Cold JIT / compile cache / engine hardening (Round 6)

**Date:** 2026-07-31  
**Scope:** `src/pynescript/compiler/engine.py`, `compiler/__init__.py`, host stamp in `backend/runtime.py`, tests  

## 1. Scope & files

| File | Change |
|------|--------|
| `src/pynescript/compiler/engine.py` | Disk IR/module cache, dual-key sanitize LRU, expanded prewarm, typed errors, nopython reason |
| `src/pynescript/compiler/__init__.py` | Export exceptions + `prewarm_numba_builtins` / disk/stats helpers |
| `backend/runtime.py` | Surface `nopython_fallback_reason` on compile responses |
| `tests/test_compiler_numba.py` | `TestCompileEngineRound6` (7 cases) |

## 2. Bugs found

| Severity | Issue | Resolution |
|----------|-------|------------|
| High | Disk rehydrate of comment-only variants created **new** `CPUDispatcher`s and broke IR `execute is` sharing | Before import, map disk `ir_key` → in-process `_IR_CACHE` and `_share_compiled` |
| Medium | Warm source hits still paid `sanitize_corpus_source` every time | Probe **raw** sha256 before sanitize; dual-key store raw+sanitized |
| Medium | nopython → object recovery was silent (no host-visible reason) | `CompiledScript.nopython_fallback_reason` + runtime field |
| Low | Bare `RuntimeError` / bare `except Exception: pass` on soft paths | `CompileError` hierarchy; debug logging on soft failures |
| Low | Builtin prewarm missed atr/macd/bb/highest/rma/cross | Expanded once-per-process warm list + public `prewarm_numba_builtins()` |

## 3. Changes

### Cache

1. **Source LRU (max 128)** — dual-key (raw + sanitized) when they differ; raw hit skips sanitize.
2. **IR LRU (max 64)** — unchanged contract; still shares warm `execute` for identical generated Python.
3. **Disk module cache** (default **on**, opt-out `PYNE_COMPILE_DISK_CACHE=0`):
   - Dir: `PYNE_COMPILE_CACHE_DIR` or `$XDG_CACHE_HOME/pynescript/compile` or `~/.cache/pynescript/compile`
   - `src_<sha>.json` → `{ir_key, titles, object_mode, nopython_fallback_reason}`
   - `ir_<sha>.py` with `@numba.njit(cache=True)` rewrite so Numba can persist `.nbc` beside the file
   - `clear_compile_cache()` = memory only; `clear_disk_compile_cache()` wipes tree

### Errors / correctness

- `CompileError` / `CompileEmitError` / `CompileLoadError` / `CompileNumbaRequiredError`
- Parse failures wrapped as `CompileEmitError("parse failed: …")` for accurate auto-mode reasons
- nopython warm-up failure → **must** object-mode re-emit or raise `CompileLoadError` (never leave a known-broken njit as the only path without recovery)
- Non-nopython warm-up errors still deferred to first real run (dummy OHLCV unrepresentative)
- Soft sanitize / prewarm failures: log at DEBUG, no silent empty swallow without breadcrumb

### Prewarm

- Public `prewarm_numba_builtins(force=False)` for host cold-start
- Kernels: sma/ema/rma/rsi/stdev/sum/wma/highest/lowest/atr/bb/macd/swma/dema/tema/hma/change/nz/cross*

## 4. Benchmarks

Env: repo `.venv`, Numba present, `n=5000` random-walk, isolated temp disk dir where noted.

| Path | Time |
|------|-----:|
| Cold SMA (empty disk + memory, first process touch) | **~946 ms** |
| Warm compile cache hit (same process) | **~0.011 ms** |
| Warm SMA run @ 5k | **~0.056 ms** |
| Cold combo after SMA (builtins already warm) | **~416 ms** |
| Warm combo run @ 5k | **~0.42 ms** |
| IR cache comment-only hit | **~5.6 ms** (parse+transpile; `execute` shared) |
| Subprocess 1 cold combo (populate disk + nbc) | **~1203 ms** |
| Subprocess 2 same source (disk IR + Numba `.nbc`) | **~735 ms** (**~39%** vs cold) |

Warm identity / IR sharing correctness preserved (`execute is` after comment-only and after memory clear + dual disk load).

## 5. Tests run

```bash
PYTHONPATH=src:. .venv/bin/python -m pytest \
  tests/test_compiler_numba.py \
  tests/test_compiler_objects.py \
  tests/test_compiler_strategy.py -q --tb=line
# 210 passed
```

New: prewarm/stats, raw cache identity, disk roundtrip, nopython reason + runtime surface, typed parse error, LRU bound.

## 6. Residual risks

1. Cross-process Numba cache still pays hundreds of ms (import + dispatcher load); not free AOT.
2. Disk cache can retain large `.nbc` sets — operators may set `PYNE_COMPILE_DISK_CACHE=0` or prune dir.
3. Dual-key source entries consume two LRU slots when sanitize rewrites chrome.
4. Stale disk IR after emitter upgrades: IR content hash changes → natural miss; meta `v` bumped only on schema change.
5. Non-nopython warm-up errors remain deferred (by design).

## 7. Out of scope

- Kernel coverage / visitor language surface (Agents 04–05)
- Strategy broker semantics (07)
- pyne-worker port of disk cache (12)
- No push / no commit of secrets
