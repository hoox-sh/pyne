# AGENT 05 — Runtime host wrap & series bookkeeping

**Date:** 2026-07-30  
**BASE_SHA:** `ca5215ac33c34f9b60584f8c230bc281dc768782`  
**Role:** PERF + DUAL-HOST (Runtime `mode=compile` wrap vs bare `CompiledScript.run`)  
**SoT:** `backend/runtime.py` (pynescript); pyne-worker is thin twin — document only this round  

## 1. Scope & files touched

| File | Change |
| --- | --- |
| `backend/runtime.py` | Fast JSON series packing; OHLCV pack + identity/fingerprint cache; host compile cache; lean `_run_compiled` pop/stamp; single-pass interpret column extract |
| `backend/evaluator.py` | **untouched** (`_pine_defs_locked` / columnar plots already in place) |
| `backend/series.py` | **untouched** |
| `docs/perf_round5/AGENT_05_runtime_host.md` | this report |

**Out of scope:** TA kernels, `visit_Call`, LSP, grammar, engine sanitize-on-cache-hit (Agent 06 note).

## 2. Bugs found

None introduced. Pre-existing failures (not from this patch):

- `tests/test_parity.py` corpus `*_strategy.pine` missing in worktree (env; files live in main repo).
- `tests/test_strategy_runtime.py::TestStrategyExtendedStats` — `strategy.cash` resolves to string `"cash"` (Agent 07 / strategy namespace).

## 3. Changes (what / why)

Round 4 left **~10×** host wrap on `ta_combo@2k` vs bare engine. cProfile of warm `mode=compile` showed:

1. `_series_values_jsonable` — pure-Python `math.isnan`/`isinf` per cell (~50% host tottime)
2. `_ohlcv_dicts_to_arrays` — dict→numpy packing (~30%)
3. `compile_script` always re-sanitizes before engine LRU hit (~sanitize in top callees)

### 3.1 Vectorized JSON series (`_series_values_jsonable`)

- Float64 ndarray: `np.isfinite` → if all finite, `arr.tolist()` only; else `tolist()` + sparse `None` patch via `flatnonzero(~finite)`.
- Integer arrays: direct float64 `tolist()` (always finite).
- Semantics unchanged: NaN / ±Inf → `None` for strict JSON.

### 3.2 OHLCV packing (`_ohlcv_dicts_to_arrays`)

- Single-pass list accumulation + one `asarray` per column (prefer direct OHLC keys).
- Bounded identity cache (`id(list)` + fingerprint of `n, first/last time/close`) for warm re-eval of the same bar list (bench / multi-run hosts).
- Volume default still `1.0` when missing/`None`; OHLC `None` → `0.0`.

### 3.3 Host compile cache (`_HOST_COMPILE_CACHE`)

- Raw-source sha256 → `CompiledScript` (max 64).
- Warm `mode=compile` skips corpus sanitize + engine re-lookup (engine LRU still authoritative for first compile).
- `compile_cached` reflects host short-circuit hit.

### 3.4 Lean interpret bookkeeping

- Single pass for OHLCV/time columns + bid/ask probe (was 6 list comps + separate `any()`).
- Series cap, append-only `current_series`, `_pine_defs_locked` after first bar: **unchanged**.

### 3.5 `_run_compiled` micro

- One `isinstance(series_map, dict)` branch for pops + JSON map.
- Skip event stamp loop when `events` empty.

## 4. Benchmarks

Python 3.14, n=**2000** bars, median of 21 after 5 warm (same process session for before/after).

### 4.1 Warm host wrap vs bare `CompiledScript.run` (ta_combo focus)

| script | bare run med (ms) | host compile med **before** | host compile med **after** | wrap× before → after |
| --- | ---: | ---: | ---: | --- |
| minimal | ~0.01 | **2.60** | **0.09** | ~260× → **~16×** (absolute µs-scale) |
| ta_sma | ~0.04 | **2.56** | **0.13** | ~67× → **~5×** |
| ta_combo | ~0.25–0.5 | **4.97** | **0.75** | ~20× → **~2.9×** |

