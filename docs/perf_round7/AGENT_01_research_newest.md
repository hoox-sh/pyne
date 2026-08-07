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

# AGENT_01 — Research: newest bar-engine / Python numeric techniques

| Field | Value |
| --- | --- |
| **Role / ID** | Round 7 Agent 01 — RESEARCH |
| **Date** | 2026-08-02 |
| **BASE_SHA** | `045190203a1991aa683147995b5f42ee71169756` |
| **Files touched** | `docs/perf_round7/AGENT_01_research_newest.md` only |
| **Code changes** | none |
| **Tests run** | n/a (research-only) |
| **Verdict** | **research-only** |

---

## Executive summary

Top **10 actionable ideas** ranked by **ROI vs risk for THIS codebase**
(pynescript interpret bar loop + TA builtins + backend Runtime host). Rank
assumes Rounds 1–6 already shipped (see “Already done / skip”).

| Rank | Idea | ROI | Risk | Why for *this* repo |
| ---: | --- | :---: | :---: | --- |
| **1** | **Product warm-compile / H2** — default `mode=auto`, IR cache on, process prewarm, document SLOs | ★★★★★ | Low | R4–R6: compile run is ~µs-scale; interpret ta_combo still ~100× slower. Biggest product win is *routing*, not more visit micro-opts. |
| **2** | **T2 residual incremental TA** — `ta.bb`/`bbw` full path, nested full recompute, any remaining O(n) kernels | ★★★★☆ | Med | Pattern proven (call-site state, `PYNE_TA_INCREMENTAL`); bb already has SMA+stdev inc in volatility.py — finish nested/compose paths + goldens. |
| **3** | **T1 series cap ↔ `max_bars_back` / `_SERIES_MAX`** — one chronological buffer policy, drop prefix in-place | ★★★★☆ | Med | Host already trims at `_SERIES_MAX`; wire TV `max_bars_back` decls + PineSeries maxlen; unbounded growth is corpus TIMEOUT class. |
| **4** | **Single chronological buffer / O(1) lookback (flagged)** — PineTS-style forward store + reverse index; drop dual PineSeries deque + list | ★★★☆☆ | Med–High | Eliminates dual representation thrash; must preserve `None`=na, newest-first semantics. Behind flag. |
| **5** | **Parse/AST multi-run cache polish (Phase 1.6)** — sha256 already exists in `backend/runtime.py`; ensure Pro API + worker hit it | ★★★☆☆ | Low | Structural win for multi-script APIs; cold parse still dominates large corpus scripts. |
| **6** | **Lazy calendar + light plot/input registries** | ★★☆☆☆ | Low | Residual host tax on minimal/strategy paths (R4 map). |
| **7** | **H1 dual-host Runtime unify** — package-level SoT; worker thin host only | ★★★☆☆ | Process | Not µs/bar alone, but prevents perf/correctness drift; required for H2 product path. |
| **8** | **cProfile bottleneck map (Phase 0 residual)** — freeze post-R6 hot frames | ★★☆☆☆ | None | Guides R7+; avoid rediscovering R6 wins. |
| **9** | **mypyc / C extension for series kernels only** (Phase 3) | ★★☆☆☆ | High | 1.5–5× on typed numeric modules; not whole AST visitor. Prefer after interpret residual < dispatch floor. |
| **10** | **Free-threaded / 3.14 JIT experiments** | ★☆☆☆☆ | High | Free-threading helps multi-run *workers*, not one sequential bar loop. Do not parallelize bars. |

---

## 1. TradingView Pine execution model / profiler (public docs)

### Execution model (must preserve)

Sources: TradingView *Language / Execution model*, *Bar states*, *Strategies*,
*Profiling and optimization* (v6 docs, 2026).

| Principle | Implication for pynescript |
| --- | --- |
| Script runs **once per historical bar**, repeatedly on **realtime ticks** with **rollback** of non-`varip` state | Bar-by-bar AST visit is correct; do not batch bars |
| After each closed-bar execution, values are **committed** into **historical buffers** | Series history is a first-class runtime structure |
| Global scope evaluates **once per execution**; local scopes 0/1/N times → **local history buffers are inconsistent** if not hit every bar | Match TV warnings: history refs on locals are fidelity hazards |
| `var` persists across bars but **rolls back** across open-bar ticks; `varip` does not | Already modeled; keep tick/fill re-exec correct |
| Indicators recalculate every tick on open bar; strategies default **once per bar** (options: `calc_on_every_tick`, `calc_on_order_fills`, …) | Strategy host path is sequential by design |
| Historical buffers: typical max **5000** bars; OHLCV/time can be **10000**; `max_bars_back` / `max_bars_back()` set depth | Cap policy should track TV limits, not “keep forever” |
| Rollback clears temporary plots/objects/`var` on open bar | Multi-tick host must re-run scopes, not “patch” last bar |

