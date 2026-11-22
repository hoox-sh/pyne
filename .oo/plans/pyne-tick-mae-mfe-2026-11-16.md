# Tick-accurate MAE/MFE on the interpret intra-bar path (D-03)

**Date:** 2026-11-16
**Card:** `pyne-tick-accurate-trail-mae-mfe-53464f88`
**Status:** Ready for Review — no commit/push

## Why MAE/MFE, not trail

Pending fills now run per tick on the interpret path (landed 2026-11-16,
`7017d042`). Per-trade MAE/MFE still had a clean inter-tick bug: the tick
loops applied `update_open_trade_extremes(high, low)` *before* that tick's
fills, so a trade opened by a tick fill never saw the fill tick's excursion at
all. The fill tick's high/low was simply dropped; a later tick could only add
its own.

Trail stops already ratchet per tick (`_update_trail_stop` inside
`process_pending_orders`). Their residual error is intratick order — whether
the high came before or after the low inside one OHLC tick — which no OHLC
tick can resolve. MAE/MFE had a fixable inter-tick error and no fill-decision
coupling, so it is the safer first slice immediately after the fill landing.

## Change (interpret feed tick path only)

- `_apply_feed_forming_bar` returns the polled tick's `(high, low)` (or
  `None`).
- Both interpret feed tick loops (`Runtime.run` via `_run_interpret`, and
  `InterpretSession._run_batch`) apply the tick's envelope in **two phases**:
  - **Before** the tick's pending fills, to trades already open at tick start,
    so a trade closed by the fill keeps the exit tick's extremes.
  - **After** the fills, to trades opened by the fill, so an entry fill sees
    its own tick.
- Unconfirmed restores re-apply the same tick envelope, so extremes persist
  like `varip` while fills roll back.
- No-feed fallback keeps the forming-bar high/low (bar-level), unchanged.
- `update_last_bar` stays bar-level: each call supplies one revised bar, not a
  tick stream. Compile intra-bar fills remain deferred (card scope), so the
  compile broker stays bar-level.

## Semantics (tick granularity)

A tick is the smallest unit: its OHLC envelope applies to every trade open
during that tick. For a long, `max_runup = high - entry` and
`max_drawdown = entry - low`; inverted for a short. Pre-entry ticks are not
counted because the trade does not exist yet; an exit tick is counted because
the trade is still open at tick start. The intratick path inside one OHLC tick
is not modeled — documented residual approximation.

## Acceptance criteria

1. Entry limit 95: tick 1 high 120 (pre-entry), tick 3 fills at 95 with high
   100 / low 94 → `max_runup == 5.0`, `max_drawdown == 1.0`; 25.0 absent.
2. Entry stop 105: tick 1 low 80 (pre-entry), trigger tick high 110 / low 90 →
   `max_runup == 5.0`, `max_drawdown == 15.0`; 25.0 absent.
3. Session twin for the entry limit: the open trade has the same extremes.
4. Limit exit 110: ticks 115/95, 118/92, then 120/90 → closed trade
   `max_runup == 20.0`, `max_drawdown == 10.0`; the exit tick is not dropped.
5. Stop exit 90: ticks 115/95, 118/92, then 120/80 → closed trade
   `max_runup == 20.0`, `max_drawdown == 20.0`.
6. Session twins for both exits have the same closed-trade extremes.
7. A trade open since bar 0 across ticks still accumulates every tick (the
   existing forming test's 20.0 / 10.0 stays).
8. No feed / `realtime_ticks=1` behavior unchanged.
9. Targeted suites green; proof token asserted.

## Failing before

- `pyne-tick-mae-mfe-2026-11-16.failing-before.txt` — entry tests on the
  pre-fix tree: `pos=1.0` but `ru=0.0`, `dd=0.0` (the fill tick is dropped).
- `pyne-tick-mae-mfe-2026-11-16.failing-before-exit.txt` — exit tests on the
  pre-two-phase tree: `cru=18.0` (the exit tick 120/90 or 120/80 is dropped;
  expected 20.0).

## Results

- `tests/test_mae_realtime_ticks.py` — **13 passed** (7 tick tests: 3 entry,
  4 exit).
- `tests/test_realtime_datafeed_ticks.py` — **13 passed**.
- `tests/test_runtime_session.py` — **21 passed**.
- Targeted realtime/strategy suite — **219 passed** (212 before this round,
  215 after the entry tests, 219 after the exit tests).
- Proof token:
  `TICK_MAE_OK tick=5.0 dd=1.0 stop_dd=15.0 exit=20.0/10.0 stop_exit=20.0/20.0 session=5.0 pos=1.0`.

Before/after: entry limit pre-fix `ru=0.0 dd=0.0` → `5.0 / 1.0`; entry stop
pre-fix `dd=0.0` → `15.0`; limit exit pre-fix `cru=18.0 cdd=8.0` →
`20.0 / 10.0`; stop exit pre-fix `18.0 / 8.0` → `20.0 / 20.0`.

## Files

- `src/pynescript/runtime/host.py` — `_apply_feed_forming_bar` returns the
  tick envelope; both interpret feed tick loops apply it pre-fill (exits) and
  post-fill (entries), and re-apply it on unconfirmed restore.
- `tests/test_mae_realtime_ticks.py` — seven tick-path regressions (entry
  limit, entry stop, session entry, limit exit, stop exit, session exits).
- `docs/known_divergences.md` — D-01/D-03/D-04 corrected: interpret feed ticks
  per tick, compile + bar-level `update_last_bar` OHLC, intratick-order
  residual.
- `.oo/plans/pyne-tick-mae-mfe-2026-11-16.{md,proof.py,failing-before.txt,failing-before-exit.txt}`.

## Residual / follow-ups

- Intratick order inside one OHLC tick is not modeled (no finer data).
- A trade opened and closed within the same tick is atomic: it is absent at
  tick start and gone before the post-fill apply, so it keeps its pre-tick
  extremes. Not modeled; needs finer-than-tick data or a same-call fill hook.
- Compile intra-bar pending fills remain deferred; compile MAE/MFE stays
  bar-level.
- `update_last_bar` accepts one revised bar per call, so its MAE/MFE stays
  bar-level; `_confirm_forming_last_bar` / `append_bars` confirmation also
  re-visits bar-level (adjacent gap, not expanded here).
- Discovered adjacent gap: interpret historical (non-realtime) bars do not
  call `update_open_trade_extremes` at all, so a trade held on historical bars
  keeps `0.0 / 0.0`; compile updates per bar. Not part of this tick slice.
