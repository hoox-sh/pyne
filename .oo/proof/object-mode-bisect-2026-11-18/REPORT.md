# Object-mode first-forcing-site bisect — 2026-11-18

**Slice 4 of the numeric-mode program.** Goal: find *which construct forces
object mode first* in the four scanned populations, not to fix anything.
Instrumentation only; no forcing logic was changed, removed, or reordered.

- Corpus: the 2,357 unique files with `outcome == "object"` in the four
  2026-11-18 populations (plotshape 1170, input_type_token 642, runtime_error 628,
  assigned_hline 255; 2,695 records → 2,357 unique files after cross-population dedup).
- Result: **all 2,357 files transpile object-mode for a named, recorded reason;
  zero files lacked a first forcing site; zero files changed outcome vs the
  2026-11-18 scan.**
- Headline: **color is not the blocker.** 87.7% of these files merely *contain* a
  `color.*` token (parity with the 75–91% census), but only **115 files (4.9%)**
  are first forced by a color site — too few to buy a numeric unlock. The
  distribution is broad: top site = 14.3%, top-5 = 54.5%, top-10 = 73.4%, and the
  string/input/strategy/array families dominate.

Artifacts in this directory: `trace.jsonl` (raw, 2357 lines), `results.jsonl`,
`aggregate.json`, `sites.md` (all 187 instrumented sites, hand-labeled),
`sites_table.py`, `object_mode_bisect_scan.py`, `aggregate.py`, `scan.log`.

## (a) Method

Instrumentation (uncommitted, `src/pynescript/compiler/compiler.py` +
`src/pynescript/compiler/engine.py`):

1. Every `self.object_mode = True` in `compiler.py` (187 textual occurrences)
   was replaced by `_om_trace(self)`, a module-level helper that (i) sets
   `object_mode = True` exactly as before, and (ii) the **first** time it is
   called per compilation, records `(caller_function, line)` on the visitor
   instance. When `PYNE_OBJECT_MODE_TRACE` is unset the helper is a no-op
   beyond the flag flip (one attribute read + one env lookup; no I/O).
2. `engine._transpile_once` computes `sha256(source)` and, after the compile
   finishes (success **or** exception), appends one JSON line
   `{"file": <sha256>, "site": "<func>", "line": <lineno>, "outcome": "ok|error"}`
   to the file named by `PYNE_OBJECT_MODE_TRACE` (O_APPEND, single write,
   errors demoted to stderr — tracing can never break a compile). Parse-stage
   failures (before a visitor exists) record nothing, as they have no forcing site.
3. The scan (`object_mode_bisect_scan.py`) re-transpiles every object-outcome
   file from the 2026-11-18 details files with `PYNE_OBJECT_MODE_TRACE` set,
   using the same `_transpile_once` path and `tests/data` corpus as the
   original scan, 7 workers. Results join trace↔corpus by sha256.
4. `aggregate.py` ranks sites by frequency, rolls sites up into families
   (hand-labeled, see `sites_table.py`), and computes the color comparison.

**First-site semantics and their limits.** The trace records the *first* forcing
site executed, i.e. the first statement that makes object mode unavoidable — not
all contributors, and not necessarily the "deepest cause" (e.g. an
`input.color` defval fires before the `plotshape(...)` that consumes it). A file
whose second and third forcing sites were never recorded may stay object-mode even
if the first site is "fixed". Counts below are therefore **upper bounds** on the
harvest of any single-site fix, not flip forecasts. The `_om_first_site` flag is
per compilation (fresh visitor per `_transpile_once`), set once, never reset.
`force_object_mode` (engine nopython recovery) would record site
`force_object_mode` — never observed in this corpus.

Verification:
- `ruff check` + `ruff format --check` clean on both changed files.
- Outcome parity vs the 2026-11-18 scan: **2357/2357 identical** (object→object).
- 0 trace lines missing, 0 unreadable files, 0 transpile errors, 0 `error`-outcome
  traces, 0 files with `object_mode` but no recorded site.
- `PYNE_OBJECT_MODE_TRACE` unset ⇒ zero writes, zero behavior change (flag flip only).
- Only files touched: `compiler.py`, `engine.py` (both uncommitted on purpose).

## (b) Ranked forcing sites (corpus-wide, n = 2357)

Top 20; full 50 firing sites in `aggregate.json` → `sites`, all 187 labeled
sites (incl. zero-hit) in `sites.md`. `line` refers to the instrumented
`compiler.py`.

