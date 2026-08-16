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

# Round 9 — Agent 04: Runtime host + series hot path

**AGENT_ID:** 04  
**ROLE:** Runtime host + series hot path (bar-loop around the evaluator visit)  
**Date:** 2026-08-16  
**BASE_SHA:** `41d3e491dc42c6ea918abc8e85e1065fae2e5af6`  
**Worktree:** `/home/jango/.grok/worktrees/git-pynescript/subagent-01a0092a-d64b-7931-8873-62722ef725f6`  
**Flag:** `PYNE_SERIES_RING` remains default **OFF** (audit reject: corpus + polarity still dual-path)  
**Verdict:** **win**

---

## 1. Role / ID

Speed the interpret bar-loop host around `evaluator.visit`: series updates,
`current_series` append/cap, plot column packing, calendar, strategy drain.
Do **not** default-on the ring. Dual-write skip when `PYNE_SERIES_RING=1`
already existed — extended the skip to unused derived series and cheapened
the default-off path.

`src/pynescript/ast/evaluator/series_buffer.py` was **not** edited (ring
correctness already holds; host dual-write skip already binds `ChronoTailView`).

---

## 2. What you did (files touched)

| File | Change |
| --- | --- |
| `src/pynescript/runtime/host.py` | Bar-loop series inline; skip unused derived / strategy snapshot / alerts; OHLCV list pack cache; historical barstate; cheaper plot-meta intern |
| `src/pynescript/runtime/series.py` | `apply_bar_sample()` helper (wrapper + optional chrono list; ring omits dest) |
| `tests/test_series_cap.py` | `apply_bar_sample` + unused derived lists stay empty |
| `tests/test_series_ring_buffer.py` | Ring `apply_bar_sample` (no dual list) |
| `tests/test_runtime_package.py` | hl2/hlc3/ohlc4/tr/time_close; `input.source` hl2 override; indicator snapshot skip vs strategy events |
| `tests/test_runtime_parity_host_r8.py` | List pack cache identity hit |
| `docs/perf_round9/AGENT_04_runtime_host.md` | this report |

**Not touched:** `runtime/evaluator.py` (Agent 01), TA submodules (Agent 02),
`expressions.py` (Agent 03). Ring default still off.

### 2.1 Cheapen default (ring-off) series update + `current_series`

cProfile of `minimal` (8 × 2000 bars) before the patch:

| exclusive | share | notes |
| --- | ---: | --- |
| `PineSeries.update` | ~5.2% | 11 wrappers × bars (`176000` calls) |
| `deque.appendleft` | ~3.3% | same |
| `snapshot_bar_series` | ~3.4% | **indicators never read this** |
| `_pack_ohlcv_columns` | ~5.2% | re-walked every interpret run |
| `Runtime.run` loop body | ~18% | float()/try + barstate + dual appends |

Changes:

1. **Inline** `.current = v` + `history.appendleft(v)` — same contract for
   deque `PineSeries` and ring `NewestFirstHistoryView`. Drops the Python
   `update()` call on the host OHLCV path.
2. **Skip unused derived** (`hl2` / `hlc3` / `ohlc4` / `tr` / `time_close`)
   unless the source names them **or** contains `input.source` (dropdown can
   pick hl2/hlc3/ohlc4/tr with no identifier). Packed OHLC cells are already
   floats — no per-bar `float()` / `try`.
3. **Cap trim:** running `_hist_n` instead of `len(sl_close)`; disable the
   per-bar check when `n_bars <= keep+slack`.
4. Ring path still binds `ChronoTailView` and skips the second list write
   (`sl_* is None`). Unused derived skip now also applies when the ring is on.

### 2.2 Host packing

- **OHLCV:** `_pack_ohlcv_columns_cached` — identity + fingerprint cache of
  Python float lists. Interpret used to re-walk dicts every run; compile
  `_ohlcv_pack_cached` now asarrays from the same list cache.
- **Plot columns:** capture lists still reused when JSON-safe (`pack_dirty`
  / unknown kinds only). Title `str()` / intern only when needed; unique-title
  suffix loop skipped when titles are already unique. **No evaluator flags
  required** — titles/kinds live on `_plot_meta_list` and are already stable
  after bar 0.

### 2.3 Empty strategy drain / drawing / alerts

Empty drain (`if strategy_events`) and empty `DrawingRegistry.export_for_api`
already existed. Remaining allocs:

