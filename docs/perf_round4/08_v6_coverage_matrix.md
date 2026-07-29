# Pine v6 Full Surface Coverage Matrix (Agent 8)

**Date:** 2026-07-29  
**Scope:** Cross-check of `docs/pine_v6_full_surface_inventory.md`, `docs/missing_features.md`, and `docs/pinescript_implementation_status.md` against live code (dispatch map, ASDL/builder, evaluator builtins, compiler, `backend.runtime.Runtime`).  
**Method:** Live `NodeLiteralEvaluator._build_builtin_map()` (870 callables), targeted parse/visit/Runtime probes, compiler path greps.  
**Legend:** **Supported** = usable real semantics for common scripts · **Partial** = registered but incomplete/mock/host-skewed · **Stub** = accepts/returns placeholders · **Missing** = not registered or hard-fails common use.

---

## Executive summary

| Layer | Estimate | Notes |
|-------|---------:|-------|
| **Dispatch surface** (callable builtins) | **~99%** of official TV function reference symbols registered | Docs claim 0 missing vs 434 TV ref list (2026-07-25 inventory); live map now **870** keys |
| **Interpret Runtime fidelity** (common real scripts) | **~84%** weighted | Strong core; residual corpus `RUN_FAIL`/`TIMEOUT` from arity/log/str edges + long-tail TA |
| **Parser / language v6** | **~94%** | Multiline, enum, UDT, export const/type/enum/func, soft keywords OK; method-in-type-body parse hole |
| **Compile mode** (`mode=compile`/`auto`) | **~70%** of interpret surface | Broad object-mode stubs; numeric njit subset for hot TA; strategy broker object-mode present |
| **Docs accuracy vs code** | **Optimistic in places** | Inventory marks some series ✅ that resolve to **string fallbacks** without host injection; `strategy.percent_of_equity` documented ✅ but **not in** `strategy_constants` dispatch |

**Overall (product-useful v6 surface, interpret + host Runtime):** **~84%**  
**Overall (symbol registration only):** **~97–99%**  
**Corpus Runtime (set01–04, prior projection):** **~90% OK** (parser residual ~5% mostly truncated scrapes)

---

## Live dispatch counts (2026-07-29)

Regenerated via `NodeLiteralEvaluator()._build_builtin_map()`:

| Namespace | Live count | Inventory (2026-07-25) | Delta note |
|-----------|----------:|-----------------------:|------------|
| `ta` | 160 | 159 | research + core helpers |
| `strategy` | 79 | 70 | risk/series expansion |
| `matrix` | 74 | 74 | full linalg + predicates |
| `array` | 57 | 56 | |
| `box` / `label` / `table` / `line` | 32 / 29 / 27 / 23 | similar | drawing surface deep |
| `color` | 26 | 8 dispatch + palette | constants in map |
| `math` | 24 | 24 | complete official set |
| `str` | 19 | 19 | |
| `timeframe` | 15 | 3–14 mixed | funcs + period flags |
| `input` | 14 (+ bare `input`) | 12–14 | `text_area`, `enum`, `active` |
| `request` | 11 | 11 | all mock/data_feed |
| `map` | 11 | 11 | complete |
| `ticker` | 9 | 9 | |
| `footprint` / `volume_row` | 9 / 8 | present | mock methods |
| `log` | 3 (+ `runtime.error`) | 3 | **no varargs** |
| `polyline` | 3 | 3 | **setters missing** |
| `chart.point.*` | 5 | 5 | chart series via host `Chart` |
| **Total callables** | **870** | 640 (2026-07-25) | map grew; inventory snapshot lag |

---

## Coverage matrix (major namespaces)

Status is **code-verified** (not doc-only). Parser / ASDL / compiler columns use: ✅ present · 🔄 partial · ❌ absent · ⚙️ by design.

