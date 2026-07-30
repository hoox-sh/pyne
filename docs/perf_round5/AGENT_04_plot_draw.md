# Round 5 — AGENT 04: Plot / drawing export path

**AGENT_ID:** 04  
**ROLE:** Plot / drawing export (PERF + BUGS)  
**BASE_SHA:** ca5215ac33c34f9b60584f8c230bc281dc768782  
**Date:** 2026-07-30

## 1. Scope & files touched

| File | Change |
|---|---|
| `backend/evaluator.py` | Steady-state value-only plot capture; faster `_unwrap_scalar` / `_serialize_color`; positional vs kwargs paths |
| `backend/runtime.py` | Post-process: str-first color, skip empty style/location, numeric column fast path |
| `src/pynescript/ast/evaluator/builtins/plotting.py` | Bar-mode registry reuse: setattr fields only (no full `_fill_plot`) |
| `src/pynescript/ast/evaluator/builtins/drawing.py` | `is_empty()` matches exportable collections (exclude linefills) |
| `src/pynescript/ast/evaluator/base.py` | Seed `shape.*` / `location.*` / `xloc.*` / `yloc.*` / `extend.*` / `display.*` / `position.*` / `hline.style_*` constants |

**Out of scope (not touched):** TA kernels, `visit_Call`, strategy fills, LSP, compiler Numba.

## 2. Bugs found

| Severity | Bug | Repro | Fix |
|---|---|---|---|
| **P1** | `shape.triangleup` / `location.belowbar` (and peers) resolved to `None` in interpret → empty `plot_meta.style` / `location` | `tests/test_bgcolor_plotshape_export.py::test_plotshape_export_bool_series_and_style` failed: `style == ""` | Add enum-namespace constants to `_MATH_CONSTANTS` in `base.py` (compiler already emitted attr names; interpret context lacked them) |
| **P2** | `DrawingRegistry.is_empty()` treated linefills as non-empty but `export_for_api` never serializes them → Runtime still built `bar_times` for no-op export | linefills-only registry | Align `is_empty` with exportable collections |
| **P2** | Empty-string style/location leaked into `plot_meta` when enums were `None` | plotshape with missing constants | Skip empty strings in `_capture_plot` + runtime meta packing |

## 3. Changes (what / why)

### Perf — steady-state plot capture (main win)

Round 4 left “skip color/title coercions when constant” on the table. After bar 0, each call site is registered in `_plot_value_cols` / `_plot_meta_list`. Bars 1…N only need the **value**:

- `_append_plot_value` — O(1) append, no meta dict writes  
- `_serialize_color` only on first sighting of a call site (4 ncalls for 4 colored plots × 2k bars; was 8000)  
- `_capture_plot` only on first sighting (8 ncalls for 8 plots)  
- Avoid `kwargs = kwargs or {}` alloc on positional-only plots  

### Perf — micro

- `_unwrap_scalar`: type-identity fast path for float/int/bool/str/None  
- `_serialize_color` / runtime `_color_str`: str/int before `getattr(to_rgba)`  
- Registry bar-mode: setattr provided fields only (fill scripts with `_pine_need_plot_ids`)  
- Numeric plot columns: `list(raw_col)` when all cells are float/int/None  

### Correctness

- Enum constants for plotshape/drawing namespaces  
- Series length still padded by `finish_bar_plots`; multi-plot titles/colors preserved  

## 4. Benchmarks

**Env:** Linux, Python from `/home/jango/Git/pynescript/.venv`, `mode=interpret`, 2000 synthetic bars.  
**Note:** wall times noisy under multi-agent load; structural metrics (ncalls) are the reliable signal.

### cProfile — 8 pure plots @ 2k bars (same script)

| Metric | Before | After |
|---|---:|---:|
| Total function calls | ~1 047 k | **~813 k** (−22%) |
| `_builtin_plot` cumtime (same-run scale) | ~0.158 s | **~0.089 s** (first quiet run) |
| `_capture_plot` ncalls | 16 000 | **8** |
| `_serialize_color` ncalls | 8 000 | **4** |
| `_append_plot_value` ncalls | — | 15 992 |

### Wall median (21 iters after 3 warmup; after patch)

| Script | med_ms |
|---|---:|
| minimal `plot(close)` @ 2k | 35.9 |
| multi 8 plots (color+plain) @ 2k | 142.3 |
| ta_combo 8 plots (sma/ema/rsi/atr/stdev/bb) @ 2k | 341.9 |

Same-session pre-patch spot (7 iters, noisier): minimal ~44.6 ms; pure multi8 ~90 ms (single quiet sample) / ~203 ms under load. **Plot path self-time and call count cut; wall ≥10% is load-dependent on this host.**

## 5. Tests run

```bash
PYTHONPATH=src:. /home/jango/Git/pynescript/.venv/bin/python -m pytest \
  tests/test_plotting_effects.py \
  tests/test_drawing_all_and_last_bar.py \
  tests/test_bgcolor_plotshape_export.py \
  tests/test_multi_plot_cross.py -q --tb=line
# 20 passed

# Broader plot-related evaluator slice
... -k "plot or bgcolor or hline or shape"  # 18 passed, 247 deselected
```

Manual: `fill(p1,p2)` Runtime path OK; plotshape meta `style=triangleup`, `location=belowbar`; bgcolor null/color alternating OK; all series length == bar count.

## 6. Residual risks / follow-ups

1. **Lazy meta color** still checked each bar when `color=` kwargs present and meta color is still None (dynamic first-bar `na`). Rare; could gate on `_plot_bars_done`.  
2. **Dispatch still dominates** multi-plot wall (`visit` / `visit_Call`) — Agent 01 territory.  
3. **`base.py` constants** overlap Agent 10 surface; if Agent 10 adds a fuller table, merge carefully (setdefault, no overwrite).  
4. **fill()** still pays PlotRegistry every bar when source matches `\bfill\s*\(` — acceptable.  
5. Linefills still not exported (pre-existing product gap).

## 7. Explicit out of scope / did not touch

- TA kernels / incremental state  
- `visit_Call` / expression dispatch  
- Strategy broker / order fills  
- LSP, grammar, compiler Numba  
- No commit / push  

---

**Handoff metric:** plot-path ncalls −22% on multi-plot; `_serialize_color`/`_capture_plot` collapsed to first bar only; plotshape style/location export fixed; **20/20** verify tests green.
