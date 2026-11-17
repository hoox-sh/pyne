# Numeric-condition `bgcolor` synthesis — numeric + positional-title parity

**Date:** 2026-11-17
**Card:** `pyne-constant-condition-bgcolor--8074788e`
**Status:** Ready for Review — numeric synthesis + positional-title parity, no commit/push

## Why / scope

`bgcolor` forced object mode because its series is color strings/None. The
common corpus shape is a ternary color expression with a numeric condition and
constant color / `na` branches:

```pine
bgcolor(close > open ? color.green : na, title="up")
```

**First slice:** support every *constant* color form — direct constant color,
`color.new(base, transp)` with constant args, hex literal, `na` — and numeric
conditions, including the `barstate.*` flags. The compiler emits a numeric
**0/1 code series** and records the true/false colors in `plot_attrs`; the host
maps codes back to color strings/None. Dynamic color expressions keep object
mode.

### Finding that shaped the slice

The first implementation only accepted `color.red`-style attributes, so
`color.new(color.red, 90)` — the form used by **every** corpus script where
`bgcolor` is the sole object-mode blocker — still fell to object mode. Measured
on set01–set04 (the card's 354 scripts): **0 unlocked**.

Root cause: `visit_Call` set `_fold_literal_color` from the *current* call name
only, so the nested `color.new` call inside a `bgcolor` argument restored the
flag to `False` and forced object mode during argument collection. Fixing that
required two more guards:

- `_is_safe_numeric_expr` rejected the injected `barstate` bool locals
  (`__isrealtime` / `__isconfirmed` / `__ishistory` / `__isnew`), so
  `barstate.isrealtime ? color.new(...) : na` stayed object.
- A dynamic color branch would have folded to `None` and silently produced an
  all-`na` series. `_bgcolor_branch_color` now returns `(supported, color)` and
  only `na` may legitimately have no color.

## Change

- `compiler.py`
  - `bgcolor` joins `plot`/`fill`/`hline` in the `_fold_literal_color` context,
    so constant `color.new` / hex / keyword colors fold instead of setting
    object mode.
  - `_emit_numeric_bgcolor` accepts `ast.Call` (color constructors),
    `ast.Constant` with `kind == "#"`, and bare `na`; ternary branches go
    through `_bgcolor_branch_color`.
  - `_is_safe_numeric_expr` whitelists the four injected `barstate` bools.
  - Positional title is string-only: `args[1]` becomes the title only when
    `_is_quoted_string_expr` is true. A numeric offset (`0`, `5`, `true`) is
    never a title, and the v5 5th positional title is ignored because interpret
    ignores it. This matches interpret for the two blocker calls.
- `runtime/evaluator.py` and `ast/evaluator/builtins/plotting.py`: the
  interpret title is keyword-first and accepts the 2nd positional only when the
  runtime value is a `str`. Numeric offsets no longer leak into the series key,
  so compile and interpret agree on positional titles.
- `engine.py`: `_apply_bgcolor_series` maps 0/1 code arrays to color/None using
  plot attrs; duplicate numeric bgcolor plot keys are dropped when an
  object-mode drawing event carries the same title; disk IR cache v61 (invalidates
  pre-title-fix v60 modules keyed by source hash alone).
- `tests/test_compiler_numba.py`: 9 bgcolor tests (6 numeric forms + 2 dynamic
  boundaries + positional-title parity), each assertion named.
- `tests/test_p1p_c_plot_parity.py`: the `bgcolor(color.new(...))` assertion now
  pins the folded rgba literal instead of the `pine_color_new` runtime helper.

## Acceptance criteria

1. `bgcolor(close > 100.5 ? color.green : na, title="up")` + `plot(close)`
   compiles `object_mode=False`, njit, no `__drawings`; series `up` matches
   interpret (`None`, `#22AB94`, …).
2. `bgcolor(color.red)` and `bgcolor(#ff0000)` stay numeric.
3. `bgcolor(color.new(color.red, 90))` stays numeric and yields
   `rgba(242, 54, 69, 0.09803921568627451)` — identical to interpret.
4. `bgcolor(cond ? color.new(c, n) : na)` and the `barstate.isrealtime` variant
   stay numeric with interpret parity.
5. `color.from_gradient(...)`, dynamic `color.new` base, and dynamic `transp`
   stay object.
6. Corpus: set01–set04 bgcolor scripts numeric **0 → 10**, no regression to
   object, no new emit errors.
7. Positional-title parity: `bgcolor(color.red, 0, true, 10, "mytitle")` and
   `bgcolor(color.red, 0, true, 10)` both key `bgcolor` in compile and
   interpret; `bgcolor(color.red, "second")` keys `second` on both; numeric
   offsets (`0`, `5`, `true`) never become keys.
8. Targeted compiler/library suite green; `./scripts/verify.sh` 5/5.

## Failing before

`.oo/plans/pyne-bgcolor-numeric-2026-11-17.failing-before.txt` — pre-fix
worktree `/tmp/opencode/pyne-prefix-bgcolor` at `bc3e3012` + the current test
file: **6 failed, 2 passed** (every constant form object mode; both dynamic
boundaries already correct).

`.oo/proof/bgcolor-2026-11-17/failing-before-positional-title.txt` — same
source minus the title gate: the new parity test fails with compile
`plot_titles == ['0', 'c']` for the 5th-positional-title case. Full before/after
keys for both blocker calls: `positional-before.txt` / `positional-after.txt`.

## Results

- New bgcolor tests — **9 passed** (`pytest tests/test_compiler_numba.py -k bgcolor`).
- Positional-title parity test — **1 passed**; before fix (throwaway worktree,
  same test) **1 failed** with compile `plot_titles == ['0', 'c']`. Both blocker
  calls: compile/interpret keys `0`/`bgcolor` before → `bgcolor`/`bgcolor`
  after; `bgcolor(color.red, 5)` `5`/`5` before → `bgcolor`/`bgcolor` after.
- `tests/test_compiler_numba.py` — **227 passed**.
- Compiler/library targeted (`tests/test_compiler*.py`,
  `tests/test_library*.py`) — **526 passed**.
- Bgcolor/plot-wire regression files (`test_plot_wire_export.py`,
  `test_bgcolor_plotshape_export.py`, `test_p1p_c_plot_parity.py`,
  `test_compiler_color_fold.py`) — **78 passed**.
- Corpus set01–set04 (`bgcolor` scripts): numeric **0 → 10**, object 289 → 279,
  emit errors 65 → 65 (unchanged), regressions to object **0**. Artifacts:
  `.oo/proof/bgcolor-2026-11-17/{scan_set01_04_before.json,
  scan_set01_04_after.json, summary.json}` (summary sha256
  `41aa622d25f127b5046915e877c481210808e519e26f3cf4e1b12be405656dcc`).
- `./scripts/verify.sh` — **5 passed, 0 skipped, exit 0** (Tests 278.7s).
  Fresh transcript: `.oo/proof/verify-bgcolor-positional-2026-11-17.txt`,
  sha256 `825ffc79bef33b98ef8b26f59d387c8fb77417cd080f525cd28bcbe1b7770931`.
  The older `.oo/proof/verify-bgcolor-2026-11-17.txt` is pre-fix and superseded.

## Files

- `src/pynescript/compiler/compiler.py`
- `src/pynescript/compiler/engine.py`
- `src/pynescript/ast/evaluator/builtins/plotting.py`
- `src/pynescript/runtime/evaluator.py`
- `tests/test_compiler_numba.py`
- `tests/test_p1p_c_plot_parity.py`
- `tests/test_bgcolor_plotshape_export.py` (object-mode fixture from the first pass)
- `.oo/plans/pyne-bgcolor-numeric-2026-11-17.{md,failing-before.txt,proof.py}`
- `.oo/proof/bgcolor-2026-11-17/` (corpus scans, positional before/after,
  failing-before transcript, evidence script)
- `.oo/proof/verify-bgcolor-positional-2026-11-17.txt`

## Residual

- Positional-title semantics are intentionally interpret-compatible, not
  Pine-perfect: both paths read a **2nd** positional string as the title and
  ignore the v5 5th positional (`title`), because interpret already did. A
  future fix should move both to Pine's position 5 and drop the 2nd-positional
  alias; until then, a non-string positional is never a title on either path.
- Of the 279 set01–set04 bgcolor scripts still in object mode, only 10 ever had
  `bgcolor` as the sole blocker (all 10 now numeric). The rest are object for
  other reasons — UDTs, drawings, `request.*`, dynamic colors.
- Constant `color.new` inside an **object-mode** script now emits the folded
  rgba literal instead of `pine_color_new(...)`; the event color is unchanged.
- set05/set06 (2315 bgcolor scripts) were not scanned; the set01–set04 method
  in `.oo/proof/bgcolor-2026-11-17/summary.json` applies unchanged.
- `barcolor`, `plotshape`, `plotchar` visual events remain object mode.
- No commit/push for this slice.