| Namespace | Status | Est. % | Parser | Evaluator | Compiler | Notes |
|-----------|--------|-------:|:------:|:---------:|:--------:|-------|
| **ta** | **Supported** | 88 | ✅ | ✅ | 🔄 | 160 symbols; core MA/osc/vol OK + incremental sma/ema/rma/rsi/macd/atr. Missing official-ish: `ta.aroon`, `ta.ao`, `ta.willr` (have `wpr`), `ta.ad` (have `accdist`), `ta.pvt` (have `vpt`), Hilbert/`ppo`/`trix`/`bop`/`ultosc`/`efi`/`fisher`. ~80 research/non-TV helpers. ATR uses EMA-of-TR (not Wilder RMA). Compile: subset njit + stubs (`dmi`/`supertrend` weak). |
| **math** | **Supported** | 98 | ✅ | ✅ | ✅ | Full 24 official (`abs`…`toradians`); `math.pi`/`e`/`phi` in base context. |
| **str** | **Supported** | 95 | ✅ | ✅ | 🔄 | 19 funcs; `format`/`format_time`/`split`/`tonumber` OK. Compile: `format_time` weak stub. String interpolation beyond `str.format` partial. |
| **array** | **Supported** | 96 | ✅ | ✅ | 🔄 | 57 ops; negative index; `sort`/`sort_indices` + UDT `sort_field`. Compile object-mode broad. |
| **map** | **Supported** | 97 | ✅ | ✅ | 🔄 | All 11 official (`new`/`put`/`get`/`keys`/`values`/…). Typed `map.new<K,V>` via Specialize. |
| **matrix** | **Supported** | 95 | ✅ | ✅ | 🔄 | 74 ops: linalg (`det`/`inv`/`pinv`/`eigen*`/`kron`/`rank`…), stats, predicates, `sort`/`sort_indices` + UDT field. |
| **strategy** | **Partial** | 78 | ✅ | 🔄 | 🔄 | entry/exit/close/cancel/order + OCA + commission + risk caps + open/closed trade series + events. **Gap:** `strategy.percent_of_equity` / `strategy.fixed` **not** in `strategy_constants` dispatch → resolve to string fallback; Runtime probe shows entry qty **1.0** not % equity. Broker not full TV tester (margin liquidation = na, etc.). Compile: `CompileStrategyBroker` object mode. |
| **request** | **Partial** | 70 | ✅ | 🔄 | 🔄 | All 11 registered (`security`, `security_lower_tf`, financial/economic/footprint/…). **Mock + optional data_feed** (by design). Compile: same-symbol passthrough stub. |
| **input** | **Supported** | 95 | ✅ | ✅ | ✅ | Bare `input` + typed (`int`/`float`/`bool`/`string`/`color`/`source`/`timeframe`/`symbol`/`session`/`time`/`price`/`text_area`/`enum`); `active` metadata; returns values + `_input_declarations`. |
| **ticker** | **Supported** | 90 | ✅ | ✅ | 🔄 | `new`/`modify`/`heikinashi`/`renko`/`kagi`/`pointfigure`/`linebreak`/`standard`/`inherit`; PercentageLTP styles. No live chart transform. |
| **timeframe** | **Supported** | 92 | ✅ | ✅ | 🔄 | `in_seconds`/`from_seconds`/`change` + period flags; host/Runtime injects `Timeframe` object + flat keys. |
| **color** | **Supported** | 97 | ✅ | ✅ | 🔄 | `new`/`rgb`/`r|g|b|t`/`from_gradient` + palette constants. |
| **log** | **Partial** | 55 | ✅ | 🔄 | 🔄 | `log.info`/`warning`/`error` + `runtime.error` registered. **Critical:** handlers accept **one** message only — `log.info("x={0}", close)` → **TypeError** (confirmed Runtime bar fail). Corpus risk: high. |
| **chart** | **Partial** | 60 | ✅ | 🔄 | 🔄 | `chart.point.*` (5) dispatch OK. Host `Chart` has `bg_color`/`fg_color`/`is_renko`/… but Pine names **`is_heikinashi`** vs code **`is_heikin_ashi`** (and similar underscore mismatches). Unresolved attrs fall back to **truthy qualified-name strings** → `chart.is_heikinashi ? 1 : 0` always **1** on Runtime (verified). `left_visible_bar_time` / `is_standard` etc. inventory-claimed ✅ are host-dependent / string stubs. |
| **polyline** | **Partial** | 40 | ✅ | 🔄 | 🔄 | Only `polyline.new` / `delete` / `all`. **Missing:** `get_points`, `set_points`, `set_line_color`, `set_line_width`, `set_line_style`, `set_fill_color`, `set_curved`, `set_force_overlay` (+ `copy` if expected). Hard `Unknown built-in` on Runtime. |
| **enum** | **Supported** | 92 | ✅ | ✅ | 🔄 | `EnumDef` ASDL + builder + visit; members; `input.enum`; export enum. Compile object-mode lighter. |
| **UDT** | **Supported** | 90 | ✅ | ✅ | 🔄 | `TypeDef`, `.new`, fields, collections of UDTs, sort_field. Compile object mode. |
| **methods** | **Supported** | 85 | 🔄 | ✅ | 🔄 | Standalone `method foo(T this) =>` + export method + call binding OK (tests). **`method` nested inside `type` body: PARSE FAIL** (`mismatched input '('`). |
| **import / export** | **Partial** | 75 | ✅ | 🔄 | 🔄 | `export const` / `export f` / `export type` / `export enum` / `export method` + in-process `LibraryRegistry`. `import user/Lib/ver as alias` OK for registered sources. **Missing:** live TradingView network libraries — unknown imports become **empty stub modules** (silent). |

