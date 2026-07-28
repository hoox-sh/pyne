# Runtime Performance Plan (no correctness loss)

> **Date:** 2026-07-28  
> **Status:** Phase 0–1 in progress  
> **Related:** `.grok/skills/pynescript-perf/`, corpus work (`.grok/skills/pynescript-corpus/`)  
> **Sources:** 4 parallel agents — online research, Runtime/series audit, evaluator/builtins audit, fine-tune synthesis

## Goal

Increase **Runtime bar-loop throughput** (ms/bar, bars/s) for interpret mode **without any correctness loss**:

- Same bar-by-bar Pine semantics
- Same series indexing / `na` / `var` / strategy event order
- Corpus set01–04 OK rate **≥ baseline** (~89.8% after re-run4)
- Prefer bit-identical outputs vs current pynescript oracle

## Hard non-goals

| Non-goal | Why |
|---|---|
| Vectorize whole scripts | Breaks control flow, `var`, strategy fills |
| Parallelize bars of one script | Sequential series + broker state |
| Drop bar-by-bar default | Corpus + strategy depend on it |
| `na` → 0 for speed | Changes signals |
| Numba-on-Cloudflare as week-1 default | Packaging / coverage gaps |
| Dual-forever Runtime forks without SoT | Drift kills fixes |

## Architecture decision

| Layer | Source of truth | Notes |
|---|---|---|
| AST evaluator + `ta.*` math | **`src/pynescript/ast/evaluator/`** | Shared by backend, worker, tests |
| Bar host Runtime | **`backend/runtime.py`** (→ later `src/pynescript/runtime/`) | Design SoT |
| pyne-worker host | `/home/jango/Git/pyne-worker/src/pynescript_backend/` | timeout / R2 / CF only; steal good patterns back |
| Compile / Numba | pynescript only | Phase 3 |

**Rule:** land TA and evaluator perf in **pynescript**. Worker sets host flags and must not re-fork evaluator math.

## Observed hot path

```
parse(source) once
for each bar:
  update PineSeries (deque appendleft)
  refresh current_series lists for ta.*
  set barstate / time / calendar
  reset plots/events
  evaluator.visit(entire AST)     ← dominant cost
  drain strategy events, collect plots
```

### Cost patterns (confirmed)

1. **TA full recompute every bar** — `_sma`/`_ema`/`_rma`/`_rsi` rebuild full series then take `[-1]` → ~O(n²)
2. **History thrash** — pynescript backend rebuilds via `list(reversed(history))` × ~8 series every bar
3. **Worker missing `_pine_defs_locked`** after bar 0 — FunctionDef/method tables can grow O(bars²)
4. **Worker re-computes hl2/hlc3/… twice** per bar (series update + list append)
5. **Bench evidence** (pyne-worker, ~3264 BTC daily bars): minimal ~23 µs/bar vs `ta_combo` ~821 µs/bar

## Definition of Done — “faster, not wrong”

A change ships only if **all** hold:

1. **Correctness**
   - Parity fixtures green (pynescript + pyne-worker)
   - TA unit suite green (`test_ta_*`, crossover/na)
   - Strategy event tests green if host touched
   - Corpus OK rate ≥ baseline; no new TIMEOUT class from unbounded growth

2. **Performance**
   - Frozen bench: **≥15%** improvement on at least one of `ta_sma` / `ta_combo` / `big_strategy`  
     **or** clear structural win with **no >5% regression** on `minimal`
   - Report before/after: `avg_ms`, `ms_per_bar`, optional corpus p50/p95

3. **Reversibility**
   - Phase 2+ behind flags (`PYNE_TA_INCREMENTAL`, etc.) or single-commit revertible
   - Document canonical file when dual-host still exists

## Phased plan

### Phase 0 — Instrumentation (risk: none)

- [x] Freeze baseline: microbench on 3264 BTC daily bars (2026-07-28 after Phase 1.1–1.3)
- [ ] Optional cProfile on `ta_combo` / `big_strategy`
- [x] Record baseline in this plan’s **Baseline** section

### Phase 1 — Free / safe wins (risk: low)

- [x] **1.1** Set `evaluator._pine_defs_locked = True` after first successful bar in **pyne-worker** Runtime (already in pynescript backend)
- [x] **1.2** Replace backend per-bar `list(reversed(history))` with **append-only** `current_series` lists (worker pattern)
- [x] **1.3** Worker: compute derived OHLC (`hl2`…) **once** per bar; reuse for series + lists
- [ ] **1.4** (optional) Lazy calendar fields / integer date math
- [x] **1.5** Align bar-mode (`_pine_bar_mode`) + incremental on worker; `_SeriesResult` only for multi-value lists
- [ ] **1.6** Parse cache by `sha256(source)` for multi-run warm path
- [ ] **1.7** Start Runtime unify checklist (worker re-exports package host)

### Phase 2 — Structural (flag + golden tests required)

- [x] **2.1** Incremental/stateful TA: `sma`, `ema`, `rma`, `rsi` keyed by call-site (`PYNE_TA_INCREMENTAL`, default on in bar mode)
- [x] **2.1b** Incremental `atr` / `macd` (EMA-of-TR and 3-EMA MACD call-site state)
- [ ] **2.2** Single chronological buffer; O(1) lookback without reverse copies
- [ ] **2.3** Cap `current_series` growth to `max_bars_back` / `_SERIES_MAX`
- [ ] **2.4** Bar-mode last-window-only rolling stats when no full-history consumer
- [ ] **2.5** Lighter plot/input registries for corpus/success-only mode

**Proof template (Phase 2):**

