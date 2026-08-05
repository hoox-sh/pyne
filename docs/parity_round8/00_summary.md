# Round 8 synthesis — Corpus parity (interpreter + compiler)

**Date:** 2026-08-04  
**BASE_SHA:** `b1035b106a17a735b9608250d82fc433194007b2`  
**Agents:** 12 spawned; several completed; parent finished critical handoffs after session drop

## Headline results

| Metric | Result |
| --- | --- |
| set01 Runtime interpret | **249/249 OK (100%)** |
| set01 Runtime compile (runs) | **249/249 OK (100%)** |
| Focused unit suite (R8 surface) | **126 passed**, 1 skipped |
| Known residual list (10 scripts @ 200 bars) | **5 OK / 5 MISMATCH** |
| Recovered from prior known MISMATCH set | `193` RSI, `156` MTF structure bias; builtins RSI/BB/supertrend green |

## Agent scoreboard

| ID | Role | Verdict | Key outcome |
|---:|---|---|---|
| 01 | Inventory | measure-only | set01 100% both modes; full sweeps aborted under load |
| 02 | Numba kernels | **blocked** | no `numba_builtins` edits |
| 03 | Compiler emit | **partial** | SYMBOL/tickerid security passthrough; cache v3 |
| 04 | Compile engine | **win** | duplicate plot title uniquify on pack |
| 05 | Interpret TA | **partial** | strict stdev/dev/variance windows |
| 06 | Strategy dual | **partial** | exit fill + percent series; strategy samples still open |
| 07 | Plot keys | **partial** | materialize visual series helper |
| 08 | request/MTF | **win** | foreign-na + HTF UDF → na; MTF bias OK |
| 09 | Collections | **win** | soft-na + goldens |
| 10 | Expressions | **win** | switch-na subject semantics |
| 11 | Runtime host | **win** | unified OHLCV pack + compile envelope |
| 12 | Harness | **win** | smoke 17 scripts; expected_error; EXPECTED_FAIL |

## Parent glue (after subagent drop)

1. Compiler `SYMBOL` / bare `tickerid` chart security (Agent 03 residual)
2. Runtime wires `merge_visual_series_from_drawings` after compile GC
3. Plotshape materialize: `False` → `None` (interpret sentinel parity)
4. Disk IR `_DISK_META_VERSION` **2 → 3**
5. Tests updated for host materialize; bare security `use_cache=False`

## Round 9 follow-up (same day)

| Fix | Result |
| --- | --- |
| Stoch `not source` early-return skipped TA slots → EMA seed thrash | **`073` OK**; `ema` after `stoch(rsi)` restored |
| Heikin-Ashi `request.security` interpret + compile | **`045` OK** |
| Goldens | `tests/test_parity_r9_kernels.py` |

## Remaining MISMATCH (next priority)

| Script | Likely owner |
| --- | --- |
| `245_ind_hma_kahlman_…` | custom HMA/Kahlman UDF float-period WMA |
| `178_ind_bulls_bears_index_bbi_2` | circular-buffer BBI + `nz` warm-up |
| `071_str_multi_vwap_crossover` | session/midnight VWAP anchors + UDT strategy |

## How to verify

```bash
PYTHONPATH=src:. .venv/bin/python -c "
from pynescript.compiler import clear_compile_cache, clear_disk_compile_cache, clear_numba_function_caches
clear_compile_cache(); clear_disk_compile_cache(); clear_numba_function_caches()
"
PYTHONPATH=src:. .venv/bin/python -m pytest \
  tests/test_compiler_engine_r8.py tests/test_runtime_parity_host_r8.py \
  tests/test_expr_parity_r8.py tests/test_corpus_collections_r8.py \
  tests/test_interp_compile_parity.py tests/test_request_data_feed.py \
  tests/test_bgcolor_plotshape_export.py -q --tb=line

PYTHONPATH=src:. .venv/bin/python scripts/compare_interp_compile.py \
  --file-list .cache/parity_r8_filelist_set01_02.txt --limit 80 --bars 200 \
  --ignore-hline-keys --ignore-fill-keys --workers 4
```

## Product impact

- **P1p** advanced: structural packing + foreign-na + visual series + security
  passthrough; value-kernel tail still open.
- **C1**: set01 Runtime fully green; collections/expr soft paths reduce long-tail
  RUN_FAIL risk on later sets.
- **Do not** re-enable concurrent 12-agent + multi-thousand corpus sweeps without
  throttling workers (false TIMEOUT).
