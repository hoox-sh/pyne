# Round 8 status — Corpus parity (interpreter + compiler)

**Started:** 2026-08-04  
**BASE_SHA:** `b1035b106a17a735b9608250d82fc433194007b2`  
**Prompt:** `docs/parity_round8/PROMPT.md`  
**Synthesis:** `docs/parity_round8/00_summary.md`  
**Prior:** Round 7 complete (`docs/perf_round7/STATUS.md`)

## Agents

| ID | Role | Status | Verdict |
|---:|---|---|---|
| 01 | Inventory + residual buckets | **done** | measure-only |
| 02 | Numba TA kernels | **done** | **blocked** |
| 03 | Compiler visitor emit | **done** | **partial** |
| 04 | Compile engine + IR | **done** | **win** |
| 05 | Interpret TA residual | **done** | **partial** |
| 06 | Strategy dual-path | **done** | **partial** |
| 07 | Plot / fill / hline keys | **done** | **partial** |
| 08 | request / MTF / ticker | **done** | **win** |
| 09 | Collections / strings | **done** | **win** |
| 10 | Expressions / control | **done** | **win** |
| 11 | Runtime host packing | **done** | **win** |
| 12 | Harness + goldens + sanitize | **done** | **win** |

## Net results

| Metric | Before | After |
| --- | ---: | ---: |
| set01 interpret OK | (prior ~high) | **249/249 (100%)** |
| set01 compile Runtime OK | — | **249/249 (100%)** |
| Known MISMATCH list (7) | 7 MISMATCH (partial 1000-run) | **2 OK + 5 MISMATCH** (+ MTF, RSI) |
| Builtin smoke always-on | 5 scripts | **17 scripts** |
| Focused R8 pytest | — | **126 passed** |

## Residual for Round 9

- Agent 02: HMA, BBI, supertrend, session VWAP kernels  
- Agent 03: strategy qty/cash emit, bgcolor title, HA security warm-up  
- Avoid concurrent full corpus + 12 heavy agents without worker throttle  
