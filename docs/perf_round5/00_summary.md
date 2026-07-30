# Round 5 summary — synthesis / bottleneck re-measure

**AGENT_ID:** 12  
**ROLE:** Synthesis / bottleneck re-measure / regression net  
**BASE_SHA (round start):** `ca5215ac33c34f9b60584f8c230bc281dc768782`  
**Measured:** 2026-07-30 on main workspace post-merge of agents 01–11 (uncommitted tree)  
**Machine:** repo `.venv` Python, `PYTHONPATH=src:.`

## Merge status

Agents **01–11 already merged into the working tree by the parent** (no worktree isolation at measurement time). This report measures the **net tree**, not per-agent isolation. No large re-merge was performed here.

**Glue fix (Agent 12 only):**

| Item | Action |
| --- | --- |
| `test_parity.py::test_parity_corpus[strategy_09_var_count]` | Stale golden: expected 50 entries after Agent 07 pyramiding fix (default `pyramiding=0` → one market entry). Regenerated `tests/fixtures/parity/json/strategy_09_var_count.json` via `generate_fixtures.py`; updated pine comment. |

No other merge-blockers found on the verify subset.

---

## Headlines (net tree vs Round 4 map)

| Metric | Round 4 | Round 5 net | Δ |
| --- | ---: | ---: | --- |
| **interpret minimal @ 2k** | 27.8 ms | **16.5 ms** | **1.68×** |
| **interpret ta_sma @ 2k** | 79.5 ms | **26.1 ms** | **3.04×** |
| **interpret ta_combo @ 2k** | 411 ms | **170 ms** | **2.42×** |
| **interpret strategy_ish @ 2k** | 177 ms | **84.4 ms** | **2.10×** |
| **ta_combo bars/s (interpret)** | ~4 870 | **~11 800** | **~2.4×** |
| **Parse set01–04 OK** | 99.64% (9 FAIL) | **99.960%** (1 FAIL intentional) | +8 recovered |
| **Warm host compile wrap (ta_combo)** | ~10–20× bare | **~2.5–3×** bare | Agent 05 |
| **Verify subset** | — | **472 passed** | after golden regen |

Compile bare `ta_combo` run remains **~1.1 ms @ 5k** (µs/bar-scale); cold JIT still dominates one-shot (~1–2 s first touch).

---

## Per-agent scorecard

Verdicts: **win** = measurable DoD met or real bugs fixed; **noop** = no meaningful net win; **regress** = >5% minimal or broken core tests on net tree. Agent-local benches may differ from net stack (compound wins).

| ID | Role | Verdict | Evidence (net / report) |
| ---: | --- | --- | --- |
| **01** | Interpret dispatch | **win** | Call-site cache; −23% ta_combo alone; bound `_call_builtin` gone from profile top-20. Net stack still dispatch-bound but cheaper. |
| **02** | Series last-sample | **win** | `_as_series` off pure-inc path; Agent 02 alone ~1.5× ta_combo. Profile: no `_as_series` reverse tax on ta_combo. |
| **03** | Residual TA inc | **win** | dema/tema/adx/dmi/supertrend/valuewhen/pivots inc; kernel 9–220× vs full recompute. Goldens green. |
| **04** | Plot / drawing | **win** | Steady-state value-only capture; plotshape style/location fixed; `_capture_plot` ncalls collapsed to first bar. |
| **05** | Runtime host wrap | **win** | Warm compile host ta_combo ~5 ms → ~0.75–2.8 ms; vectorized JSON + OHLCV identity cache + host compile cache. |
| **06** | Compiler Numba | **win** | dema/tema/swma + IR cache + builtin warm; kernel 17–50×; tests 182 passed. |
| **07** | Strategy broker | **win** | High: `strategy.cash` string collision; entry commission / openprofit compile parity; market pyramiding + reverse `close`. |
| **08** | Parser / sanitize | **win** | Sanitize FPs (empty-arrow, free-indent parens, multiline string); corpus **2476/2477**. |
| **09** | Collections / UDT | **win** | UDT `sort_field`, matrix insert/empty new, `order.*`; +8 tests; 232 collection suite. |
| **10** | v6 surface P0 | **win** | printf `log.*`; chart `is_pnf` + viewport times; compile chart flags; 64 surface tests. |
| **11** | LSP | **win** | Symbols double-flush, refs in bodies, EOF edit, AST reuse (~18–64× feature paths); 44 LSP tests. |
| **12** | Synthesis | **meta** | Re-bench + scorecard; one golden glue fix; no feature work. |

