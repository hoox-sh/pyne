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

# Round-4 Agent 10 — End-to-end bottleneck map

**Date:** 2026-07-29  
**Role:** Measurement / synthesis (no large rewrites)  
**Machine:** worktree code + main `.venv` Python 3.14  
**Driver:** `scripts/bench_pipeline.py`  
**Prior art:** `docs/perf_agents_summary.md` + rounds 1–3 agent reports (do **not** re-open as “new”)

---

## Executive ranking (top bottlenecks remaining)

| Rank | Bottleneck | Where | Est. headroom | ROI |
| ---: | --- | --- | --- | --- |
| 1 | **AST visit / `visit_Call` / `_call_builtin` dispatch** | interpret bar loop | 1.3–2× on TA multi | **High** — still ~80%+ of interpret wall after TA/inc + host opts |
| 2 | **`_as_series` / `_expect_series` materialization** | technical builtins | 1.2–1.5× on multi-TA | **High** — #2 tottime; pure-inc already has last-sample path partially |
| 3 | **Cold Numba compile (first touch)** | `compile_script` | 5–50× one-shot UX | **High** for interactive/API; low for warm multi-run hosts |
| 4 | **`plot` / `_plot_upsert` interpret path** | backend evaluator + plotting | 1.1–1.3× multi-plot | **Med-High** — top-3 tottime on ta_combo |
| 5 | **Runtime host wrap around compile** | `backend.runtime._run_compiled` | 2–10× vs bare `CompiledScript.run` | **Med-High** — packing / OHLCV conversion / result normalize |
| 6 | **Object-mode strategy broker** | compile strategy path | 1.5–3× strat scripts | **Med** — already 4–6× improved in r3; still ≫ numeric TA |
| 7 | **Warm parse of large scripts (ANTLR)** | `helper.parse` | 1.5–3× large only | **Med** for LSP/format; low for Runtime (cached) |
| 8 | **Dynamic typing tax (`dict.get` / `isinstance` / `getattr`)** | evaluator core | 1.05–1.2× | **Med-Low** — hard; need specialized bytecode or compile |
| 9 | **Corpus fail modes blocking default-compile** | interpret/compile surface | product ROI | **High product** — not µs, but enables #1 path globally |
| 10 | **Dual-host / pyne-worker lag on heavy strategies** | worker Runtime | host parity | **Med** — 1.3 s big_strategy @ 3.2k bars |

**Already solved (do not rediscover):** SLL-first parse (~5×), unparse reuse (~2×), incremental TA interpret (up to ~6×), host bar-loop pre-bind (+20–36%), type-keyed visitor, Numba `*_inc` kernels (up to ~110× MACD), object-mode strategy 4–6×, plot registry O(plots). See `perf_agents_summary.md`.

---

## Measurement setup

```text
PYTHONPATH=src:. .venv/bin/python scripts/bench_pipeline.py --profile
```

| Knob | Value |
| --- | --- |
| Interpret bars | 2000 synthetic OHLCV |
| Compile bars | 5000 synthetic OHLCV |
| Stats | median of multi-iter after warmup |
| Profile | cProfile, ta_combo interpret, 1500 bars |
| Size scripts | builtin corpus: 170 B / 686 B / 16 232 B |

---

## 1. Parse / unparse

| size | script | bytes | warm parse med (ms) | warm unparse med (ms) | cold parse (ms) |
| --- | --- | ---: | ---: | ---: | ---: |
| small | `balance_of_power.pine` | 170 | **2.57** | 0.021 | 446 |
| med | `choppiness_index.pine` | 686 | **13.0** | 0.102 | 289 |
| large | `auto_fib_extension.pine` | 16232 | **240** | 1.63 | 1564 |

**Notes**

- Unparse is **negligible** on Runtime hot path (LSP / format only).
- Cold parse includes ANTLR/class import first-touch; warm large still ~0.24 s → LSP/diagnostics tax on big scripts.
- Prior agent: SLL-first already shipped; residual is ANTLR `adaptivePredict` / large-grammar cost, not Python builder.

---

## 2. Interpret Runtime (bar loop)

n = **2000** bars, mode=`interpret`, median of 5:

