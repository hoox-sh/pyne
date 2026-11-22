# Numeric / object / error transpile scan — four re-sourced populations (2026-11-18)

Card: `pyne-numeric-object-error-transp-fa4960d2` (HQ; slice 3 of `.oo/plans/engine-review-2026-11-18.md` §4).
Seat: oo-spec-2 (Deploy). Scope: measurement + artifacts only. No source, tests, board, or commits touched.
Method is the bgcolor method from `.oo/proof/numeric-mode-remeasure-2026-11-17/scan_numeric_mode.py`,
generalized and parametrized: every `tests/data/setXX/**/*.pine` (set01–06) matching the population regex is
transpiled once via `pynescript.compiler.engine._transpile_once(src)` (parse + CompilerVisitor only — no
JIT, no bar loop, no disk index). Classification (identical to 2026-11-17):

- `object_mode is True` → **object**; `object_mode is False` → **numeric**
- exception → **error** (reported separately, never folded into object/numeric; overwhelmingly scraped-doc parse failures, `CompileEmitError` 100%)
- `timeout = 0` (no per-file timeout, as before)

Scanner: `scan_numeric_object_error.py` (self-describing; population patterns embedded).
Scanned tree = `a85c6cb6` (all `run-*.json`/`before-*.json` record `repo_head=a85c6cb6...`; the scan ran
before the current HEAD landed). **HEAD is now `e157fd14`** ("perf(runtime): reuse cached object-mode
re-emit on the realtime host path", 2026-11-18; delta vs `a85c6cb6` is a single file,
`src/pynescript/runtime/host.py`, +8/−5). That change swaps a per-call `use_cache=False` transpile for
the engine's cache-backed `compiled._object_mode_for_realtime()` on the **realtime host path only**.
The scan calls `pynescript.compiler.engine._transpile_once` directly and never exercises the host path,
and no transpile semantics change is claimed by that diff — so scan results are expected to carry over
unchanged. **This was not re-proven by re-running the scan at `e157fd14`.** (Earlier note: HEAD had
already moved past the plan's `9d6e7dd6` at scan time; `a85c6cb6` itself was a cache change, expected
non-semantic, likewise not proven. Compiler source line refs below are against the scanned tree `a85c6cb6`.)
Interpreter: `/usr/bin/python` (3.14.10, same as the re-measure). 7 worker processes (`ProcessPoolExecutor`);
per-file results are independent, so results are identical in expectation to a sequential run.
`details-<population>.jsonl` = one JSON record per file `{file, set, outcome, [kinds]|[error], ms}`.
`summary.json` = aggregate; `before-*.json` / `details-*-before.jsonl` = per-population baselines.

## 1. Headline (scanned tree `a85c6cb6`, all six sets)

| population | match (regex) | set01–04 | set05–06 | all six | numeric | object | error |
|---|---|---|---|---|---|---|---|
| plotshape | `plotshape` | 359 | 2875 | 3234 | **54** | 1170 | 2010 |
| input_type_token | `type\s*=\s*input\s*\.` | 115 | 1878 | 1993 | **14** | 642 | 1337 |
| runtime_error | `runtime\.error` (i) | 553 | 199 | 752 | **55** | 628 | 69 |
| assigned_hline | `=\s*hline\s*\(` (ml) | 48 | 479 | 527 | **6** | 255 | 266 |

Per-set counts (numeric/object/error):

| set | plotshape | input_type_token | runtime_error | assigned_hline |
|---|---|---|---|---|
| set01 | 0/58/0 (58) | 2/78/0 (80) | 0/10/0 (10) | 0/16/0 (16) |
| set02 | 1/46/14 (61) | 0/7/1 (8) | 4/79/0 (83) | 0/5/0 (5) |
| set03 | 1/77/94 (172) | 0/15/2 (17) | 20/265/6 (291) | 0/15/2 (17) |
| set04 | 1/12/55 (68) | 0/4/6 (10) | 19/148/2 (169) | 0/6/4 (10) |
| set05 | 16/289/1817 (2122) | 2/219/1320 (1541) | 0/18/53 (71) | 5/75/259 (339) |
| set06 | 35/688/30 (753) | 10/319/8 (337) | 12/108/8 (128) | 1/138/1 (140) |
| **set01–04** | **3/193/163 (359)** | **2/104/9 (115)** | **43/502/8 (553)** | **0/42/6 (48)** |
| **set05–06** | **51/977/1847 (2875)** | **12/538/1328 (1878)** | **12/126/61 (199)** | **6/213/260 (479)** |
| **all six** | **54/1170/2010 (3234)** | **14/642/1337 (1993)** | **55/628/69 (752)** | **6/255/266 (527)** |