**No agent scored as net regress** on `minimal` (R5 **faster** than R4 by ~40%). No agent left the verify core red after the parity golden update.

---

## Official `bench_pipeline.py` (net tree)

Command:

```bash
PYTHONPATH=src:. .venv/bin/python scripts/bench_pipeline.py
PYTHONPATH=src:. .venv/bin/python scripts/bench_pipeline.py --profile
```

### Parse / unparse (warm medians)

| size | script | bytes | parse_med_ms | unparse_med_ms |
| --- | --- | ---: | ---: | ---: |
| small | balance_of_power | 170 | ~2.4–2.5 | ~0.015 |
| med | choppiness_index | 686 | ~11–13 | ~0.07 |
| large | auto_fib_extension | 16232 | ~215–230 | ~1.2–1.3 |

### Interpret Runtime (n=2000)

| script | med_ms | µs/bar | bars/s |
| --- | ---: | ---: | ---: |
| minimal | **16.5** | 8.3 | **121 000** |
| ta_sma | **26.1** | 13.1 | **76 600** |
| ta_combo | **170** | 85 | **11 800** |
| strategy_ish | **84.4** | 42 | **23 700** |

(Second run with `--profile` within noise: minimal 17.6 / ta_combo 167 / strategy_ish 75.)

### Compile + execute (n=5000)

| script | cold_ms | warm_ms | run_med_ms | mode |
| --- | ---: | ---: | ---: | --- |
| minimal | ~500–535 | ~0.23 | **0.008** | numba |
| ta_sma | ~260–290 | ~0.22 | **0.056** | numba |
| ta_combo | ~1.0–2.1 s | ~0.69 | **1.09** | numba |
| strategy_ish | ~9–10 | ~0.6–0.8 | **27–30** | object |

Runtime `mode=compile` wrap (from same JSON, warm): minimal **~0.15 ms**, ta_sma **~0.22 ms**, ta_combo **~2.75 ms** vs bare run **~1.1 ms** → wrap ≈ **2.5×** on ta_combo (was ~10–20× in R4).

---

## Updated top-10 bottleneck ranking

Profile: `bench_pipeline.py --profile` — **ta_combo interpret**, 1500 bars, ~1.02 M calls, **0.54 s** wall (was ~1.0 s / 1.5 M calls in R4).

| Rank | Bottleneck | Where | Est. residual headroom | Notes vs R4 |
| ---: | --- | --- | --- | --- |
| **1** | **AST visit / `visit_Call` / bar-loop dispatch** | `visitor.visit`, `visit_Call`, `visit_Assign` | 1.2–1.5× multi-TA | Still ~cumtime dominant; Agent 01 removed `_call_builtin` / qualified dispatch from top-20 |
| **2** | **Cold Numba compile (first touch)** | `compile_script` / njit | large oneshot UX | Still ~1–2 s ta_combo cold; IR cache + pre-warm help second script only |
| **3** | **Arg collect / typing tax** | `_collect_call_args`, `dict.get`, `_expect_int` | 1.05–1.2× | Visible after dispatch/series wins |
| **4** | **TA kernel + `_expect_series` steady state** | `*_inc_update`, BB path | small on pure-inc | `_as_series` **no longer** top self-time on ta_combo last-sample path |
| **5** | **Plot path (residual)** | `_builtin_plot` backend | 1.05–1.15× multi-plot | Much cheaper after steady-state append (Agent 04) |
| **6** | **Runtime host wrap (compile warm)** | JSON `tolist`, result packing | ~1× internal raw API | ~2.5–3× bare; cold OHLCV pack still ~1 ms |
| **7** | **Object-mode strategy broker** | compile strategy | 1.5–3× | Correctness improved (07); still ≫ numeric TA |
| **8** | **Warm parse of large scripts** | ANTLR `helper.parse` | 1.5–3× large only | ~215–230 ms @ 16 KB; LSP paid once/doc after Agent 11 cache |
| **9** | **Dual-host / pyne-worker lag** | worker Runtime twin | parity + wrap | JSON/pack/cache not ported (Agent 05 doc) |
| **10** | **Product surface long-tail** | request.*, TV ATR, set05 | product ROI | P0 closed this round; residual P1/P2 + dual-host |

