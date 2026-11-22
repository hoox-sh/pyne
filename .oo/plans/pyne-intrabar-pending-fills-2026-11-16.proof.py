# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Assertion proof: pending limit fills on the interpret intra-bar tick path."""

# ruff: noqa: S101, T201

from __future__ import annotations

from typing import Any

from pynescript.ast.evaluator.builtins.strategy import StrategyBuiltinsMixin
from pynescript.ast.evaluator.builtins.strategy import StrategyState
from pynescript.runtime import Runtime
from pynescript.util.datafeed import MockDataFeed


_PENDING_LIMIT = """//@version=6
strategy("rt pending", overlay=true)
if barstate.isfirst
    strategy.entry("L", strategy.long, limit=95.0)
plot(strategy.position_size, "pos")
"""

_MARKET = """//@version=6
strategy("rt market", overlay=true)
if barstate.isfirst
    strategy.entry("L", strategy.long)
plot(strategy.position_size, "pos")
"""

_PARTIAL = """//@version=6
strategy("rt partial", overlay=true)
if barstate.isfirst
    strategy.entry("L", strategy.long, qty=10, limit=95.0, max_fill_per_bar=3)
plot(strategy.position_size, "pos")
"""

_FULL_PARTIAL = """//@version=6
strategy("rt full partial", overlay=true)
if barstate.isfirst
    strategy.entry("L", strategy.long, qty=3, limit=95.0, max_fill_per_bar=3)
plot(strategy.position_size, "pos")
"""


def _bars(n: int = 5, low_override: float | None = None, offset: int = 0) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i in range(n):
        c = 100.0 + offset + i
        low = low_override if (low_override is not None and i == 2) else c - 1.0
        out.append(
            {
                "time": 1_704_067_200_000 + (offset + i) * 86_400_000,
                "open": c,
                "high": c + 1.0,
                "low": low,
                "close": c,
                "volume": 1000.0,
            }
        )
    return out


