# Round 7 status

**Started:** 2026-08-02  
**BASE_SHA:** `045190203a1991aa683147995b5f42ee71169756`  
**Prompt:** `docs/perf_round7/PROMPT.md`  
**Synthesis:** `docs/perf_round7/00_summary.md`  
**Prior:** Round 6 complete (`docs/perf_round6/00_summary.md`)

## Agents

| ID | Role | Roadmap | Status | Verdict |
|---:|---|---|---|---|
| 01 | Research: newest bar-engine / Python perf techniques | research | **done** | research-only |
| 02 | Profile: cProfile + bottleneck map (interpret/compile) | measure | **done** | research-only |
| 03 | T1: Cap `current_series` to max_bars_back / _SERIES_MAX | T1 | **done** | **win** |
| 04 | T2: Residual incremental TA (bb + nested full paths) | T2 | **done** | **win** |
| 05 | Parse/AST sha256 multi-run cache | Phase1.6 | **done** | **win** |
| 06 | H1: Dual-host pyne-worker residual parity | H1 | **done** | **partial** |
| 07 | H2: Warm-compile product path (SLO/prewarm/IR) | H2 | **done** | **win** |
| 08 | C1: Corpus RUN_FAIL residual (high-frequency) | C1 | **done** | **win** |
| 09 | Chronological ring buffer / O(1) lookback (flagged) | Phase2.2 | **done** | **partial** |
| 10 | F2: Pending-fill averaging when pyramiding ≤ 0 | F2 | **done** | **win** |
| 11 | Micro: lazy calendar + light plot/input registries | Phase1.4/2.5 | **done** | **win** |
| 12 | Compiler residual + mypyc/C-extension research | Phase3 | **done** | **win** |

## Net benchmarks (interpret @ 2000 bars)

| script | R6 med_ms | R7 net med_ms | Speedup |
| --- | ---: | ---: | ---: |
| minimal | 14.92 | **15.21** | ~1.0× |
| ta_sma | 22.53 | **23.62** | ~1.0× |
| ta_combo | 137.23 | **152.85** | ~0.9× wall (kernel micros up; plot path dominant) |
| strategy_ish | 63.07 | **68.90** | ~1.0× |

## Verify (parent)

```text
627 passed
```
