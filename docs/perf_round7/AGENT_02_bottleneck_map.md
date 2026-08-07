# Copyright (C) 2024-2026 jango_blockchained
#
# This file is part of pynescript.
#
# pynescript is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pynescript is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: AGPL-3.0-or-later

# Round 7 Agent 02 — Bottleneck map (cProfile / measure)

| Field | Value |
| --- | --- |
| **Role / ID** | MEASURE — interpret + compile bottleneck map |
| **Agent** | 02 |
| **Date** | 2026-08-02 |
| **BASE_SHA (prompt)** | `045190203a1991aa683147995b5f42ee71169756` |
| **Machine** | Linux x86_64, 8 CPUs, Python 3.14.6 (`.venv`) |
| **Driver** | `scripts/bench_pipeline.py` + ad-hoc cProfile scripts |
| **Verdict** | **research-only** (measurement quality high; no code changes shipped) |

**Files touched:** this report only; raw bench JSON
`docs/perf_round7/bench_r7_agent02.json` (and `.cache/bench_pipeline_latest.json`).

**Note:** Concurrent Round-7 agents (T1 / lazy calendar) mutated `backend/runtime.py`
during late re-probes. Numbers below are from **successful** runs before those
breakages; late re-profile aborted on transient `SyntaxError` /
`dict.set_bar_time` errors in the shared tree.

---

## 1. Baseline — `bench_pipeline.py`

```bash
PYTHONPATH=src:. .venv/bin/python scripts/bench_pipeline.py --profile \
  --json docs/perf_round7/bench_r7_agent02.json
```

### 1.1 Interpret Runtime (n = 2000 bars, mode=`interpret`)

| script | **R7 med_ms** | µs/bar | bars/s | min–max_ms | **R6 med_ms** | R7 / R6 |
| --- | ---: | ---: | ---: | --- | ---: | ---: |
| **minimal** | **43.67** | 21.8 | 45 800 | 43.0–44.7 | 14.92 | **2.93×** |
| **ta_sma** | **51.37** | 25.7 | 38 900 | 49.9–84.6 | 22.53 | **2.28×** |
| **ta_combo** | **464.48** | 232 | 4 310 | 434–**1209** | 137.23 | **3.38×** |
| **strategy_ish** | **142.16** | 71.1 | 14 100 | 138–160 | 63.07 | **2.25×** |

Reconfirm (separate process, warmup 3 / iters 7): minimal 41–44, ta_sma 51–55,
ta_combo **480–525**, strategy_ish ~143 — same ballpark.

**vs Round 6:** all four scripts are **~2.3–3.4× slower** on this host than the
R6 summary table. Caveats:

- R6 may have been a quieter/faster host; this box shows CPU scaling ~95%.
- **ta_combo max ≫ med** (up to ~1.2–2.0 s) → intermittent GC / pathological
  spikes, not just steady-state.
- Round-4 map had ta_combo ~**411 ms** on a similar tree — closer to R7 than R6’s
  137 ms. Treat R6 absolute numbers as optimistic; **relative ranking** of
  callees still matches prior maps.

### 1.2 Variant isolation (interpret @ 2000)

| variant | med_ms | note |
| --- | ---: | --- |
| ta_combo **with** 8× `plot(...)` | **~480** | default bench script |
| ta_combo **no plots** (same TA) | **~102** | ~**4.7×** faster |
| `ta.bb` only + 1 plot | ~89 | BB alone is a large slice of TA cost |
| minimal (`plot(close)`) | ~44 | floor ≈ host + one plot + series updates |

**Implication:** on multi-plot TA scripts, **plot path + host result packing
dominate wall time** (~75–80% of ta_combo). Kernel-only work is closer to
~100 ms for the full ta_combo indicator body.

### 1.3 Compile + execute (n = 5000)

| script | cold_ms | warm_ms | run med_ms | bars/s | mode |
| --- | ---: | ---: | ---: | ---: | --- |
| minimal | ~556–1908\* | **0.011–0.013** | **0.008** | ≫1e8 | numba |
| ta_sma | ~447–464 | **0.015–0.018** | **0.055** | ~9e7 | numba |
| ta_combo | ~2.9–4.4k\* | **0.012–0.014** | **1.05–1.08** | ~4.8e6 | numba |
| strategy_ish | **~5–10** | **0.011–0.013** | **~27.5** | ~1.8e5 | **object** |

