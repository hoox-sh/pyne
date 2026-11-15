# PYNE nested realtime rollback — slice 1: Map values

- **Date:** 2026-11-15
- **Seat:** `oo-spec-2` (Engineering)
- **Card:** `PYNE: deepen interpret realtime rollback for nested Matrix/Map/UDT containers (one-level copy leaks mutations)`
- **Status:** implementation slice; no commit/push.

## Slice choice and why

The realtime snapshot stores a shallow `dict.copy()` for `Map` contents
(`map.py:copy_contents`). Nested values — a map, list/array, Matrix or UDT stored
as a map value — stay shared with the snapshot, so mutations on an unconfirmed
tick leak into the next tick.

**Map** is the right first slice: it is the container that owns arbitrary nested
values, and its `copy_contents`/`restore_contents` pair is the exact rollback
hook. Matrix already copies its row lists; UDT fields are shallow but scalar
field rollback is covered by existing tests. Fixing Map recursively also covers
Matrix/UDT values nested inside a map.

## Acceptance criteria

1. A nested **map** value inside a `var` map: mutating it on unconfirmed ticks
   rolls back; the confirmed tick commits. Interpret final value `1.0`, matching
   compile (`3.0` before the fix).
2. A nested **list/array** value: interpret == compile ==
   `[1, 1, 1, 1, 2]` (before: interpret `4`).
3. A nested **Matrix** value: interpret final value `1.0` (before `3.0`).
   Compile mode has a pre-existing nested-Matrix gap, out of scope.
4. Scalar `map.put` rollback and UDT scalar-field rollback are unchanged
   (existing tests).
5. Snapshot/restore preserves nested identity when the live nested object
   still exists (restore writes into it rather than replacing it).
6. Existing `tests/test_realtime_rollback.py` and targeted suites stay green.

## Out of scope (documented)

- Nested **UDT** test: the same recursive path handles UDT `fields`, but the
  UDT slice owns its dedicated coverage.
- Top-level lists/dicts deeper than the host's one extra level
  (`_copy_list_dict_level`) — separate host slice.
- Compile-mode nested Matrix/UDT map-value gaps (pre-existing; interpret is
  the card's scope).
- Two map keys aliasing the same nested object may split into separate restored
  objects; correctness of values is preserved.

## Implementation sketch

- `map.py`: module-level `_snapshot_value(value)` builds a recursive node:
  `("list", [...])`, `("dict", {...})`, `("typed", copy_contents())` for
  Map/Matrix, `("udt", {field: node})`, `("value", scalar)`.
- `_restore_value(current, node)` writes back in place: lists/dicts are cleared
  and refilled, typed containers call `restore_contents`, UDT fields are
  refilled; scalars are returned.
- `Map.copy_contents` returns `_snapshot_value(self.data)`;
  `Map.restore_contents` calls `_restore_value(self.data, snap)`.
- The host already treats `copy_contents`/`restore_contents` as the typed
  container contract; no host change needed.

## Proof plan

- Failing-before: nested map interpret `3.0` vs compile `1.0`; nested list
  interpret `4` vs compile `2`.
- After: interpret == compile for map/list; nested Matrix interpret `1.0`.
- Proof script prints `NESTED_ROLLBACK_OK ...`; attached with a named
  `--expect` assertion. Targeted pytest counts recorded below.

## Results

### Failing-before (pre-fix `map.py`, HEAD `e342328b`)

```text
2 failed, 25 deselected
FAILED test_var_map_nested_map_value_rolls_back_unconfirmed_ticks
FAILED test_var_map_nested_list_value_rolls_back_unconfirmed_ticks
```

Nested map: interpret `3.0` vs compile `1.0`. Nested list: interpret
`[1,1,1,1,4]` vs compile `[1,1,1,1,2]`. Nested Matrix also leaked (`3.0`);
after the fix it is `1.0` (interpret). Transcript:
`pyne-nested-realtime-rollback-2026-11-15.failing-before.txt`.

### After

- `tests/test_realtime_rollback.py` — **33 passed** (8 new tests).
- Targeted library/UDT/compiler/realtime suites — **196 passed**.
- Full `tests/test_compiler_*.py` — **483 passed**.
- `./scripts/verify.sh` — **RED (2 failed / 3 passed)**: pre-existing
  `REVIEW.md` formatting and four 0.7.0-era tests (debt card
  `pynescript: verify red after 0.7.1 — 4 tests expect 0.7.0 CLI surfaces + REVIEW.md format drift`).
- Proof token:
  `NESTED_ROLLBACK_OK map=1.0 list=2.0 matrix=1.0 scalar=1.0 udt=1.0 cycle=1 removed=1 replaced=1`.

### Checker round 2 — cycles and removed/replaced containers

- **Cycles/self-references.** The recursive snapshot raised `RecursionError`
  on a self-referential map/list; the host caught it, skipped the snapshot and
  let an unconfirmed tick commit. Fixed with an ancestor `seen` set that raises
  `RealtimeSnapshotError`; `_copy_container_contents` re-raises it so the host
  cannot silently skip the snapshot. Regression:
  `test_snapshot_realtime_scope_cyclic_map_raises`.
- **Removed/replaced nested containers.** Typed/UDT snapshot nodes now carry
  the original object; restore writes into it and returns it, so a removed or
  replaced nested Map/Matrix/UDT comes back with its original type and values
  instead of a raw payload tuple/dict. Regressions:
  `test_map_snapshot_restores_removed_nested_map`,
  `..._matrix`, `..._udt`, and `test_map_snapshot_restores_replaced_nested_map`.

### Pre-existing gate failures (not this slice)

`./scripts/verify.sh` is red on two upstream issues from the 8 commits merged
before this slice:

- **Format:** `REVIEW.md` needs formatting (`bun fmt --check`).
  `git diff HEAD -- REVIEW.md` is empty; its last change is upstream `4ddab46e`.
- **Tests:** four failures reproduce with HEAD's `src`
  (`PYTHONPATH=<HEAD src>`): `test_download_builtins_removed`,
  `test_pygls_initialize_advertises_semantic_token_legend`,
  `test_pyne_lsp_version_flag`, `test_list_facade_templates_removed` — the
  `0.7.1` release / removed CLI surfaces vs tests still expecting `0.7.0`.

Lint, typecheck and OKF pass; the slice's targeted (191) and compiler (483)
suites are green. This slice does not touch `REVIEW.md`, the version, or the
CLI/MCP surfaces.

### Files

- `src/pynescript/ast/evaluator/builtins/map.py` — recursive
  `_snapshot_value`/`_restore_value`; `copy_contents`/`restore_contents`.
- `tests/test_realtime_rollback.py` — nested map, nested list, nested Matrix.
- `.openorchestrate/plans/pyne-nested-realtime-rollback-2026-11-15.md` (this
  file), `.proof.py`, `.failing-before.txt`.
