# BinOp-in-UDF object-mode forcing — spike verification — 2026-11-18

Slice: slice-5 spike (BinOp-in-UDF gate). Scope: verify the uncommitted prototype in
`src/pynescript/compiler/compiler.py`, measure the transpile-level effect, take one
focused look at the ichimoku anomaly. Nothing committed, staged, or pushed. No other
files touched by the prototype; `.prettierignore`, `tests/test_cli_util_coverage.py`,
`.vscode/` were already dirty before this session and were left alone.
`.oo/proof/object-mode-bisect-2026-11-18/` untouched. Board not edited (Chief owns it).

**Recommendation: NO-GO on merging this prototype as the slice-5 deliverable. GO on a
narrowly-scoped follow-up (Arg-unwrap fix + re-measure), and the real unlock is a
dedicated slice: UDF return-type inference + call-site argument numericity. See "Go /
No-Go".**

## (i) Mechanism — static reading only, no runtime verification

The gate (`visit_BinOp`, `compiler.py` L9209, gate at L9222-9236; previously L9249 in the bisect report)
forces `object_mode = True` + `pine_add()` for `Add` of two bare `Name` operands inside
a UDF — the 89-file first-forcing site from the bisect. The prototype narrows it:
if **both** operands pass `_ast_is_numeric(...)`, the gate falls through to the plain
`+` path instead of forcing object mode.

`_ast_is_numeric` was extended with three branches:

- `ast.Subscript` — numeric iff the subscripted value is numeric (history refs of numeric series).
- `ast.Conditional` — numeric iff both branches are numeric.
- `ast.Call` — delegated to new `_ast_call_is_numeric`:
  - `nz` / `fixnan`: numeric iff **all** args are numeric;
  - bare names in `_NUMERIC_BARE_CALLS` (abs/min/max/pow/sqrt/trig/log/floor/ceil/round/sign…);
  - `math.*` in `_NUMERIC_MATH_CALLS` (bare set ∪ {avg, sum, round_to_mintick, todegrees, toradians});
  - `ta.*` in `_NUMERIC_TA_CALLS` (ema/sma/wma/rma/vwma/dema/tema/hma/rsi/stoch/atr/stdev/variance/highest/lowest/highestbars/lowestbars/change/barssince/valuewhen/cum/linreg/vwap);
  - bool-returning `ta.crossover/crossunder/rising/falling` deliberately excluded.

Safety argument (as written into the code comment, not independently proven): a wrong
"numeric" claim reaches njit, which is expected to hard-fail into the existing
object-mode recovery path rather than silently miscompute. That is a recovery-path
assumption, not a guarantee; see "Not verified".

## (ii) What was measured

Transpile-level only, via `pynescript.compiler.engine._transpile_once` on the 89
population files (`/tmp/opencode/binop89.txt`, `tests/data/...`), object/numeric flag
read off the visitor. Re-run this session (`/tmp/opencode/outcome_spike_recheck.json`):

- **Before (baseline outcome_before.json): 89 / 89 object mode.**
- **After prototype (this session): 83 object, 6 numeric.** Exit 0, zero transpile errors.
- The 6 flips, exactly the 6 from the original measurement:

```
set03/indicators/0367_ind_mesa_adaptive_moving_average_mama.pine
set03/indicators/0425_ind_directional_movement_index_dx.pine
set03/indicators/0426_ind_directional_movement_index_dx_2.pine
set03/indicators/0630_ind_archer_moving_averages_trends_amat.pine
set03/indicators/0631_ind_archer_moving_averages_trends_amat_2.pine
set04/indicators/0527_ind_midpoint_midpoint.pine
```

Regression gates (this session, real exit codes):

| Gate | Result | exit |
|---|---|---|
| `pytest tests/test_compiler_library_inline.py tests/test_compiler_engine_r8.py tests/test_compiler_engine_edges_coverage.py -q` | 88 passed | 0 |
| `pytest tests/ -k numeric -q` | 137 passed, 5313 deselected | 0 |
| `pytest tests/ -k 'object_mode or realtime' -q` | 149 passed, 5301 deselected | 0 |

## (iii) What this does NOT establish

- A flip is a **transpiler flag**, not a runtime property. No generated module was
  executed for the 6 files; no dtype assertion, no plot-value comparison, no corpus run.
- Nothing here shows the flipped files are *faster* or *correctly* numeric end-to-end;
  the nopython→object recovery path could still swallow a bad numeric claim silently.
- The whitelist approach cannot see through *arguments*: `math.max(a, b)` is claimed
  numeric without inspecting `a`/`b`. That is deliberate (over-inclusive by design) and
  is the single biggest residual risk in the prototype.
- Parent-task figures carried forward, **not re-derived this session**: "30 of 89 files
  are forced by a later, second-order site even if this gate passes" and the bisect
  first-forcing methodology. The 68/116 figure below was re-counted this session.

## Prototype diff summary

- 1 file, `src/pynescript/compiler/compiler.py`, **+46 / −0** (pure insertion).
- New: `_NUMERIC_BARE_CALLS`, `_NUMERIC_MATH_CALLS`, `_NUMERIC_TA_CALLS` frozensets;
  `_ast_call_is_numeric()`; three new `_ast_is_numeric` branches (Subscript,
  Conditional, Call); the `visit_BinOp` gate now skips object-mode forcing when both
  Name operands are provably numeric.
- No behavior change intended or observed for non-UDF code paths; the gate only ever
  *narrows* a forcing rule.
- Pre-existing dirty files unrelated to the prototype: `.prettierignore`,
  `tests/test_cli_util_coverage.py`, `.vscode/`.

## Ichimoku anomaly — root cause FOUND (not fixed, out of scope)