- `snapshot_bar_series()` ran **every bar for indicators** (3 list appends +
  `signed_position_size`). Now gated on `\bstrategy\b`.
- Event `clear()` / drain skipped when the script is not a strategy.
- Alert export import+walk skipped when source has no `alert(` /
  `alertcondition(`.
- `DrawingRegistry.limits_dict()` still always stamped on `meta` (envelope).

### 2.4 Realtime / call-index micros

- Historical-only hosts keep pre-loop `isnew`/`ishistory`/`isconfirmed`/
  `isrealtime` and only flip `islastconfirmedhistory` on the last bar.
- Reset `_cross_call_i` / `_ta_call_i` only when the source uses those
  families (`ta.` / crossover). `_plot_call_i` still every bar.
- Multi-tick realtime path unchanged (`_discard_realtime_plot_tick` +
  `reset_plots`).

---

## 3. Before / after

Isolated interpret (`n=2000`, warmup 3 / iters 9, same process recipe)
**before** this patch vs official `scripts/bench_pipeline.py` **after**.

| script | before med_ms | after med_ms | Δ | bars/s after |
| --- | ---: | ---: | ---: | ---: |
| **minimal** | 25.080 | **16.36** | **−34.5%** | 122k |
| **ta_sma** | 38.123 | **26.14** | **−31.4%** | 76.5k |
| ta_combo | 207.615 | 178.21 | −14.2% | 11.2k |
| strategy_ish | 103.391 | 87.85 | −15.0% | 22.8k |

Official after (`/tmp/r9_a04.json`):

```text
minimal      16.36 ms   8.18 µs/bar   122285 bars/s
ta_sma       26.14 ms  13.07 µs/bar    76499 bars/s
ta_combo    178.21 ms  89.10 µs/bar    11223 bars/s
strategy_ish 87.85 ms  43.93 µs/bar    22765 bars/s
```

DoD: **≥10–15% on `minimal` and `ta_sma`** (host-bound). No >5% regression
on any of the four interpret scripts. Compile path unchanged (cache reuse only).

Structural proof (independent of wall time):

- Default `make_pine_series()` is still `PineSeries` (flag off).
- Indicators: `_strategy_state._size_hist` stays empty (no snapshot alloc).
- Unused `current_series["hl2"]` / `["tr"]` stay length 0 on `plot(close)`.
- Warm interpret of the same `ohlcv_data` object returns the **same list
  objects** from `_pack_ohlcv_columns_cached`.

---

## 4. Tests

```bash
PYTHONPATH=src:. .venv/bin/python scripts/bench_pipeline.py --json /tmp/r9_a04.json
PYTHONPATH=src:. .venv/bin/python -m pytest \
  tests/test_series_cap.py tests/test_series_ring_buffer.py \
  tests/test_runtime_package.py tests/test_runtime_parity_host_r8.py \
  tests/test_parity.py tests/test_evaluator.py -q --tb=line
```

| suite | result |
| --- | --- |
| exclusive (cap / ring / package / host r8) | **76 passed** |
| `tests/test_parity.py` + `tests/test_evaluator.py` | **268 passed, 6 skipped** |
| new goldens | derived series, `input.source` hl2, indicator snapshot skip, list pack cache, `apply_bar_sample` ring/legacy |

Ring default-off + on/off close-offset parity tests still green.

---

## 5. Residual / follow-ups

1. **Default path still dual-writes** OHLCV (`PineSeries` deque + chrono lists).
   Unifying onto the ring requires default-on `PYNE_SERIES_RING` — **rejected**
   until corpus + polarity are single-path.
2. **`visit_Call` / plot capture / nested TA** still dominate `ta_combo`
   (Agents 01–03). Host is no longer the first exclusive slice on that script.
3. Plot-meta intern is once-per-run O(plots). Further reuse would need
   evaluator-stable interned titles across warm `Runtime.run` (not required).
4. `DrawingRegistry.limits_dict()` still allocates a 4-key dict every run
   for AXIS GC caps — envelope, not bar-loop.
5. `time` series is always updated (too common to scan-skip). `open`/`high`/
   `low`/`volume` likewise.

---

## 6. Verdict

**win** — host-bound `minimal` / `ta_sma` ≥30% faster on this machine; also
≥10% on `ta_combo` / `strategy_ish`. Zero correctness loss vs current oracle
(series offsets, `na`, var/varip, last-bar flags, `input.source`). Ring stays
flagged off.
