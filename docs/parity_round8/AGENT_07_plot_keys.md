# Round 8 — AGENT 07: Plot / fill / hline / bgcolor / plotshape keys

| Field | Value |
| --- | --- |
| **Role / ID** | Agent 07 — Plot / fill / hline keys |
| **Verdict** | **partial** (helper + goldens green; Runtime compile still needs one-line wire-up) |
| **Date** | 2026-08-04 |
| **Owns** | `src/pynescript/ast/evaluator/builtins/plotting.py`, `drawing.py`; tests `test_bgcolor_plotshape_export.py`, `test_plotting_effects.py`, `test_multi_plot_cross.py`, `test_drawing_*` |

## Goal

Reduce **structural_only** / **fill_background** / hline key asymmetry between interpret and compile by exporting titled visual series keys on **both** modes (fill, bgcolor, plotshape). Prefer real key parity over harness `--ignore-hline-keys` / `--ignore-fill-keys`.

## What you did (files touched)

| File | Change |
| --- | --- |
| `src/pynescript/ast/evaluator/builtins/plotting.py` | Shared defaults (`DEFAULT_VISUAL_TITLES`), `uniquify_series_title`, `materialize_visual_series_from_drawings`, `merge_visual_series_from_drawings` — lift compile `__drawings` bgcolor/plotshape/plotchar/plotarrow into titled series + plot_meta |
| `src/pynescript/ast/evaluator/builtins/drawing.py` | `DrawingRegistry.merge_visual_series_from_drawings` wrapper for Runtime compile packing |
| `tests/test_bgcolor_plotshape_export.py` | Uniquify + materialize dual-mode goldens (plotshape/plotchar/bgcolor) |
| `tests/test_multi_plot_cross.py` | `test_plotshape_bgcolor_keys_via_materialize_match_interpret` |
| `tests/test_plotting_effects.py` | Default title stability for visual kinds |
| `docs/parity_round8/AGENT_07_plot_keys.md` | This report |

**Not edited (handoff):** `compiler/compiler.py` (Agent 03), `compiler/engine.py` (Agent 04), `backend/runtime.py` (Agent 11).

## Before / after (structural proof)

### Already dual-mode (pre-existing, re-confirmed)

| Kind | Interpret series key | Compile series key |
| --- | --- | --- |
| `hline` titled / default | `Oversold`, `hline`, `hline_2`, … | same (compiler emits constant series + drawings) |
| `fill` titled / default | `Background`, `fill`, `fill_2`, … | same (null/nan column + drawings) |

Harness flags still optional for residual noise; product keys already match for hline/fill.

### Residual (compile missing series; drawings present)

| Kind | Interpret | Compile raw | After `merge_visual_series_from_drawings` |
| --- | --- | --- | --- |
| `plotshape` titled | `Buy Label`, `bull`, … | only in `__drawings` | **series keys + bool values match** |
| `plotshape` default | `shape`, `shape_2`, … | drawings (`title` null) | **keys recovered** (fancy_shapes: 35 → 0 only_interp) |
| `plotchar` | `x`, … | drawings | **keys recovered** |
| `bgcolor` default | `bgcolor`, `bgcolor_2` | drawings (no title field) | **keys recovered** via call-site order |
| `bgcolor` **titled** | e.g. `up_bg` | drawings **drop title** | materialize falls back to `bgcolor`/`bgcolor_2` until Agent 03 emit fix |

### Sample corpus proof (40 bars, local Runtime)

| Script | Before only_interp (visual) | After materialize |
| --- | --- | --- |
| `set01/…/123_ind_fancy_shapes.pine` | 35× `shape*` | **0** only_interp / only_compile; **0** value mismatches |
| `set01/…/107_ind_supertrend.pine` | `Buy Label`, `Sell Label`, `Long Stop Start`, `Short Stop Start`, `plot_6` | Labels/shapes recovered; residual **`plot_6` vs `plot`** (empty `title=""` plot — Agent 03/04) |

## Implementation notes

### Materialize algorithm

