# Numeric-condition `plotshape` synthesis — statement form + constant metadata

**Date:** 2026-11-17
**Card:** `pyne-plotshape-constant-conditio-9d93e431`
**Status:** Ready for Review — numeric synthesis, no commit/push

## Why / scope

`plotshape` forced object mode for every call because `_DRAWING_FUNCS` sends it
straight to the drawing-event list. The common corpus shape is a statement-form
call with a numeric/bool condition and constant visual metadata:

```pine
plotshape(close > open, title="bull", style=shape.triangleup, location=location.belowbar, color=color.green)
```

**This slice** keeps that shape on the nopython path. The compiler emits a
numeric `1.0`/`0.0` marker series and records the visual metadata in
`plot_attrs`; the host maps `1.0 → True`, `0.0 → None` and stamps the meta, so
the series key/value contract matches interpret.

**Supported:** statement-form call (`_stmt_expr`), proven-numeric condition
(including ternary numeric expressions and bool series), literal title, constant
`style` / `location` / `color` / `text` / `size` / `display`, and foldable
`offset` / `editable` / `show_last`.

**Out of scope — stays object mode:** dynamic color (`color.from_gradient`,
per-bar color ternary), dynamic style, dynamic title/text/size/display,
assigned handles (`p = plotshape(...)`), calls inside functions. `plotchar`,
`plotarrow`, and `barcolor` are untouched.

## Change

- `compiler.py`
  - `plotshape` joins the `_fold_literal_color` context, so constant
    `color.green` / `color.new(...)` / hex fold to wire strings instead of the
    `pine_color_new(...)` runtime helper.
  - `_emit_numeric_plotshape` is called from `visit_Call` before the
    `_DRAWING_FUNCS` block, next to the existing `bgcolor` hook.
  - The emitter validates the condition with `_is_safe_numeric_expr` /
    `_is_numeric_or_bool_literal`, resolves kwargs before positional slots
    (`series`, `title`, `style`, `location`, `color`, `text`, `size`), and fails
    closed on any dynamic wire attr instead of emitting disagreeing metadata.
  - `_PLOTSHAPE_SIZE_VALUES` restores interpret's integer wire values
    (`tiny=8`, `small=10`, `normal=12`, `large=16`, `huge=20`, `auto="auto"`).
    `size` / `text_size` are explicit attrs because they are not in
    `_PLOT_ATTR_SPECS`.
  - Emits `numba_store(plot_N, __bar_idx, (1.0 if pine_bool(cond) else 0.0))`
    and queues a `plotshape` event so a mixed script that later flips object
    mode keeps the series key.
- `engine.py`
  - `_apply_plotshape_series` maps numeric `1.0`/`0.0` arrays to `True`/`None`
    object arrays (the interpret contract).
  - The mixed-mode duplicate-key drop now covers `plotshape` as well as
    `bgcolor` when an object-mode drawing event carries the same title.
  - `_DISK_META_VERSION` **61 → 62** (codegen semantics changed; invalidates
    disk IR keyed by source hash).
  - Meta path verified end to end: `_stamp_compile_plot_kinds` +
    `_stamp_compile_plot_attrs` overlay `style` / `location` / `color` /
    `text` / `size` / `text_size` onto `plot_meta`; no new stamper was needed.
- Tests
  - `tests/test_compiler_plotshape_numeric.py` — 12 tests: 7 numeric-positive
    (compile↔interpret series + meta parity) and 5 object-mode boundaries.
  - `tests/test_compiler_numba.py::test_plotshape_enum_string_constants`
    updated to assert folded attrs on the numeric path instead of object-mode
    drawing strings.
  - `tests/test_bgcolor_plotshape_export.py::test_drawing_registry_merge_visual_series_wrapper`
    and `tests/test_compiler_objects.py::test_plotshape_and_fill_recorded` force
    object mode so the drawing-event helpers remain covered.
  - `.prettierignore` ignores `.oo/` in addition to `.openorchestrate/`
    (OpenOrchestrate state is already gitignored, not source).

