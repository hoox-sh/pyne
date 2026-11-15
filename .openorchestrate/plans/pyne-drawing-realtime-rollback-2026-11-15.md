# PYNE drawing state rollback — slice 1: interpret set_xy / set_text

- **Date:** 2026-11-15
- **Seat:** `oo-spec-2` (Engineering)
- **Card:** `PYNE: drawing state rollback on unconfirmed realtime ticks (in-place set_xy/set_text/delete not restored)`
- **Status:** implementation slice in progress; no commit/push.

## Why this slice

The inventory flagged drawing mutations on unconfirmed realtime ticks. Reproduction
shows the leak is in **interpret**, not compile:

```text
interpret: line.set_xy1(l, 5, 999.0) on an unconfirmed tick -> exported p1=999.0
compile:   same script -> exported p1=100.5 (append-only __drawings truncation works)
```

`_snapshot_realtime_scope` restores `var` bindings/containers but not the
`DrawingRegistry` class lists; `DrawingRegistry` dataclass objects mutate in place
(`set_xy`, `set_text`, `delete`). Compile already truncates appended mutation
events.

This slice restores one mutation class: **existing line/label field mutations**
(`set_xy*`, `set_text`) plus `deleted` state. New drawings created on an
unconfirmed tick are truncated with the registry list length. Table cells,
polyline point lists, and nested linefill contents stay out of scope.

## Acceptance criteria

1. On an unconfirmed interpret realtime tick, `line.set_xy1`/`set_xy2` and
   `label.set_text` mutations are restored to their pre-tick values before the
   next tick.
2. Drawings created on an unconfirmed tick do not survive the rollback
   (registry lists truncate to the snapshot length).
3. A confirmed realtime tick commits its drawing mutation (rollback must not
   erase the final tick).
4. Compile-mode drawing rollback behavior is unchanged.
5. Failing-before tests exist for `set_xy1` and `set_text`; targeted realtime
   and drawing suites stay green.

## Out of scope

- `table.cell` cell-map rollback.
- Polyline `points` list rollback.
- Nested linefill/table contents.
- Drawing GC changes or object-mode getters.

## Implementation sketch

- In `runtime/host.py`, snapshot `DrawingRegistry` list lengths and each existing
  object's dataclass `__dict__` before an intermediate tick.
- Restore by truncating lists to the snapshot lengths and writing the saved
  fields back into the same objects (identity preserved).
- Attach the snapshot to `_snapshot_realtime_scope` / `_restore_realtime_scope`;
  `varip` names are unaffected.

## Proof plan

- Failing-before: interpret `line.set_xy1` exports `p1=999.0`; `label.set_text`
  exports `LEAK`.
- After: exports `p1=100.5` / `text=orig`; confirmed-tick mutation persists.
- Targeted `test_compiler_realtime.py` + new drawing rollback tests; named
  `oo proof attach --expect` assertion.

## Implementation

- `runtime/host.py:1377-1434` — `_snapshot_drawing_registry` /
  `_restore_drawing_registry`: snapshot registry list lengths and existing
  dataclass `__dict__` fields; restore truncates new drawings and writes fields
  back into the same objects.
- `runtime/host.py:1478` — snapshot is attached to `_snapshot_realtime_scope`.
- `runtime/host.py:1553` — restore runs from `_restore_realtime_scope` after the
  existing var/once restore.

Compile mode is untouched; its append-only `__drawings` truncation already
rolls back these mutations.

## Failing-before evidence

```text
test_interpret_line_set_xy_rolls_back_on_unconfirmed_tick
  assert line["p1"] == 100.5   -> 999.0

test_interpret_label_set_text_rolls_back_on_unconfirmed_tick
  assert label["text"] == "orig"  -> "LEAK"

test_interpret_new_drawing_on_unconfirmed_tick_is_truncated
  assert len(lines) == 1  -> 3
```

## After evidence

- New tests: `tests/test_drawing_realtime_rollback.py` — **6 passed**
  (`set_xy1`, `set_xy2`, `set_text`, `delete`, new-drawing truncation,
  confirmed-tick commit).
- Targeted realtime/drawing suite — **50 passed**.
- Proof output:
  `DRAWING_ROLLBACK_OK xy1=100.5 xy2=100.5 text=orig new=1 confirmed=999 deleted=1`.

## Proof

- `.openorchestrate/plans/pyne-drawing-realtime-rollback-2026-11-15.proof.py`
- `oo proof attach --expect "DRAWING_ROLLBACK_OK xy1=100.5 xy2=100.5 text=orig new=1 confirmed=999 deleted=1"`
- Proof records are attached to the card; the plan artifact proof is re-attached
  after this final edit so it pins the current content.
