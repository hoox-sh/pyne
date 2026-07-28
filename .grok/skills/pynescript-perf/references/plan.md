# Runtime performance plan (reference copy)

Canonical OpenCode plan:

`.opencode/plans/2026-07-28-runtime-performance.md`

This file is the **Grok skill reference** copy. Keep both in sync when phases complete.

---

## Goal

Faster Runtime interpret path **without** correctness loss (Pine bar semantics).

## SoT

| Layer | Canonical path |
|---|---|
| Evaluator / TA | `src/pynescript/ast/evaluator/` |
| Runtime host design | `backend/runtime.py` |
| Worker host | `pyne-worker/src/pynescript_backend/` (timeout/R2 only long-term) |

## Phases

### Phase 0 — Measure

Freeze `benchmark.py` CSV; optional cProfile.

### Phase 1 — Safe

1. Worker: `_pine_defs_locked` after bar 0  
2. Backend: append-only `current_series`  
3. Worker: one-pass derived OHLC  
4. Align bar-mode vs `_SeriesResult`  
5. Optional parse cache / lazy calendar  

### Phase 2 — Structural (flagged)

Incremental SMA/EMA/RMA/RSI by call-site; single ring buffer; series cap; corpus light mode.

### Phase 3 — Optional

Compile/Numba auto-route; mypyc.

## Non-goals

Whole-script vectorization, parallel bars, `na`→0, dual-forever forks.

## DoD

Parity green · corpus OK ≥ baseline · ≥15% on TA bench or structural win · no >5% minimal regression.

## Baseline note

Corpus Runtime set01–04: **89.79%** OK (2224/2477) after re-run4 (2026-07-28).

## Progress

| Date | Note |
|---|---|
| 2026-07-28 | 4-agent research complete |
| 2026-07-28 | Phase 1.1–1.3 implemented (defs lock, append-only series, one-pass OHLC) |
| 2026-07-28 | Phase 1.5 + 2.1: bar-mode align + incremental sma/ema/rma/rsi (default on) |
| 2026-07-28 | Bench: ta_sma ~9.5×, ta_combo ~4.9× vs PYNE_TA_INCREMENTAL=0; tests green |

## Phase 2.1 usage

```bash
# default: incremental on in Runtime bar mode
# disable:
PYNE_TA_INCREMENTAL=0 python ...

# golden parity vs full recompute
.venv/bin/python -m pytest tests/test_ta_incremental.py -q
```

Key code: `src/pynescript/ast/evaluator/builtins/technical_submodules/core.py`
(`_sma_inc_update`, `_ema_inc_update`, `_rma_inc_update`, `_rsi_inc_update`).
EOF

## Phase 2.1b (macd/atr) — 2026-07-28

Incremental `ta.macd` (3 internal EMAs) and `ta.atr` (EMA of TR, matching current full path).
Bench 3264 bars: macd ~3x, atr ~10x, combo ~8.5x vs `PYNE_TA_INCREMENTAL=0`.