**Already solved this round (do not rediscover):** call-site dispatch cache; last-sample pure-inc; dmi/adx/supertrend/valuewhen/pivots/dema/tema interpret inc; plot steady-state; host JSON/OHLCV/compile cache; dema/tema/swma Numba + IR cache; strategy.cash/commission/pyramiding; sanitize free-indent + multiline string; matrix/array UDT sort; printf log + chart P0; LSP AST reuse.

---

## cProfile structural (ta_combo interpret @ 1500 bars)

| R4 (approx) | R5 net |
| --- | --- |
| ~1.5–1.6 M calls, ~1.0 s | **~1.02 M calls, ~0.54 s** |
| Top: visit → visit_Call → `_call_builtin` → `_dispatch_qualified` → `_as_series` | Top: visit → visit_Call → visit_Assign → `_collect_call_args` → `_expect_series` (pass-through) → kernels / plot |
| `_call_builtin` / qualified dispatch in top-10 | **gone from top-20** |
| `_as_series` high tottime | **absent** (last-sample path) |

---

## Verify subset (Agent 12)

```bash
.venv/bin/python -m pytest tests/test_ta_incremental.py tests/test_evaluator.py \
  tests/test_compiler_numba.py tests/test_parity.py -q --tb=line
# → 472 passed (after strategy_09 golden regen)
```

First run: **471 passed, 1 failed** (`strategy_09_var_count` golden vs pyramiding). Fixed by regenerating fixture.

---

## Residual risks / recommended next round

| Priority | Item | Owner hint |
| --- | --- | --- |
| P0 product | Prefer **default compile + warm workers** on Pro API (interpret still ~150× slower on ta_combo once warm-compiled) | API / Runtime product |
| P1 perf | Further cut **visit/Call** tax (specialized bytecode, fewer visit frames, pre-bound UDF bodies) | interpret / Agent 01 follow-on |
| P1 perf | **Cold JIT** — disk cache of njit or process-pool warm workers | compiler / deploy |
| P1 dual-host | Port Agent 05 pack/JSON/cache + Agent 07 commission/pyramiding semantics to **pyne-worker** | dual-host |
| P1 correctness | **pine-worker** TS parity golden for `strategy_09` (now 1 event) | pine-worker |
| P2 | Full-history residual TA: kc, mfi, sar, alma, correlation, percentiles | TA |
| P2 | Compile stubs: real dmi/supertrend; ALMA/percentrank; sort_field on compile array | compiler |
| P2 | Exit commission / slippage TV parity (both hosts still entry-only / no exit slip) | strategy |
| P2 | Compile chart viewport times still 0.0 stubs | compiler |
| P2 | LSP UTF-16 positions; debounced didChange parse | LSP |
| P3 | True TV supertrend band ratchet (interpret currently simplified oracle) | TA correctness track |
| P3 | ATR EMA→Wilder RMA re-baseline only with dedicated PR + goldens | correctness |

**set05:** not re-swept this round; prior themes (OOB, none-callable, matrix object-mode) partially addressed by 09; remaining bulk is scrape chrome.

---

## Merge order note (historical)

Recommended (PROMPT): correctness **07 → 09 → 10 → 08** then interpret **01 → 02 → 03 → 04 → 05** then **06**, **11**, last **12**. Parent already applied merges; if re-applying from worktrees, keep that order — hotspots: `expressions.py`, `technical_submodules/*`, `backend/runtime.py`, `base.py` constants, `strategy.py`.

---

## One-liner

**Round 5 stacked large interpret wins (~2.4× ta_combo vs R4) by dispatch cache + last-sample series + residual TA inc + lean plots; host compile wrap fell to ~2.5–3× bare; correctness closed strategy.cash/pyramiding, sanitize FPs (99.96% parse), collections UDT sort, P0 surface, and LSP outline/edit bugs. Next leverage is default-compile product path and residual visit tax / cold JIT — not more SMA kernels.**
