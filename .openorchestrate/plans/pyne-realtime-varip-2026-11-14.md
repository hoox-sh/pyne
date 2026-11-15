# PYNE realtime / `varip` — slice 1: numeric realtime contract

- **Date:** 2026-11-14
- **Seat:** `oo-spec-2` (Engineering)
- **Card:** `PYNE: full realtime/varip semantics support — gap inventory + implementation`
- **Status:** slice 1 implemented and proven; **Ready for Review**; no commit/push.

## Why this slice

The #1 inventory found three realtime gaps:

1. Numeric nopython has no realtime tick loop; active realtime windows force
   object mode in `Runtime._run_compiled` (`runtime/host.py:4501-4505`), while
   numeric emit hardcodes `__isrealtime=False`, `__isconfirmed=True`,
   `__ishistory=True`, `__isnew=True` (`compiler/compiler.py:1412-1417`).
2. Interpret rollback is one-level / best-effort for nested Matrix/Map/UDT.
3. No intra-bar tick path for broker fills/trails/MAE-MFE.

This slice addresses the smallest correctness hole in (1): **`CompiledScript.run`
silently ignores realtime kwargs in numeric mode.** `Runtime.run` already routes
an active realtime window to object mode, but direct engine callers get historical
`barstate` flags and `varip` behaves like `var`. That is a silent divergence, not
a performance gap.

Matrix/Map rollback already has `copy_contents`/`restore_contents` one-level
support (`host.py:1321-1374`, `map.py:95-110`, `matrix.py:410-425`); deepening it
is a separate, larger slice and is out of scope here.

## Acceptance criteria

1. `CompiledScript.run(..., rt_first=..., rt_ticks=...)` on a numeric script
   routes that run through object mode and matches interpret for
   `barstate.isrealtime`, `barstate.isconfirmed`, `barstate.ishistory`.
2. Numeric `varip` under a realtime window matches interpret:
   `var` commits once on the confirmed tick; `varip` re-initializes per tick.
3. Historical `CompiledScript.run()` (no realtime kwargs) stays numeric and
   byte-for-byte series-compatible with the current behavior.
4. The numeric `CompiledScript` object is not mutated by a realtime run:
   a subsequent historical run still reports `object_mode is False`.
5. Failing-before tests exist and pass after the change; targeted
   `test_compiler_realtime.py`, `test_compiler_numba.py`, and
   `test_compiler_color_fold.py` suites are green.

## Out of scope

- Adding a real Numba tick loop (route to object mode for now).
- Deep-copying nested Matrix/Map/UDT internals on interpret rollback.
- Intra-bar broker fills / trail / MAE-MFE tick path.

## Implementation sketch

In `CompiledScript.run`, after OHLCV/time coercion, if
`rt_first is not None and not self.object_mode`, transpile with
`force_object_mode=True`, exec the recovered module, and run that recovered
`CompiledScript` with the same realtime kwargs. Do not mutate `self`, so the
numeric cache entry stays numeric for historical runs.

## Proof plan

- Failing-before test: numeric `CompiledScript.run` with `rt_first` returns
  `barstate.isrealtime=0` and `varip == var`.
- After: same call matches interpret; historical run unchanged.
- `oo proof attach --expect` named assertion, plus targeted pytest counts.

## Implementation

- `compiler/engine.py:732-750` — `CompiledScript.run` detects
  `rt_first is not None and not self.object_mode` after OHLCV/time coercion and
  routes that call through a recovered object-mode `CompiledScript`.
- `compiler/engine.py:785-802` — `_object_mode_for_realtime()` transpiles with
  `force_object_mode=True`, execs the module, and returns a transient
  `CompiledScript`. It does not mutate the numeric instance.
- Historical runs (no `rt_first`) are unchanged.

## Perf note

`_object_mode_for_realtime` transpiles + execs a transient object-mode script
per realtime call; there is no compiled-script cache. The parse cache is reused,
but transpile/exec still costs ~**1.13 ms/call** vs ~**0.008 ms** for a historical
numeric call on a trivial 100-bar script. This is a deliberate correctness-first
trade-off in this slice. Follow-up card (already filed, Todo):
**"PYNE: cache transient object-mode realtime script"**
(`pyne-cache-transient-object-mode-7ed4272f`). The cache is **not** implemented
here.

## Failing-before evidence

Before the change, the two new tests failed exactly on the divergence:

```text
test_numeric_compiled_run_routes_realtime_to_object_mode
  assert out["rt"][-1] == 1.0   -> 0.0

test_numeric_compiled_run_varip_matches_interpret_realtime
  assert out["vip"][-1] == 1.0  -> 8.0
```

## After evidence

- `tests/test_compiler_realtime.py` new tests: **2 passed**.
- Targeted suite `test_compiler_realtime.py + test_compiler_numba.py +
  test_compiler_color_fold.py`: **233 passed**.
- Proof output: `REALTIME_SLICE_OK numeric_rt=1 varip=1 historical=1`.
- Historical run after a realtime run still reports `object_mode is False`
  and returns historical `barstate`/`varip` values.

## Proof

- `.openorchestrate/plans/pyne-realtime-varip-2026-11-14.proof.py`
- `oo proof attach --expect "REALTIME_SLICE_OK numeric_rt=1 varip=1 historical=1"`
- Proof IDs: `57818fbc-c8da-4e8b-858c-d7d3c4484996` (assertion),
  `1285071d-8972-4b15-9dac-f947ff709189` (233 passed),
  `2310dcd5-4887-46a1-871f-ace13af0b82c` (plan artifact).
