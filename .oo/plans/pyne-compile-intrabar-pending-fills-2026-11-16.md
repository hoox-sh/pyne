# Compile object-mode intra-bar pending fills

**Date:** 2026-11-16
**Card:** `pyne-compile-object-mode-intra-b-189acd98`
**Status:** Working — first slice, no commit/push

## Why

Interpret re-evaluates pending limit/stop orders on every polled realtime tick
(`process_pending_orders` inside the tick loop, after the per-tick broker
snapshot, with a per-bar `max_fill_per_bar` budget and `ERROR_KIND_ORDER` on a
tick fill exception). Compile object mode only called `begin_bar` once per bar,
so a limit/stop that crossed on a later polled forming tick never filled. This
was the explicitly deferred half of the interpret intra-bar slice
(`.oo/plans/pyne-intrabar-pending-fills-2026-11-16.md`).

## Choice / blocker check

Compile object mode is pure Python and already has the realtime tick loop,
polled forming OHLC, and broker snapshot/restore, so codegen can host the call
cleanly. No blocker; implement the full first slice.

Insertion point: after the per-tick `__strategy.snapshot()` and var/TA
snapshots, before the body. The snapshot restores unconfirmed fills; the
confirmed tick commits. The per-bar budget lives on `CompileStrategyBroker` and
is copied by snapshot/restore so a re-tick cannot reuse it.

## Change

- `compiler.py` `_emit_object_mode`: import `StrategyOrderError`; in the tick
  loop, when `__bar_rt and __n_ticks > 1 and __strategy.pending_orders`, call
  `process_pending_orders(open, high, low, close)` after the snapshot. Wrap
  exceptions in `StrategyOrderError`; apply the post-fill tick envelope.
- `strategy_broker.py`: `StrategyOrderError`; per-bar `_bar_fill_budget` /
  `_bar_fill_bar`; reset on bar change; budget accounting; copy-on-snapshot and
  restore.
- `engine.py`: disk IR cache version 56 (codegen changed).
- `host.py`: compile error handler maps `StrategyOrderError` to
  `ERROR_KIND_ORDER` with an "Order fill error" label.
- `docs/known_divergences.md`: compile intra-bar fills are no longer deferred.

## Acceptance criteria

1. With `data_feed` + `realtime_ticks=3`, compile object mode fills a pending
   buy limit that only crosses on tick 2; final `strategy.position_size` = 1.0,
   matching interpret on the same fixture.
2. Unconfirmed tick fills roll back; final position is 1.0, not 2/3.
3. `max_fill_per_bar=3` shares one per-bar budget across bar-start and tick
   calls: final position 3.0, not 6/9.
4. An exception in the compile tick fill path returns
   `ERROR_KIND_ORDER` (`"order"`) with the original message.
5. Historical/bar-start fills and no-feed behavior are unchanged.
6. Targeted suites and `./scripts/verify.sh` 5/5 stay green.

## Failing before

`.oo/plans/pyne-compile-intrabar-pending-fills-2026-11-16.failing-before.txt`
— 3 failed: compile pending limit left position `0.0` (interpret `1.0`);
compile partial budget `0.0` (interpret `3.0`); compile tick error produced no
`error_kind` instead of `"order"`.

## Results

- New compile intra-bar tests — **3 passed**.
- `tests/test_realtime_datafeed_ticks.py` — **16 passed**.
- Targeted `datafeed + compiler_strategy + compiler_realtime + mae + session`
  — **135 passed**.
- `tests/test_compiler_numba.py + test_compiler_color_fold.py` — **217 passed**.
- `./scripts/verify.sh` — **5 passed, 0 skipped**.

## Proof

Card `pyne-compile-object-mode-intra-b-189acd98` (HQ board), attached from the
workspace root with `OO_SEAT=oo-spec-2`:

| Proof | Id | Assertion |
| --- | --- | --- |
| named compile intra-bar tests | `dd80146f-d143-49f6-a1f5-cb0f521445f2` | 3 tests PASSED (fill, partial budget, ORDER error) |
| named token | `cde41f77-0720-4474-8777-80bd648a16dd` | `COMPILE_INTRABAR_OK fill=1.0 partial=3.0 err=order match=1` |
| targeted suite | `abc3d904-a75a-4c81-a2fd-ca9862a5209e` | 135 passed |
| `./scripts/verify.sh` | `c932d6ca-6651-4d09-888e-f34ed5a416dd` | all passed, 5 passed / 0 skipped |

SHA-256: compiler `7a8d1c8486b600057e0f35538a52960c875c3a2d0c81a19813458837df4226b4`,
broker `f6ac7c9c62c7e537e9acdef869c9dcc560005d40818e4a5aa34fc81a45b07caf`,
engine `1d751b8ff6b97bda635df0ac796196aca7a167d6004758d5621636357bf159d3`,
host `862db0487eb726d64f156e5170c8b3ced7069c453901697773cf1b274f0e524b`,
tests `e118c37a7b3578ca4e804396349abb7c049e4119feef4e97b308887dfb177123`,
docs `bf0666075335108fb22c8890d5367d37c7d440945c18680ac4f4f171d8085085`,
patch `23783c872f174116ee593f44ea5ca9e6e1a14f7bc61aa94562341b96469faf93`.
Verify transcript: `.oo/proof/verify-compile-intrabar-2026-11-16.txt`.

## Files

- `src/pynescript/compiler/compiler.py`
- `src/pynescript/compiler/strategy_broker.py`
- `src/pynescript/compiler/engine.py`
- `src/pynescript/runtime/host.py`
- `tests/test_realtime_datafeed_ticks.py`
- `docs/known_divergences.md`
- `.oo/plans/pyne-compile-intrabar-pending-fills-2026-11-16.{md,failing-before.txt,proof.py}`

## Residual

- Numeric nopython still has no tick loop; strategy scripts are object mode, so
  this slice covers the realtime strategy path.
- Tick-accurate trail stops / MAE-MFE beyond the forming H/L remain the D-01 /
  D-03 residual; this slice applies the existing tick envelope after fills.
- No commit/push for this slice.
