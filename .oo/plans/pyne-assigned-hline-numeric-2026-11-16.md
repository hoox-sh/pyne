# Assigned `hline` numeric synthesis — first slice

**Date:** 2026-11-16
**Card:** `pyne-numeric-synthesis-for-assig-10a09d47`
**Status:** Working — first slice, no commit/push

## Why / scope

Statement-form `hline(...)` already synthesizes metadata + a numeric series
without object mode. An **assigned** `h = hline(...)` still forced object mode
because the RHS lowers to a drawing handle.

**First slice:** support a top-level assigned hline whose handle is **never
referenced again** (a dead handle). The hline metadata and plot series are
synthesized exactly like statement form; the dead target is set to `np.nan` and
the script stays numeric. Any later read of the handle (`hline.delete(h)`,
`fill(h, …)`, `plot(h)`, rebind) keeps object mode. Non-numeric prices fall back
to object mode. This is the smallest safe subset; expression `fill` and visual
events (`bgcolor`/`plotshape`) remain separate slices.

## Change

- `compiler.py` `_collect_unused_hline_targets`: top-level `h = hline(...)`
  assignments where the target Name occurs only as the assignment target.
- `compiler.py` `_emit_assigned_hline`: visit args with literal-color folding,
  require a proven-numeric price, append the hline plot/event, and emit
  `plot_idx[bar] = price` + `h = np.nan`.
- `compiler.py` `visit_Assign`: use the synthesis only for plain, top-level,
  dead-handle hline assignments while still numeric.
- `tests/test_compiler_numba.py`: dead assigned hline numeric regression and
  handle-use object-mode boundary.
- `tests/test_compiler_engine_r8.py`: keep the object-mode drawings-envelope
  test by making its hline handle used (`hline.delete(h)`).

## Acceptance criteria

1. `h = hline(50, "mid", color=color.red, linestyle=hline.style_dashed)` +
   `plot(close)` compiles `object_mode=False`, njit, no `__drawings`; hline
   series is 50, plot attrs preserve `linestyle`, and series match interpret.
2. Two dead assigned hlines both stay numeric with correct series.
3. Any handle use (`hline.delete(h)`, `fill(h, h, …)`) keeps object mode.
4. Statement hline/fill numeric synthesis and the object-mode drawings envelope
   stay green.
5. Targeted compiler/library suite green; `./scripts/verify.sh` 5/5.

## Failing before

`.oo/plans/pyne-assigned-hline-numeric-2026-11-16.failing-before.txt` — pre-fix
worktree at `a3c73539` + new tests: dead-handle test failed (object mode);
handle-use boundary passed.

## Results

- New assigned-hline tests — **2 passed**.
- `tests/test_compiler_numba.py` — **218 passed**.
- Compiler/library targeted (`tests/test_compiler*.py`,
  `tests/test_library*.py`) — **517 passed**.
- `./scripts/verify.sh` — **5 passed, 0 skipped**, 279.0s fresh run
  (2026-11-17). Transcript
  `.oo/proof/verify-assigned-hline-2026-11-17.txt`, SHA-256
  `8a79dd5ec93ff7a63b452b57d6913cd58a5c5fdd4b53f9799a2681208d083135`.

## Proof

Card `pyne-numeric-synthesis-for-assig-10a09d47` (HQ board), attached from the
workspace root with `OO_SEAT=oo-spec-2`:

| Proof | Id | Assertion |
| --- | --- | --- |
| named assigned-hline tests | `2af582af-a697-4e1c-af33-8f676bd63b8f` | 2 tests PASSED (dead handle numeric, handle use object) |
| named token | `ca34131f-815c-49d8-af02-b1c607b09767` | `ASSIGNED_HLINE_OK dead=1 two=1 handle_use=object` |
| targeted compiler/library | `4fa4daa8-6e73-4449-a5d4-83892506abc2` | 517 passed |
| verify command record | `ec1db7ee-1080-4ae9-b298-07cf94bd8590` | recorded exit 0 |
| verify transcript (2026-11-17) | `cc714f7d-0b93-41a0-8a76-085a5c229e5d` | `.oo/proof/verify-assigned-hline-2026-11-17.txt` (279.0s) |
| verify transcript hash | `d9129814-7b61-4c06-9b15-444ea3521646` | `8a79dd5ec93ff7a63b452b57d6913cd58a5c5fdd4b53f9799a2681208d083135` |

**Proof-integrity note:** the earlier 2026-11-16 transcript artifact
`607c9021-0422-4549-8de0-04bbe0e760eb` / hash
`5e3d19db-2c0d-4be7-b118-319de0999bfc` (`602ed2bf…`) is **superseded**. That
file was rewritten after the proof with byte-identical content, so it cannot
prove an independent run. The 2026-11-17 transcript above is the output of a
fresh `./scripts/verify.sh` run (279.0s) and is the current evidence.

SHA-256: compiler `56cd064ba843b9e08a87c4c27d3c6d8b15362b1632319cb1b604644b3e8260b5`,
tests `16c69c06b133a15b65d806d647e600833785a1c6ce8a7640020022665f28a4af`,
engine_r8 `994cca2e4d7c4a2ec93bdbab649be3aa3743854128bdda224895da6a23f64e79`,
patch `ee5adcc4af82d8adfadb8bb6db1bfd5e2bf793da8de0c2ed914a20ec2a647c9f`.

## Files

- `src/pynescript/compiler/compiler.py`
- `tests/test_compiler_numba.py`
- `tests/test_compiler_engine_r8.py`
- `.oo/plans/pyne-assigned-hline-numeric-2026-11-16.{md,failing-before.txt,proof.py}`

## Residual

- Assigned hline inside conditionals/functions, handle property reads, and
  expression `fill` remain object mode.
- `bgcolor` / `plotshape` visual-event synthesis remains object mode (separate
  slices).
- No commit/push for this slice.
