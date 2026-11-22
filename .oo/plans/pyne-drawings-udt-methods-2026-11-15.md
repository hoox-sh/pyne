# PYNE drawings / UDT / methods — slice 1: UDT-returning call receiver types

- **Date:** 2026-11-15
- **Seat:** `oo-spec-2` (Engineering)
- **Card:** `PYNE: drawings, UDT and method corners — gap inventory + implementation`
- **Status:** slice 1 implemented and proven; no commit/push; awaiting gate.

## Why this slice

The #1 inventory ranked three correctness gaps:

1. Library/exported methods are not executed on compile; imported library
   method calls are stubbed to `np.nan`/`None`, so explicit compile can silently
   return `na`.
2. UDT/method overload dispatch is heuristic and can silently pick the wrong
   implementation.
3. Drawing state rollback on unconfirmed realtime ticks is incomplete.

This slice takes the smallest concrete wrong-result case in (2): a UDF that
returns a UDT loses its receiver type at the call site, so a same-arity method
overload falls back to the last definition. Repro before the fix:

```pine
type A
    float v
type B
    float v
method tag(B this) => 200.0
method tag(A this) => 100.0
makeB() => B.new(0.0)
plot(makeB().tag())   // lowered to tag__1_A(makeB()) -> 100.0
```

Library execution (gap 1) is a larger feature; drawing rollback (gap 3) needs a
different reproduction. This slice removes a silent wrong-method result with a
small, local type-metadata addition.

## Acceptance criteria

1. A UDF whose body returns `Type.new(...)` records its UDT return type.
2. `_receiver_type_from_expr` uses that return type for a call expression, so
   `makeB().tag()` dispatches to `B.tag` (200.0), not the last same-arity
   overload (`A.tag`, 100.0).
3. If the same UDF name maps to more than one UDT return type (ambiguous
   overloads), **or a non-UDT overload shares the Pine name**, inference returns
   `None` and existing fallback behavior is unchanged.
4. Existing UDT/method overload suites stay green.
5. Failing-before test is added and passes after the change.

## Out of scope

- Executing imported library methods (gap 1).
- Inferring receiver types from array/map elements or arbitrary chained calls.
- Drawing realtime rollback (gap 3).

## Implementation sketch

- Track `func_return_udt_types: dict[str, set[str]]` keyed by the **emitted**
  function name only. Populate when `_func_body_returns_udt(last_ast)` is true
  and `_infer_udt_type(last_ast)` yields a type. Keying by the Pine name would
  let a UDT overload poison a same-name non-UDT call.
- In `_receiver_type_from_expr`, match a call expression and return the single
  recorded UDT type; return `None` when the set has 0 or >1 types.

## Proof plan

- Failing-before test: `makeB().tag()` returns 100.0 and lowers to
  `tag__1_A(makeB())`.
- After: returns 200.0 and lowers to `tag__1_B(makeB())`.
- Targeted UDT/method overload suites + `oo proof attach --expect` assertion.

## Implementation

- `compiler.py:695` — `func_return_udt_types: dict[str, set[str]]`.
- `compiler.py:9763-9768` — when a UDF body returns a UDT, infer the type from
  the last expression (`_infer_udt_type`) and record it under the emitted
  function name only.
- `compiler.py:7362-7366` — `_receiver_type_from_expr` recognizes a call
  expression and returns the recorded UDT type only when exactly one type is
  associated with that name; ambiguous names stay uninferred.

## Failing-before evidence

```text
plot(makeB().tag())  ->  safe_float(tag__1_A(makeB()))  ->  100.0
plot(pick(1.0).tag()) ->  safe_float(tag__1_A(pick(1.0))) -> 100.0
```

`makeB()` returns `B`, but the same-arity fallback picked the last definition
(`A.tag`). The mixed-overload case is the regression guard: `pick(float)` is
non-UDT and must not inherit `B` from `pick(int)`.

## After evidence

```text
plot(makeB().tag())   ->  safe_float(tag(makeB()))          -> 200.0
plot(pick(1.0).tag()) ->  safe_float(tag__1_A(pick(1.0)))   -> 100.0
```

- New tests: `tests/test_compiler_method_return_types.py` — **2 passed**.
- UDT/method targeted suite (`test_compiler_method_return_types.py`,
  `test_set06_method_overloads.py`, `test_udt_methods.py`,
  `test_set06_color_overload.py`, `test_compiler_switch_udt_coverage.py`) —
  **52 passed**.

## Proof

- `.oo/plans/pyne-drawings-udt-methods-2026-11-15.proof.py`
- `oo proof attach --expect "UDT_RETURN_DISPATCH_OK tag=200.0 wrong=0 mixed=100.0"`
- Proof records are attached to the card; the plan artifact proof is re-attached
  after this final edit so it pins the current content.