\*Cold JIT highly variable (Numba first-touch / disk IR / process state).

| path | ta_combo @ 5k |
| --- | --- |
| Bare `CompiledScript.run` | **~1.05 ms** |
| Host `Runtime(..., mode=compile)` warm | **~2.2 ms** (~2× pack overhead) |
| Warm `compile_script` cache hit | **~0.012 ms** (disk/IR cache healthy — R6 H2 residual) |

**Pipeline cost (ta_combo-ish, from bench breakdown):**

| scenario | dominant |
| --- | --- |
| One-shot interpret | run **~98%** / parse ~2% (med script) |
| Cold compile + one run | cold compile **~99.96%** / run negligible |
| Warm multi-run product | prefer **compile** (H2); interpret only when ineligible |

### 1.4 Parse / unparse (reference)

| size | script | bytes | warm parse | warm unparse | cold parse |
| --- | --- | ---: | ---: | ---: | ---: |
| small | balance_of_power.pine | 170 | 2.51 ms | 0.014 ms | 439 ms |
| med | choppiness_index.pine | 686 | 10.7 ms | 0.071 ms | 267 ms |
| large | auto_fib_extension.pine | 16232 | **211 ms** | 1.22 ms | 1346 ms |

Unparse is LSP/format-only. Large warm parse still a Phase-1.6 / Agent 05 target.

---

## 2. cProfile — interpret ta_combo

### 2.1 Setup

- Script: `SCRIPTS["ta_combo"]` (sma/ema/rsi/atr/stdev/bb/highest/lowest + 8 plots)
- Bars: **2000** (primary); also 1500 via `--profile`
- Warmup: 1 full `Runtime.run` then profile 1 run
- Sort: `cumtime` and `tottime`, top 20–30

Wall under cProfile ≈ **0.89 s** @ 2000 (profiler tax ~1.5–2× vs ~0.46 s median wall).

### 2.2 Top cumulative callees (warm ta_combo @ 2000)

| rank | ncalls | tottime (s) | cumtime (s) | % cum of run | function | map |
| ---: | ---: | ---: | ---: | ---: | --- | --- |
| 1 | 1 | 0.025 | **0.892** | 100% | `backend.runtime.Runtime.run` | host |
| 2 | 36k/2k | 0.029 | **0.847** | 95% | `ast.visitor.visit` | dispatch |
| 3 | 2k | 0.022 | **0.844** | 95% | `statements.visit_Script` | dispatch |
| 4 | 34k | 0.056 | **0.727** | **82%** | **`expressions.visit_Call`** | dispatch |
| 5 | 18k | 0.012 | 0.391 | 44% | `statements.visit_Expr` | dispatch |
| 6 | 16k | 0.022 | 0.388 | 44% | `statements.visit_Assign` | dispatch |
| 7 | 16k | 0.034 | **0.319** | **36%** | **`backend.evaluator._builtin_plot`** | plot / A11 |
| 8 | 16k | **0.216** | **0.259** | **29%** | **`_capture_plot` / plot append path** | plot / A11 |
| 9 | 2k | 0.041 | 0.091 | 10% | `_builtin_ta_bb` | T2 / A04 |
| 10 | 2k | 0.003 | 0.051 | 6% | `_builtin_ta_ema` | residual TA |
| 11 | 2k | 0.003 | 0.044 | 5% | `_bollinger_bands` | T2 |
| 12 | 2k | 0.039 | 0.044 | 5% | `_ema_inc_update` | residual TA |
| 13 | 4k | 0.032 | 0.043 | 5% | `_stdev_inc_update` | T2 (bb+stdev) |
| 14 | 2k | 0.007 | 0.043 | 5% | `_builtin_ta_atr` | residual TA |
| 15 | 4k | 0.021 | 0.034 | 4% | `_sma_inc_update` | residual TA |
| 16 | 32k | 0.023 | 0.032 | 4% | `_as_plot_int` | plot |
| 17 | 2k | 0.003 | 0.029 | 3% | `_builtin_ta_rsi` | residual TA |
| 18 | 2k | 0.003 | 0.028 | 3% | `_builtin_ta_lowest` | residual TA |
| 19 | 2k | 0.003 | 0.027 | 3% | `_builtin_ta_stdev` | T2 |
| 20 | 34k | 0.021 | 0.026 | 3% | `_eval_arg_plan` | visit_Call residual |