### Language / syntax (non-namespace)

| Construct | Status | Notes |
|-----------|--------|-------|
| `//@version`, indicator/strategy/library | Supported | Declarations + kwargs metadata |
| `var` / `varip` / `:=` | Supported | First-bar assign; ReAssign |
| `for`/`for in`/`while`/`switch`/`if` | Supported | Dynamic `for` to-bound re-eval (v6) |
| Multiline `"""` / `'''` | Supported | Lexer + unparser |
| Strict bool / short-circuit | Partial→Supported | Core paths; edge na-bool residual |
| Bitwise ops / soft keywords | Supported | Corpus sanitize path |
| Typed UDF returns | Supported | Parser |

---

## High-impact gaps that break corpus Runtime

Ranked by **hard fail / wrong answer** risk on open-source corpus (not docs polish):

| # | Gap | Kind | Impact | Evidence |
|---|-----|------|--------|----------|
| 1 | **`log.*(fmt, …args)` arity** | Runtime | **High** — many scripts use printf-style `log.info` | Runtime: `log_info() takes 1 positional argument but 2 were given` |
| 2 | **Qualified-name string fallback** for unknown attrs | Semantics | **High** — silent wrong bools/values | `visit_Attribute` last resort returns `"chart.is_heikinashi"` (truthy) |
| 3 | **`strategy.percent_of_equity` / `strategy.fixed` constants** | Runtime | **High** for strategy corpus | Not in `strategy_constants`; entry size stays default 1.0 in probe |
| 4 | **`polyline.set_*` / `get_points` missing** | Runtime | **Medium–High** when used | Hard unknown builtin |
| 5 | **Official TA holes** (`ta.aroon`, `ta.ao`, `ta.willr`, Hilbert, …) | Runtime | **Medium** long-tail | Live map missing ~15–18 common TV names |
| 6 | **TV `import TradingView/…` empty stubs** | Runtime | **Medium** | Import succeeds; member use is no-op/empty |
| 7 | **`chart.is_heikinashi` host attr mismatch** | Semantics | **Medium** | Chart uses `is_heikin_ashi`; Pine name never binds |
| 8 | **`request.*` mock-only** | Fidelity | **Medium** (by design) | Multi-symbol/TF scripts “run” but wrong data |
| 9 | **method-inside-`type` body parse** | Parser | **Low–Medium** style | Standalone methods OK; nested form fails |
| 10 | **Compile stubs / numerical TA parity** | Compile + correctness | **Medium** for `mode=compile`/`auto` | `request.security` passthrough; ATR EMA vs RMA; weak `dmi`/`supertrend` |

Other residual (docs already track): corpus PARSE_FAIL ~118 truncated scrapes; TIMEOUT long scripts; `linefill.all` empty until modeled; strategy margin/session edges.

---

## Docs vs code discrepancies (audit notes)

| Claim (docs) | Code reality |
|--------------|--------------|
| Official TV ref **0 missing** dispatch (inventory 2026-07-25) | Symbol registration still excellent; **not** full semantic fidelity. Some official TA names still absent (`ta.aroon`, …). |
| `strategy.fixed` / `percent_of_equity` ✅ | **Not registered** in `StrategyConstantsMixin`; string fallback only. |
| `chart.is_heikinashi` ✅ | Host attr `is_heikin_ashi`; Pine name → string / wrong ternary. |
| `polyline.*` surface complete | Only new/delete/all. |
| `log.*` supported | Single-string only; multi-arg **Runtime crash**. |
| missing_features “~99%+ core v6” | True for **parser + common builtins registration**; **~84%** for end-to-end Runtime fidelity. |

---

## Prioritized implementation backlog

### P0 — Parser / silent semantics (correctness, low surface area)