| # | line | n | % | site (function) — label |
|---|------|---|---|--------------------------|
| 1 | 6300 | 337 | 14.3% | visit_Call — input with quoted/version-like defval, or input.color/symbol/timeframe/session/string defval |
| 2 | 6583 | 283 | 12.0% | visit_Call — `array.*`/`matrix.*` call |
| 3 | 2949 | 279 | 11.8% | visit_Assign — string constant RHS (e.g. `const string x = '…'`) |
| 4 | 5715 | 205 |  8.7% | _emit_strategy_attr — strategy direction/avg_price attrs |
| 5 | 6267 | 180 |  7.6% | visit_Call — `strategy()` declaration |
| 6 | 2977 | 107 |  4.5% | visit_Assign — stringy RHS (expr classifies as string) |
| 7 | 9249 |  89 |  3.8% | visit_BinOp — `Add` of two bare Names inside a UDF |
| 8 | 4842 |  84 |  3.6% | visit_Attribute — `type=input.<stringy>` token |
| 9 | 1194 |  83 |  3.5% | _visit_import_inner — `import` of a library |
|10 | 3127 |  82 |  3.5% | visit_Assign — catch-all: unclassified non-numeric RHS |
|11 | 6262 |  69 |  2.9% | visit_Call — `library()` declaration |
|12 | 6365 |  55 |  2.3% | visit_Call — `hline()` non-numeric price |
|13 | 5010 |  51 |  2.2% | visit_Attribute — dividends/currency/earnings/splits stub attr |
|14 | 6567 |  48 |  2.0% | visit_Call — drawing constructor (label/line/box/table/polyline) |
|15 | 4799 |  48 |  2.0% | visit_Name — bare type name used as a value |
|16 | 6626 |  48 |  2.0% | visit_Call — `color.new`/`color()` outside literal-fold position |
|17 | 4734 |  32 |  1.4% | visit_Name — bare color-name constant (`red`, …) |
|18 | 8018 |  32 |  1.4% | visit_Call — `float()` cast of non-numeric arg |
|19 | 7962 |  32 |  1.4% | visit_Call — `color.rgb` |
|20 | 7825 |  27 |  1.1% | visit_Call — `nz()` with non-numeric arg |

Family roll-up (sums to 2357):

| family | n | % |
|---|---:|---:|
| input (stringy/quoted defval, stringy token) | 421 | 17.9% |
| string (const RHS / stringy RHS / str.* / tostring / BinOp string) | 415 | 17.6% |
| strategy (declaration + attrs + history) | 391 | 16.6% |
| array/matrix/sequence | 308 | 13.1% |
| misc (alert 26, BinOp-in-UDF 89, catch-all-misc, …) | 201 | 8.5% |
| library (imports, library(), stubs, unknown calls) | 154 | 6.5% |
| color (color.* outside fold position + named constants) | 115 | 4.9% |
| drawing (ctor/setters/getters/hline/fill) | 111 | 4.7% |
| namespace (type names, tz, stub namespaces) | 109 | 4.6% |
| coercion (safe_float/nz/float-cast of non-numeric) | 63 | 2.7% |
| syminfo 33 · timeframe 12 · udt 9 · math 5 · enum 4 · map 2 · udf 2 · plot 1 · switch-if 1 | 67 | 2.8% |

Per-population dominant sites: plotshape → string const (19.8%), input
stringy (18.5%), strategy attrs (11.1%); runtime_error → `array.*` calls
(43.3%), BinOp-in-UDF (9.9%), library() (8.6%); input_type_token → `strategy()`
(18.1%), input.color/… defval (15.4%), strategy attrs (14.3%), input token
(12.6%); assigned_hline → hline price (21.6%), string const (15.3%), input
stringy (13.7%), bare type name (10.2%).

Notably, **not one object-outcome file was first forced by `runtime.error`**
(the `runtime-error` family has 0 first-site hits) — consistent with the prior
finding that 90.6% of runtime_error object files carry a literal single-arg
`runtime.error` which is already numeric-legal.

## (c) The color.* question

Two different numbers, kept separate:

| measure | plotshape | input_type | runtime_error | assigned_hline | overall |
|---|---|---|---|---|---|
| files with `color.*` token (census, reproducible: `\bcolor\s*\.`) | 1034/1170 = 88.4% | 582/642 = 90.7% | 574/628 = 91.4% | 192/255 = 75.3% | 2068/2357 = 87.7% |
| files whose **first forcing site** is a color site | 83 | 16 | 9 | 19 | **115 / 2357 = 4.9%** |