### Profiler guidance (what TV optimizes *for authors*)

Pine Profiler wraps significant lines/blocks with timing; flames on top-3
hot regions. Compiler already drops unused/redundant code. Author-facing
advice that maps to *our* engine:

1. Prefer **built-in TA** over hand loops over history (we already make builtins O(1) via incremental state).
2. Avoid unnecessary **series materialization** and full-history scans.
3. Profile **across configurations** (period length changes loop cost).
4. Nested `if` can expose more granular costs than `switch`/`else if` (tooling only).

**Takeaway for R7+:** Our bottleneck is no longer “SMA is O(n²)” (fixed in R1–R6);
it is **AST visit + host bookkeeping + residual non-inc kernels + cold product path**.

---

## 2. Open Pine runtimes — buffer layouts & lookback

### PyneCore (PyneSys)

Docs: [Core Concepts](https://pynecore.org/docs/overview/core-concepts/).

| Technique | Detail | pynescript mapping |
| --- | --- | --- |
| **AST transform** of annotated Python → Pine semantics | `SeriesTransformer`, `PersistentTransformer`, function isolation | We interpret Pine AST; optional future: compile to specialized Python (Phase 3) |
| **Circular series buffers** (`SeriesImpl`) | `max_bars_back` default **500**; `add`/`set`; `series[n]` = n bars ago | Closest to ideal for **T1 + Phase 2.2** |
| **Persistent state vector** | Plain list slots, literal indexes — “fastest” bar state | Inspiration for `var` storage densification (low priority) |
| **Function isolation** | Per call-site state tree | We use `_ta_call_i` / call-site keys — same idea |
| **NA propagation** | Typed NA, never silent zero | Aligns with our hard constraint |

### PineTS (LuxAlgo / QuantForge)

Docs: [AGENTS.md](https://github.com/LuxAlgo/PineTS/blob/main/AGENTS.md), Series architecture notes.

| Technique | Detail | pynescript mapping |
| --- | --- | --- |
| **Forward chronological storage** | `push` O(1); oldest→newest arrays | Prefer over newest-first deque if we unify buffers |
| **Reverse access** | `close[0]` = last element via `$.get` / `Series.from` | We use newest-first deque; either layout OK if one representation |
| **Incremental TA + `_callId`** | O(1) per bar; never re-sum full window | **Done** for hot path in R1–R6 |
| **Committed vs tentative state** | Live bar must not corrupt history | Relevant for realtime/tick host later |
| **NaN handling in state** | Check before updating rolling sums | We use `None` as na — keep fail-closed |

### Layout comparison (current pynescript)

```
TV mental model:   historical buffer per series, depth max_bars_back
PineTS:            list forward chrono + reverse index O(1)
PyneCore:          circular buffer, configurable max_bars_back
pynescript today:  PineSeries: deque newest-first (slots)
                   current_series: list append-only chrono, trim by _SERIES_MAX
                   (dual store — Phase 2.2 target to collapse)
```

**Recommendation:** Adopt **PineTS forward + O(1) reverse** *or* **PyneCore circular** as single SoT; keep PineSeries as a thin view. Flag: e.g. `PYNE_SERIES_RING=1`.

---

## 3. Python hot-path tools (2024–2026)

| Tool | Fit | Guidance |
| --- | --- | --- |
| **Numba** | Already primary compile path (`compiler/`, nopython kernels) | Continue expanding kernels; disk IR + prewarm shipped R6 — **H2 productizes** |
| **mypyc** | 1.5–5× on typed pure-Python; AOT C extensions | Good for `series.py` / rolling helpers / small numeric modules; **alpha** tooling; do not mypyc the full visitor first |
| **Cython** | Mature, numpy-friendly | Only if mypyc insufficient for tight loops; more syntax tax |
| **Nuitka** | Already used for **LSP binary**, not bar loop | Keep for packaging; not interpret ROI |
| **NumPy rolling** | Vectorized windows | Useful **inside** one TA kernel for batch recompute/fallback; **never** whole-script vectorization |
| **array.array / memoryview** | Dense float buffers | Candidate for chronological OHLCV columns in host (already somewhat columnar in runtime) |
| **deque ring** | O(1) append/pop; maxlen | Already on PineSeries; chrono lists use list+del prefix |
| **CPython 3.13–3.14 free-threading + JIT** | Multi-threaded apps; specializing interpreter | Parallelize **independent runs** (API workers), not bars of one script |
| **Empirical compilers study (2025)** | Codon/PyPy/Numba large wins on pure numeric CLBG; mypyc moderate | Confirms: specialize **kernels**, not dynamic AST walks |

**Verdict:** Short term stay **Numba + pure-Python incremental TA**. Medium term pilot **mypyc** on `backend/series.py` + rolling helpers. Avoid Codon (subset) and free-thread single-script hopes.

---

## 4. Incremental / online algorithms (SMA/EMA/RSI/BB/ATR)

| Indicator | Online form | Status in pynescript |
| --- | --- | --- |
| **SMA** | Rolling sum + window deque O(1) | **Done** (`_sma_inc_update`) |
| **EMA / RMA** | Exponential recurrence | **Done** |
| **RSI** | RMA of gains/losses | **Done** |
| **MACD** | Nested EMAs | **Done** (2.1b) |
| **ATR** | EMA/RMA of TR | **Done** (fidelity: Wilder re-baseline = F1, opt-in) |
| **BB** | SMA + sample stdev | **Partial** — `_bollinger_bands` uses `_sma_inc_update` + `_stdev_inc_update` in bar mode; residual full paths / nested compose still T2 |
| **Stdev / variance** | Running sum + sumsq (Welford optional) | Inc path uses sum/sumsq; Welford more stable for long periods |
| **Correlation** | Online bivariate moments | Inc added R6 |
| **Highest/Lowest** | Monotonic deques | Done R4+ |

### Welford / exponential smoothers

- **Welford** (Wikipedia / numerical analysis): numerically stable online mean/variance; preferred when periods are large or values are large-magnitude prices.
- **Wilder RMA**: α = 1/period (not EMA’s 2/(period+1)); F1 only with goldens.
- **Sliding-window Welford / sum-of-squares**: for BB sample stdev (ddof=1), sum/sumsq over non-na window matching `statistics.stdev` is correct; Welford sliding variants reduce cancellation risk — optional polish behind flag if goldens prove drift.

**Do not** replace Pine `na` with 0 to keep windows dense.

---

## 5. AST interpreter micro-optimizations

Industry + R5–R6 practice:

| Technique | Status | Notes |
| --- | --- | --- |
| Specialize `visit_Call` / arg plans | **Done R6** | Name/Const skip; 1/2/3-arg unroll |
| Call-site / builtin resolution cache | **Done R5–R6** | `_SITE_*` classification |
| Direct `visit_Call` from assign/expr | **Done R6** | Fewer visit frames |
| FunctionDef freeze params/body plan | **Done R6** | |
| `__slots__` on hot objects | **Partial** | `PineSeries` has slots; expand to strategy/plot structs carefully |
| Free-lists / object reuse | Open | Reuse plot/event dicts per bar (R4–R5 lighter registries) |
| Method / type dispatch cache | Residual | Attribute load on builtins still costly; bound methods on first resolve |
| Typed IR / bytecode | Phase 3 | Compile path already; interpret stays tree-walk by design |
| PyPy method cache / specializing interpreter | Env-level | Don’t depend on; write CPython-friendly tight loops |

**After R6:** interpret micro-opts are **diminishing returns**. Next 10–20% on ta_combo is more likely **series dual-store**, **registry**, and **residual TA** than another visit_Call plan.

---

## 6. What NOT to do (Pine fidelity)

Hard non-goals (roadmap + TV model + peer runtimes):

| Anti-pattern | Why forbidden |
| --- | --- |
| **Vectorize whole scripts** | Breaks control flow, `var`/`varip`, strategy fills, barstate |
| **Parallelize bars of one run** | Sequential series + broker state; race on history buffers |
| **Silent `na` → 0** | Changes crosses, RSI warmup, signals |
| **Drop bar-by-bar default** | Corpus + strategy event order depend on it |
| **Share TA state across call sites** | Pine function isolation; PineTS `_callId` rule |
| **Recalculate full history every bar** (without flag) | O(n²); peers ban this |
| **Numba-on-edge as default** | Packaging / coverage (skill.md) |
| **Hand-edit generated grammar** | AGENTS.md |
| **ATR Wilder / TV supertrend “fix” without goldens** | F1 only |

---

## Techniques already used in Rounds 1–6 (done / skip)

| Technique | Round | Status |
| --- | --- | --- |
| `_pine_defs_locked` after bar 0 | Phase1 / R1 | **Done** — skip |
| Append-only `current_series` (no reverse every bar) | Phase1 | **Done** — skip |
| One-pass hl2/hlc3/ohlc4/tr | Phase1 | **Done** — skip |
| `_pine_bar_mode` + incremental TA flag | Phase1–2 | **Done** — skip |
| Inc: sma/ema/rma/rsi/macd/atr | Phase2.1 | **Done** — skip |
| Inc residual: vwap, mom, swma, linreg, dema/tema, dmi/adx, supertrend, mfi/sar/kc/alma/corr/percentiles, … | R4–R6 | **Done** — skip rediscovery |
| Call-site cache + arg plans + visit_Call specialize | R5–R6 | **Done** — skip unless profile proves new frame |
| `_as_series` skip on pure-inc path | R5 | **Done** — skip |
| PineSeries `__slots__` + last-sample helpers | R5–R6 | **Done** |
| Plot steady-state / lighter capture | R4–R5 | **Done** — residual registry polish only |
| Compiler Numba kernels + history `[]` numeric surface | R4–R6 | **Done** |
| Disk IR cache, dual-key LRU, prewarm API | R6 | **Done** — H2 = productize |
| Host fail-cache, inputs→interpret auto | R6 | **Done** — H1 residual is worker/package unify |
| `_SERIES_MAX` materialization + runtime trim | Partial (code present) | **T1** still open for max_bars_back wiring / policy |
| BB inc via sma+stdev | Partial in tree | **T2** finish nested/full residual |

---

## Techniques to apply next (R7+) with concrete file targets

### A. Roadmap-aligned (P1–P2)

| ID | Action | Primary files |
| --- | --- | --- |
| **H2** | Warm-compile product path: deploy defaults IR on, prewarm at worker boot, document SLOs | `backend/runtime.py`, `backend/app.py`, `src/pynescript/compiler/engine.py`, docs under `docs/pyne/` |
| **H1** | Package-level Runtime SoT; pyne-worker thin host parity | `backend/runtime.py`, sister `/home/jango/Git/pyne-worker/...` |
| **T1** | Cap series to `max_bars_back` / `_SERIES_MAX`; honor `max_bars_back()` decls | `backend/runtime.py`, `backend/series.py`, `src/pynescript/ast/evaluator/builtins/utility.py`, `technical_submodules/core.py` |
| **T2** | Residual inc TA (bb compose, nested full paths) | `technical_submodules/volatility.py`, `core.py`, `basic.py`, `moving_averages.py`; goldens `tests/test_ta_incremental.py` |
| **C1** | Corpus RUN_FAIL tail | sanitize + evaluator residuals (other agents) |
| **F2** | Pending-fill averaging pyramiding ≤ 0 | `src/pynescript/ast/evaluator/builtins/strategy.py`, `compiler/strategy_broker.py` |
| **Phase 1.6** | Ensure parse/AST sha256 cache hits on all multi-run hosts | `backend/runtime.py` (cache present ~L48+), Pro API entrypoints |
| **Phase 2.2** | Single chronological buffer / O(1) lookback **flagged** | `backend/series.py`, `backend/runtime.py`, evaluator series accessors |
| **Phase 1.4 / 2.5** | Lazy calendar; light plot/input registries | `backend/runtime.py`, evaluator plot paths |
| **Phase 0** | cProfile map post-R6 | `scripts/bench_pipeline.py --profile` |

### B. Research-backed, not yet scheduled

| Action | Files | Flag / gate |
| --- | --- | --- |
| Sliding Welford for stdev if goldens show sumsq drift | `core.py` `_stdev_inc_update` | behind inc flag |
| Dense OHLCV columns (`array('d')` / memoryview) for host | `backend/runtime.py` | opt-in |
| mypyc pilot on series + rolling | `backend/series.py` (+ thin helpers) | optional extra; CI matrix |
| Free-list reuse for per-bar plot/event containers | evaluator plot/strategy | goldens |
| Document max historical buffer = 5000 default TV policy | utility + runtime | docs + cap |

### C. Explicit skip this round

- Whole-script Numba without control-flow analysis  
- Free-threaded bar parallel  
- mypyc of entire `expressions.py` visitor (high risk, low fidelity control)  
- Re-tuning already-shipped sma/ema/rsi inc  

---

## Citations / URLs

### TradingView
- Execution model: https://www.tradingview.com/pine-script-docs/language/execution-model/
- Profiling & optimization: https://www.tradingview.com/pine-script-docs/writing/profiling-and-optimization/
- Bar states: https://www.tradingview.com/pine-script-docs/concepts/bar-states/
- Strategies / broker emulator: https://www.tradingview.com/pine-script-docs/concepts/strategies/
- Limitations / max bars back: https://www.tradingview.com/pine-script-docs/writing/limitations/
- Buffer error RE10143: https://www.tradingview.com/pine-script-docs/errors/RE10143/
- Memory / max_bars_back guidance RE10139: https://www.tradingview.com/pine-script-docs/errors/RE10139/

### Open runtimes
- PyneCore core concepts: https://pynecore.org/docs/overview/core-concepts/
- PyneCore GitHub: https://github.com/pynesys/pynecore
- PineTS AGENTS / architecture: https://github.com/LuxAlgo/PineTS/blob/main/AGENTS.md  
  (Series: forward storage, reverse access; incremental TA + `_callId`)
- LuxAlgo PineTS acquisition note: https://www.luxalgo.com/blog/luxalgo-acquires-pinets-to-bring-pine-script-r-everywhere/

### Algorithms & Python engines
- Welford online variance: https://en.wikipedia.org/wiki/Algorithms_for_calculating_variance
- ATR methods (SMA / EMA / Wilder): https://www.macroption.com/atr-calculation/
- mypyc introduction (1.5–5×): https://mypyc.readthedocs.io/en/latest/introduction.html
- Empirical study Python compilers 2025: https://arxiv.org/html/2505.02346v1
- Python 3.14 free-threading / specializing interpreter: https://docs.python.org/3/whatsnew/3.14.html
- Python 3.13 free-threading & JIT overview: https://realpython.com/python313-free-threading-jit/

### Internal
- Perf skill: `.grok/skills/pynescript-perf/SKILL.md`
- Runtime plan: `.opencode/plans/2026-07-28-runtime-performance.md`
- R6 summary: `docs/perf_round6/00_summary.md`
- Roadmap: `docs/ROADMAP.md`

---

## Residual / follow-ups

1. Agent 02 should produce post-R6 cProfile map so ranks 2–6 are ordered by real tottime, not theory.
2. Confirm whether T1 series-cap agent should **raise** `_SERIES_MAX` toward TV 5000 for deep-lookback scripts or keep 256 with `max_bars_back` override (fidelity vs memory).
3. Phase 3 mypyc pilot only after interpret residual is series/TA-bound, not dispatch-bound.
4. Keep dual-host H1 as process/correctness ROI even when bench is flat.

---

## Recommended R7 merge order (orchestrator)

Suggested merge / verify sequence so later agents don’t fight earlier ones:

1. **Agent 02** (profile / bottleneck map) — measurement baseline, no semantic risk  
2. **Agent 05** (parse/AST sha256 multi-run) — low risk, host-only  
3. **Agent 03** (T1 series caps) — structural memory; flags + goldens  
4. **Agent 04** (T2 residual TA inc) — after or with T1 so windows respect caps  
5. **Agent 11** (lazy calendar + light registries) — host micro, low risk  
6. **Agent 09** (chronological ring / O(1) lookback, flagged) — depends on T1 policy; high review  
7. **Agent 07** (H2 warm-compile product) — product path; after IR cache already in tree  
8. **Agent 06** (H1 dual-host) — process; can parallel docs once SoT frozen  
9. **Agent 08** (C1 corpus residual) — correctness; can parallel with perf if no file clash  
10. **Agent 10** (F2 pending-fill) — strategy fidelity; goldens  
11. **Agent 12** (compiler residual + mypyc research) — last; no default on  
12. **Agent 01** (this report) — research-only, no merge dependency  

**Parallel bands:** {02}, {05 ∥ 08 ∥ 10}, {03 → 04 → 09}, {11}, {07}, {06}, {12}.  
**Do not** merge 09 before 03 goldens. Prefer **H2 (07)** early for product latency even if interpret ROI is elsewhere.

---

## Verdict

**research-only** — no production code changed. Findings reinforce the open roadmap (H1/H2/T1/T2) and peer-runtime patterns (circular / forward-chrono series, call-site incremental TA, no whole-script vectorization). Largest remaining ROI for *users* is **warm compile productization**; largest remaining interpret structural win is **series buffer unify + residual TA**, not further visit_Call specialization.
