# PYNE intra-bar tick path — slice 1: pending limit/stop fills

- **Date:** 2026-11-16
- **Seat:** `oo-spec-2` (Engineering)
- **Card:** `PYNE: intra-bar tick path for broker fills/trails/MAE-MFE (OHLC-path approximation only)`
- **Status:** implementation slice; no commit/push.

## Slice choice and why

Pending OHLC fills run **once per bar before the tick loop**
(`process_pending_orders` / compile `begin_bar`). A limit/stop placed on an
earlier bar is therefore only tested against the bar's initial OHLC, even when
a supplied feed later grows the forming bar's high/low past the trigger.

This slice re-evaluates pending orders on **each interpret tick** against the
polled forming OHLC. It is the smallest correctness improvement with a clear
observable effect: a pending limit that only crosses on tick 2 now fills and
commits on the confirmed tick. Trail/MAE-MFE already use the forming H/L per
tick; making them tick-accurate needs the same path and is the next slice.

## Acceptance criteria

1. With `data_feed` + `realtime_ticks=3`, a pending buy limit at 95 that the
   forming bar only crosses on tick 2 fills; the confirmed tick commits:
   `strategy.position_size` = `1.0` on the last bar.
2. Without a crossing forming bar (no feed), the limit stays pending:
   position `0.0` for every bar.
3. Unconfirmed tick fills roll back (no double fill): the final position is
   `1.0`, not 2/3.
4. Historical bar-start fills are unchanged (market entry at next open, limit
   fill on a bar whose low crosses).
5. Interpret path only; compile object-mode intra-bar fills are deferred (the
   generated tick loop needs a codegen change).
6. Targeted realtime/compiler suites stay green.

## Out of scope (documented)

- Compile object-mode intra-bar fills (separate codegen slice).
- Tick-accurate trail stops / MAE-MFE beyond the forming H/L (D-01/D-03
  residual).
- Live exchange ticks: `CCXTProDataFeed.poll_ohlcv` returns the last cached
  candle, not a socket tick (D-04).

## Implementation sketch

- In `Runtime.run`'s interpret tick loop, after the per-tick event clear and
  before `visit`, call `process_pending_orders(open_, high, low, close)` with
  the polled forming bar when `bar_rt and n_ticks > 1` and pending orders
  exist.
- The per-tick broker snapshot (taken before the clear) restores unconfirmed
  fills; the confirmed tick commits and its events drain after the loop.
- Mirror the call in the session `_run_batch` tick loop so `update_last_bar`
  runs behave the same.
- Orders placed on the current bar remain inactive (`placed_bar == cur_bar`
  guard in `process_pending_orders`).

## Proof plan

- Failing-before: the feed fixture leaves position `0.0` on every bar.
- After: `1.0` on the last bar; no-feed `0.0`; historical fills unchanged.
- Proof script prints `INTRABAR_FILL_OK ...`; named `--expect` assertion.
- Targeted pytest counts recorded below.

## Results

### Failing-before (pre-fix `host.py`)

```text
1 failed, 1 passed
FAILED test_feed_tick_fills_pending_limit_intrabar
```

The feed fixture left `strategy.position_size` at `0.0` on every bar; the
no-feed control already passed. Transcript:
`pyne-intrabar-pending-fills-2026-11-16.failing-before.txt`.

### After

- `tests/test_realtime_datafeed_ticks.py` — **13 passed** (5 new tests).
- `tests/test_runtime_session.py` — **21 passed** (6 new tests).
- Strategy/realtime targeted suites — **206 passed** (includes session tests).
- Full `tests/test_compiler_*.py` — **483 passed**.
- `./scripts/verify.sh` — **PASS** (5/5).
- Proof token:
  `INTRABAR_FILL_OK fill=1.0 nofeed=0.0 hist=1.0 market=1.0 session=1.0 survive=1.0 partial=3.0 session_partial=3.0 tick_err=order`.

### Checker round 2 — session parity, fill budget, error guard

- **Session `update_last_bar` parity.** Added the guarded pre-visit
  `process_pending` call to `update_last_bar` and `_confirm_forming_last_bar`.
  Regressions: pending limit fills on `update_last_bar`; a fill committed by
  `append_bars(realtime_ticks=3)` survives a re-tick; confirmation keeps the
  fill.
- **Duplicate partial fills.** `max_fill_per_bar` is now a per-bar budget on
  `StrategyState` (`_bar_fill_budget` / `_bar_fill_bar`, snapshot/restored with
  the broker). The bar-start call consumes it; tick calls cannot refill the same
  bar. Regressions: `3.0` (not `6.0`) for `realtime_ticks=3` no-feed and with a
  crossing feed; `realtime_ticks=1` and compile stay `3.0`.
- **Order-fill error guard.** The new tick calls are wrapped like the bar-start
  call; an exception returns `ERROR_KIND_ORDER`. Regression:
  `test_tick_order_fill_error_returns_order_kind`.
- **Budget snapshot aliasing.** `StrategyState.restore` aliased
  `_bar_fill_budget` (setattr fallback), so a re-tick mutated the bar-open
  snapshot and the next restore saw the used budget. Fixed by copying it like
  `pending_orders`. Regressions: direct snapshot isolation; partial
  `update_last_bar` twice (3.0 both); update then empty append/confirm (3.0);
  update then next crossing bar (6.0); append-tick partial then two updates
  (3.0); even qty=3 full fill survives a second update (3.0).

### Files

- `src/pynescript/runtime/host.py` — per-tick pending fill in the `Runtime.run`
  interpret tick loop, the session `_run_batch` twin, `update_last_bar` and
  `_confirm_forming_last_bar`, with `ERROR_KIND_ORDER` guards.
- `src/pynescript/ast/evaluator/builtins/strategy.py` — per-bar
  `max_fill_per_bar` budget and copy-on-restore.
- `tests/test_realtime_datafeed_ticks.py` — feed fill, no-feed control, partial
  budget, tick error.
- `tests/test_runtime_session.py` — session fill/survival/confirm and partial
  budget aliasing regressions.
- `.oo/plans/pyne-intrabar-pending-fills-2026-11-16.md` (this
  file), `.proof.py`, `.failing-before.txt`.
