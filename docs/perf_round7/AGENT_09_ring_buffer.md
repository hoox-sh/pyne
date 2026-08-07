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

# Round 7 — Agent 09: Chronological ring buffer / O(1) lookback (Phase 2.2)

**AGENT_ID:** 09  
**ROLE:** DESIGN + partial IMPLEMENT — single chronological buffer with O(1)
Pine lookback, behind flag  
**Roadmap:** Phase 2.2 residual (`PROMPT.md`)  
**BASE_SHA:** `045190203a1991aa683147995b5f42ee71169756`  
**Date:** 2026-08-02  
**Flag:** `PYNE_SERIES_RING` — default **OFF** (`0`)  
**Verdict:** **partial**

---

## 1. Problem

Today the host keeps **two** series representations:

| Store | Layout | Lookback | Used by |
| --- | --- | --- | --- |
| `backend.series.PineSeries` | newest-first `deque` + `appendleft` | `hist[n]` O(1) at ends | context `close`/`high`/…, `series[n]` |
| `evaluator.current_series` lists | chronological (oldest first) | `list[-(n+1)]` O(1) | `ta.*` via `_as_series` / name lookup |

PineTS-style engines use **one chronological array** and map Pine offset
`n → physical[-(n+1)]`. That:

1. Removes the need to `list(reversed(PineSeries.history))` when materializing
   for window TA (already mitigated on pure-inc path; still residual on full
   recompute).
2. Aligns wrapper storage with `current_series` so a future single-buffer host
   can drop dual update (`series.update` + `list.append` every bar).

T1 (Agent 03) caps `current_series` via `PYNE_SERIES_CAP` / `_SERIES_MAX` /
`max_bars_back`. This agent does **not** own that path — ring flag is
orthogonal.

---

## 2. Design

### 2.1 Storage + lookback

```
ChronologicalSeriesBuffer
  layout: oldest → newest
  append(v):   O(1)   (list grow, or modular ring when maxlen set)
  lookback(n): O(1)   physical index of newest is end; series[n] → end - n
  series[n]:   na on negative / OOB / None / NaN  (never invent 0)
```

**Capped mode** (`maxlen=N`): fixed-capacity modular ring — overwrite oldest
when full. Composes with T1 mentally: host can pass
`pineseries_history_length(series_cap=…)` as `history_length`.

**Uncapped mode** (`maxlen=None`): plain list append (amortized O(1)).

Why not `deque(append)` alone? CPython deque middle index is O(n). Modular
list indexing is true O(1) for arbitrary lookback depth within the window.

### 2.2 PineSeries-compatible surface

`RingPineSeries` mirrors `backend.series.PineSeries`:

| API | Behaviour |
| --- | --- |
| `.current` | newest scalar |
| `.history` | `NewestFirstHistoryView` — `history[0]` == current (legacy duck-type) |
| `.update(v)` | append chronological |
| `series[n]` | O(1) lookback via buffer |
| `.history_length` / `.set_history_length` | parity with Agent 03 resize API |
| `chrono_order = True` | migration marker for zero-copy `_as_series` |

`list(reversed(ring.history))` still yields chronological order so existing
`TechnicalHelpers._as_series` (newest-first reverse) keeps working **without**
core TA edits this round.

### 2.3 Flag

| Env | Default | Effect |
| --- | --- | --- |
| `PYNE_SERIES_RING` | **off** (`0` / unset) | `make_pine_series()` → classic `PineSeries` |
| `1` / `true` / `yes` / `on` | — | `make_pine_series()` → `RingPineSeries` |

**No correctness loss when flag off:** factory returns the same class as
before; Runtime bar loop only swaps the constructor call.

### 2.4 Migration path (current → single chronological buffer)

```
Phase A (this ship) — dual path, flag off by default
  PineSeries (deque appendleft)  ──default──►  Runtime context
  RingPineSeries (chrono ring)   ──flag on──►  Runtime context
  current_series lists           ──always───►  ta.* / T1 cap

Phase B (follow-up)
  _as_series: if getattr(v, "chrono_order", False):
      return v.buffer.chronological()[-cap:]   # no reverse
  or share one ChronologicalSeriesBuffer as both context series
  and current_series entry (view adapters)

Phase C (optional unify)
  Drop dual update in Runtime bar loop:
    one buffer.append per OHLCV field
    context["close"] = wrapper over buffer
    current_series["close"] = chrono view / same buffer
  Keep PYNE_SERIES_RING as kill-switch until goldens green at scale
```