1. **Attribute resolution:** do not return truthy qualified-name strings for unknown `chart.*` / `strategy.*` / `syminfo.*` — return `na` / raise / host default.  
2. **Chart host aliases:** `is_heikinashi` → `is_heikin_ashi`, `is_linebreak` → `is_line_break`, `is_pnf` → `is_point_figure`, add `is_standard` if needed.  
3. **Register `strategy.percent_of_equity` / `strategy.fixed` / cash qty-type constants** in `strategy_constants.py` and honor in entry sizing.  
4. **Optional:** allow `method` declarations nested in `type` body (grammar) if corpus uses that style.

### P1 — Runtime corpus killers

1. **`log.info/warning/error(msg, *args)`** — format with `str.format` semantics (or join); stop TypeError.  
2. **`polyline` setters/getters** — at least `set_line_color`/`width`/`style`, `get_points`/`set_points`, store on `Polyline` dataclass.  
3. **High-frequency missing TA:** `ta.aroon` (tuple), `ta.ao`, alias `ta.willr`→`wpr`, `ta.ad`→`accdist` or real AD, `ta.pvt`.  
4. **Import stubs:** fail closed or provide minimal TV library shims for top corpus imports; never silent wrong members without diagnostics.  
5. **`request.security` fidelity** when data_provider present (already partially wired) — document mock behavior clearly in Runtime errors.

### P2 — Polish / parity / compile

1. Expand compile njit TA (bb full, remaining smoothers); reduce object-mode stubs.  
2. ATR Wilder RMA re-baseline behind golden tests (correctness track).  
3. Incremental TA for remaining heavy kernels (`ta.bb`, nested helpers).  
4. Cap `current_series` to `max_bars_back`; unify backend vs pyne-worker host.  
5. Regenerate `pine_v6_full_surface_inventory.md` from live 870-key map; fix status on chart/strategy/log/polyline rows.  
6. `linefill.all` modeling; drawing force_overlay edge cases.

---

## Compiler support snapshot

| Area | Compile support |
|------|-----------------|
| Hot TA (`sma`/`ema`/`rsi`/… ) | Numeric njit path |
| `math.*` / many `str.*` / `array.*` / `matrix.*` / `map.*` | Object mode helpers in `numba_builtins` + visitor lowering |
| `strategy.entry/exit/…` | Object-mode `CompileStrategyBroker` + pending fills |
| `request.*` | Same-symbol / NaN stubs |
| UDT / enum / drawing | Object mode auto-switch |
| Unknown calls | Often no-op stub (avoids NameError; can hide bugs) |

`Runtime.run(..., mode="auto")` tries compile then falls back to interpret — good for coverage, not for parity guarantees.

---

## Optional test locks added

`tests/test_v6_surface_locks.py` (interpret locks for implemented, under-tested bits):

- Enum member compare + plot path  
- `timeframe.in_seconds` / `from_seconds`  
- `map.new` + put/get  
- `log.info` single-arg (documents current supported shape)  
- `polyline.new` + `delete`  
- `export enum` library registration  

These lock **current** support; they do not assert the P0/P1 gaps.

---

## Uncertainty

- Exact official TV function count and naming drift (2025–2026 monthly notes) — TA missing list is **best-effort** vs common reference names, not a scraped TV index on this date.  
- Corpus fail taxonomy mix (arity vs timeout vs truncated) — uses prior 2026-07-28 projections (~89.8% OK), not a fresh full re-run in this audit.  
- pyne-worker host drift vs `backend.runtime` — not fully re-diffed file-by-file.  
- Inventory “partial-heuristic” (docstring stub/mock) under-counts real semantic partials (string fallback, qty constants).

---

## Top 10 gaps (quick list)

1. `log.*` multi-arg format crash  
2. Unknown attribute → truthy string fallback  
3. `strategy.percent_of_equity` / `strategy.fixed` missing constants + sizing  
4. `polyline` mutator surface missing  
5. Missing official TA names (`aroon`, `ao`, `willr`, Hilbert, …)  
6. Empty TV library import stubs  
7. `chart.is_heikinashi` host naming mismatch  
8. `request.*` mock-only multi-symbol fidelity  
9. Method nested in `type` body parse failure  
10. Compile-mode semantic stubs + TA numerical parity (ATR RMA)

**Overall estimate: ~84% product Runtime coverage · ~97–99% dispatch registration · ~94% parser/language.**

**Report path:** `docs/perf_round4/08_v6_coverage_matrix.md`