Errors are dominated by scraped-doc parse failures in set05 (e.g. input_type_token set05: 1320/1541 = 85.7%
error; plotshape set05: 1817/2122 = 85.6%). Errors were not "fixed"; counts are as-produced. No errors changed
between before/after baselines (see §4). Error class is 100% `CompileEmitError` in all four populations.

## 2. Did the landed numeric slices move their own populations? (set01–04 before → after)

Baselines = parent commit of each slice's fix (git archive of `src/` only, corpus re-used unchanged).
Parentage re-verified 2026-11-18 via `git rev-parse <fix>~1`: parent(`885dc745`)=`98cc8e70`,
parent(`a3c73539`)=`885dc745`, parent(`bc3e3012`)=`a3c73539`, parent(`915b65ba`)=`01a11897`,
and parent(`e157fd14`)=`a85c6cb6` — all OK:

| population | baseline sha (parent of fix) | before n/o/e | after (HEAD) n/o/e | flips object→numeric |
|---|---|---|---|---|
| input_type_token (fix `885dc745`) | `98cc8e70` | 0/106/9 | 2/104/9 | **2** — `set01/indicators/154_ind_hampel_filter.pine`, `set01/indicators/163_ind_mean_absolute_deviation_bands.pine` |
| runtime_error (fix `a3c73539`) | `885dc745` | 0/545/8 | 43/502/8 | **43** — full list in `summary.json → before_after.runtime_error.changed_files` (incl. tsi, ppo, macd, alma, fisher, inertia, …) |
| assigned_hline (fix `bc3e3012`) | `a3c73539` | 0/42/6 | 0/42/6 | **0** |
| plotshape (fix `915b65ba`) | `01a11897` | 0/196/163 | 3/193/163 | **3** — `set02/.../118_ind_beta_distribution_cdf_betadist_2`, `set03/.../0928_ind_highlow`, `set04/.../0873_ind_day_and_direction_change` |

