# PYNE library methods/UDTs — slice 1: scalar-receiver methods

- **Date:** 2026-11-15
- **Seat:** `oo-spec-2` (Engineering)
- **Card:** `PYNE: inline exported library methods and UDTs on compile (currently fail closed)`
- **Status:** implementation slice in progress; no commit/push.

## Why this slice

The previous slice inlines exported pure free functions and fails closed for
methods/UDTs. The smallest next capability is an **exported method on a
built-in scalar receiver** (`float`, `int`, `bool`, `color`, `string`). The
existing UDF/method emitter can emit these directly; a consumer call
`lib.scale(close, 2.0)` maps to the inlined method with the receiver as the first
argument.

UDT-receiver methods require inlining type declarations, constructors, and
method dispatch; they stay fail-closed for this slice.

## Acceptance criteria

1. A library exporting
   `export method scale(float this, float factor) => this * factor`
   compiles and runs: `lib.scale(close, 2.0)` → `201.0, 203.0, 205.0, 207.0`.
2. Scalar receiver tags `float`, `int`, `bool`, `color`, `string` (including
   `simple`/`series` qualifiers) are inlined.
3. UDT-receiver methods are skipped and remain fail-closed if called, with a
   clear compile error pointing to interpret/auto.
4. A library exporting both a scalar-receiver and UDT-receiver method with the
   same name fails closed as an unsupported overload (no scalar method wins).
5. Existing free-function inlining, alias-before-builtin resolution, and
   no-library stub behavior remain unchanged.
6. Targeted library/compiler suites stay green.

## Out of scope

- Library-exported UDT types, constructors, and UDT-receiver methods.
- Library-to-library calls.
- `ta.*` inside library bodies, keyword args, overloaded library functions.
- Library IR caching.

## Implementation sketch

- In `visit_Import`, allow exported `method` functions whose first formal type
  tag is a scalar receiver; skip UDT receivers.
- Reuse the existing mangled-name emission and `(alias, name)` mapping; the
  consumer’s `lib.name(receiver, ...)` becomes a direct inlined call.
- Keep the existing body validator and fail-closed errors for unsupported
  constructs.

## Proof plan

- Failing-before: `lib.scale(close, 2.0)` returned
  `unsupported library method lib.scale`.
- After: `201.0, 203.0, 205.0, 207.0`; UDT method still fails closed.
- Named `oo proof attach --expect` assertion plus targeted pytest counts.

## Implementation

- `compiler.py:1106-1112` — exported `method` functions with scalar receiver
  tags are accepted; UDT receivers are skipped and remain unmapped.
- Existing mangled emission and `(alias, name)` mapping are reused; consumer
  `lib.scale(close, 2.0)` becomes a direct inlined call with the receiver as
  first argument.
- Existing body validator and fail-closed errors are unchanged.

## Failing-before evidence

```text
mode=compile, libraries=[Lib scale(float)]
  -> error_kind=compile
  -> "unsupported library method lib.scale; use mode=interpret or auto"
```

## After evidence

```text
lib.scale(close, 2.0) -> 201.0, 203.0, 205.0, 207.0
UDT receiver method   -> error_kind=compile, unsupported library method
```

- New tests: `tests/test_compiler_library_inline.py` — **12 passed**.
- Targeted library/compiler suite — **290 passed**.
- Proof output:
  `LIBRARY_INLINE_OK sum=101.5 reuse=1 same_name=1 const=1 internal=1 plot_collision=1 alert_collision=1 method=201.0 udt_method=1 overload=1 unsupported=1 no_lib=1`.

## Proof

- `.openorchestrate/plans/pyne-library-inline-2026-11-15.proof.py` (extended)
- `oo proof attach --expect "LIBRARY_INLINE_OK ... method=201.0 udt_method=1 overload=1 ..."`
- Proof records are attached to the card; the plan artifact proof is re-attached
  after this final edit so it pins the current content.

## Checker condition: same-name scalar + UDT method

`compiler.py:1106-1140` now tracks skipped UDT method names alongside accepted
scalar methods. If a name appears in both sets, or a skipped method precedes a
same-name scalar method, the import fails closed with
`overloaded library method/function <name> is not supported`. Regression:
`test_scalar_and_udt_method_overload_fails_closed` (`overload=1`).

**Minor, not implemented:** a scalar method called with a UDT/string receiver
can still return silent `[None…]` because the compiler does not type-check UDF
arguments generally. That is a separate type-checking slice.
