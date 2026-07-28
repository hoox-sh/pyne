---
name: pynescript-perf
description: >
  Speed up pynescript / pyne-worker Runtime bar-loop evaluation without
  correctness loss. Use when the user mentions Runtime performance, ms/bar,
  bars/sec, incremental TA, _pine_defs_locked, series history thrash, or runs
  /pynescript-perf.
---

# pynescript-perf

Agent workflow for **Runtime performance** (interpret bar loop + TA builtins).
Full plan: `references/plan.md` and
`.opencode/plans/2026-07-28-runtime-performance.md`.

## Hard constraints (never violate)

1. **Zero correctness loss** — same bar-by-bar semantics, series offsets, `na`,
   `var`, strategy event order vs current pynescript oracle (prefer bit-identical).
2. **Do not** vectorize whole scripts or parallelize bars of one run.
3. **Do not** silent-coerce `na` → 0 for speed.
4. **Evaluator/TA math** lands in `src/pynescript/ast/evaluator/` first.
5. **Runtime host** design SoT is `backend/runtime.py`; pyne-worker is thin host
   (timeout/R2/CF). Keep copies in sync until unified.
6. Phase 2+ (incremental TA, ring buffer reindex) **behind flags** + golden tests.
7. `from __future__ import annotations` on every new Python file.

## Quick diagnosis

Interpret mode cost is dominated by:

1. Full TA recompute every bar (`_sma`/`_ema`/`_rsi` … then take last value)
2. Per-bar history rebuild (`list(reversed(history))` on backend)
3. Missing `_pine_defs_locked` on worker → O(bars²) def tables
4. Full AST re-walk every bar (intentional Pine; optimize kernels not control flow)

## Safe first patches (Phase 1) — done 2026-07-28

| ID | Change | File |
|---|---|---|
| 1.1 | `_pine_defs_locked = True` after first bar | `pyne-worker/.../runtime.py` |
| 1.2 | Append-only `current_series` (no reverse every bar) | `pynescript/backend/runtime.py` |
| 1.3 | Compute hl2/hlc3/ohlc4 once per bar | worker `runtime.py` |
| 1.5 | Worker `_pine_bar_mode` + incremental TA | worker `evaluator.py` |

## Phase 2.1 incremental TA — done 2026-07-28

- Call-site state for `ta.sma` / `ema` / `rma` / `rsi` in bar mode
- Flag: `PYNE_TA_INCREMENTAL=0` to disable (default on)
- Golden: `tests/test_ta_incremental.py`
- Observed: **~9.5×** `ta_sma`, **~4.9×** `ta_combo`, **~3×** `ta_macd`, **~10×** `ta_atr` (3264 bars)

## Commands

```bash
# Worker Runtime bench (sibling repo)
cd /home/jango/Git/pyne-worker
PYTHONPATH=src .venv/bin/python scripts/benchmark.py --warmup 3 --duration 30

# Parity / smoke
cd /home/jango/Git/pyne-worker && PYTHONPATH=src .venv/bin/python -m pytest tests/test_parity.py tests/test_smoke.py -q
cd /mnt/data/home/jango/Git/pynescript && .venv/bin/python -m pytest tests/test_parity.py tests/test_evaluator.py -q --tb=line

# Corpus sample (Runtime OK rate must not fall)
cd /home/jango/Git/pyne-worker
PYTHONPATH=src .venv/bin/python scripts/corpus_run_sets.py --sets set01 --timeout 8 --bars 50
```

## Definition of Done

- Tests green (parity + TA + strategy if touched)
- Corpus OK rate ≥ baseline (~89.8% set01–04 re-run4)
- Bench: ≥15% on a TA-heavy script **or** structural win; no >5% regression on `minimal`
- Dual-host: document which file is canonical

## Explicit non-goals

- Whole-script vectorization
- Parallel bars
- Numba-on-edge as default
- Hand-edit generated grammar

## See also

- `references/plan.md` — full phased plan + baselines
- `.opencode/plans/2026-07-28-runtime-performance.md` — same plan for OpenCode
- `.grok/skills/pynescript-corpus/` — corpus correctness (orthogonal; keep OK rate)
EOF