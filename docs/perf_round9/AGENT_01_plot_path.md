# Copyright (C) 2024-2026 jango_blockchained
#
# This file is part of pynescript.
#
# pynescript is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pynescript is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: AGPL-3.0-or-later

# Round 9 Agent 01 — Plot-path structural (capture / `_builtin_plot`)

| Field | Value |
| --- | --- |
| **Role / ID** | 01 — plot-path structural (capture / `_builtin_plot*` / `_write_plot_cell`) |
| **Date** | 2026-08-16 |
| **BASE_SHA** | `41d3e491dc42c6ea918abc8e85e1065fae2e5af6` |
| **Machine** | Linux, parent `.venv` Python 3.14 (`/mnt/data/home/jango/Git/pynescript/.venv`) |
| **Verdict** | **partial** (structural win + fill/kwargs capture; official `ta_combo` ~2%) |

## Role

Cut interpret plot-path cost. Round 7 cProfile had plot capture + `_builtin_plot` +
packing at ~75% of `ta_combo` wall. After R5–R7 (columnar pre-size, light plots,
call-site reuse, skip `PlotRegistry` when no `fill()`), that map is stale:

- `_capture_plot` is already **8 ncalls** (first bar only)
- `_pack_interpret_plot_columns` reuses JSON-safe lists (~0 ms)
- positional `_builtin_plot` is ~**3%** exclusive of a profiled `ta_combo` run
- remaining ~50 ms / 2k bars vs no-plot `ta_combo` is almost all **`visit_Call`
  × 8** (Agent 03), not cell writes

This agent attacked leftover **per-bar** work on kwargs/color plots, fill-script
registry, `_as_plot_int`, and pre-sized write branches.

## Files touched

| File | Change |
| --- | --- |
| `src/pynescript/runtime/evaluator.py` | Unified steady-state `_builtin_plot` (positional **and** kwargs); `_plot_color_pending`; cached `super()` registry; slim `_write_plot_cell` / `_append_plot_value`; `_as_plot_int` + PineSeries type-identity |
| `src/pynescript/ast/evaluator/builtins/plotting.py` | `_bar_reuse_plot` — skip title/style/int after first bar; `_as_str`/`_as_int` type-identity |
| `tests/test_plotting_effects.py` | `_as_plot_int` + bar-mode title reuse |
| `tests/test_multi_plot_cross.py` | kwargs column length / `plot(na)` / lazy first color |
| `docs/perf_round9/AGENT_01_plot_path.md` | this report |

**Not edited:** `src/pynescript/runtime/host.py` (Agent 04). Packing already
reuses capture lists when `pack_dirty` is false — **no host patch required**.

## What changed (1–3 real wins)

### 1. Steady-state `_builtin_plot` — kwargs == positional

After first registration, both `plot(s)` and `plot(s, title=…, color=…)`:

- type-identity coerce (`float`/`int`/`None`) then index-write `cols[i][bar]`
- **no** `_append_plot_value` / `_write_plot_cell` / `_serialize_color`
- `_plot_color_pending`: skip per-bar `kwargs.get("color")` + `meta.get` once
  every site has a non-null color (dynamic `color=na` on bar 0 still fills later)
- `_pine_need_plot_ids` False → no `Plot` / `super()` (Runtime default, no `fill()`)

`_write_plot_cell` dropped `_plot_n_bars` triple-branch: `bar < len(col)` write
else append. No leftover `list.append` growth on host pre-sized columns.

### 2. `_as_plot_int` / unwrap type-identity

- `_as_plot_int`: `int` / `None` / `float` / `bool` before `_unwrap_scalar`
- `_unwrap_scalar`: `type is PineSeries` → `.current` (no `getattr`)
- plotting `_as_str` / `_as_int` same identity path

### 3. No per-bar Plot / string work when registry is on (fill scripts)

- `_maybe_registry` caches `super()._builtin_plot*` (no `getattr(super(), name)`
  every bar)
- `_bar_reuse_plot`: after bar 0, only series/color/price/handles; **no**
  `_as_str(title)` / `_as_int(linewidth)` / `_fill_plot` / `**fields` dict
- CustomEvaluator inits `_plot_call_i = 0`

## Before / after

