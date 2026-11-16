# Cross-library UDT constructor + method — first slice

**Date:** 2026-11-16
**Card:** `pyne-cross-library-udts-methods--3fc6cd11`
**Status:** Working — first slice, no commit/push

## Why / scope

Cross-library free functions and methods already inline with collision-free
`__xlib_<n>` aliases. A library A importing B's exported UDT and constructing it
(`b.Box.new(x)`) failed closed as `library function make uses unsupported name b`:
the cross-library alias rewrite only handled one-level `alias.fn(...)`, so the
nested `alias.Type.new(...)` root was left as the local alias and the body guard
rejected it as a free name.

**First slice:** support A importing B's exported UDT type + constructor in A's
exported function, including B's UDT method on the constructed value
(`b.Box.new(x).bump()`), using the existing synthetic `__xlib_<n>` alias scoping.
Cycle safety already comes from `_library_import_stack` and is re-asserted.

**Kept fail-closed:** cross-library UDT type annotations (`b.Box box = ...`),
re-exported aliases, duplicate type names across libraries, and nested
UDT-field types. These need separate alias/type-registration work.

## Change

- `compiler.py` `_rewrite_cross_library_aliases`: rewrite the root `Name` of any
  call's attribute chain, not only one-level `alias.fn(...)`. This covers
  `alias.Type.new(...)` and `alias.Type.method(...)`.
- `compiler.py` `_library_function_unsupported`: add the synthetic
  cross-library aliases (`extra_namespaces`) to `allowed_names`, so the
  rewritten root is not rejected as an unsupported free name.
- `tests/test_compiler_library_inline.py`: A→B constructor+method regression and
  a fail-closed type-annotation scope test.

## Acceptance criteria

1. A imports B's exported `Box`; `b.Box.new(x).v` and
   `b.Box.new(x).bump()` in A's exported functions compile and match interpret.
2. Cross-library cycles still fail closed with `recursive library import`
   (existing regression).
3. Cross-library UDT type annotation stays fail-closed
   (`unsupported name b`, use interpret/auto).
4. Existing single-library UDT/method tests stay green.
5. Targeted compiler/library suite green; `./scripts/verify.sh` 5/5.

## Failing before

`.oo/plans/pyne-cross-library-udts-2026-11-16.failing-before.txt` — pre-fix
worktree at `380b8527` + the new test: compile failed with
`library function make uses unsupported name b`; interpret passed.

## Results

- New cross-library UDT tests — **2 passed**.
- Library suite (inline, fail-closed, export import, export method) — **71
  passed**.
- Compiler/library targeted (`tests/test_compiler*.py`,
  `tests/test_library*.py`) — **509 passed**.
- `./scripts/verify.sh` — **5 passed, 0 skipped** (single final run after the
  cross-library UDT change).

## Proof

Card `pyne-cross-library-udts-methods--3fc6cd11` (HQ board), attached from the
workspace root with `OO_SEAT=oo-spec-2`:

| Proof | Id | Assertion |
| --- | --- | --- |
| named cross-library UDT tests | `07d478e7-bcb4-4f5c-8905-59afc83cbf66` | 3 tests PASSED (constructor/method, annotation fail-closed, cycle fail-closed) |
| named token | `fd4d6970-ec59-4384-822c-d85d8c2b2a23` | `XLIB_UDT_OK ctor=1 method=1 annot=fail_closed cycle=fail_closed` |
| targeted compiler/library | `892bc769-8cb4-45f2-8499-dbc8c8073eb6` | 509 passed |
| verify (no re-run) | `f0558f72-ca93-4d2b-bc71-598d19f481ec` | recorded exit 0 |
| verify transcript | `fb25fc44-bb0c-4c90-86c6-9719df808350` | `.oo/proof/verify-cross-library-udts-2026-11-16.txt` |

SHA-256: compiler `2f0f064e6e5106c9d3e914a0463f8a09cb7eb8d12b19f9d292ec514d309ae813`,
tests `8dc48a2ce104cfe7a7ff9b3daab90da477e18334ecc72aa0eb8b2a8fee5649a0`,
patch `db728d89cac2c89f5e684daaca97b78a242ae85b2f3e8edf39b0c1d04d3b81b0`.

## Files

- `src/pynescript/compiler/compiler.py`
- `tests/test_compiler_library_inline.py`
- `.oo/plans/pyne-cross-library-udts-2026-11-16.{md,failing-before.txt,proof.py}`

## Residual

- Cross-library UDT type annotations, re-exported aliases, duplicate type names
  across libraries, and nested UDT-field types remain fail-closed.
- No commit/push for this slice.