(Also high ncalls: `list.append` 72k, `getattr` 144k, `dict.get` 94k, `len` 132k —
typing / container tax.)

### 2.3 Top exclusive time (tottime)

| rank | tottime | % of 0.892s | function | owner |
| ---: | ---: | ---: | --- | --- |
| 1 | **0.216** | **24.2%** | plot capture / columnar append | **11** (plot registries / light capture) |
| 2 | 0.056 | 6.3% | `visit_Call` body | residual micro / **12** research |
| 3 | 0.041 | 4.6% | `_builtin_ta_bb` | **04** T2 |
| 4 | 0.039 | 4.4% | `_ema_inc_update` | **04** residual |
| 5 | 0.034 | 3.8% | `_builtin_plot` | **11** |
| 6 | 0.032 | 3.6% | `_stdev_inc_update` | **04** T2 |
| 7 | 0.029 | 3.3% | `visit` | dispatch envelope |
| 8 | 0.025 | 2.8% | `Runtime.run` host loop body | **03** T1 trim, **09** ring, **11** calendar |
| 9–12 | ~0.022–0.024 | ~2.5% each | `append` / `getattr` / `_as_plot_int` / `visit_Script` | micro |
| — | 0.021 | 2.4% | `_sma_inc_update` | **04** |
| — | 0.019 | 2.1% | `_atr_inc_update` | residual |
| — | 0.018 | 2.0% | `_rsi_inc_update` | residual |
| — | 0.016 | 1.8% | `_lowest_inc_update` (window scan) | **04** / structure |
| — | 0.011 | 1.2% | `_expect_series` | series / **03** |

### 2.4 No-plot TA profile (same kernels, no `plot`)

~0.345 s profiled / **~102 ms** median wall:

| focus | role when plots removed |
| --- | --- |
| `visit_Call` / `visit_Assign` / `visit` | **dominant envelope** again |
| `_stdev_inc_update` + `_sma_inc_update` | top kernel tottime (bb doubles both) |
| `_builtin_ta_bb` | largest single builtin cumtime among TA |
| `_expect_series` / `_series_last` / `_ta_next_slot` | per-call TA glue |
| `PineSeries.update` | OHLCV host series (~18k updates) |

### 2.5 Optional line-level notes (no line_profiler run)

| region | file | observation |
| --- | --- | --- |
| `visit_Call` | `expressions.py:558+` | Site cache + arg plans already shipped (R6 A01). Residual cost is **frame volume** (34k calls @ 2k bars ≈ 17 calls/bar for ta_combo) + `_eval_arg_plan` + handler invoke. |
| Plot capture | `backend/evaluator.py` `_capture_plot` / `_append_plot_value` | First bar registers meta; steady-state should append-only. Monkeypatch: **8 capture / 15 992 append** @ 2k×8 — good. Still ~1/4 exclusive time under cProfile (list growth + host packing after loop). |
| Host packing | `runtime.py` ~1160–1300 | Per-plot `list(raw_col)` / `_json_plot_value` over **plots × bars**. Numeric fast path exists (`all(float|int|None)`) but still copies. |
| `_stdev_inc_update` | `core.py:458` | O(1) window math; called **2×/bar** (standalone `ta.stdev` + inside `ta.bb`). |
| `_highest`/`_lowest` | `core.py:508+` | Incremental window but **full scan of period** each bar (O(period)); fine for 20, worse for large lengths. |
| Series lists | `runtime` hot loop | `current_series` append + **T1 trim** (Agent 03 in-flight): observed lens **~310** with cap 256 + slack. `PineSeries.history` still **maxlen 1000**. |

### 2.6 Pathological / noisy run (first `--profile` @ 1500)

One profiled run showed `_stdev_inc_update` at **1.56 s tottime / 71%** — not reproducible on warm re-runs. Correlates with ta_combo **max_ms spikes (1–2 s)**. Suspect GC, transient full-recompute, or mid-edit tree. **Do not optimize from that single sample**; use the warm @2000 table.

---

## 3. Series / memory snapshot (after T1 partial land)