### Official `bench_pipeline.py` (interpret @ 2000)

```bash
PYTHONPATH=src:. /mnt/data/home/jango/Git/pynescript/.venv/bin/python \
  scripts/bench_pipeline.py --json /tmp/r9_a01_after2.json
```

| script | before med_ms | after med_ms | Δ |
| --- | ---: | ---: | ---: |
| **minimal** | 26.03 | **24.58** | **−5.6%** |
| ta_sma | 38.25 | 37.26 | −2.6% |
| **ta_combo** | 202.55 | **198.87** | **−1.8%** |
| strategy_ish | 101.95 | 102.26 | +0.3% (noise) |

No >5% regression on `minimal`. `ta_combo` official wall is **not** 10–15% —
positional capture was already lean; remaining tax is `visit_Call`.

### Variant isolation (same host; interpret @ 2000)

| script | before med_ms | after med_ms | note |
| --- | ---: | ---: | --- |
| ta_combo **no plots** | 146 | ~162* | *later session noisier; delta vs 8-plot still ~50 ms |
| ta_combo 8× `plot(s)` | 197 | ~199 | positional — already hot |
| ta_combo `title=` kwargs | 244 | ~256* | leftover is **arg eval** of `title=` (Agent 03) |
| ta_combo titled+**color** | 273 | ~276* | capture body 2.6× cheaper (see cProfile) |
| 8× `plot(close)` | 63.6 | **60.7** | PineSeries unwrap |
| **fill + 2 plots** | **81.5** | **68.5–70.9** | **−13–16%** real path |

\*Absolute ms drifted with machine load; use cProfile for kwargs capture.

### Structural cProfile (titled+color, 8 plots × 2000)

| metric | before | after |
| --- | ---: | ---: |
| `_builtin_plot` tottime / cumtime | 0.042 / **0.085** | 0.024 / **0.032** (**2.6×**) |
| `_append_plot_value` ncalls | 15 992 | **0** |
| `_write_plot_cell` ncalls | 15 992 | **0** |
| `_serialize_color` ncalls | 8 (already) | **8** |
| `_lazy_plot_color` ncalls | — | **0** (colors set on bar 0) |

Fill script (2 plots + `fill()`): `_as_str` **3** (first bar), `_bar_reuse_plot`
2000, `_plot_upsert` **1**, `_fill_plot` **3**.

## Tests

```bash
PYTHONPATH=src:. /mnt/data/home/jango/Git/pynescript/.venv/bin/python -m pytest \
  tests/test_plotting_effects.py tests/test_bgcolor_plotshape_export.py \
  tests/test_lazy_calendar_plots.py tests/test_multi_plot_cross.py \
  tests/test_drawing_all_and_last_bar.py tests/test_drawing_export_last_bar.py \
  tests/test_parity.py tests/test_evaluator.py -q --tb=line
# 325 passed, 6 skipped
```

Locked: titles/kinds, `plot(na)` → `None` (never 0), kwargs column length ==
bars, lazy first non-null `color`, fill handles, bar-mode title reuse.

## Host packing (Agent 04)

`_pack_interpret_plot_columns` already reuses capture lists for
`plot`/`hline`/`bgcolor`/`fill`/`plotshape`/`plotchar`/`plotarrow` when
`pack_dirty` is false. Capture still stores JSON-safe cells and only sets
`_plot_pack_dirty` on non-scalar leftovers. **No parent patch.**

## Residual / follow-ups

1. **`visit_Call` × 8** is the remaining ~50 ms `ta_combo` plot tax (~25% of
   200 ms). Agent 03. Capture cannot remove those frames.
2. `plot(..., title=…, color=…)` still evaluates kwargs every bar (AST). Capture
   no longer pays for them; dispatch still does.
3. Fill scripts still call `_maybe_registry` every plot (needed for handles);
   only the `getattr(super())` + string coerce is gone.
4. Do not default-on `PYNE_LIGHT_PLOTS` (drops series export).

## Verdict

**partial**

- Structural: kwargs/color capture aligned with positional; no per-bar Plot /
  string / `_as_plot_int` / append growth on the default path.
- Real wall: fill **−13–16%**; official `ta_combo` **−1.8%** (visit_Call bound);
  `minimal` **−5.6%** (no regression).