| script | med (ms) | µs/bar | bars/s |
| --- | ---: | ---: | ---: |
| **minimal** | 27.8 | 13.9 | **72 000** |
| **ta_sma** | 79.5 | 39.7 | **25 200** |
| **ta_combo** | **411** | **205** | **4 870** |
| **strategy_ish** | 177 | 88.3 | **11 300** |

Scripts:

- `minimal` — `plot(close)`
- `ta_sma` — single SMA-14
- `ta_combo` — sma/ema/rsi/atr/stdev/bb/highest/lowest + 8 plots
- `strategy_ish` — dual SMA crossover + entry/close

**vs prior round-2 host numbers (same order of magnitude):** minimal ~34 ms, ta_multi ~323 ms, ta_combo ~443 ms — current tree is at least as good (minimal **28 ms**, combo **411 ms**).

### Flame-style cost (ta_combo interpret @ 1500 bars)

Wall ≈ **0.96–1.08 s** for one profiled run (~1.6 M calls).

#### Top 20 cumulative (`cumtime`)

| rank | cumtime (s) | focus | function |
| ---: | ---: | --- | --- |
| 1 | 1.08 | host | `Runtime.run` |
| 2 | 1.01 | dispatch | `NodeVisitor.visit` |
| 3 | 1.00 | stmt | `visit_Script` |
| 4 | 0.88 | expr | `visit_Call` |
| 5 | 0.61 | stmt | `visit_Assign` |
| 6 | 0.59 | builtins | `_call_builtin` |
| 7 | 0.49 | expr | `_dispatch_qualified_attribute_builtin` |
| 8 | 0.34 | stmt | `visit_Expr` |
| 9 | 0.16 | plot | `backend.evaluator._builtin_plot` |
| 10 | 0.13 | series | `_expect_series` |
| 11 | 0.09 | series | `_as_series` |
| 12 | 0.09 | expr | `_collect_call_args` |
| 13 | 0.07 | expr | `_is_qualified_attribute_builtin_call` |
| 14 | 0.06 | plot | `plotting._builtin_plot` |
| 15 | 0.06 | micro | `dict.get` |
| 16 | 0.05 | ta | `_builtin_ta_highest` |
| 17 | 0.05 | ta | `_builtin_ta_sma` |
| 18 | 0.05 | micro | `isinstance` |
| 19 | 0.05 | ta | `_builtin_ta_lowest` |
| 20 | 0.05 | ta | `_builtin_ta_bb` |

#### Top tottime (self time) — true hot native Python

| rank | tottime (s) | function | read |
| ---: | ---: | --- | --- |
| 1 | 0.068 | `visitor.visit` | dispatch tax |
| 2 | 0.065 | `_as_series` | chrono materialize |
| 3 | 0.060 | `backend._builtin_plot` | multi-plot |
| 4 | 0.058 | `dict.get` | maps |
| 5 | 0.053 | `visit_Call` | call setup |
| 6 | 0.047 | `isinstance` | typing |
| 7 | 0.042 | `_call_builtin` | builtin resolve |
| 8 | 0.035 | `Runtime.run` | host loop body |
| 9 | 0.032 | `getattr` | attrs |
| 10 | 0.031 | `ast_qualified_name` | `ta.x` paths |

**Read:** Individual TA kernels (`_sma_inc`, `_stdev_inc`, highest…) are **no longer** the dominant self-time after rounds 1–3. Remaining interpret cost is **infrastructure**: visitor dispatch, call plumbing, series materialization, and plotting.

---

## 3. Compile + execute

n = **5000** bars, direct `compile_script` + `CompiledScript.run`:

| script | cold compile (ms) | warm compile (ms) | run med (ms) | bars/s | mode |
| --- | ---: | ---: | ---: | ---: | --- |
| minimal | 651 | 0.017 | **0.008** | ~6e8 | numba |
| ta_sma | 501 | 0.015 | **0.059** | ~8e7 | numba |
| ta_combo | **3153** | 0.016 | **1.13** | ~4.4e6 | numba |
| strategy_ish | 13.8 | 0.010 | **39.2** | ~1.3e5 | object |

### Runtime host: interpret vs `mode=compile` (n=2000)

