# Round 5 status

**Started:** 2026-07-30  
**BASE_SHA:** `ca5215ac33c34f9b60584f8c230bc281dc768782`  
**Prompt:** `docs/perf_round5/PROMPT.md`  
**Synthesis:** `docs/perf_round5/00_summary.md`  
**Measured net tree:** 2026-07-30 (agents 01–11 merged uncommitted; Agent 12 re-bench)

## Agents

| ID | Role | Status | Verdict |
|---:|---|---|---|
| 01 | Interpret dispatch | done (merged) | **win** |
| 02 | Series materialization | done (merged) | **win** |
| 03 | Residual TA incremental | done (merged) | **win** |
| 04 | Plot / drawing | done (merged) | **win** |
| 05 | Runtime host | done (merged) | **win** |
| 06 | Compiler Numba | done (merged) | **win** |
| 07 | Strategy broker | done (merged) | **win** |
| 08 | Parser / sanitize | done (merged) | **win** |
| 09 | Collections / UDT | done (merged) | **win** |
| 10 | v6 surface P0 | done (merged) | **win** |
| 11 | LSP | done (merged) | **win** |
| 12 | Synthesis | **done** | meta + golden glue |

## Net benchmarks (interpret @ 2000 bars)

| script | R4 med_ms | R5 net med_ms | Speedup |
| --- | ---: | ---: | ---: |
| minimal | 27.8 | **16.5** | 1.68× |
| ta_sma | 79.5 | **26.1** | 3.04× |
| ta_combo | 411 | **170** | 2.42× |
| strategy_ish | 177 | **84.4** | 2.10× |

## Verify (parent merge)

```text
993 passed, 1 xfailed  (R5 cluster: TA, evaluator, strategy, compiler, collections,
                        v6 surface, sanitize, plot/draw, LSP, parity)
```

Glue: regenerated `strategy_09_var_count` golden after Agent 07 pyramiding fix.
Working tree uncommitted — no push.


Glue: regenerated `strategy_09_var_count` parity JSON after Agent 07 pyramiding semantics.

## Merge order (applied by parent)

Correctness: **07 → 09 → 10 → 08**  
Interpret: **01 → 02 → 03 → 04 → 05**  
Then: **06**, **11**  
Last: **12** synthesis + `00_summary.md`