No numeric→object regressions; no error-count changes anywhere (expected — the fixes don't touch parseability).
Runtime.error is the only slice with a material effect: **+43 flips (0 → 43 numeric in set01–04)** from files
whose *only* object-mode blocker was the non-literal/multi-arg runtime.error path. Baselines include earlier
slices (noted per row); e.g. the runtime_error baseline contains the input.* fix, the hline baseline contains
input.* + runtime.error, the plotshape baseline (`01a11897`) contains everything except `915b65ba` itself.

For reference, the bgcolor population (prior slice, `0968048c`) on the same re-measure harness: set01–04 went
0 → 10 (2026-11-17 gate) → **11** numeric on recheck (`.oo/proof/numeric-mode-remeasure-2026-11-17/`;
`scan_set01_04_recheck.json`: total 354, numeric 11, object 278, error 65; verified 2026-11-18). The +1 is the
same `0873_ind_day_and_direction_change.pine` that flipped again in the plotshape population here —
`scan_set01_04_recheck.json` records it with `om=false`, `kinds=['bgcolor','plotshape']`: one script, two
population matches, same underlying fix path (constant-condition numeric synthesis).
set05+06 bgcolor (18/1238/1059) was only ever measured post-fix; no pre-fix set05+06 baseline exists.

## 3. What actually forces object mode (compiler source + measured presence)

"Presence" column = fraction of the population's object-mode files containing ≥1 instance of the construct
(presence ≠ causation; per-file attribution would require bisecting the compiler, which is out of scope).
Forcing rules from source (scanned tree `a85c6cb6`):

| construct | rule (file:line, approx.) | populations affected |
|---|---|---|
| `input.string/text_area/color/symbol/timeframe/session` tokens | `visit_Attribute` → `object_mode=True` unless attr ∈ `_NUMERIC_INPUT_ATTRS` (`int,integer,float,bool,source,price,time`) — compiler.py:4778–4786, 3151 | input_type_token |
| any *unrecognized* `input.<token>` (e.g. `input.resolution`, 71 files) | same `else` branch → object mode | input_type_token |
| stringy `defval` / stringy `type` on `input(...)` | `_is_stringy_input_call` / `_is_stringy_value` — compiler.py:3165, 3229; stringy defval or no-defval string inputs → object (compiler.py:6216–6277) | input_type_token |
| `runtime.error` with non-literal or multi-arg call | `runtime_error` keeps `object_mode=True` unless `len(args) ≤ 1` and the arg is a quoted literal → `pine_raise_njit` (compiler.py:6539–6553) | runtime_error |
| `runtime_error_code` | always object (no numeric path) | runtime_error |
| `hline` price not provably numeric, or handle read later (`fill(h1,h2)`, `hline.delete`), or non-statement position | synthesizer declines → `_DRAWING_FUNCS` object path (compiler.py:2310, 2599–2612, 6300–6310; `_emit_assigned_hline`) | assigned_hline |
| plotshape with dynamic (non-constant) style/location/color/text/size/display/offset/editable/show_last, non-statement position, or dynamic condition | falls back to object drawing path (compiler.py:2492–2600 → 6501–6510) | plotshape |
| any `color.*` value in an expression position | color handling in object mode | all four (most common co-occurrence) |
| strategy()/library import/UDT/varip/array-map-matrix/string ops/switch/security… | independent forcing sites | all four |

Measured presence in object-mode files (census, `census-*.txt`):

| family | plotshape (n=1170) | input_type_token (n=642) | runtime_error (n=628) | assigned_hline (n=255) |
|---|---|---|---|---|
| `color.*` | 88.4% | 90.7% | 91.4% | 75.3% |
| array/map/matrix | 26.2% | 15.7% | 62.1% | 8.6% |
| strategy() | 22.8% | 37.9% | 1.4% | 6.7% |
| drawing (label/line/box/table/polyline) | 47.0% | 32.9% | 13.7% | 22.4% |
| string ops | 33.8% | 10.6% | 15.6% | 12.5% |
| library import | 7.9% | 3.0% | 8.1% | 4.7% |
| UDT decls | 7.9% | 2.8% | 3.3% | 0.4% |
| varip | 0.5% | 0.9% | 0.2% | 0.4% |
| stringy input token | 6.0% | 39.1% | 2.5% | 4.7% |
| **no known family (residual)** | **84** | **10** | **0** | **56** |

runtime.error call-shape among its object-mode files: **569 / 628 (90.6%) are literal single-arg calls — i.e. the
`runtime.error` itself is already numeric-legal and the file stays object for other reasons.** Only 59 (9.4%)
are non-literal/multi-arg (still forced by the runtime.error rule itself). `runtime_error` co-occurs with
`color.*` in 91.4% of its object-mode files — the dominant shared blocker is color/string/series handling,
not `runtime.error`.

Input-token population composition (all 1993 files; re-verified 2026-11-18 by re-tokenizing with
`type\s*=\s*input\s*\.\s*([A-Za-z_]\w*)`; numeric = int/integer/float/bool/source/price/time, stringy =
string/text_area/color/symbol/timeframe/session, other = anything else): **1,394 have numeric-class tokens and no
stringy token** (1,200 numeric-only + 194 numeric+"other"); **244 have stringy and no numeric** (235 + 9
stringy+"other"); **284 have both** (214 + 70 both+"other"); **71 are "other"-only and every one is
`input.resolution`** (the "other"-only bucket is exactly `{('resolution',): 71}`). So at most 1,394 files could
ever benefit from the 885dc745 slice; in practice only 2 flipped (see §2) — the rest are blocked by unrelated
constructs. Set01–04: 60 files have numeric-class tokens and no stringy token; 2 flipped.

**No population forces object mode as a class** (each has a numeric residue: 54/14/55/6). But no population is
anywhere near "unlocked": numeric share is 1.7% / 0.7% / 7.3% / 1.1%. Measured headroom from the landed slices is
single-digit (runtime_error: 43 files; the other three: ≤3 flips each).

### Population overlap and explicit residuals

The four populations are **not** disjoint samples; do not sum their counts across populations as if independent.
Computed 2026-11-18 from the `details-*.jsonl` files: union of matched files across the four populations is
**5,626**; **818 files (14.5%) match ≥2 populations**. Pairwise (file-level, any set):
plotshape ∩ input_type_token **523**; plotshape ∩ assigned_hline **108**; input_type_token ∩ assigned_hline **69**;
plotshape ∩ runtime_error **42**; input_type_token ∩ runtime_error **12**; runtime_error ∩ assigned_hline **3**;
triple/quadruple overlaps: plotshape+input_type_token+assigned_hline **53**, plotshape+input_type_token+runtime_error **5**,
plotshape+runtime_error+assigned_hline **1**, input_type_token+runtime_error+assigned_hline **1**, all four **1**.
Set01–04 overlaps: **57 files** match ≥2 populations. Consequence: the union of "object-mode" counts overstates the
distinct blocked corpus, and per-population flip counts are not additive.

Explicit residuals, restated:

- **Unattributed plotshape files: 84** (object-mode, matching no known forcing family; full list in `census-plotshape.txt`).
- **Unattributed input_type_token files: 10** (`census-input_type_token.txt`).
- **Unattributed assigned_hline files: 56** across all sets (all-files scope), **9 in set01–04** (`census-assigned_hline.txt`,
  `census-assigned_hline-set01_04.txt`).
- **runtime_error: 0** unattributed — but note its forcing is split: 569/628 (90.6%) object-mode files have only
  literal single-arg `runtime.error` calls (already numeric-legal; file is object for other reasons), and only
  **59 (9.4%)** are kept in object mode by the runtime.error rule itself. Blocking those 59 yields at most 59 flips
  even before accounting for other constructs.
- **`input.resolution` tokens:** 71 files whose *only* `input.<attr>` tokens are `resolution` (the other-only bucket
  is exactly `{('resolution',): 71}`, re-verified 2026-11-18); 344 files contain `input.resolution` anywhere.
  Else-branch → object mode. Derived from token regexes over source, not bisection.
- **input_type_token composition:** see the re-verified breakdown in §3 (1,394 numeric-no-stringy / 244
  stringy-no-numeric / 284 both / 71 other-only-resolution). At most 1,394 files could benefit from `885dc745`;
  only 2 flipped.
- **Set05+06 numbers carry no before/after delta** (no pre-fix corpus state ever existed); they are HEAD-only.

## 4. Before/after integrity checks

- Flips are exclusively object→numeric (0 regressions, 0 error changes) in all four baselines.
- Errors before == errors after in every population (parse failures are compiler-independent).
- Flip file lists: `summary.json → before_after.*.changed_files`; runtime_error's 43 files listed in full there.
- Baselines are git-archive extracts of `src/` only (`/tmp/opencode/oo-base-*`), corpus = current HEAD
  `tests/data` (last changed 2026-11-05, `add91aba`, per `git log -- tests/data`).
- `plotshape` + `assigned_hline` show set01–04 zero flips vs their own slices → those two slices, as landed,
  did **not** move this corpus's set01–04 population at the whole-file level.
- Reproduction re-check (2026-11-18, post-scan): `aggregate.py` exits 0 and rewrites `summary.json`
  byte-identically (diffed against a pre-run backup); `census.py` re-run for assigned_hline exits 0 — the
  all-files scope reproduces `census-assigned_hline.txt` exactly, and the set01–04 scope is saved as
  `census-assigned_hline-set01_04.txt` (42 object-mode files, 33 color_token, 9 residual).
- `details-*.jsonl` line counts equal the run totals exactly (after: 3234/1993/752/527; before: 359/115/553/48).
- Baseline parentage verified via `git rev-parse <fix>~1` for all four slices and for `e157fd14` (see §2).
- Proof directory is gitignored; no tracked repo files were modified by this work.

## 5. Recommendation (next unlock)

Do **not** commission more token-folding slices on these four populations — measured flips per slice are 0–43
and diminishing. Two concrete next steps, in order:

1. **Object-mode attribution pass (cheap, ~1–2 days, read-only instrumentation).** The decisive unknown is *which*
   construct sets `object_mode` first in each file. Add a temporary debug hook (e.g. env-gated first-setter log of
   `inspect`/`self.*` site) in a scratch worktree — not committed — and run the ~2,300 object-mode files across the
   four populations (2,357 distinct files; 787 in set01–04). Hypothesis to test: `color.*` (present in 75–91% of object-mode files here) and
   color-valued `plotshape`/`plot`/`bgcolor` arguments are the common root. If confirmed, the next real unlock is a
   color-handling slice, not another token slice.
2. **Assigned-hline zero-flip investigation** (hours): the `bc3e3012` synthesizer never fired on this corpus
   (set01–04: 0 flips; residual 56 files in object mode with no known family, e.g. `set05/.../6829_ind_toggle_hline_using_na_values.pine`).
   Likely causes to check: price not provably numeric (`_is_safe_numeric_expr` rejects), handle consumed by
   `fill`/`hline.delete`, or file already object for another reason before the hline is visited. If confirmed "no
   eligible dead handles exist in this corpus", that slice should be considered exhausted for this corpus, not
   extended.

Descoping `input_type_token` further work is also supported by data: only 2/115 flips in set01–04 despite 60
numeric-token-only files → the remaining files are blocked by non-input constructs.

**Bottom line — the next tractable numeric unlock, if any:** there is no evidence for a cheap token-level unlock in
these four populations. The landed slices yielded 2–43 flips each (Runtime.error being the best: 43), and the
measured headroom is bounded: runtime_error has at most 59 files whose forcing is attributable to the rule itself
(the other 569 are object-mode for other reasons), assigned_hline shows 0 flips with likely zero dead eligible
handles in this corpus, plotshape/input_type_token flips are 3 and 2. The only unlock with a plausible large
blast radius is a **color-handling slice**, but that hypothesis is unproven — color.* is *present* in 75–91% of
the object-mode files, which is presence, not causation. Until the attribution pass (step 1) names the actual
first object-mode setter, the honest answer is: **no token-level slice is worth commissioning next; the tractable
move is the cheap attribution pass, and only its result can justify (or kill) a color-handling slice.** If
attribution shows the first-setter is usually something else (e.g. drawing calls, UDTs, string ops), then there is
no tractable numeric unlock left in these four populations beyond long-tail, file-by-file work.

## 6. What was NOT verified / caveats

- Transpile-only scan: "numeric" means `_transpile_once` reaches `object_mode=False` — **not** that Numba/JIT
  compiles or that a bar loop runs. No corpus run, no interpreter run, no compile+run was performed.
- Before/after covers **set01–04 only** (as specified); set05+06 has no baseline (would require a pre-fix
  corpus-state comparison that never existed; set05+06 numbers are HEAD-only).
- Census columns are "file contains ≥1 X", **not** "X forced object mode". The 84/10/0/56-file residuals are
  unexplained by my family list (may be Pine v3/v4 idioms, e.g. `study(...)` + bare `type=integer` literals,
  dynamic plotshape args, in-function placement, etc.) — not root-caused.
- `runtime.error` multi-arg/dynamic share (59/628) is measured by a balanced-paren heuristic, labeled approximate.
- The scan ran at scanned-tree `a85c6cb6`. HEAD is now `e157fd14` (single file `src/pynescript/runtime/host.py`,
  realtime host path re-emit via the cached object-mode instance; no `_transpile_once` change). The scan was
  **not re-run at `e157fd14`**; carrying the numbers forward is an expectation, not a measurement. `a85c6cb6`
  itself was likewise already a cache-only change vs the 2026-11-17 re-measure's tree, unverified then as well.
- Error files are ~all scraped docs; their parse failure is unrelated to this work and was not attempted to be
  fixed (correctly).
- Parallel workers (7) vs the sequential 2026-11-17 scan: per-file classification is independent; timing differs,
  results should not (no shared state in `_transpile_once`).
- `input.resolution` forcing is via the unrecognized-token else-branch — derived from source reading, not bisection.
  (The 71 other-only files were re-verified to be exactly the `input.resolution` cases, but the object-mode
  attribution itself was not bisected.)

## 7. Artifacts (this directory)

- `scan_numeric_object_error.py` — parametrized scanner (patterns embedded)
- `run-{plotshape,input_type_token,runtime_error,assigned_hline}.json` — HEAD per-population summaries
- `before-{plotshape,input_type_token,runtime_error,assigned_hline}.json` — baseline (set01–04) summaries
- `details-{population}.jsonl` / `details-{population}-before.jsonl` — per-file outcomes (7581 records total)
- `summary.json` — machine-readable aggregate (per-set/scope counts + before/after + flip lists)
- `census-{population}.txt` — object-mode forced-family census (raw output of `census.py`)
- `census-assigned_hline-set01_04.txt` — assigned_hline census restricted to set01–04 (42 object-mode files)
- `census.py` — census tool; `aggregate.py` — aggregator (re-run 2026-11-18, byte-identical summary); `scan.log` — full progress log
- Timing: plotshape 694s, input_type_token 370s, runtime_error 144s, assigned_hline 111s; baselines 25–111s;
  total wall ≈ 26 min on 7 workers; all runs exit 0.

Env/method parity with `.oo/proof/numeric-mode-remeasure-2026-11-17/`: same scanner lineage, same interpreter,
same corpus path, same `_transpile_once` call, same classification rules; scan method identical, only fan-out
parallelism new.