The census percentages reproduce the 2026-11-18 census (88.4/90.7/91.4/75.3)
exactly — same regex on the same corpus. But co-occurrence is not causation:
only 4.9% of files are *forced* by color (sites 6626/4734/7962/6657 + fold-failure).
Per-population first-color shares: plotshape 83/1170 = 7.1%, input_type_token
16/642 = 2.5%, runtime_error 9/628 = 1.4%, assigned_hline 19/255 = 7.5%.
(Per-population first-site counts sum > 115 because files belong to several
populations; the union count is 115.)

**Verdict: the color hypothesis is refuted as the blocking root cause.** A color
slice is capped at ≤115 files (4.9%) even under perfect execution and with zero
second-order blockers — and it would do nothing for the 95.1% of files forced
by input/stringy/strategy/array/library/etc. Color is the *most common
co-resident* in these files, not the gate.

## (d) Top-5 blocking constructs (by first-forcing family, n, % of 2357)

1. **Non-numeric/string inputs** — 421 files, 17.9% (site 6300: 337 — quoted or
   version-like defval or `input.color/symbol/timeframe/session/string/text_area`;
   site 4842: 84 — `type=input.<stringy>` attribute token). Semantics: these
   values are strings; numeric mode cannot hold them.
2. **String constants / stringy expressions in assignments** — 415 files, 17.6%
   (site 2949: 279 — `const string x = '…'` style string-constant RHS; site 2977:
   107 — stringy expr RHS; the rest str.* / tostring / string BinOp).
3. **strategy() and strategy.direction/avg_price attrs** — 391 files, 16.6%
   (strategy() declaration 180; strategy direction/avg_price/series attrs 211).
4. **array.\*/matrix.\* calls** — 308 files, 13.1% (site 6583 fires on any
   `array.`/`matrix.` builtin call; dominant in runtime_error: 43.3% of that
   population).
5. **misc bucket (catch-alls & heuristics)** — 201 files, 8.5%: BinOp `Add` of
   two bare names inside a UDF (89, 3.8% — a suspicious blanket heuristic),
   assignment catch-all (82, 3.5%, same as the unknown bucket), alert()/alertcondition()
   (26), plus 4 one-offs. These are identifiable code paths but not a single
   construct.

(Library imports — 154 files, 6.5% — would be #6; UDT-related sites total only
9 files, 0.4%; UDT-first-forcing is negligible in this corpus.)

## (e) Residual "unknown / unattributed" bucket — 84 files (3.6%)

Definition: first forcing site is a catch-all, not an attributable construct:
site 3127 (unclassified non-numeric RHS in assignment, 82 files), site 8077
(unknown call → object-mode stub, 2 files), sites 5151 / 1445 (0 each).
They are enumerated in `aggregate.json` (`unknown_bucket_examples`). Examples:

- set01/indicators/165_ind_t3_moving_average.pine
- set01/indicators/199_ind_ttm_squeeze_plus_macd_line.pine
- set01/indicators/215_ind_kdj.pine
- set01/indicators/224_ind_chop_and_explode_ps5.pine
- set01/indicators/226_ind_chop_and_explode_ps5_v_2.pine
- set01/indicators/250_ind_similarity_search_karobein_and_seasonal_random_index.pine
- set02/indicators/200_ind_ehlers_reverse_ema_reverseema.pine
- set02/indicators/243_ind_predictability_regime_index.pine
- set03/indicators/0285_ind_ehlers_reverse_ema_reverseema.pine
- set03/indicators/0338_ind_one_euro_filter_oneeuro.pine