| structure | observed after ta_combo @ 2000 | roadmap |
| --- | --- | --- |
| `current_series[*]` OHLCV lists | **len ≈ 310** (cap on, keep 256 + slack) | **T1 / Agent 03** — already trimming |
| `PineSeries.history` | **max hist = 1000** | floor `DEFAULT_PINESERIES_HISTORY`; ring flag **09** |
| Plot columns | 8 × 2000 cells | **11** packing |
| `PYNE_SERIES_RING` | default off | **09** O(1) lookback |

---

## 4. Bottleneck → ROADMAP → Round 7 owner

| # | Bottleneck | Est. % wall (ta_combo interpret) | Roadmap ID | Owner agent | Risk | Headroom |
| ---: | --- | ---: | --- | ---: | --- | --- |
| 1 | **Multi-plot capture + host series packing** | **~75–80%** of ta_combo wall (vs no-plot) | Phase 1.4 / 2.5 | **11** | Low–Med: must keep AXIS multi-series shape | High on multi-plot scripts |
| 2 | **AST `visit` / `visit_Call` / assign envelope** | **~80%+ cumtime** envelope; ~6–15% exclusive after R6 | residual Phase 1 | micro / **12** (mypyc/C) | Med: semantic site cache already subtle | Med without compile path |
| 3 | **`ta.bb` nested path + double stdev/sma** | ~10% cum; larger in no-plot | **T2** | **04** | Med: BB golden parity | Med–High on BB-heavy |
| 4 | **Residual inc kernels** (ema/atr/rsi/stdev/highest scan) | ~15–25% exclusive of no-plot | **T2** | **04** | Low if already-inc; Med for new kernels | Med aggregate |
| 5 | **`current_series` / history growth** | mem + occasional spikes; trim now on | **T1** | **03** | **High** if cap &lt; period or full-recompute | Mem high; CPU if spikes |
| 6 | **Cold Numba compile** | UX one-shot; not warm loop | **H2** | **07** (+ **12**) | Low for cache; Med for prewarm policy | High for interactive |
| 7 | **Object-mode strategy execute** | ~27 ms @ 5k vs µs numeric | compiler residual | **12**, broker **10** (F2) | Med | Med on strategies |
| 8 | **Warm large parse (ANTLR)** | ~210 ms large scripts | Phase 1.6 | **05** | Low | High multi-run / LSP |
| 9 | **Host compile wrap pack** | ~2× bare run | H1/H2 host | **06**, **07** | Low | Low absolute (ms) |
| 10 | **Calendar / context fields / registries** | small unless enabled | Phase 1.4 | **11** | Low | Low–Med |
| 11 | **Ring buffer O(1) lookback** | off by default | Phase 2.2 | **09** | Med correctness | Med if lookback-heavy |
| 12 | **Corpus / compile eligibility** | product path share | **C1** | **08** | — | Enables compile globally |
| 13 | **Dual-host parity** | not on this bench | **H1** | **06** | — | Worker lag only |
| 14 | **Pending-fill averaging** | strategy economics | **F2** | **10** | Med semantics | Not perf-primary |

### Function → % time → owner → risk (condensed)

| function / area | % time (basis) | owner | risk |
| --- | --- | ---: | --- |
| `_capture_plot` / `_builtin_plot` / plot packing | **24% tottime** / **~75% wall** vs no-plot | **11** | low–med |
| `visit_Call` | **82% cum** / **6% tot** | **12** (+ residual) | med |
| `_builtin_ta_bb` + `_bollinger_bands` | **~10% cum** | **04 (T2)** | med |
| `_stdev_inc_update` (×2 via bb+stdev) | **~4% tot** | **04 (T2)** | low |
| `_ema` / `_sma` / `_atr` / `_rsi` inc | **~10% tot** combined | **04** | low |
| `_highest`/`_lowest` window scan | **~2–3% tot** | **04** / **09** | low |
| `Runtime.run` series append + T1 trim | host loop | **03 (T1)** | **high** if wrong cap |
| `compile_script` cold | **0.5–4 s** one-shot | **07 (H2)** / **12** | low cache |
| strategy object `run` | **~28 ms / 5k** | **12** / **10** | med |
| `parse` large | **~210 ms warm** | **05** | low |
| `_expect_series` / `_series_last` | **~2%** | **03** / series | low |

