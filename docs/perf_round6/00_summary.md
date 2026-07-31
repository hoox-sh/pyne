# Round 6 summary — synthesis / net tree

**BASE_SHA:** `0fc741bba73895ced13fe83b739c0d955f9c50f7`  
**Measured:** 2026-07-31 on main workspace after all 12 agents completed  
**Note:** worktree isolation did not separate filesystems; agents co-edited the shared tree. Net verification is the source of truth.

## Headlines (net tree vs Round 5)

| Metric | Round 5 | Round 6 net | Δ |
| --- | ---: | ---: | --- |
| **interpret minimal @ 2k** | 16.5 ms | **14.92 ms** | **1.11×** |
| **interpret ta_sma @ 2k** | 26.1 ms | **22.53 ms** | **1.16×** |
| **interpret ta_combo @ 2k** | 170 ms | **137.23 ms** | **1.24×** |
| **interpret strategy_ish @ 2k** | 84.4 ms | **63.07 ms** | **1.34×** |
| **ta_combo bars/s (interpret)** | ~11 800 | **~14 600** | **~1.24×** |
| **compile warm ta_combo** | ~0.69 ms | **~0.015 ms** | disk/IR cache |
| **compile run ta_combo @ 5k** | ~1.09 ms | **1.059 ms** | flat (already µs-scale) |

## Per-agent scorecard

| ID | Role | Verdict | Evidence |
| ---: | --- | --- | --- |
| **01** | Interpret visit/Call | **win** | Arg plans / direct visit_Call; ta_combo −7% agent-local; visit frames −70% structural |
| **02** | Series / expect | **win** | Shared pine_expect_int; dema/tema last-sample; PineSeries slots; ~1.13× ta_combo vs R5 |
| **03** | Residual TA inc | **win** | mfi/sar/kc/alma/correlation/percentiles; kernel up to ~142× |
| **04** | Compiler numeric kernels | **win** | Real dmi/adx/supertrend/alma/percentrank nopython (interpret oracle) |
| **05** | Compiler language surface | **win** | `_is_safe_numeric_expr` no longer rejects history `[]`; chart times; math stays numeric |
| **06** | Cold JIT / engine | **win** | Disk IR cache, typed CompileError*, dual-key LRU, prewarm API |
| **07** | Strategy broker | **win** | Exit commission + exit slippage; compile pyramiding; bad-arg events |
| **08** | Error handling | **win** | `error_kind` payload; body TypeError fail-closed; strategy apply fail-closed |
| **09** | Collections / UDT | **win** | sort_field/fill range/map keys object-mode parity; better type errors |
| **10** | na-safety | **win** | Crossover `<=`/`>=`; rising short-series bar-mode; MRO guard; VIDYA warmup golden |
| **11** | Parser / sanitize | **win** | set05 chrome recovery ~61% of prior FAIL CSV; FP lock on `?` in titles |
| **12** | Runtime host | **win** | inputs→interpret auto; Numba-optional object compile; host fail-cache |

**No agent scored as net regress** on `minimal` (R6 faster than R5).

## Verify (parent)

```text
763 passed  (core: TA, evaluator, parity, compiler×3, error_handling, collections,
             sanitize, oca_commission, strategy runtime/events, order_fills)
168 passed, 1 xfailed  (matrix/map/udt, lexer, multi-plot, plotting, risk)
```

## Residual / next

| Priority | Item |
| --- | --- |
| P1 dual-host | Port R5–R6 host pack/fail-cache/error_kind/inputs-auto to **pyne-worker** |
| P1 product | Prefer warm compile workers on Pro API |
| P2 | ATR Wilder / TV supertrend ratchet only with dedicated goldens |
| P2 | pending-fill averaging when pyramiding≤0 still loose |
| P3 | chart host real time arrays in execute signature |

## One-liner

**Round 6 stacked residual interpret wins (~1.24× ta_combo vs R5), exit-side strategy economics, fail-closed body errors, broad compiler coverage (dmi/supertrend/alma + numeric surface), disk IR cache, residual TA inc (mfi/sar/kc), and sanitize set05 recovery — all green on 763-core verify.**
