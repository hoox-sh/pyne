# Numeric `varip` parity — route `varip` scripts to object mode

**Date:** 2026-11-16
**Card:** `pyne-numeric-varip-parity-numeri-8745bc87`
**Status:** Working — first slice, no commit/push

## Why

Numeric nopython is historical-only: it hardcodes
`__isrealtime=False`, `__isconfirmed=True`, `__ishistory=True`,
`__isnew=True` and has no tick loop. A top-level `varip` therefore compiles
with `_var_init_cond` = `(__bar_idx == 0 or __isrealtime)`, which is identical
to `var` in numeric mode. Historically that is reference-correct (`varip`
persists across bars like `var`), but it is silent: numeric mode cannot honor
`varip`'s per-tick persistence, and callers cannot tell the two apart.

Active realtime windows already route to object mode at the host
(`Runtime._run_compiled`) and at `CompiledScript.run`, so numeric realtime is
historical-only. The remaining honest improvement is to stop numeric mode from
compiling `varip` at all: route any script containing `varip` through object
mode, which owns the tick loop and `var`/`varip` rollback.

**Choice:** graceful object-mode routing rather than a hard compile error
(option a) or a numeric tick loop (option b). A hard error would reject valid
historical `varip` scripts and would break the host's realtime re-emit path
before it can choose object mode. A numeric tick loop is a much larger slice.
Object mode is the only host that can honor `varip` semantics today; routing to
it removes the silent numeric `varip`-as-`var` path without changing results.

## Change

`compiler.py` `visit_Script`: after body generation, if `self.varip_vars` is
non-empty, set `self.object_mode = True` before the numeric/object emit choice.
UDF `varip` already forced object mode; this closes the top-level case. Non-
`varip` numeric scripts remain on the njit path.

## Acceptance criteria

1. A script containing top-level `varip` compiles with `object_mode=True` and
   emits the object-mode tick loop, not `@numba.njit`.
2. Historical `varip` series still match interpret (`varip` persists across
   bars; `vip == n` for n bars).
3. Realtime `varip` series match interpret (`varip` re-inits per tick; `var`
   commits once on the confirmed tick).
4. Non-`varip` numeric scripts remain numeric (`object_mode=False`, njit).
5. Failing-before test exists and passes after the change.
6. Targeted realtime/numba/color-fold suite and `./scripts/verify.sh` 5/5.

## Failing before

`.oo/plans/pyne-numeric-varip-parity-2026-11-16.failing-before.txt` — 2 failed:
both `test_varip_compiled_run_matches_interpret_realtime` and
`test_varip_forces_object_mode_not_numeric` saw `object_mode=False` for a
`varip` script.

## Results

- Varip tests (`test_compiler_realtime.py -k varip`) — **4 passed**.
- `tests/test_compiler_realtime.py` — **17 passed**.
- Targeted `test_compiler_realtime.py + test_compiler_numba.py +
  test_compiler_color_fold.py` — **234 passed**.
- `tests/test_runtime_package.py` — **16 passed**.
- `./scripts/verify.sh` — **5 passed, 0 skipped**.

## Proof

Card `pyne-numeric-varip-parity-numeri-8745bc87` (HQ board), attached from the
workspace root with `OO_SEAT=oo-spec-2`:

| Proof | Id | Assertion |
| --- | --- | --- |
| named varip contract | `ce23a0f9-1917-4ea5-8440-83912d684928` | 4 varip tests PASSED (object-mode route, historical, realtime, two-RT-bar) |
| targeted suite | `3f7d3016-6a39-43c9-b5d1-b9779c1f727a` | 234 passed |
| `./scripts/verify.sh` | `a3dc0cbc-ce51-4ef9-8a52-c6945356d23e` | all passed, 5 passed / 0 skipped |

SHA-256: compiler `228225e8e5b1e47901516172b29d442a0f2407edfb1bee5f9c9488d25d7c81b1`,
tests `0185618784147f7ec51382976752e41369075efc9420364d85a4b48337691f98`,
docs `6e40a1055bcd0dc2b63cd0c41de8299c3fc8aabeee5613ff8722a6a164f87a2c` /
`5c66d5a0b42dbb47f3a7086acb512b679e70f7cf80ac7ec2c7bfbe5a2a58e68d` /
`31a9f15d3efab68dd62fe1fe63afe435fd9fa76c61ea4f6a5acf04a5f08e8edf`,
patch `6a7910d887c4a6ce3a70c6aecae5aa028686569422056b52e5a10a5c589b4983`.
Verify transcript: `.oo/proof/verify-numeric-varip-2026-11-16.txt`.

## Files

- `src/pynescript/compiler/compiler.py` — route `varip` scripts to object mode.
- `tests/test_compiler_realtime.py` — varip object-mode/historical/realtime
  contract tests.
- `docs/known_divergences.md`, `docs/missing_features.md`,
  `docs/pinescript_implementation_status.md` — numeric historical-only contract
  and varip object-mode routing.
- `.oo/plans/pyne-numeric-varip-parity-2026-11-16.{md,failing-before.txt}`.

## Residual

- UDF `var`/`varip` per-call-site state cloning is the compiler's documented
  design; unchanged by this slice.
- Numeric nopython remains historical-only for non-`varip` scripts (no tick
  loop, no polling). `varip` scripts lose numeric speed by design.
- No commit/push for this slice.
