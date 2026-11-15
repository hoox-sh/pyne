# PYNE library UDTs — slice 1: exported type + constructor + UDT-receiver method

- **Date:** 2026-11-15
- **Seat:** `oo-spec-2` (Engineering)
- **Card:** `PYNE: inline library-exported UDT types, constructors and UDT-receiver methods on compile`
- **Status:** implementation slice; no commit/push.

## Slice choice and why

Include **all three** in one slice: exported `type`, its constructor, and
methods whose receiver is that type.

Reason: once the type is registered, the method path is the existing
`visit_FunctionDef` receiver-dispatch machinery (the same one that already
handles script-local `method` on UDTs). Splitting methods into a second slice
would duplicate the import-time plumbing without reducing risk. Constructor
support alone would also leave `b.bump()` silently `None`, which is worse than
fail-closed.

Current state (measured, see Failing-before):

- `lib.Box.new(...)` on compile does **not** fail closed — it silently emits
  `None` series because the call falls through the unknown-method branch.
- `b.bump()` on a library instance is likewise silent `None`.
- Only the alias form `lib.bump(x)` fails closed ("unsupported library
  method"), because `library_methods` has no entry.

Script-local `type Box` + `Box.new()` + `method bump(Box this)` already compiles
and runs correctly, so this slice is library wiring, not new UDT semantics.

## Acceptance criteria

1. Library exporting `type Box` with scalar fields plus
   `export method bump(Box this) => this.v + 1`:
   `b = lib.Box.new(close)`, `plot(b.v, "v")` →
   `100.5, 101.5, 102.5, 103.5`; `plot(b.bump(), "b")` →
   `101.5, 102.5, 103.5, 104.5`. Compile output equals interpret output.
2. Alias form `lib.bump(b)` inlines to the same function (Pine allows both
   `instance.method()` and `lib.method(instance)`).
3. Field defaults declared in the exported type are honored when the
   constructor omits the argument.
4. A library type with a non-scalar field (UDT/array/map field) is **not**
   registered; calling its constructor fails closed with a compile error that
   names the type and points to `interpret`/`auto` — no silent `None`.
5. A script-declared `type` with the same name as an imported library type
   fails closed with a clear compile error instead of silently merging the two.
6. A library UDT method whose body is outside the inline allowlist (library
   constant, internal call) fails closed at import.
7. A library UDT method called with a non-UDT receiver fails closed (both
   `lib.bump(close)` and `close.bump()`), no silent na. General UDF argument
   type checking stays out of scope; this guard is library-method only.
8. Existing behavior unchanged: free-function inlining, scalar-receiver
   methods, same-name scalar+UDT overload fail-closed, parse-cache deep copy,
   alias-before-builtin resolution, no-library stub, nopython recovery.
9. Targeted library/compiler suites stay green; `scripts/verify.sh` passes.

## Out of scope (documented, still fail closed)

- UDT fields that reference another UDT, array, map, or matrix.
- Coexistence of a library type and a same-named script type (fail closed).
- Same-name overloads among two library UDT methods (fail closed).
- `Type.copy`, exported enums, library-to-library calls.
- General UDF argument type checking (pre-existing limitation, unchanged).

## Implementation sketch

- `compiler.py:visit_Import`
  - collect exported `TypeDef` nodes alongside exported functions;
  - validate fields: scalar type tags only, literal/`na` defaults only;
  - register accepted types with `visit_TypeDef`; map `(alias, Type) → Type`;
  - record rejected types with a reason for fail-closed constructor errors;
  - accept `method` whose receiver is a registered library type;
  - emit UDT methods under their **Pine name** (receiver-type dispatch needs
    `b.bump()` to resolve by `udt_var_types`); free functions stay mangled.
- `_library_type_name()` helper shared by `_looks_like_udt_ctor`,
  `_infer_udt_type`, `_type_spec_name` and `visit_Call`.
- `visit_TypeDef`: collision guard against imported library type names.
- `visit_Call`: constructor branch for `alias.Type.new(...)`; fail-closed
  branches for rejected types and rejected/skipped library methods.
- Library-method receiver guard: compare the declared receiver tag with the
  inferred argument/receiver tag; mismatch → `library_inline_error`.

## Proof plan

- Failing-before: compile of the fixture returns `None` series (silent na);
  alias-form UDT method returns `unsupported library method`.
- After: compile series equal interpret series for ctor, field, and method;
  fail-closed cases return `error_kind=compile` with specific messages.
- Proof script prints one `LIBRARY_UDT_OK ...` token per criterion; attached
  with a named `--expect` assertion.
- Targeted pytest counts recorded below.

## Results

### Failing-before (HEAD `7d22dced` compiler, final 20-test file)

```text
9 failed, 11 passed
FAILED test_library_udt_type_constructor_and_method_inline
FAILED test_library_udt_method_alias_form_inlines
FAILED test_library_udt_typed_declaration_and_udt_param_inline
FAILED test_library_udt_color_field_variable_is_not_stringy
FAILED test_library_udt_method_named_like_builtin_dispatches
FAILED test_library_udt_with_udt_field_fails_closed
FAILED test_script_type_colliding_with_library_type_fails_closed
FAILED test_library_udt_method_unsupported_body_fails_closed
FAILED test_library_udt_method_wrong_receiver_fails_closed
```

Full transcript: `pyne-library-udt-inline-2026-11-15.failing-before.txt`
(run against a copy of `src/` with HEAD's `compiler.py`; working tree untouched).
Part A of the transcript is the 18-test subset — **7 failed / 11 passed**,
matching checker proof `f6f82599`; Part B is the full final 20-test file —
**9 failed / 11 passed**.

Before: `b = lib.Box.new(close)` and `b.bump()` compiled to `None` series —
silent na, not even fail-closed. Only the alias form `lib.bump(x)` raised
`unsupported library method`.

### After

- `tests/test_compiler_library_inline.py` — **20 passed**.
- Targeted library/UDT/compiler suites — **128 passed**:
  `test_compiler_library_inline`, `test_compiler_library_fail_closed`,
  `test_library_export_import`, `test_library_export_method`,
  `test_udt_types`, `test_udt_methods`, `test_udt_instantiation`,
  `test_compiler_method_return_types`, `test_compiler_switch_udt_coverage`,
  `test_set06_udt_switch_drawing`.
- Full `tests/test_compiler_*.py` — **452 passed**.
- `scripts/verify.sh` — **PASS** (transcript `…verify.txt`).
- Previous slice proof still green:
  `LIBRARY_INLINE_OK … method=201.0 udt_method=1 overload=1 …`.
- First full compiler run caught a fall-through in the new constructor branch
  (`chart.point.new` hit the branch without a mapping and left `func_name`
  unbound). Fixed by requiring a known `(alias, type)` pair in the branch
  condition; rerun is clean. Recorded here so the guard is not mistaken for
  defensive noise.

## Checker conditions (round 2)

- **C1 — stale failing-before.** Re-ran the final 20-test file against pristine
  HEAD `7d22dced`; replaced the transcript. Count is 9 failed / 11 passed for
  the final file; the original 18-test subset is 7 failed / 11 passed
  (checker `f6f82599`). The omitted `test_library_udt_typed_declaration_and_udt_param_inline`
  is now in the transcript and fails before the fix.
- **C2 — plan artifact predates final edit.** Plan is re-attached after this
  edit and a hash proof pins the current sha256 (see board proof cell).
- **C3 — color-field UDT misclassified as string.** `visit_Assign` ran the
  stringy-RHS detection before the UDT branch; a visited UDT dict containing a
  quoted color hex marked the variable `string`, so `x.col()` failed the
  receiver guard. Fixed with `is_udt_handle_rhs` (ctor/copy) taking precedence
  over stringy detection. Regression:
  `test_library_udt_color_field_variable_is_not_stringy`.
- **C4 — builtin-named UDT method hijacked.** `b.plot()` reached builtin
  `plot` lowering because `func_name == "plot"` is checked after the method
  branch. Fixed by dispatching instance-form UDF/UDT methods
  (`method_src is not None and func_name in user_funcs`) before builtin
  lowering. Regression: `test_library_udt_method_named_like_builtin_dispatches`
  (instance + alias form). Interpret mode still has a separate builtin-name
  collision for this fixture; compile is the card's scope and now matches the
  method semantics.

## Documented minors (no behavior change in this slice)

- **(a) Library free function constructing a UDT** (`export make(float v) => Box.new(v)`)
  fails closed with `calls unsupported namespace Box`. Allowing `Type.new` in
  `_library_function_unsupported` is a follow-up; interpret/auto works.
- **(b) Color field default written as `color.red`** is rejected as a
  non-literal default (`_library_default_literal` accepts constants and `na`).
  Scalar color fields without defaults are supported (C3 test).
- **(c) Extra constructor arguments** beyond the declared field count are
  ignored, matching the existing script-UDT `Type.new` behavior. No arity guard
  in this slice.


### Proof

```text
LIBRARY_UDT_OK ctor=1 field=100.5 default=2.0 method=101.5 alias=101.5 nested=1 collision=1 body=1 receiver=1 color=101.5 builtin_name=101.5 free=101.5 scalar_method=201.0 overload=1 parse_cache=1 no_lib=1
```

### Files

- `src/pynescript/compiler/compiler.py` — import-time type registration,
  constructor resolution, UDT-method emission, receiver guards, collision
  guards.
- `tests/test_compiler_library_inline.py` — 9 new tests (20 total).
- `.openorchestrate/plans/pyne-library-udt-inline-2026-11-15.md` (this file),
  `.proof.py`, `.failing-before.txt`, `.verify.txt`.