**ta_combo warm host ~6.6× faster** (4.97 → 0.75 ms). Wrap gap vs bare engine from ~10–20× toward **~3×** (residual = JSON `tolist` + engine.run + result dict).

### 4.2 Component (ta_combo @ 2k, post)

| component | before (ms) | after warm (ms) |
| --- | ---: | ---: |
| OHLCV pack | ~1.8 | ~0.002 (identity hit) / ~0.9–1.9 cold |
| JSON series (5 plots) | ~2.6 | ~0.34 |
| bare / engine run | ~0.25–0.5 | same |
| sanitize on warm compile | visible in cProfile | **gone** (host cache) |

cProfile warm ×20 `ta_combo`: ~191 calls/run (was ~3.4k); top tottime = `CompiledScript.run` then `ndarray.tolist` / jsonable.

### 4.3 `scripts/bench_pipeline.py` (interpret / bare compile — host wrap not fully broken out)

| path | med |
| --- | --- |
| interpret minimal@2k | 24.2 ms |
| interpret ta_combo@2k | 374.9 ms |
| bare compile run ta_combo@5k | 1.07 ms |

No interpret regression signal on minimal (host column extract is setup-only).

## 5. Tests run

```bash
PYTHONPATH=src:. .venv/bin/python -m pytest \
  tests/test_parity.py tests/test_strategy_runtime.py tests/test_evaluator.py \
  -q --tb=line -k 'not corpus'
# → 261 passed, 2 failed (strategy.cash pre-existing), 15 deselected

PYTHONPATH=src:. .venv/bin/python scripts/bench_pipeline.py
```

Manual: compile host series tails ≡ bare `CompiledScript.run` for `ta_combo` (NaN→None only on non-finite).

## 6. Residual risks / follow-ups

| Item | Notes |
| --- | --- |
| Cold OHLCV pack | Still ~1 ms/2k bars for new list objects; further win needs C/numba pack or columnar API input |
| JSON always materializes Python lists | Required for Flask/JSON; optional raw-numpy response flag could drop wrap to ~1× bare for internal callers |
| Engine sanitize-before-cache | Agent 06: hash raw or sanitize only on miss |
| OHLCV pack fingerprint | Only samples first/last bar; in-place middle mutation of same list object could stale-cache (API builds new lists; low risk) |
| pyne-worker twin | Still uses 5 list comps + naive `tolist()` / nan check only on primary plot — **drift documented below** |

## 7. Dual-host drift (pyne-worker)

Path: `/home/jango/Git/pyne-worker/src/pynescript_backend/runtime.py`  
**Canonical SoT remains pynescript `backend/runtime.py`.** Worker not patched this round.

| Topic | pynescript backend (after) | pyne-worker twin |
| --- | --- | --- |
| OHLCV → arrays | list+asarray + identity/fp cache | 5× `[float(b.get(...)) for b in …]` |
| Plot JSON NaN | all series, vectorized finite mask | primary `plots` only; `series` raw `.tolist()` (NaN may leak) |
| Host compile cache | raw sha256 → CompiledScript | none (sanitize every call) |
| Interpret columns | single-pass + bid/ask | multi list-comp |
| API extras | `plot_meta`, `inputs`, `meta`, `compile_ms` | thinner (`plots`/`series`/events) |
| Timeout | no | every 32 bars |

Recommend porting JSON + pack cache when worker compile path is next touched.

## 8. Explicit out of scope / did not touch

- TA incremental kernels / ATR semantics  
- Evaluator dispatch / `visit_Call`  
- `_SERIES_MAX` / bar semantics / `_pine_defs_locked` policy  
- `backend/evaluator.py` plot capture  
- `backend/series.py` PineSeries  
- Grammar, LSP, pyne-worker code edits  
- Commit / push  
