# Agent 03 — T1: Cap `current_series` to `max_bars_back` / `_SERIES_MAX`

**Role:** T1 series memory cap  
**Date:** 2026-08-02  
**Roadmap ID:** T1  
**Verdict:** **win**

## What shipped

Formalized host OHLCV list capping (Round-2 always-on trim) into a documented,
flagged policy with goldens and `max_bars_back` awareness.

### Files

| File | Change |
| --- | --- |
| `backend/series.py` | Cap policy API: `series_cap_enabled`, `resolve_series_cap`, `parse_max_bars_back_from_source`, `trim_series_lists`, `series_cap_limit`, `pineseries_history_length`, `estimate_series_bytes`; `PineSeries.set_history_length`; docs for min history / EMA residual. Coexists with Agent 09 `make_pine_series` / `PYNE_SERIES_RING`. |
| `backend/runtime.py` | Interpret path: resolve cap from env + `_SERIES_MAX` + source `max_bars_back`; optional trim via `trim_series_lists` when flag on; stash `_pine_series_cap` / `_pine_series_cap_enabled` on evaluator; PineSeries history floor 1000, raised when cap/MBB larger. |
| `tests/test_series_cap.py` | **New** — policy unit tests + Runtime goldens (capped ≡ uncapped last N). |
| `docs/perf_round7/AGENT_03_series_cap.md` | This report. |

### Flags

| Env | Default | Meaning |
| --- | --- | --- |
| **`PYNE_SERIES_CAP`** | **ON** (`1`) | Trim append-only `current_series` OHLCV lists. Disable: `0` / `false` / `no` / `off`. |
| **`PYNE_SERIES_MAX`** | unset | Absolute cap size override (positive int). |
| Cap size | `max(_SERIES_MAX, max_bars_back)` | `_SERIES_MAX` default **256**; script `max_bars_back=N` raises host keep size. |
| Slack | **64** | Grow to `keep+64`, then `del lst[:drop]` back to `keep` (amortized; no rebind). |

**Why default ON:** Cap has been always-on since Round 2 host hygiene; goldens below prove last-N identity for periods ≪ cap under default incremental TA. Default OFF would regress memory and reintroduce unbounded growth.

### Correctness / min history

| Kernel class | Min history needed | Cap-safe when |
| --- | --- | --- |
| Window (`sma`, `highest`, `lowest`, …) | **period `p`** samples | `p ≤ cap` |
| Recursive + **incremental TA** (default) | Last sample + call-site state | Always (once warm) |
| Recursive + **full recompute** (`PYNE_TA_INCREMENTAL=0`) | Full series for bit-identity | Can diverge when `bars ≫ cap` |

- OOB history → **`None` (na)**, never `0`.
- PineSeries maxlen floor remains **1000** (pre-T1 host default); raised only when resolved cap/`max_bars_back` is larger — no regression for `close[n]` with `n ≤ 999`.

### Trim strategy

Prefer **in-place `del lst[:drop]`** on chronological lists (not deque for `current_series`): TA helpers slice/list-index chrono lists; deque would break `series[-max:]`. Slack avoids O(n) delete every bar.

## Before / after (structural proof)

Simulation: 20 000 bars × 6 OHLCV-style lists, keep=256, slack=64:

| Mode | Final list len | ~pointer bytes (6 lists) | Append wall |
| --- | ---: | ---: | ---: |
| Uncapped | 20 000 | ~960 000 | 0.020 s |
| Capped | 305 | ~14 640 | 0.021 s |

**Memory ratio ~78×** at 20k bars (scales as `n_bars / cap`). CPU of trim is negligible vs AST/TA.

Production Runtime already trimmed before this round; T1 adds **flag**, **max_bars_back**, **tests**, and a single policy module.

## Goldens (tests)

```bash
PYTHONPATH=src:. .venv/bin/python -m pytest tests/test_series_cap.py -v --tb=short
# 15 passed
```

Coverage:

- Flag default ON / disable tokens  
- `resolve_series_cap` + `PYNE_SERIES_MAX` absolute override  
- Source scan `max_bars_back=N`  
- `trim_series_lists` keeps newest; slack bound  
- PineSeries OOB → `None` (not 0); `set_history_length`  
- Runtime: SMA / EMA+RSI / combo last N with cap on ≡ off  
- Runtime: `max_bars_back=400` → `_pine_series_cap == 400`  
- Runtime: cap off → full `len(current_series)==n_bars`  
- Runtime: cap on → `keep ≤ len ≤ keep+slack` after 500 bars  

## Other tests

```text
tests/test_series_cap.py                          15 passed
tests/test_evaluator.py + tests/test_ta_incremental.py
  — multi-run failures are parse-cache AST mutation (Agent 05 residual):
    same source reused → empty plots on 2nd Runtime.run without clear_parse_cache().
  — Not caused by T1; proven: clear_parse_cache() between runs restores parity.
```

T1 tests call `clear_parse_cache()` between Runtime invocations.

## Residual / follow-ups

1. **Parse cache mutates AST** (Agent 05): process-level LRU returns same `Script` object; second interpret empties plots. Fix: copy-on-cache or freeze tree / clone before visit. Blocks clean multi-run goldens without clear.
2. **Full-recompute EMA/RMA** with long charts + list cap: document-only residual when `PYNE_TA_INCREMENTAL=0`; default inc path is fine.
3. **Dual-host**: mirror flag + `trim_series_lists` usage in pyne-worker when H1 lands residual host parity (list cap already partially mirrored historically).
4. **`max_bars_back(series, N)` call form** only partially covered (regex catches `max_bars_back=N` assignment / kwargs, not all positional call shapes).
5. ROADMAP / `docs/missing_features.md`: mark T1 done at synthesis.

## Verdict

**win** — T1 complete: flagged default-ON series cap, `max_bars_back` raise, in-place trim, goldens prove last-N identity for normal lookbacks, structural memory win documented, zero na→0 coercion, no whole-script vectorization.
