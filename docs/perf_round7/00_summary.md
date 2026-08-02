# Round 7 summary — open backlog + residual perf + research

**BASE_SHA:** `045190203a1991aa683147995b5f42ee71169756`  
**Measured:** 2026-08-02 after 12 parallel agents + orchestrator merge fixes  
**Prompt:** `docs/perf_round7/PROMPT.md`

## Headlines

| Area | Result |
| --- | --- |
| **Open backlog** | T1 ✅, T2 ✅, H2 ✅, F2 ✅, C1 advanced, H1 partial (worker), ring buffer partial |
| **Research** | Newest techniques ranked; R1–R6 marked done/skip |
| **Parse multi-run** | LRU AST cache + call-site scrub on hit (fixes empty-plot poison) |
| **Interpret @ 2k** | minimal **15.2 ms**, ta_sma **23.6 ms**, ta_combo **153 ms**, strategy_ish **69 ms** |
| **Compile** | warm ~0.01 ms; ta_combo run ~1.06 ms; residual nopython kernels (median/wpr/cmo/bbw) |

## Net benchmarks (interpret @ 2000 bars)

| script | R6 med_ms | R7 med_ms | notes |
| --- | ---: | ---: | --- |
| minimal | 14.92 | **15.21** | ~flat (machine noise) |
| ta_sma | 22.53 | **23.62** | ~flat |
| ta_combo | 137.23 | **152.85** | structural T2 wins on kernel micros; full combo dominated by plot path (A02) |
| strategy_ish | 63.07 | **68.90** | F2 semantics; ~flat wall |

Compile warm ta_combo still **~0.01 ms**; run **~1.06 ms @ 5k**.

## Per-agent scorecard

| ID | Role | Verdict | Evidence |
| ---: | --- | --- | --- |
| **01** | Research newest techniques | **research-only** | Top ROI: H2, T2, T1, ring buffer, dual-host; fidelity non-goals |
| **02** | cProfile bottleneck map | **research-only** | Plot packing ~75% of ta_combo wall; visit_Call envelope |
| **03** | T1 series cap | **win** | `PYNE_SERIES_CAP` default ON; ~78× long-run list memory |
| **04** | T2 residual TA inc | **win** | bb/kama/cmo/stochrsi; kama ~121×, bb ~217×, stochrsi ~717× kernel |
| **05** | Parse/AST cache | **win** | sha256 LRU; multi-parse ~1000×; + scrub on hit |
| **06** | H1 dual-host | **partial** | pyne-worker inputs/series/multi-run; package unify open |
| **07** | H2 warm compile | **win** | SLOs, prewarm API/CLI, disk cache deploy defaults |
| **08** | C1 corpus residual | **win** | +10 RUN_FAIL modes; set01 sample 65/65 |
| **09** | Ring buffer 2.2 | **partial** | `ChronologicalSeriesBuffer` + `PYNE_SERIES_RING=0` default |
| **10** | F2 pending-fill VWAP | **win** | pyramiding≤0 averages; interpret+compile goldens |
| **11** | Lazy calendar + light plots | **win** | always-on lazy cal; `PYNE_LIGHT_PLOTS` −10–20% multi-plot |
| **12** | Compiler Phase 3 + kernels | **win** | mypyc deferred; nopython median/wpr/cmo/bbw |

## Orchestrator merge fixes

1. **`numba_bbw` unpack** — `(upper, middle, lower)` not `(mid, upper, lower)`  
2. **Parse-cache call-site scrub** — `_scrub_pine_call_sites` on cache hit; Runtime host clear  
3. **`input.source` list overrides** — keep series lists for source-name defaults (bar_index sample)

## Verify (parent)

```text
627 passed  (series cap/ring/parse-cache/lazy-plots, TA incremental, order fills,
             evaluator, parity, compiler residual kernels, corpus residuals, backend)
```

## Residual / next

| Priority | Item |
| --- | --- |
| P1 | H1 package-level Runtime unify (single host module) |
| P1 | Prefer warm compile on Pro path + document SLOs in ops |
| P2 | Default-on ring buffer after corpus green; drop dual list write |
| P2 | Plot-path structural win (dominant interpret residual per A02) |
| P2 | F1 ATR Wilder only with dedicated goldens |
| P3 | mypyc on `pine_expect_int` if profiled |

## One-liner

**Round 7 closed open P2s (T1/T2/F2) and H2 product warm-compile, advanced C1/H1, shipped parse cache + call-site scrub, residual incremental TA (bb/kama/stochrsi), opt-in ring buffer, lazy calendar / light plots, and Phase 3 research with four new nopython kernels — 627-core verify green.**