1. Filter `__drawings` to kinds `{bgcolor, plotshape, plotchar, plotarrow}`.
2. Discover call sites from bar 0 event order.
3. Title = event `title` if non-empty, else `DEFAULT_VISUAL_TITLES[kind]`, then `uniquify_series_title` against existing plot keys.
4. Fill per-bar columns: bgcolor → color string / null; plotshape/char → bool; plotarrow → float.

### Why not only compiler `plots.append`?

- **hline/fill** already use float64 plot arrays (constant price / nan placeholder) — works with engine `_coerce_plot_array`.
- **bgcolor** series are **color strings**; float64 coercion would destroy values → prefer drawings lift (object-safe) or object-array emit + engine support.
- **plotshape** bools can be float 0/1 via emit *or* drawings lift; drawings already carry `series` + `title`.

## Tests run

```bash
PYTHONPATH=src:. .venv/bin/python -m pytest \
  tests/test_bgcolor_plotshape_export.py \
  tests/test_plotting_effects.py \
  tests/test_multi_plot_cross.py \
  tests/test_drawing_all_and_last_bar.py \
  tests/test_drawing_gc.py -q --tb=short
# 34 passed
```

## Residual / handoff

### Agent 11 — Runtime compile packing (one-liner win)

In `_run_compiled` after `json_series` is built and drawings GC’d (~line 1822):

```python
from pynescript.ast.evaluator.builtins.drawing import DrawingRegistry
# ...
drawings = DrawingRegistry.gc_exported_drawings(drawings, drawing_limits)
DrawingRegistry.merge_visual_series_from_drawings(
    json_series, drawings, len(ohlcv_data)  # or n_bars
)
# Optionally build plot_meta for compile the same way interpret does.
```

This clears structural_only for plotshape/default bgcolor **without** compiler changes and without harness ignore flags. Prefer this for bgcolor **value** parity (strings).

### Agent 03 — Compiler emit (bgcolor title + optional series)

1. **`_emit_drawing` bgcolor branch** must include `title` (today title is stripped from kwargs and not added for bgcolor). Required so titled `bgcolor(..., title="up_bg")` materializes as `up_bg`, not `bgcolor`.
2. Optional: register `plots.append` for plotshape/plotchar like fill/hline for nopython-friendly float series (bool→0/1). Still need object series or drawings for bgcolor colors.
3. **Empty plot titles**: `plot(..., title="")` currently becomes series key `""` → engine rewrites to `"plot"`. Interpret packages empty as `plot_{call_site_index}`. Align empty title to `plot_{len(self.plots)}` (or uniquified `plot`) on both sides.

Suggested bgcolor emit (mirror fill title stamp):

```python
# in _emit_drawing, kind == "bgcolor":
parts.append(f"'color': {args[0] if args else 'None'}")
if "title" in kwargs:
    parts.append(f"'title': {kwargs['title']}")
elif len(args) > 1:
    parts.append(f"'title': {args[1]}")
# and do NOT exclude title from kwargs loop for bgcolor, or stamp like hline/fill
```

### Agent 04 — Engine empty key

`_normalize_result` maps `""` → `"plot"`. Coordinate with Agent 03 empty-title policy so interpret `plot_N` and compile keys match.

### Agent 11 / backend evaluator — plotarrow series

Interpret `CustomEvaluator` captures bgcolor/plotshape/plotchar but **not** `plotarrow` (only drawings on compile). Optional: add `_builtin_plotarrow` capture for full visual parity.

### Out of scope / intentional

- **barcolor**: neither mode exports a series key today.
- **fill value column**: both modes export all-null cells; color lives in plot_meta / drawings — key parity only (acceptable).
- Harness ignore flags remain valid for unfixed titled-bgcolor until Agent 03 title emit ships.

## Verdict

**partial** — Real dual-mode path for plotshape/plotchar/default bgcolor is implemented and golden-tested (materialize helper). hline/fill product dual-mode already OK. Product Runtime compile still needs Agent 11 wire-up; titled bgcolor needs Agent 03 drawing title; empty `title=""` plot keys need Agent 03/04.