These need per-file triage (most are of the shape "RHS is a call/expr the
compiler cannot prove numeric"); e.g. 165_ind_t3_moving_average and family are
feedback-filter loop scripts. They are NOT silently bucketed — every one is
listed and individually inspectable. The related "misc" family (201 files) is
attributed but not construct-named; the BinOp-in-UDF heuristic (89 files, e.g.
`set02/indicators/119_ind_parabolic_sar_extended_sarext.pine: sar + af*(ep-sar)`
class of expressions) is the largest single "probably over-broad heuristic"
candidate seen by this trace.

## (f) Recommendation

**Do not commission a color slice, and do not expect any single compiler slice to
unlock this corpus. Confirm object-mode steady state for these four populations;
the only candidate worth even a spike is the BinOp-in-UDF heuristic — expected
gain ≤3.8%, likely much less.**

Reasoning, from first-site counts (upper bounds; real flips are strictly lower
because of second-order forcing sites):

1. The three biggest families (~38.1% string-semantics, 16.6% strategy, 13.1%
   array/matrix) are **capability gaps, not bugs**: numeric mode has no string
   scalars, no strategy broker, no float-array kernels. "Fixing" them means
   extending the numeric backend — a program, not a slice.
2. Color: ≤115 files (4.9%), of which most (plotshape+assigned_hline, ~102)
   are likely to re-force on the next site anyway. The census co-occurrence
   (87.7%) was not causation. A color slice is not justified by this data.
3. Library imports (154, 6.5%) and UDTs (9, 0.4%): object mode is the designed
   answer; unlocking means numeric-mode libraries/UDTs — out of scope.
4. runtime.error: **0 files** first-forced by it — the earlier runtime.error
   slice (43 flips) already harvested what that path allowed; nothing left there.
5. Plausible-but-small candidates only: site 9249 (BinOp name+name inside a UDF,
   89 files / 3.8%) looks like an over-broad conservative rule — worth a *look*
   (one function, one predicate) to see if it can be narrowed safely; site 3127
   (82, 3.5%) is a genuinely opaque bucket needing per-file triage, not a slice.
   Combined ceiling ≤171 files (7.3%), realistically far fewer after second-order
   forcing, and both are single-heuristic tweaks, not "the" unlock.
6. Even a fantasy "fix everything cheap" (color 115 + BinOp 89 + catch-all 82 +
   nz/casts) tops out at ~12% of this corpus with no guarantee of end-to-end
   numeric residency; the residual string/input/strategy mass would remain.

**Expected unlock of any single recommended slice: ≤4% with high uncertainty —
i.e. effectively zero. The honest status is steady state: these four populations
are object-mode by construction, and the compiler's forcing logic matches that
reality.** If the program wants a measurable next step, it is a *design* decision
(strings-in-numeric or strategy-in-numeric), not a compiler bugfix — take it to
the operator as a fork in the road, not a ticket.

## (g) Not verified / caveats

- Transpile-only: `object` means `_transpile_once` finished with
  `object_mode=True`. It does **not** mean Numba/JIT compiles, and says nothing
  about runtime behavior, correctness, or performance. No corpus or runtime
  execution was performed.
- First-site semantics: only the FIRST forcing site is recorded; a file may have
  several forcing constructs. Fixing the first does not guarantee a numeric flip
  (second-order sites would re-force). Unlock estimates above are upper bounds.
- First-site attribution is order-dependent (visit order ≈ source order). A file
  forced at line 1 by a cosmetic construct (e.g. a `const string` at the top) is
  attributed there even though other sites would force it too.
- `force_object_mode` (engine nopython-recovery re-emit) never appeared — this
  scan measures the compile-time forcing surface only, not the runtime fallback.
- `error`-outcome files: none here (2357/2357 ok). Parse-failure files would be
  invisible to the tracer (no visitor exists) — not applicable to this corpus.
- Source was read with `errors="ignore"` (matches prior scans); non-UTF8 bytes
  could alter the sha256 join key — none observed (0 unmatched files).
- Files in multiple populations are counted once per population in the
  per-population tables (union = 2357); corpus-wide tables count each file once.
- Identical-content files (same sha256) are indistinguishable in the trace; each
  compile appended one line, and counts were assigned per results record, so
  duplicates are counted per file, not per unique content.
- The instrumentation itself (2 helpers + 187 call-site substitutions + 1 line
  in `_transpile_once`) was behavior-verified only via: ruff clean, the 2357/2357
  outcome parity check, and spot-traces — not via the pytest suite (intentionally
  not run; no tests were modified).
- HEAD moved during the work (e157fd14 → a84bd88b, `test(runtime)`: adds an
  unrelated test file; lands *after* this instrumentation began). My edits to
  `engine.py`/`compiler.py` are unaffected (different files) and remain
  uncommitted as required.
- Trace line numbers refer to the instrumented `compiler.py` in this working
  tree; any future edit invalidates them (sites.md records the same snapshot).

## Provenance

- Scanner: `object_mode_bisect_scan.py` (this dir), adapted from
  `numeric-object-error-scan-2026-11-18/scan_numeric_object_error.py`.
- Scan wall clock: 565 s for 2,357 files (7 workers, 4.2 files/s), 2026-11-18
  ~14:56–15:05. Full log: `scan.log`.
- Aggregation: `aggregate.py` → `aggregate.json` (full per-site table with
  per-population breakdowns and example files) — read that for anything not in
  this report.
- `sites.md`: all 187 forcing sites with line numbers, enclosing function,
  one-line label, and family.
- Enumeration of the 187 sites preceded instrumentation (STEP 1 of the task);
  the trace then measured which of them actually fire.
