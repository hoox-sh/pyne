# Interpret historical bars: per-bar MAE/MFE (D-03)

**Date:** 2026-11-16
**Card:** `pyne-interpret-historical-bars-n-40170970`
**Status:** Ready for Review — no commit/push

## Why

The interpret bar loops never called `update_open_trade_extremes` on historical
(non-realtime) bars. A position held across historical bars kept
`max_runup=0.0` / `max_drawdown=0.0`, while the compile broker updates per bar:
`begin_bar` calls `_update_leg_extremes` before pending fills, and the fill path
calls it again when a leg opens. A 5-bar held trade gave interpret
`[0,0,0,0,0]` and compile `[0,2,3,4,5]`.

## Change

1. In both interpret bar loops (`InterpretSession._run_batch` and
   `Runtime.run` via `_run_interpret`), when `need_strategy` and `not bar_rt`,
   call `update_open_trade_extremes(high, low)`:
   - before the bar-start pending fill (trades already open, exit bars), and
   - after the bar-start pending fill (trades opened by the fill, entry bar).
2. In `process_pending_orders`, after each fill, apply the current bar/tick
   envelope immediately (compile `_update_leg_extremes` at leg open). A leg
   opened by that fill therefore carries the envelope into a same-bar close.

Bar-level for historical bars; realtime bars keep the per-tick envelope path.

## Semantics

A trade open at historical bar N accumulates bar N's high/low; a trade opened
by bar N's bar-start fill also gets bar N's high/low (post-fill call). A
same-bar entry+exit keeps the entry bar's extremes because the fill path
applies them at leg open, before the closing fill. Exit bars are included
because the pre-fill call runs before the close. This is the same two-phase
rule as the interpret tick path, at bar granularity.

## Acceptance criteria

1. Held long: entry fills bar 1 open (100); bars 1-4 high/low 102/98, 103/97,
   104/96, 105/95 → interpret `ru`/`dd` series `[0,2,3,4,5]`, identical to
   compile.
2. Session twin (`create_session` historical bars) has the same series.
3. Same-bar full open+close: long limit 95 (qty 1) + short order limit 105
   (qty 1) both fill on bar high 106 / low 94 → closed long `cru/cdd = 11/1`
   on interpret and compile. Position is not asserted (pre-placed
   `strategy.order` reverse semantics differ; separate pre-existing card).
4. Same-bar partial: long qty 2 + short qty 1 → closed leg `22/2` on both
   hosts; position not asserted for the same reason.
5. `update_last_bar` initial value reflects the last historical bar (ru=1.0
   for the existing fixture), then the forming tick restores and applies its
   envelope as before.
6. Realtime tick tests (entry/exit tick semantics) unchanged.
7. Targeted suites green; named token asserted.

## Failing before

- `pyne-historical-extremes-2026-11-16.failing-before.txt` — interpret
  `[0,0,0,0,0]` vs compile `[0,2,3,4,5]` (2 failed).
- `pyne-historical-extremes-2026-11-16.failing-before-samebar.txt` — same-bar
  closed long interpret `0/0` vs compile `11/1` (and partial `0/0` vs `22/2`);
  checker evidence `19ec803a` / hash `49f0ce34`.

## Results

- `tests/test_mae_realtime_ticks.py` — **17 passed** (4 new: 2 held-trade, 2
  same-bar).
- `tests/test_realtime_datafeed_ticks.py` — **13 passed**.
- `tests/test_runtime_session.py` — **21 passed**.
- Targeted realtime/strategy suite — **223 passed**.
- Proof token:
  `HIST_EXTREMES_OK interp=5.0/5.0 compile=5.0/5.0 session=5.0/5.0 samebar=11.0/1.0 partial=22.0/2.0 series=0,2,3,4,5`.

## Files

- `src/pynescript/runtime/host.py` — historical pre-fill and post-fill
  extremes calls in both interpret bar loops.
- `src/pynescript/ast/evaluator/builtins/strategy.py` — fill-path immediate
  extremes update after each fill (same-bar entry+exit parity with compile).
- `tests/test_mae_realtime_ticks.py` — held-trade + session tests and same-bar
  full/partial closed-leg tests.
- `docs/known_divergences.md` — D-03 historical + same-bar note; atomic
  same-tick residual removed.
- `.oo/plans/pyne-historical-extremes-2026-11-16.{md,proof.py,failing-before.txt,failing-before-samebar.txt}`.

## Residual

- Historical bars stay bar-level (no tick path); intratick order unmodeled.
- Pre-placed `strategy.order` reverse-order position semantics still differ
  between hosts (pre-existing, separate card). The closed-leg MAE/MFE now
  matches; the position result does not, and the tests isolate that.
- `update_last_bar` / confirmation remain bar-level (adjacent).
- Multi-leg close aggregates max extremes across reduced legs (unchanged).