def _run(src: str, *, feed: Any = None, bars: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return Runtime(symbol="RT").run(
        src,
        bars if bars is not None else _bars(),
        mode="interpret",
        realtime_ticks=3,
        data_feed=feed,
    )


def main() -> None:
    ts = 1_704_067_200_000 + 4 * 86_400_000
    candles = [
        [ts, 104.0, 105.0, 96.0, 104.0, 10.0],
        [ts, 104.0, 105.0, 94.0, 104.0, 20.0],
        [ts, 104.0, 105.0, 94.0, 104.0, 30.0],
    ]

    # 1. Feed tick crosses the pending limit on tick 2; confirmed tick commits.
    feed_out = _run(_PENDING_LIMIT, feed=MockDataFeed(scripted=candles))
    assert "error" not in feed_out, feed_out.get("error")
    feed_pos = [float(v) for v in feed_out["series"]["pos"]]
    assert feed_pos[-1] == 1.0, feed_pos
    assert feed_pos[:-1] == [0.0, 0.0, 0.0, 0.0], feed_pos

    # 2. No feed / no crossing forming bar: the limit stays pending.
    nofeed = _run(_PENDING_LIMIT)
    assert "error" not in nofeed, nofeed.get("error")
    assert [float(v) for v in nofeed["series"]["pos"]] == [0.0, 0.0, 0.0, 0.0, 0.0]

    # 3. Historical bar-start limit fill unchanged.
    hist = _run(_PENDING_LIMIT, bars=_bars(low_override=94.0))
    assert "error" not in hist, hist.get("error")
    hist_pos = [float(v) for v in hist["series"]["pos"]]
    assert hist_pos == [0.0, 0.0, 1.0, 1.0, 1.0], hist_pos

    # 4. Market entry at the next bar's open unchanged.
    market = _run(_MARKET)
    assert "error" not in market, market.get("error")
    assert [float(v) for v in market["series"]["pos"]] == [0.0, 1.0, 1.0, 1.0, 1.0]

    # 5. Session update_last_bar fills, survives re-tick, survives confirmation.
    sess = Runtime(symbol="RT").create_session(_PENDING_LIMIT, _bars(4), mode="interpret")
    tick = dict(_bars(4)[-1])
    tick["low"] = 94.0
    update_out = sess.update_last_bar(tick)
    assert "error" not in update_out, update_out.get("error")
    assert update_out["series"]["pos"][-1] == 1.0, update_out["series"]["pos"]
    confirm_out = sess.append_bars(_bars(1, offset=4))
    assert "error" not in confirm_out, confirm_out.get("error")
    assert confirm_out["series"]["pos"][-1] == 1.0, confirm_out["series"]["pos"]

    ts4 = 1_700_000_000_000 + 4 * 60_000
    feed = MockDataFeed(
        scripted=[
            [ts4, 104.0, 105.0, 96.0, 104.0, 10.0],
            [ts4, 104.0, 105.0, 94.0, 104.0, 20.0],
            [ts4, 104.0, 105.0, 94.0, 104.0, 30.0],
        ]
    )
    sess2 = Runtime(symbol="RT").create_session(_PENDING_LIMIT, _bars(4), mode="interpret", data_feed=feed)
    append_out = sess2.append_bars(_bars(1, offset=4), realtime_ticks=3)
    assert "error" not in append_out, append_out.get("error")
    assert append_out["series"]["pos"][-1] == 1.0, append_out["series"]["pos"]
    tick2 = dict(_bars(1, offset=4)[0])
    tick2["low"] = 94.0
    survive_out = sess2.update_last_bar(tick2)
    assert "error" not in survive_out, survive_out.get("error")
    assert survive_out["series"]["pos"][-1] == 1.0, survive_out["series"]["pos"]

    # 5b. Session partial budget: restore must copy (not alias) the snapshot.
    state = StrategyState()
    state._bar_fill_budget["L"] = 3.0
    snap = state.snapshot()
    state.restore(snap)
    assert state._bar_fill_budget is not snap["_bar_fill_budget"]
    state._bar_fill_budget["L"] = 6.0
    assert snap["_bar_fill_budget"] == {"L": 3.0}

    def _crossing(bar: dict[str, Any]) -> dict[str, Any]:
        tick_bar = dict(bar)
        tick_bar["low"] = 94.0
        return tick_bar

    sess_partial = Runtime(symbol="RT").create_session(_PARTIAL, _bars(4), mode="interpret")
    for _ in range(2):
        update_twice = sess_partial.update_last_bar(_crossing(_bars(4)[-1]))
        assert "error" not in update_twice, update_twice.get("error")
        assert update_twice["series"]["pos"][-1] == 3.0, update_twice["series"]["pos"]
    confirm_partial = sess_partial.append_bars([])
    assert confirm_partial["series"]["pos"][-1] == 3.0, confirm_partial["series"]["pos"]
    next_crossing = _bars(1, offset=4)
    next_crossing[0]["low"] = 94.0
    next_out = sess_partial.append_bars(next_crossing)
    assert next_out["series"]["pos"][-1] == 6.0, next_out["series"]["pos"]

    full_partial = Runtime(symbol="RT").create_session(_FULL_PARTIAL, _bars(4), mode="interpret")
    for _ in range(2):
        full_out = full_partial.update_last_bar(_crossing(_bars(4)[-1]))
        assert "error" not in full_out, full_out.get("error")
        assert full_out["series"]["pos"][-1] == 3.0, full_out["series"]["pos"]

    # 6. max_fill_per_bar is consumed once per bar across bar-start + ticks.
    partial_bars = _bars(5)
    partial_bars[-1]["low"] = 94.0
    for ticks in (1, 3):
        partial_out = Runtime(symbol="RT").run(
            _PARTIAL, partial_bars, mode="interpret", realtime_ticks=ticks
        )
        assert "error" not in partial_out, partial_out.get("error")
        assert partial_out["series"]["pos"][-1] == 3.0, (ticks, partial_out["series"]["pos"])

    partial_feed = MockDataFeed(
        scripted=[
            [ts, 104.0, 105.0, 94.0, 104.0, 10.0],
            [ts, 104.0, 105.0, 94.0, 104.0, 20.0],
            [ts, 104.0, 105.0, 94.0, 104.0, 30.0],
        ]
    )
    partial_feed_out = Runtime(symbol="RT").run(
        _PARTIAL, partial_bars, mode="interpret", realtime_ticks=3, data_feed=partial_feed
    )
    assert "error" not in partial_feed_out, partial_feed_out.get("error")
    assert partial_feed_out["series"]["pos"][-1] == 3.0, partial_feed_out["series"]["pos"]

    # 7. A tick fill exception returns ERROR_KIND_ORDER.
    real_pending = StrategyBuiltinsMixin.process_pending_orders

    def boom(self, *, open_=None, high=None, low=None, close=None):
        if low is not None and float(low) <= 94.0:
            raise RuntimeError("tick fill boom")
        return real_pending(self, open_=open_, high=high, low=low, close=close)

    StrategyBuiltinsMixin.process_pending_orders = boom
    error_feed = MockDataFeed(
        scripted=[
            [ts, 104.0, 105.0, 96.0, 104.0, 10.0],
            [ts, 104.0, 105.0, 94.0, 104.0, 20.0],
            [ts, 104.0, 105.0, 94.0, 104.0, 30.0],
        ]
    )
    try:
        err_out = Runtime(symbol="RT").run(
            _PENDING_LIMIT, _bars(5), mode="interpret", realtime_ticks=3, data_feed=error_feed
        )
    finally:
        StrategyBuiltinsMixin.process_pending_orders = real_pending
    assert err_out.get("error_kind") == "order", err_out
    assert "tick fill boom" in str(err_out.get("error") or "")

    print("INTRABAR_FILL_OK fill=1.0 nofeed=0.0 hist=1.0 market=1.0 session=1.0 survive=1.0 partial=3.0 session_partial=3.0 tick_err=order")


if __name__ == "__main__":
    main()