Symptom: `0358_ind_ichimoku_cloud.pine` line 58 (`tenkan_high + tenkan_low`) still
forces object mode although `nz(high[i])` should look numeric under the new check.

Root cause (verified by instrumented `_ast_is_numeric` run this session):
**pynescript `Call.args` are `Arg` wrapper nodes, not expressions.**
`_ast_call_is_numeric` does `all(self._ast_is_numeric(a) for a in node.args)`; every
`Arg` falls through `_ast_is_numeric` (no `Arg` branch) → `False`. Therefore **every
`nz`/`fixnan` call classifies as non-numeric**, `h`/`l` never enter `numeric_locals`,
`tenkan_high`/`kijun_high`/… never qualify, and the line-58/59/60/61 gates all fire.
Probe trace: lines 36/37 `Call -> False`; names `h`, `l`, `tenkan_high` … all `False`;
bare `Name` OHLCV reads correctly `True`. The 6 measured flips succeeded because the
bare/`math.*`/`ta.*` branches never inspect args — only the `nz`/`fixnan` branch does,
and it is dead as written.

Fix would be one line — unwrap `getattr(a, "value", a)` before recursing (verify `Arg`
against keyword args / `name` field) — but that changes the measured population, so it was
**not** applied. Expected effect: at minimum the two ichimoku files flip; possibly more
(nz/fixnan-fed locals elsewhere). Real but unmeasured.

## The 30-elsewhere finding and the inference ceiling

- From the spike analysis (carried, not re-derived): ~30 of the 89 BinOp-gated files are
  forced at other, later sites even if this gate passes — so the realistic ceiling for
  this one heuristic is well under 89, and the measured 6 is consistent with that.
- Gate-event inventory (`/tmp/opencode/gate_events.json`, re-counted this session):
  **116 events across 53 files; 68 (58.6%) have neither operand with any local numeric
  evidence (lnum=F, rnum=F); 40 have only the right operand, 8 only the left.** The
  events are dominated by untyped UDF params (`x`/`src`/`len`: None) and locals whose
  numericity lives across a function boundary.
- Conclusion: the whitelist route is **exhausted**. What remains needs return-type
  inference for UDF calls and call-site argument numericity propagated into callee
  bodies — that is a dedicated slice ("UDF return-type inference + call-site arg
  numericity"), explicitly out of scope for this spike. The 6/89 is the honest
  single-heuristic yield.

## Go / No-Go

**NO-GO on merging this prototype as-is as the slice-5 result.**

Reasons: (1) one of its three new branches (nz/fixnan arg check) is dead code as
written, so it ships an unverified branch that *looks* like it covers the common
`nz(...)` pattern and does not; (2) zero runtime verification of the 6 flips;
(3) residual risk that the over-inclusive bare/math/ta whitelist claims numeric for
expressions njit rejects — safe only if the object-mode recovery path always catches it,
which was not exercised here; (4) measured yield 6/89 (6.7%) with the gate population
already known to be mostly second-order forced (~30) or inference-bound (68/116 events).

**GO (conditional) on a follow-up slice, in this order:**
1. Unwrap `Arg` in `_ast_call_is_numeric` (+ fixture pinning `nz(high[i])` numeric),
   re-run the 89-file measure; expect ≥ 6, ichimoku pair should flip. Still transpile-only.
2. Add one runtime assertion harness for the flipped files (exec the generated numeric
   module, compare a few plot outputs vs object mode) before any merge decision.
3. Then, and only then, decide on merge; the general unlock (UDF return-type inference +
   call-site arg numericity) is a separate design slice, not an extension of this diff.

Do not expand the whitelist further in this spike. Do not merge on these results alone.

## Not verified / caveats

- No corpus-scale run, no runtime dtype or plot-value verification of the 6 flips;
  transpile flag only.
- The nopython→object recovery path (the safety net for over-claiming) was not exercised.
- "30 of 89 forced elsewhere" and all bisect first-forcing counts are carried from the
  2026-11-18 bisect (`.oo/proof/object-mode-bisect-2026-11-18/`), not re-measured here;
  only the 68/116 event split and the 89→6 flip delta were re-counted this session.
- ichimoku root cause is confirmed for the `Arg`-wrap mechanism (probe evidence above);
  the size of the effect after unwrapping was NOT measured.
- Baseline (`outcome_before.json`) was produced in the earlier session; not re-generated.
- Pre-existing dirty files (`.prettierignore`, `tests/test_cli_util_coverage.py`,
  `.vscode/`) were not inspected and are not part of this slice.
- `tests/` green here means: these 374 selected tests pass; the rest of the suite
  (5313/5301 deselected in gates 2/3) was not re-run in this session.

## Evidence / artifacts

- Flip re-measurement: `/tmp/opencode/outcome_spike_recheck.json` (83 object / 6 numeric,
  exit 0). Command: `PYTHONPATH=src .venv/bin/python /tmp/opencode/measure.py /tmp/opencode/outcome_spike_recheck.json`
- Gate logs: `/tmp/opencode/gate1.log` (88 passed), `/tmp/opencode/gate2.log` (137), `/tmp/opencode/gate3.log` (149)
- Ichimoku probes: `/tmp/opencode/ichimoku_dbg.py` … `ichimoku_dbg5.py` (instrumented `_ast_is_numeric`, AST dump of the `Arg` wrapper)
- Bisect context (untouched): `.oo/proof/object-mode-bisect-2026-11-18/`
- Gate definition: `src/pynescript/compiler/compiler.py` `visit_BinOp` (~L9230),
  `_ast_is_numeric` (L3859), `_ast_call_is_numeric` (L3844).