```text
1. Capture current plots/events for fixed OHLCV
2. Implement behind flag (default off)
3. Diff outputs (prefer bit-identical)
4. Enable by default after green gates
5. Re-bench + corpus sample
```

### Phase 3 — Bigger swings (only if still needed)

- [ ] Auto-route pure indicators to `mode="compile"` / Numba (desktop/API)
- [ ] Disk cache of compiled modules
- [ ] mypyc / C extension for series kernels

## Top 8 actions (execution order)

| Rank | Action | Land in | Effort | Risk | Impact |
|---:|---|---|---|---|---|
| 1 | Phase 0 baseline | both | 0.5d | None | Enables all work |
| 2 | `_pine_defs_locked` on worker | pyne-worker Runtime | 15m | Low | High on UDF/methods |
| 3 | Append-only `current_series` | pynescript backend | 1–2h | Low | Med–high long runs |
| 4 | Single TA return model | evaluators | 0.5–1d | Med | Unblocks incremental |
| 5 | Incremental hot TA behind flag | `technical_submodules/core.py` | 2–3d | Med–High | Largest for TA |
| 6 | Unify Runtime into package | both repos | 1–2d | Process | Maintainability |
| 7 | Parse/AST cache by hash | shared Runtime | 2–4h | Low | Multi-run APIs |
| 8 | Compile auto-route (desktop) | pynescript | multi-day | High | 10–100× subset |

## Baseline

### Historical (from `pyne-worker/benchmark_results.csv`, pre Phase 1)

| Script | bars | avg_ms | ≈ µs/bar |
|---|---:|---:|---:|
| minimal | ~3264 | 75 | ~23 |
| big_strategy | ~3264 | 999 | ~306 |
| ta_sma | ~3264 | 1218 | ~373 |
| ta_combo | ~3264 | 2681 | ~821 |

### After Phase 1.1-1.3 (pre-incremental)

| Script | avg_ms | us/bar |
|---|---:|---:|
| minimal | 83.7 | 25.6 |
| ta_sma | 2754 | 844 |
| ta_combo | 2419 | 741 |

### After Phase 2.1 incremental TA (2026-07-28, 3264 bars, 5 iters)

| Script | inc=1 avg_ms | inc=0 avg_ms | speedup |
|---|---:|---:|---:|
| minimal | 83.2 | 85.2 | ~1.0x |
| ta_sma | **268** | 2556 | **~9.5x** |
| ta_combo | **415** | 2051 | **~4.9x** |
| nested ema(sma) | **210** | 924 | **~4.4x** |

Disable with `PYNE_TA_INCREMENTAL=0`. Golden: `tests/test_ta_incremental.py`.

### After Phase 2.1b macd/atr (2026-07-28, 3264 bars, 4 iters)

| Script | inc=1 avg_ms | inc=0 avg_ms | speedup |
|---|---:|---:|---:|
| ta_macd | **300** | 912 | **~3.0x** |
| ta_atr | **314** | 3193 | **~10.2x** |
| combo (macd+atr+rsi+sma) | **745** | 6299 | **~8.5x** |


Corpus set01-04 Runtime OK: **2224/2477 (89.79%)** after re-run4 (2026-07-28).

## Key files

| Path | Role |
|---|---|
| `backend/runtime.py` | Flask / Pro bar host (append-only target) |
| `backend/series.py`, `backend/evaluator.py` | PineSeries, `_pine_bar_mode` |
| `src/pynescript/ast/evaluator/statements.py` | `_pine_defs_locked` guards |
| `src/pynescript/ast/evaluator/builtins/technical_submodules/core.py` | `_sma`/`_ema`/… |
| `/home/jango/Git/pyne-worker/src/pynescript_backend/runtime.py` | Worker bar host |
| `/home/jango/Git/pyne-worker/scripts/benchmark.py` | Throughput bench |

## Industry references (research agent)

- TradingView execution model + profiler docs
- PyneCore: bar-by-bar fidelity + AST→Python; circular series buffers
- PineTS: forward chronological arrays + reverse-index lookback (O(1))
- Reject whole-script vectorization / parallel bars for default path

## Week calendar

| Day | Focus |
|---|---|
| Mon | Phase 0 baseline + profile |
| Tue | 1.1 defs lock + 1.2 append-only + 1.3 hl once |
| Wed | Series/TA return model alignment |
| Thu–Fri | Incremental SMA/EMA/RSI behind flag + proof |
| Fri end | DoD checklist; decide Phase 3 |

## Progress log

| Date | Change |
|---|---|
| 2026-07-28 | Plan written from 4-agent research |
| 2026-07-28 | Phase 1.1: worker `_pine_defs_locked` after first bar |
| 2026-07-28 | Phase 1.2: backend append-only `current_series` (no reverse every bar) |
| 2026-07-28 | Phase 1.3: worker one-pass hl2/hlc3/ohlc4/hlcc4 |
| 2026-07-28 | Validation: pyne-worker parity+smoke 25 passed; pynescript test_evaluator 255 passed, 1 pre-existing `ta.tr` nan vs None fail (unrelated) |
| 2026-07-28 | Phase 1.5: worker `_pine_bar_mode` + `_pine_ta_incremental` |
| 2026-07-28 | Phase 2.1: incremental sma/ema/rma/rsi in `core.py`; wire basic/moving_averages/oscillators; `_ta_call_i` reset each bar |
| 2026-07-28 | Golden `tests/test_ta_incremental.py` 8 passed; parity+ta tests green; ta_sma ~9.5× vs full recompute |
EOF
| 2026-07-28 | Phase 2.1b: incremental macd/atr; golden + bench (~3× macd, ~10× atr, ~8.5× combo) |