## Acceptance criteria

1. `plotshape(close > open, title="bull", style=shape.triangleup, location=location.belowbar, color=color.green)`
   compiles `object_mode=False`, keeps `@numba.njit`, and emits no
   `__drawings`; series `bull` matches interpret (`True, None, …`).
2. `plotshape(true, title="mark")` stays numeric and is all `True`.
3. `plotshape(series=longSignal, …)` resolves the keyword condition.
4. Constant `color.new(color.green, 0)` folds to
   `rgba(34, 171, 148, 1.0)`; no `pine_color_new(` in generated code.
5. Ternary numeric condition `close > open ? close : na` maps the `na` branch
   to `None`.
6. `text="BUY"` / `size=size.small` meta matches interpret: `text="BUY"`,
   `size=10`, `text_size=10`.
7. Positional title/style/location/color slots stay numeric with parity.
8. Dynamic gradient color, dynamic color ternary, dynamic style, dynamic
   title, and assigned handle stay object.
9. Targeted suites green; full suite green; `./scripts/verify.sh` 5/5.

## Failing before

`.oo/plans/pyne-plotshape-numeric-2026-11-17.failing-before.txt` — HEAD
`0968048c` plus the 12-test file: **7 failed, 5 passed** (all seven numeric
positives forced object mode; the five boundaries were already correct).
sha256 `a82a27d269112639612d2d038133a59539f5692030b403faffdbd87eebb7e10a`.

## Results

- `tests/test_compiler_plotshape_numeric.py` — **12 passed** (was 7 failed /
  5 passed).
- Targeted set (`test_compiler_plotshape_numeric.py`,
  `test_compiler_objects.py`, `test_compiler_numba.py`,
  `test_bgcolor_plotshape_export.py`, `test_p1p_c_plot_parity.py`) —
  **284 passed, 4 skipped**.
- Full suite (`pytest -x -q`) — **5397 passed, 14 skipped, 1 xfailed**.
- `./scripts/verify.sh` — **5 passed, 0 skipped, exit 0** (Tests 291.6s).
  Transcript `.oo/proof/verify-plotshape-2026-11-17.txt`, sha256
  `4d2d33b07fac40c0d6b27ee692e6981351447edd176f928bc399c19854152fd4`.
- Independent proof script `.oo/plans/pyne-plotshape-numeric-2026-11-17.proof.py`
  — 7 positive + 5 boundary cases pass, token
  `PLOTSHAPE_NUMERIC_OK positives=7 boundaries=5`. Output:
  `.oo/proof/plotshape-numeric-proof-2026-11-17.txt`.

## Files

- `src/pynescript/compiler/compiler.py`
- `src/pynescript/compiler/engine.py`
- `tests/test_compiler_plotshape_numeric.py` (new)
- `tests/test_compiler_numba.py`
- `tests/test_bgcolor_plotshape_export.py`
- `tests/test_compiler_objects.py`
- `.prettierignore`
- `.oo/plans/pyne-plotshape-numeric-2026-11-17.{md,failing-before.txt,proof.py}`
- `.oo/proof/verify-plotshape-2026-11-17.txt`
- `.oo/proof/plotshape-numeric-proof-2026-11-17.txt`

## Residual

- Of the ~359 corpus scripts blocked by `plotshape`, only those with a
  statement-form call, a proven-numeric condition, and fully constant visual
  metadata unlock. Dynamic metadata, assigned handles, and calls inside
  functions stay object.
- `plotchar`, `plotarrow`, and `barcolor` are untouched.
- `size` / `text_size` are explicit attrs; a future cleanup could add them to
  `_PLOT_ATTR_SPECS` if other visual kinds need the same treatment.
- No corpus scan was run in this slice; the ~359 number is the card estimate,
  not a re-measured count.
- No commit/push for this slice. Worktree
  `/mnt/data/home/jango/Git/pyne-plotshape-wt` at `0968048c` (detached), left
  uncommitted for review.