---

## 5. Round 6 residue vs still-dominant costs

| Already shipped (do not rediscover) | Still dominant / residual |
| --- | --- |
| Incremental TA for sma/ema/rsi/atr/stdev/… | **bb nested** full/partial paths (**T2**) |
| `visit_Call` site cache + arg plans (R6 A01) | **Call volume** still ~17/bar on ta_combo; exclusive ~6% |
| Columnar plot capture + steady append | **Packing copy** + multi-plot still ~4–5× vs no-plot |
| Host compile cache / disk IR (warm ~0.01 ms) | **Cold JIT** multi-second; product prewarm (**H2**) |
| Numba numeric bar loop ~1 ms @ 5k | Object strategy **~27 ms**; host wrap ~2× |
| Series/list pre-bind in Runtime | **T1 cap** landing; PineSeries floor 1000; ring off |
| Fail-closed / error_kind / inputs→interpret | **C1** corpus still blocks default-compile share |

**Apparent R6 regression (absolute ms):** R7 host is **slower** than R6 summary
by ~2–3× across the board. Prefer this report’s medians as **R7 baseline** for
speedup claims. Spike tail on ta_combo (max 1–2 s) is a **stability** concern
for Agent 03/04 (cap + TA path), not only mean throughput.

---

## 6. Recommended attack order (for other agents)

1. **Agent 11** — multi-plot wall: avoid re-copy of numeric columns; optional
   pre-sized arrays; skip packing when host already has columns; lazy meta.
2. **Agent 04 (T2)** — share SMA/stdev state inside `ta.bb`; ensure no full
   recompute nested path; highest/lowest monotonic deque if length large.
3. **Agent 03 (T1)** — finish series cap goldens; confirm no spike from
   trim/`del` amortization; document interaction with `PYNE_TA_INCREMENTAL=0`.
4. **Agent 07 (H2)** — product prewarm + SLO on cold path; keep warm hit ≪1 ms.
5. **Agent 05** — sha256 parse/AST multi-run cache (large script / multi-eval).
6. **Agent 12** — only after 1–3: mypyc/C on visit_Call hot helpers; object-mode
   strategy micro.
7. **Agent 09** — ring series behind flag when lookback-heavy scripts show up.
8. **Agent 08 / 06 / 10** — product/correctness (C1/H1/F2), not primary µs.

**Compile path guidance:** for eligible numeric scripts, **warm compile already
wins by 100–400×** vs interpret on ta_combo. Interpret optimization is for
ineligible scripts, auto-fallback, and strategy object mode.

---

## 7. Tests / commands run

| command | result |
| --- | --- |
| `PYTHONPATH=src:. .venv/bin/python scripts/bench_pipeline.py --profile --json docs/perf_round7/bench_r7_agent02.json` | **ok** (baseline + profile) |
| Ad-hoc reconfirm medians + cProfile @2000 | **ok** |
| Variant no-plot / bb-only | **ok** |
| Compile bare vs host | **ok** |
| Series-cap / plot-path monkeypatch counts | **ok** (T1 cap on) |
| Late re-profile after concurrent edits | **aborted** (transient runtime errors) |

No production code changed by this agent.

---

## 8. Residual / follow-ups

- Re-run full `bench_pipeline.py` once Agents 03/11 land cleanly; refresh STATUS
  net table against **this** baseline (not R6 137 ms).
- Optional: `py-spy` / `scalene` for line-level plot packing confirmation.
- Investigate ta_combo **max_ms spikes** (GC? trim? accidental full TA?).
- Profile **strategy_ish** broker fill path when F2 is touched (not primary here).

---

## 9. Top 5 bottlenecks (executive)

1. **Plot capture + host multi-series packing** (~75–80% of ta_combo interpret wall) → Agent **11**
2. **AST visit / `visit_Call` dispatch envelope** (~82% cumtime) → residual / Agent **12**
3. **`ta.bb` nested + dual stdev/sma** (~10% cum) → **T2** Agent **04**
4. **Series history policy** (T1 trim landing; PineSeries 1000; spike risk) → **T1** Agent **03** (+ **09** ring)
5. **Cold compile / object-mode strategy** (product path) → **H2** Agent **07** + **12**

**Verdict: research-only** — map is actionable; no optimizations implemented by Agent 02.
