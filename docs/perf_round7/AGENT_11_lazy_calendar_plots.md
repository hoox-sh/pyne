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

# Agent 11 — Lazy calendar + light plot/input registries

| Field | Value |
| --- | --- |
| **Role / ID** | Round 7 Agent 11 — MICRO PERF (Phase 1.4 + 2.5) |
| **Date** | 2026-08-02 |
| **Verdict** | **win** (lazy calendar structural + light plots ≥10–20% on plot-heavy) |

## What you did

### Phase 1.4 — Lazy calendar (`backend/runtime.py`)

Replaced eager / name-scan calendar fill with **`LazyCalendarContext`**:

- Bar loop only calls `context.set_bar_time(bar_time)` (invalidate prior-bar cache).
- `year` / `month` / `dayofmonth` / `hour` / `minute` / `second` / `dayofweek` materialise via `utc_parts_from_ms` on **first read** of any missing calendar key.
- User assignments to a calendar key are preserved (materialise fills only missing keys).
- Removed `_CAL_NAME_RE` crude scan + `need_calendar` branch (false positives such as `dayofweek.monday` and comments no longer force civil-date math every bar).

Default path correctness: bare calendar series still produce UTC integer fields identical to prior `apply_utc_parts_to_context` eager fill.

### Phase 2.5 — `PYNE_LIGHT_PLOTS=1` (corpus / success-only)

| Layer | Behaviour when `PYNE_LIGHT_PLOTS=1` |
| --- | --- |
| `backend/runtime.py` | Sets `evaluator._pine_light_plots`; forces `_pine_need_plot_ids=False`; skips series/plot_meta packing |
| `backend/evaluator.py` | Early-return plot/hline/bgcolor/plotshape/plotchar; no columnar capture |
| `…/builtins/input.py` | `_record_input` no-op (AXIS input panel not needed) |

**Default off** — full plot export unchanged when env unset.

## Measurement (interpret, 2000 bars, median of 15)

Host: local `.venv`, `mode=interpret`.

| Script | Default | `PYNE_LIGHT_PLOTS=1` | Notes |
| --- | --- | --- | --- |
| minimal (`plot(close)`) | **45.4 ms** | ~46 ms | light ≈ noise (one plot) |
| enum-only (`dayofweek.monday`) | **47.5 ms** | — | ≈ minimal; **no false-positive calendar tax** |
| cal year (`plot(year)`) | **63.2 ms** | — | materialise cost when actually used |
| multi (8 visuals, `color.new`, shapes) | **187.1 ms** | **168.5 ms** | **−10.0%** |
| 20× `plot(close)` | **153.1 ms** | **122.4 ms** | **−20.1%** |

### Pre-change baseline context

| Scenario | Prior behaviour | After |
| --- | --- | --- |
| Script never names calendar | Skip fill (scan) | `set_bar_time` only (~same) |
| `dayofweek.monday` only | Scan **forces** full UTC fill (~+10 ms / 2k bars) | **No materialise** until bare cal key read |
| Bare `year` every bar | Eager fill all 7 fields | Materialise all 7 on first access / bar (same order of cost) |
| Always-on eager (forced) vs skip | ~55 ms vs ~45 ms on minimal | N/A — lazy never eagers unused |

**Requirement check:** calendar access is rare on typical indicator scripts → lazy helps false-positive and unused paths; when always accessed, cost is unchanged (not worse by design).

## Files touched

| File | Change |
| --- | --- |
| `/mnt/data/home/jango/Git/pynescript/backend/runtime.py` | `LazyCalendarContext`, `_env_truthy`, light-plots wiring, remove cal name scan |
| `/mnt/data/home/jango/Git/pynescript/backend/evaluator.py` | `_pine_light_plots` capture skip + early returns |
| `/mnt/data/home/jango/Git/pynescript/src/pynescript/ast/evaluator/builtins/input.py` | skip `_record_input` under light |
| `/mnt/data/home/jango/Git/pynescript/tests/test_lazy_calendar_plots.py` | **new** unit + Runtime tests |

**Not touched:** series lists (Agent 03), parse cache (Agent 05), plotting `PlotRegistry` bar-mode reuse (already O(plots)).

## Flags

| Env | Default | Effect |
| --- | --- | --- |
| `PYNE_LIGHT_PLOTS` | off | `1`/`true`/`yes`/`on` → empty `series`/`plots`/`plot_meta`/`inputs`; run still OK/error |

No flag for lazy calendar — always on; zero correctness loss vs prior successful calendar scripts.

## Tests run

```bash
PYTHONPATH=src:. .venv/bin/python -m pytest \
  tests/test_lazy_calendar_plots.py \
  tests/test_time_parts.py \
  tests/test_bgcolor_plotshape_export.py \
  tests/test_plotting_effects.py -q --tb=line
# 22 passed (lazy + plot suite)
```

Covered:

- Lazy materialise / invalidate / user assignment
- Runtime bare calendar series UTC values
- `dayofweek.*` enum without bare series
- Intraday hour/minute
- Light empty export + input skip + default restore

## Residual / follow-ups

1. Light mode still **evaluates** plot call arguments (`color.new`, series math) — only capture/export is skipped. Larger corpus wins would need AST-level “no side-effect plot sink” (risky).
2. Optional: selective field materialise (year-only skips full civil date) — micro; civil math is already integer Hinnant (~2–3 µs/bar).
3. Compile path does not use `LazyCalendarContext` (separate object-mode / Numba host).
4. Document `PYNE_LIGHT_PLOTS` in corpus runner / `scripts/showcase.py` if C1 residual harness wants throughput.

## Verdict

**win**

- Lazy calendar: structural correctness-preserving win (eliminates false-positive eager fill; default path full export intact).
- Light plots: **≥10%** multi-visual, **~20%** 20-plot series; flag-gated; default path unchanged.
