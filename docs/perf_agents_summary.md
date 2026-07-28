# Performance agents summary (2026-07-28)

Four isolated worktree agents optimized **parse**, **unparse**, **evaluate**,
and **compile+execute**. Results were merged into the main workspace.

Full writeups: `perf_agent_parse.md`, `perf_agent_unparse.md`,
`perf_agent_evaluate.md`, `perf_agent_compile_execute.md`.

## Headlines

| Area | Win | Notes |
|---|---|---|
| **Parse** | **~5.4×** (complex ~16 KB script) | SLL-first + LL fallback; skip annotations without `@`; `_setLocations` fast path |
| **Unparse** | **~1.95×** (99 set01 scripts) | Thread-local unparser reuse; type-keyed dispatch; less CM overhead |
| **Evaluate** | **~1.9–6.5×** TA Runtime paths | Incremental stdev/BB/highest/lowest/wma/tr/change (`PYNE_TA_INCREMENTAL`) |
| **Compile+exec** | **~49–110×** MACD/MULTI run | Incremental Numba kernels + tuple plot returns + LRU cache 128 |

## Verification

```text
506 passed  (test_ta_incremental, test_evaluator, test_parse_and_unparse,
             test_compiler_numba, test_compiler_objects, test_compiler_strategy)
```

## Key code touch points

- Parse: `src/pynescript/ast/helper.py`, `builder.py`
- Unparse: `src/pynescript/ast/unparser.py` (+ thin `helper.unparse` wire-up)
- Evaluate: `ast/evaluator/builtins/technical_submodules/{core,basic,volatility,moving_averages,advanced}.py`, `tests/test_ta_incremental.py`
- Compile: `compiler/{compiler,engine,numba_builtins}.py`

## Flags

- Interpret incremental TA: default **on**; disable with `PYNE_TA_INCREMENTAL=0`
- Compile path always uses incremental kernels for ema/rma/atr/macd/cum/vwap/obv when those builtins are emitted