| script | interpret med (ms) | compile host med (ms) | speedup |
| --- | ---: | ---: | ---: |
| minimal | 27.0 | 2.08 | **13×** |
| ta_sma | 74.2 | 2.23 | **33×** |
| ta_combo | 381 | 9.40 | **40×** |
| strategy_ish | 153 | 17.3 | **8.8×** |

**Gap:** bare `CompiledScript.run` for ta_combo is **~0.5–1.1 ms** @ 2–5k bars; Runtime `mode=compile` is **~9 ms** @ 2k → host wrap / convert / pack still leaves **~10×** on the table vs bare engine.

### Amortization (ta_combo, order-of-magnitude)

| Scenario | Cost model | Prefer |
| --- | --- | --- |
| 1 run, cold process | parse 13 ms + interpret 410 ms ≈ **420 ms** | **interpret** |
| 1 run, cold Numba | cold compile ~3 s + run 1 ms ≈ **3 s** | interpret |
| N≥10 warm host runs | compile cache hit; run ~1–9 ms each | **compile** |
| Interactive edit (parse every keystroke) | warm parse 3–240 ms | parse cache / debounce |

---

## 4. Pipeline cost breakdown (% time)

### A) One-shot **interpret** (parse once + run ta_combo @ 2k)

| stage | ms | % of oneshot |
| --- | ---: | ---: |
| parse (warm med) | 13 | **3%** |
| interpret run | 411 | **97%** |
| **total** | **424** | 100% |
| unparse | 0.1 | not on path |

### B) **Compile** cold + one warm execute (ta_combo @ 5k)

| stage | ms | % |
| --- | ---: | ---: |
| cold compile (Numba JIT) | 3153 | **~99.96%** |
| execute | 1.1 | **~0.04%** |

### C) Steady-state **warm multi-run host** (ta_combo)

| stage | ms/run | share of steady |
| --- | ---: | --- |
| warm compile cache | 0.02 | negligible |
| bare execute | ~1 | small |
| Runtime compile host | ~9 | still small vs interpret 411 |
| interpret (fallback) | 411 | baseline if not compiled |

**Flame ranking across full product surface**

```text
INTERPRET HOT PATH (default today)
├─ visit / visit_Call / _call_builtin ████████████████████ ~55–70%
├─ series _as_series / _expect_series  ████████ ~10–15%
├─ plot path                           ██████ ~10–15%
├─ host Runtime bar bookkeeping        ████ ~5–8%
└─ actual TA kernels (inc)             ███ ~5–10%

COMPILE HOT PATH (supported subset)
├─ cold Numba first-touch              ████████████ (one-time)
├─ object-mode strategy broker         ████ (strat only)
├─ Runtime host wrap vs bare run       ███
└─ numeric *inc kernels                ▏ (already excellent)

SIDE PATHS
├─ parse large / cold                  LSP & first request
└─ unparse                             format only
```

---

## 5. Coverage notes (`.cache` summaries)

| Corpus | Mode | Rate | Source |
| --- | --- | ---: | --- |
| set01+02 | compile | **100%** (494/494) | `runtime_corpus_set01_set02_compile_final_summary.txt` |
| set01+02 | compile v20 | **99.8%** (1 timeout) | `…_v20_summary.txt` |
| set03 | compile final | **98.5%** (968/983) | `runtime_corpus_set03_compile_final_summary.txt` |
| set01–03 | compile v13 (older) | 79% | nopython / drawings / names — largely fixed later |
| set02 | **interpret** | **85.3%** (209/245) | `runtime_corpus_set02_interpret_summary.txt` |
| parse set01–04 | parse | **94.2%** | `corpus_parse_set01_set04_summary.txt` |
| parse set01–05 | parse | **49%** (set05 noise/HTML) | `corpus_parse_set01_set05_summary.txt` |

**Top interpret fail (set02):** `float() argument … not 'PineSeries'` (14×) — correctness, not speed; blocks “interpret is always safe fallback” narrative.

**Top historical compile fails (older v13):** Numba nopython type imprecision, drawings, undefined names — improved to ~98–100% on cleaned sets.

**Perf research consensus** (`.cache/perf_research_summary_2026-07-28.md`): keep bar-by-bar; kill history rebuilds; incremental TA; single Runtime SoT — **mostly executed**.

