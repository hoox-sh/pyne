> Delivered from axis on 2026-11-09. Owner: pyne / HQ. Status: Done.
# Handoff: pynescript /ws/live — full `count` vs evaluated columns

from: axis / oo-spec-2
to: pyne / HQ
date: 2026-11-09
updated: 2026-11-09
severity: P0 (live chart lag)

## Symptom
AXIS live chart applies a ~10k-point full snapshot on every tick instead of a delta.
Measured live over 125 s: 54 paints, client requested `mode:"delta"` 53 times,
55/55 replies were `via:"stream-full"` (`context:"snapshot"`), one every ~2.1 s.
Client-side counters: `seqGap`/`resync` climb; payload→commit median 1904 ms, max 2696 ms
(~50% main-thread duty cycle).

## Mechanism (captured, read-only probe, key redacted)
SEND {"type":"subscribe","payload":{"kind":"script","meta":{"history_bars":10100,...}}}
RECV {"type":"full","seq":1,"count":10100,"bar_times_len":10022,
      "series_lens":{"RSI":10022,"Overbought":10022,"Oversold":10022},"plots_len":10022}
RECV {"type":"delta","seq":3,"count":10022,"base_index":10021,"tail_len":1,"forming":true}

The full declared `count` from the session window (10100) while plots/series/bar_times
were the evaluated prefix (10022). The following delta was numbered from the evaluated
count (10022). A client that caches the declared count can never splice: `count <
cachedCount` and `base_index > cachedCount` both reject, so it re-subscribes and gets
another full — every tick.

## Where
- `backend/api/live_ws.py` `_emit_ready` / `_emit_snapshot` — previously
  `make_full(..., ensured.count | len(bars), ...)` while columns came from
  `live_session.result()`.
- `backend/app.py` `_delta_envelope` — delta `count`/`base_index` from `result["count"]`.
- `src/pynescript/runtime/host.py` `result()` — `count = n_result_bars`, `session_bars = self._n_bars`.

## Decision / fix
Contract: `full.count` equals the evaluated prefix (`result["count"]` /
`len(plots)` / `len(bar_times)`), matching delta numbering.

- Added `LiveConnection._script_full_columns` — builds script full kwargs from
  `result()` and slices `bar_times` to that count (`result["times"]` when present).
- `_emit_ready` (script) and `_emit_snapshot` use that count instead of the
  ensure-window length. Series-kind full frames still use `len(bars)`.

## Proof
```
PYTHONPATH=src .venv/bin/python -m pytest tests/test_live_ws.py -q --tb=short
→ 22 passed, exit 0
```
Regression: `test_script_full_count_matches_evaluated_prefix_not_ensure_window`
(ensure_count=10, evaluated=8 → full.count=8, bar_times/plots/series length 8,
forming tip delta `base_index=7` agrees).

## Axis-side status
AXIS already caches the evaluated column count. With the server contract fixed,
deltas should splice without a resubscribe. Live confirmation still needs a
patched Pro API build deployed against AXIS.
