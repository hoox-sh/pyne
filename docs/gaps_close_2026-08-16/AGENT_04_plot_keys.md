# Copyright (C) 2024-2026 jango_blockchained
#
# SPDX-License-Identifier: AGPL-3.0-or-later

# AGENT 04 — Close compile plot keys (hline / fill / bgcolor / empty title)

| Field | Value |
| --- | --- |
| **Role / ID** | 04 — compile plot keys |
| **Verdict** | **win** |
| **Date** | 2026-08-16 |
| **BASE_SHA** | `ffd43641` |

## Goal

Dual-host series **keys** match for first-party scripts so harness
`--ignore-hline-keys` / `--ignore-fill-keys` are not required.

Residual from `docs/parity_round8/AGENT_07_plot_keys.md`:

1. `_emit_drawing` bgcolor dropped `title=` → titled bgcolor materialized as `bgcolor` not `up_bg`.
2. `plot(..., title="")` compile `""` / `"plot"` vs interpret `plot_N`.
3. hline/fill titled/default already uniquified — keep matching.

## What changed

| File | Change |
| --- | --- |
| `src/pynescript/compiler/compiler.py` | bgcolor drawing stamps `title=`; empty/missing `plot()` title → `plot_{visual_index}`; `_visual_plot_i` tracks interpret capture order (hline/fill/plot + bgcolor/plotshape/plotchar) |
| `src/pynescript/compiler/engine.py` | `_normalize_result` maps empty key → `plot_N` (not `"plot"`); `_DISK_META_VERSION` 9 → 10 |
| `tests/test_bgcolor_plotshape_export.py` | titled bgcolor dual-host golden |
| `tests/test_multi_plot_cross.py` | combined key-set golden |
| `tests/test_plotting_effects.py` | empty title registry stays `""` (host/compile rename) |
| `tests/test_plot_keys_dual_host.py` | **new** normalize + compile titles + dual-host keys |
| `docs/gaps_close_2026-08-16/AGENT_04_plot_keys.md` | this report |

**Not changed:** numeric TA kernels, nvi, supertrend, trail, Flask, pynets, `request.*`, harness CLI ignore flags (still optional).

## Before / after

Script:

```pine
hline(30)
hline(70)
p_empty = plot(close, title="")
p_open = plot(open)
fill(p_empty, p_open, title="Background")
bgcolor(..., title="up_bg")
plotshape(..., title="Buy Label")
```

| Kind | Interpret (unchanged) | Compile before | Compile after |
| --- | --- | --- | --- |
| untitled hlines | `hline`, `hline_2` | same | same |
| titled fill | `Background` | same | same |
| titled bgcolor | `up_bg` | `bgcolor` (title dropped) | **`up_bg`** |
| `plot(close, title="")` | `plot_2` | `""` → `"plot"` | **`plot_2`** |
| `plot(open)` | `plot_3` | `plot_3` or drifted | **`plot_3`** |
| titled plotshape | `Buy Label` | recovered via drawings | **`Buy Label`** |

Key set both hosts:

`hline`, `hline_2`, `plot_2`, `plot_3`, `Background`, `up_bg`, `Buy Label`

## Implementation notes

- Empty title uses **interpret capture index** (`_visual_plot_i`), not only `len(self.plots)`. bgcolor / plotshape are drawings (not float plots) but still consume a capture slot so later `plot_N` keys stay aligned.
- bgcolor title is stamped in `_emit_drawing` (kwargs, or a string positional). Host `merge_visual_series_from_drawings` then lifts `up_bg` instead of default `bgcolor`.
- Object-mode leftover `""` dict keys are remapped in `_normalize_result` to `plot_{count of existing non-__ keys}`.
- Disk IR version bumped so cached emit without bgcolor titles is not reused.

## Tests run

```text
PYTHONPATH=src:. .venv/bin/python -m pytest \
  tests/test_bgcolor_plotshape_export.py \
  tests/test_plotting_effects.py \
  tests/test_multi_plot_cross.py \
  tests/test_interp_compile_parity.py \
  tests/test_plot_keys_dual_host.py \
  -q --tb=short
  → 50 passed, 18 skipped
```

Skipped: optional third-party corpus in `test_interp_compile_parity.py` (files absent). Always-on first-party smoke ran with `ignore_hline_keys=False` / `ignore_fill_keys=False`.

`tests/test_compiler_engine_r8.py` has 4 pre-existing `__drawings`-in-pack-result assertions (not owned; not caused by empty-key remap).

## Residual

- **barcolor** still has no series key (intentional, both modes).
- **plotarrow** not counted in `_visual_plot_i` (interpret does not capture it as a series).
- Harness `--ignore-hline-keys` / `--ignore-fill-keys` remain as optional CLI.

## Verdict

**win** — titled bgcolor, empty `plot(title="")`, untitled `plot(open)`, two hlines, titled fill, and titled plotshape share one series key set on interpret and compile.