---

## 6. pyne-worker benchmark

`python scripts/benchmark.py --iterations 15 --warmup 3`  
Data: BTCUSDT 1d, **3264 bars**

| script | avg ms | min–max | runs/min | errors |
| --- | ---: | --- | ---: | ---: |
| **big_strategy** | **1279** | 1187–1371 | 47 | 0 |
| **minimal** | **43.5** | 42–46 | 1380 | 0 |

Rough bars/s: minimal ~75k (aligns with pynescript host ~72k @ 2k); big_strategy ~2.5k bars/s (heavy strategy + drawings/broker path).

---

## 7. Recommended next engineering order

Ordered by **expected product impact × feasibility**, given prior rounds already harvested easy TA/host wins:

### P0 — Make the fast path the default

1. **Prefer `mode=auto` / compile in Pro API & AXIS** for supported numeric+strategy subset; keep interpret fallback.  
   - Rationale: **8–40×** already measured; cold JIT amortized on warm workers.  
2. **Shrink Runtime compile host overhead** toward bare `CompiledScript.run` (OHLCV once → arrays; avoid per-run re-pack). Target: host compile ≈ 1–2× bare run, not 10×.

### P1 — Interpret residual (fallback & unsupported)

3. **Last-scalar / skip `_as_series`** for pure-incremental `ta.*` call sites (residual from evaluate r3).  
4. **`visit_Call` / `_call_builtin` micro-cache**: per-script resolved builtin callable map; cut qualified-name + registry checks per bar.  
5. **Lighter multi-plot**: after r3 registry upsert, reduce backend `_builtin_plot` tottime (skip color/title coercions when constant).

### P2 — Compile UX & strategy

6. **Disk / process warm for Numba builtins** (already `cache=True` on kernels; ensure worker processes pre-touch common scripts).  
7. **Object-mode strategy**: remaining broker/`set_bar` costs after r3 4–6× win.  
8. **Parse timeouts / large-script LSP**: optional background parse; don’t block editor on 16 KB+ scripts for 240 ms+ if debounced.

### P3 — Coverage (enables P0 globally)

9. Fix top interpret `PineSeries`→float sites and missing builtins (`math.isfinite`, log arity).  
10. Keep compile corpus ≥98% on set01–03; track regressions in CI smoke (not full 5k-bar matrix).

### Explicit non-goals (still rejected)

- Whole-script vectorization / parallel bars  
- `na`→0  
- Unbounded series history  
- Replacing ANTLR wholesale (diminishing returns after SLL)

---

## 8. Where other agents should focus

| Agent focus | Do this | Don’t redo |
| --- | --- | --- |
| **Evaluate / TA** | scalar-only inc path; remaining non-inc (ADX, complex) | sma/ema/bb/stdev/hma/… already inc |
| **Dispatch / visitor** | call-site resolution cache; reduce `isinstance`/`get` | type-keyed visit maps already in |
| **Runtime host** | compile wrap, series cap already done | pre-bind loop again |
| **Compile/Numba** | host API, AOT/prewarm, object strat | re-implement ema/macd/hma_inc |
| **Plot** | constant-title fast path | O(plots) registry again |
| **Parse** | large-script / timeout UX | SLL-first / annotation skip |
| **Coverage** | PineSeries float, builtins gaps | — |

---

## 9. Reproduce

```bash
# from pynescript repo / worktree
PYTHONPATH=src:. .venv/bin/python scripts/bench_pipeline.py --profile \
  --json .cache/bench_pipeline_latest.json

# pyne-worker
cd ../pyne-worker
python scripts/benchmark.py --iterations 15 --warmup 3
```

Artifacts:

- `scripts/bench_pipeline.py` — E2E driver  
- `.cache/bench_pipeline_latest.json` — raw timings  
- This report: `docs/perf_round4/10_bottleneck_map.md`

---

## 10. One-line summary

**Interpret is now dispatch+series+plot bound (~5k bars/s multi-TA); compile is kernel-fast (~4M bars/s multi-TA) but cold-JIT and host-wrap limited — next wins are default-compile + residual interpret plumbing, not more SMA kernels.**
