# PYNE nz() numeric-param/local unlock — slice 1: targeted forms

- **Date:** 2026-11-15
- **Seat:** `oo-spec-2` (Engineering)
- **Card:** `PYNE: nz() numeric-param/local unlock (targeted forms; corpus measurement pending)`
- **Status:** implementation slice; no commit/push.

## Slice choice and why

`nz(close)` already stays on the nopython path (`numba_nz`). The object-mode
flip comes from the argument classifier: a bare numeric parameter or a numeric
local is not recognized as safe numeric, so `nz(src)` emits `nz_py(...)` and
sets `object_mode = True`.

The smallest useful slice is to recognize **explicitly numeric params**
(`float` / `int`) and **numeric locals derived from them or from literals**,
then keep `numba_nz` for those. String/UDT/array/map arguments keep the
existing `nz_py` object path. Untyped params and full corpus unlocking are
follow-ups.

## Acceptance criteria

1. `f(float src) => nz(src)` compiles with `object_mode == False` and returns
   the source series (`100.5, 101.5, 102.5, 103.5`).
2. `f(float src) => nz(src, 5.0)` stays numeric; `f(na)` returns `5.0`
   (NaN replacement exercised on the nopython path).
3. `f(float src) => x = src * 2.0; nz(x)` stays numeric and returns
   `201.0, 203.0, 205.0, 207.0`.
4. `nz(close)` remains numeric (regression).
5. `f(string s) => nz(s, "x")` remains object mode with `nz_py` (regression).
6. Values match interpret for the numeric cases.
7. Targeted compiler/library/UDT suites stay green.

## Out of scope (documented)

- **Full-corpus measurement** — targeted forms only; a deterministic 200-file
  sample of the 6,440 corpus files using `nz(` showed 0 object→numeric
  transitions. Follow-up card tracks the full sweep.

- **Untyped params** (type inference) — explicit `float`/`int` only.
- `nz` keyword arguments (`nz(source=…)`).
- `nz` over arrays/maps/UDTs/drawings (still `nz_py`).
- `fixnan` (separate builtin).
- Full-corpus sweep (6,440 files using `nz(`); this slice proves the classifier
  on targeted forms, not a corpus-wide unlock count.

## Implementation sketch

- `_ast_is_numeric(node)` — Constant number, numeric param (`float`/`int`),
  numeric local, chart series, `*_arr` series, UnaryOp/BinOp over those.
- `_is_numeric_nz_arg(node, expr)` — bare numeric name, `_is_safe_numeric_expr`,
  or `_ast_is_numeric`.
- Track `numeric_locals` per function; save/restore in `visit_FunctionDef`;
  update on `Assign` from a numeric RHS.
- `nz` branch: keep `object_mode`/string guards, replace the broad
  `scalar_vars`/safe-numeric test with `_is_numeric_nz_arg` for **both** the
  source and the replacement; emit `numba_nz` only when both are numeric,
  `nz_py` otherwise.
- No new builtin: `numba_nz` / `_numba_nz_jit` already handle NaN + replacement.

## Proof plan

- Failing-before: the three numeric-param/local cases compile with
  `object_mode == True` (`nz_py`).
- After: `object_mode == False` (`numba_nz`), values and NaN replacement
  correct; string/UDT cases unchanged.
- Proof script prints `NZ_NUMERIC_OK ...`; attached with a named `--expect`
  assertion. Targeted pytest counts recorded below.

## Results

### Failing-before (HEAD `7aa5c2b8`)

```text
4 failed, 2 passed
FAILED test_nz_numeric_param_stays_numeric
FAILED test_nz_numeric_param_replacement_handles_nan
FAILED test_nz_numeric_local_from_param_stays_numeric
FAILED test_nz_numeric_param_history_stays_numeric
```

The series and string-param regressions already pass before the change.
Transcript: `pyne-nz-numeric-unlock-2026-11-15.failing-before.txt`.

### After

- `tests/test_compiler_nz_numeric.py` — **9 passed**.
- Targeted library/UDT/compiler suites — **163 passed** (includes
  `test_set06_import_stub_nan.py`).
- Full `tests/test_compiler_*.py` — **483 passed**.
- Proof token:
  `NZ_NUMERIC_OK param=100.5 repl=100.5 nan=5.0 hist=100.5 local=201.0 series=100.5 string=1 str_local=1 str_param=1 num_local_repl=100.5`.
- Corpus note: a deterministic 200-file sample of the 6,440 corpus files that
  use `nz(` showed **0 object→numeric transitions**. Those scripts flip object
  for other constructs (UDTs, arrays, `request.*`), so the sample cannot isolate
  this classifier. The unlock is proven on the targeted forms; a full-corpus
  sweep is a follow-up.

### Replacement classifier (checker round 2)

`nz(src, s)` with a string local/param replacement emitted `numba_nz(src, s)`:
the branch classified the source but only ran `_looks_like_string_expr` on the
replacement, missing bare string locals/params. Fixed by classifying the
replacement with `_is_numeric_nz_arg` plus explicit `string_scalars` /
`string_series` checks. Regressions: string-local and string-param replacement
tests assert `object_mode=True` and `nz_py`; the numeric-local replacement stays
`numba_nz`.

### Regression caught by the full gate

The first full `verify.sh` run caught `test_corpus_3725_import_stub_runs`:
`NameError: type_ is not defined`. `_py_ident()` mutates `ident_map` for
builtin-shadow names, so calling it at the top of `visit_Assign` renamed the
`type` *references* to `type_` while the store stayed `type`. Fixed by tracking
only the Pine name and resolving emitted names through a reverse `ident_map`
check (`_numeric_local_name`). The set06 test is now in the targeted set.

### Files

- `src/pynescript/compiler/compiler.py` — numeric AST classifier, per-function
  numeric locals, `nz` branch uses `numba_nz` for numeric args.
- `tests/test_compiler_nz_numeric.py` — 9 tests.
- `.oo/plans/pyne-nz-numeric-unlock-2026-11-15.md` (this file),
  `.proof.py`, `.failing-before.txt`.
