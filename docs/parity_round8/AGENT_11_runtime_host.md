# AGENT 11 — Runtime host packing parity

**Role / ID:** 11 — Runtime host packing  
**Date:** 2026-08-04  
**Owns:** `backend/runtime.py` (+ tests; `backend/series.py` untouched)

## Goal

Host packing parity so the **same script + same OHLCV** does not diverge between
`mode=interpret` and `mode=compile` **only because the host packed bars
differently**. Fix envelope gaps on compile. Do **not** paper over value
mismatches by switching auto backends.

## Bugs found

| Bug | Interpret | Compile | Impact |
| --- | --- | --- | --- |
| Volume default | `b.get("volume", **0.0**)` | missing/None → **1.0** | `plot(volume)` / VWAP-ish scripts diverge when host omits volume |
| Time default | `b.get("time", 0) or 0` → **0 every bar** | synthetic **`i * 60_000`** | `plot(time)` / calendar / `time[n]` diverge when host omits times |
| None volume/time cells | treated as 0 / 0 | 1.0 / synthetic | same |
| Compile envelope | full `plot_meta`, `overlay`, `script_name`, `inputs` | **missing** top-level keys | AXIS / dual-mode clients saw asymmetric envelopes |

Auto path already only fell back on eligibility / compile / runtime **errors**
(not value allclose). Documented that explicitly so future hosts do not add a
“mismatch → interpret” switch.

## What we did (files touched)

### `/mnt/data/home/jango/Git/pynescript/backend/runtime.py`

1. **Single packing contract** via `_pack_ohlcv_columns`:
   - OHLC missing/`None`/bad → `0.0`
   - volume missing/`None`/bad → `1.0` (explicit `0` kept)
   - time missing/invalid → `bar_index * 60_000`
2. **`_ohlcv_pack_cached`** — identity+fingerprint cache of `(o,h,l,c,v,t)` float64
   arrays; `_ohlcv_dicts_to_arrays` / `_ohlcv_times_to_array` share it.
3. **Interpret bar loop** uses `_pack_ohlcv_columns` (no second packing policy).
   Updates `last_bar_time` + chart viewport from packed times (incl. synthetic).
4. **Compile `_run_compiled`**:
   - one `_ohlcv_pack_cached` call for all six columns
   - series envelope parity: `plot_meta`, `overlay`, `script_name`, `script_type`,
     `inputs`, and matching `meta.*` from `_parse_script_header_fields`
5. **`_run_auto` docstring** — no value-mismatch backend swap.

### `/mnt/data/home/jango/Git/pynescript/tests/test_runtime_parity_host_r8.py` (new)

- Shared pack unit tests (volume 1.0, synthetic time, cache, numpy↔list)
- Interpret↔compile plot parity on **missing** volume/time bars
- Compile envelope keys + header parse
- Auto stays on compile when eligible; structural fallback reasons only

### Not touched

- `backend/series.py` — no change required for packing
- `backend/evaluator.py` — packing only (plot collectors unchanged)
- Compiler visitor / numba kernels (other agents)

## Before / after

**Before (missing vol/time OHLCV, `plot(volume)` + `plot(time)`):**

| Series | interpret | compile |
| --- | --- | --- |
| volume | `[0, 0, 0, …]` | `[1, 1, 1, …]` |
| time | `[0, 0, 0, …]` | `[0, 60000, 120000, …]` |

**After:** both modes → volume `1.0`, time synthetic `i * 60_000`.

**Compile envelope before:** no `plot_meta` / `script_name` / `overlay` / `inputs`.  
**After:** keys present; header-derived name/overlay match interpret for simple declarations.

## Tests run

```bash
PYTHONPATH=src:. .venv/bin/python -m pytest \
  tests/test_runtime_parity_host_r8.py \
  tests/test_compiler_numba.py::TestRuntimeAutoMode -q --tb=short
# → 12 + 5 = 17 passed
```

Manual smoke: missing-field bars → matching vol/time series both modes; compile
`script_name` / `plot_meta` populated.

## Residual / handoff

| Item | Owner |
| --- | --- |
| `time_close` last-bar policy: interpret `+86_400_000` vs compile `+59999` | Agent 03/04 (emit), not host OHLCV pack |
| Compile `plot_meta` lacks color/linewidth/hline style (engine does not export) | Agent 04/07 if product needs full meta from compile |
| Rich `input.*` declaration list on compile (still `[]`; overrides remain interpret-only) | known; auto + inputs already forces interpret |
| pyne-worker dual-host lag on pack helpers | product dual-host PR (R6 residual) |
| Corpus value MISMATCH on TA kernels | Agents 02/03/05 — not packing once bars include volume+time |

## Verdict

**win** — packing-only interpret↔compile divergences on volume/time defaults fixed
under a shared host contract; compile series envelope keys aligned; auto does not
hide value bugs by mode switching; goldens green.
