# Plot / drawing bookkeeping (round 3)

**Date:** 2026-07-28  
**Scope:** Interpret Runtime path — `PlotRegistry` / `_builtin_plot` bar-mode storage, `DrawingRegistry.export_for_api` empty fast path  
**Constraint:** zero correctness loss on plot series + drawings when present; Runtime API (`plots` / `series` / `plot_meta` / `drawings`) unchanged  

## Summary

Round-2 left host bar-loop opts; cProfile still showed `_builtin_plot` / registry growth and always-on drawing export. This round targets **bookkeeping only**:

| Change | Effect |
|---|---|
| **Bar-mode Plot reuse** | `PlotRegistry` stays **O(plots)** not O(bars×plots); no per-bar dataclass alloc after first bar |
| **`Plot` slots + lazy meta** | Smaller objects; no empty `meta={}` on every plot |
| **Cheaper `_kw` / defaults** | No empty-dict alloc; skip `str()` on default titles/styles; positional fast path for `plot(series)` |
| **`DrawingRegistry.is_empty` + export early-out** | Empty scripts skip nested work / list walks |
| **Runtime skip** | No `bar_times` materialization when registry empty |

### Correctness probes (500 bars)

- `plot(close)` → `plots[-1] == close`, `drawings == []`
- Multi-plot script → series keys `c/o/h/l/hl2/sma/ema` full length
- `PlotRegistry` after minimal run: **1** entry (not 500)
- After plot-heavy: **10** entries (plot×7 + plotshape/hline/bgcolor) — not 5000
- `line.new` + `label.new` on last bar → export types `{line, label}`

### Microbench (2000 synthetic bars, median of 7, 2 warmup)

| Script | med_ms |
|---|---:|
| minimal (`plot(close)`) | ~25.6 |
| plot-heavy (7 plots + shape/hline/bgcolor + sma/ema) | ~283.9 |

(Host noise varies; numbers are post-change absolute times, not A/B stash — main win is **bounded registry memory** and empty-export skip.)

### Tests

```text
287 passed  tests/test_evaluator.py tests/test_ta_incremental.py
            tests/test_plotting_effects.py tests/test_drawing_all_and_last_bar.py
            tests/test_pine_surface_gaps.py
```

## What changed

### `src/pynescript/ast/evaluator/builtins/plotting.py`

1. **`@dataclass(slots=True) Plot`** — lower per-instance cost; `meta` defaults to `None` (only set for plotcandle wick/border).
2. **`_plot_upsert`** — when `_pine_bar_mode`, index via `_plot_call_i` into `PlotRegistry.plots` and **mutate in place** (`_fill_plot` writes full defaults so stale kind/fields cannot leak). Non-bar mode still appends once per call (unit tests / single-shot eval).
3. **Positional fast path** for `plot(series[, title, color, …])` with `kwargs` empty/None.
4. **`_kw` / `_as_str` / `_as_int`** — no `kwargs or {}` empty dict; avoid redundant `str()` on strings.

### `src/pynescript/ast/evaluator/builtins/drawing.py`

1. **`DrawingRegistry.is_empty()`** — O(1) list-truthiness over 6 registries.
2. **`export_for_api` early return `[]`** when no exportable objects (lines/boxes/labels/tables/polylines).
3. **Module-level `_export_*` helpers** — no nested function defs per export call.

### `backend/runtime.py` (surgical)

1. Reset **`evaluator._plot_call_i = 0`** each bar (alongside `_ta_call_i` / `_cross_call_i`).
2. **Skip** `bar_times` list + `export_for_api` when `DrawingRegistry.is_empty()`.

### Dual-host (`pyne-worker`)

- Mirrored `_plot_call_i = 0` per bar in `src/pynescript_backend/runtime.py`.
- Worker interpret path does not call `export_for_api` (compile path uses `__drawings` only) — no export skip needed.

## Non-goals / left on table

- **`CustomEvaluator.plot_outputs` dicts** still one dict per `plot()` per bar (Runtime series API). Further win would store value-only columns + once-only meta; out of this OWN set beyond light runtime touch.
- Drawing object **creation** cost when scripts actually draw (line/label.new every bar) — not addressed; only empty-registry path.
- Compiler / TA kernels / visitor dispatch — other agents.

## How to verify

```bash
PYTHONPATH=src python -m pytest tests/test_evaluator.py tests/test_ta_incremental.py \
  tests/test_plotting_effects.py tests/test_drawing_all_and_last_bar.py -q --tb=line
```