**Do not** merge with T1 list trim in the same PR — Agent 03 owns
`trim_series_lists` / `resolve_series_cap`. Ring `maxlen` should track
`pineseries_history_length(...)` (already wired in Runtime when creating
series).

---

## 3. What shipped

| File | Change |
| --- | --- |
| `src/pynescript/ast/evaluator/series_buffer.py` | **NEW** — `ChronologicalSeriesBuffer`, `NewestFirstHistoryView`, `RingPineSeries`, `series_ring_enabled`, `make_series` |
| `backend/series.py` | `series_ring_enabled()`, `make_pine_series()` factory; module doc for flag |
| `backend/runtime.py` | Host OHLCV series via `make_pine_series(history_length=_ps_hist)` (minimal hook) |
| `tests/test_series_ring_buffer.py` | **NEW** — 19 goldens |
| `docs/perf_round7/AGENT_09_ring_buffer.md` | this report |

**Not shipped (intentionally):**

- `_as_series` zero-copy branch for `chrono_order` (would touch Agent 02/03 TA hot path)
- Removing dual `current_series` list appends
- Enabling the flag by default
- Changing legacy `PineSeries` deque layout

---

## 4. Structural proof (no full-path bench claim)

Flag **off** (default):

```text
make_pine_series() → backend.series.PineSeries  # identical class
```

Flag **on**:

```text
series[n] → ChronologicalSeriesBuffer.lookback(n)  # O(1) modular / list end
history[0] → lookback(0)                           # duck-type for _series_last
reversed(history) → chronological                  # _as_series still correct
```

Runtime parity (ring on ≡ ring off) for `close[0]`/`[1]`/`[3]`/`[20]` including
na OOB — covered by `test_runtime_flag_on_close_offsets_match_off`.

No ≥10% interpret bench claim this round (partial integration; dual list
update still runs). Structural win is the buffer type + safe opt-in host wire.

---

## 5. Tests

```bash
PYTHONPATH=src:. .venv/bin/python -m pytest tests/test_series_ring_buffer.py -q --tb=short
# → 19 passed

PYTHONPATH=src:. .venv/bin/python -m pytest \
  tests/test_ta_incremental.py::test_pineseries_history_offset_na_and_float -q
# → 1 passed (legacy PineSeries unchanged)
```

Goldens include:

- empty / `[0]` / `[1]` / `[n]` / OOB → na
- float trunc, NaN, negative, `None` index → na
- `maxlen` ring drops oldest
- newest-first view ≡ deque semantics for reverse materialize
- RingPineSeries ≡ PineSeries offsets on same update stream
- flag default off → legacy class
- Runtime off path + Runtime on/off parity

**Note:** host parse-AST multi-run cache can return a mutated tree for the
*same* source string on a second `Runtime.run` in-process (residual of
Phase 1.6 / Agent 05). Parity test uses distinct source comments to avoid
that collision — not a ring bug.

---

## 6. Residual / follow-ups

1. **`_as_series` chrono fast path** — if `chrono_order`, skip reverse; use
   `buffer.chronological()` or a capped tail view.
2. **Single buffer host** — stop dual-writing PineSeries + `current_series`
   lists once flag-on corpus is green.
3. **Default-on** only after: full `test_ta_incremental` + Runtime parity +
   corpus sample with `PYNE_SERIES_RING=1`.
4. **Parse AST multi-run** — second visit of cached tree loses plots
   (`script_name` becomes `"plot"`). Out of scope here; blocks fair multi-run
   benches until fixed.
5. **pyne-worker twin** — if worker constructs `PineSeries` directly, switch
   to `make_pine_series` for H1 parity (Agent 06).

---

## 7. Ownership / non-interference

| Concern | Owner | Interaction |
| --- | --- | --- |
| `current_series` cap / `trim_series_lists` | Agent 03 (T1) | Untouched; ring uses same `history_length` from `pineseries_history_length` |
| TA last-sample / `_as_series` reverse | Agent 02 residual | Duck-type preserved via newest-first view |
| Lazy calendar context | Agent 11 | Concurrent Runtime edits; series factory independent |

---

## 8. Verdict

**partial** — Phase 2.2 buffer type + unit goldens + flagged Runtime factory
shipped; default path bit-identical. Full single-buffer host and `_as_series`
zero-copy left for a follow-up once T1 settles and multi-run parse cache is
stable.
