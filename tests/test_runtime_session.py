"""Delta / resume: appending new bars must equal full replay (streaming scripts)."""

from __future__ import annotations

from pynescript.runtime import Runtime


def _bars(n: int, offset: int = 0) -> list[dict]:
    return [
        {
            "open": 100.0 + offset + i,
            "high": 101.0 + offset + i,
            "low": 99.0 + offset + i,
            "close": 100.5 + offset + i,
            "volume": 1000.0 + i,
            "time": 1_700_000_000_000 + (offset + i) * 60_000,
        }
        for i in range(n)
    ]


def test_session_append_equals_full_replay_sma() -> None:
    src = """
//@version=5
indicator("sess sma")
plot(ta.sma(close, 5), "sma")
plot(close, "c")
"""
    full_bars = _bars(30)
    full = Runtime(symbol="TEST").run(src, full_bars, mode="interpret")
    assert "error" not in full, full.get("error")

    rt = Runtime(symbol="TEST")
    sess = rt.create_session(src, _bars(20), mode="interpret")
    out = sess.append_bars(_bars(10, offset=20))
    assert "error" not in out, out.get("error")
    assert out["series"]["sma"] == full["series"]["sma"]
    assert out["series"]["c"] == full["series"]["c"]


def test_session_append_var_counter() -> None:
    src = """
//@version=5
indicator("sess var")
var int v = 0
v := v + 1
plot(v, "v")
"""
    full = Runtime(symbol="TEST").run(src, _bars(15), mode="interpret")
    rt = Runtime(symbol="TEST")
    sess = rt.create_session(src, _bars(10), mode="interpret")
    out = sess.append_bars(_bars(5, offset=10))
    assert out["series"]["v"] == full["series"]["v"]
    assert out["series"]["v"][-1] == 15


def test_ta_multitick_matches_single_tick() -> None:
    """Realtime re-ticks of the same bar must not corrupt incremental TA."""
    src = """
//@version=5
indicator("ta tick")
plot(ta.sma(close, 3), "s")
plot(ta.ema(close, 5), "e")
"""
    bars = _bars(10)
    once = Runtime(symbol="TEST").run(src, bars, mode="interpret", realtime_ticks=1)
    assert "error" not in once, once.get("error")
    multi = Runtime(symbol="TEST").run(src, bars, mode="interpret", realtime_ticks=3)
    assert "error" not in multi, multi.get("error")
    assert multi["series"]["s"] == once["series"]["s"]
    assert multi["series"]["e"] == once["series"]["e"]


def test_session_realtime_window_matches_full_run() -> None:
    """Session tail with a realtime window must equal full-run same window."""
    src = """
//@version=5
indicator("sess rt")
var int v = 0
v := v + 1
plot(v, "v")
plot(ta.sma(close, 3), "s")
"""
    bars = _bars(12)
    full = Runtime(symbol="TEST").run(src, bars, mode="interpret", realtime_ticks=3)
    assert "error" not in full, full.get("error")
    rt = Runtime(symbol="TEST")
    sess = rt.create_session(src, _bars(8), mode="interpret")
    out = sess.append_bars(_bars(4, offset=8), realtime_ticks=3)
    assert "error" not in out, out.get("error")
    assert out["series"]["v"] == full["series"]["v"]
    assert out["series"]["s"] == full["series"]["s"]


def test_session_update_last_bar_tick_then_append() -> None:
    """Forming-bar ticks overwrite the last cell; later appends stay exact."""
    src = """
//@version=5
indicator("sess tick")
var int v = 0
v := v + 1
plot(v, "v")
plot(close, "c")
plot(ta.sma(close, 3), "s")
"""
    rt = Runtime(symbol="TEST")
    sess = rt.create_session(src, _bars(10), mode="interpret")
    assert sess.bar_count == 10
    # Two forming ticks on bar 9 with a revised close; count must not grow
    # and var must commit once per bar (not once per tick).
    tick1 = dict(_bars(10)[-1])
    tick1["close"] = 1000.5
    tick1["high"] = 1001.0
    out1 = sess.update_last_bar(tick1)
    assert "error" not in out1, out1.get("error")
    assert sess.bar_count == 10
    tick2 = dict(tick1)
    tick2["close"] = 2000.5
    out2 = sess.update_last_bar(tick2)
    assert sess.bar_count == 10
    assert out2["series"]["v"][-1] == 10
    assert out2["series"]["c"][-1] == 2000.5
    # Appending the next closed bar must match a full replay where bar 9
    # already had the revised OHLC.
    revised = _bars(10)
    revised[-1] = dict(tick2)
    full = Runtime(symbol="TEST").run(src, revised + _bars(1, offset=10), mode="interpret")
    assert "error" not in full, full.get("error")
    out3 = sess.append_bars(_bars(1, offset=10))
    assert "error" not in out3, out3.get("error")
    assert out3["series"]["v"] == full["series"]["v"]
    assert out3["series"]["c"] == full["series"]["c"]
    assert out3["series"]["s"] == full["series"]["s"]


def test_session_empty_init_then_append() -> None:
    """Sessions may start empty; appended columns must not alias."""
    src = """
//@version=5
indicator("sess empty")
plot(ta.sma(close, 3), "s")
plot(close, "c")
"""
    rt = Runtime(symbol="TEST")
    sess = rt.create_session(src, [], mode="interpret")
    assert sess.bar_count == 0
    out = sess.append_bars(_bars(5))
    assert "error" not in out, out.get("error")
    assert out["count"] == 5
    full = Runtime(symbol="TEST").run(src, _bars(5), mode="interpret")
    assert out["series"] == full["series"]


def test_session_barstate_historical_defaults_on_append() -> None:
    """Appended bars must not inherit the previous last-bar barstate flags."""
    src = """
//@version=5
indicator("sess flags")
plot(barstate.islastconfirmedhistory ? 1 : 0, "lch")
plot(barstate.isrealtime ? 1 : 0, "rt")
plot(barstate.isconfirmed ? 1 : 0, "conf")
plot(barstate.isnew ? 1 : 0, "nw")
"""
    rt = Runtime(symbol="TEST")
    sess = rt.create_session(src, _bars(5), mode="interpret")
    out0 = sess.result()
    assert out0["series"]["lch"][-1] == 1
    assert out0["series"]["rt"][-1] == 0
    assert out0["series"]["conf"][-1] == 1
    out = sess.append_bars(_bars(2, offset=5))
    assert "error" not in out, out.get("error")
    assert out["series"]["rt"][5] == 0
    assert out["series"]["rt"][6] == 0
    assert out["series"]["conf"][5] == 1
    assert out["series"]["conf"][6] == 1
    assert out["series"]["nw"][5] == 1
    assert out["series"]["nw"][6] == 1
    assert out["series"]["lch"][5] == 0
    assert out["series"]["lch"][6] == 1


def test_session_update_last_bar_confirms_on_append() -> None:
    """Forming ticks are unconfirmed; append re-visits the last bar as confirmed."""
    src = """
//@version=5
indicator("sess conf")
plot(barstate.isconfirmed ? 1 : 0, "conf")
plot(barstate.isrealtime ? 1 : 0, "rt")
plot(close, "c")
"""
    rt = Runtime(symbol="TEST")
    sess = rt.create_session(src, _bars(5), mode="interpret")
    tick = dict(_bars(5)[-1])
    tick["close"] = 999.0
    out1 = sess.update_last_bar(tick)
    assert "error" not in out1, out1.get("error")
    assert out1["series"]["conf"][-1] == 0
    assert out1["series"]["rt"][-1] == 1
    out2 = sess.append_bars(_bars(1, offset=5))
    assert "error" not in out2, out2.get("error")
    assert out2["series"]["conf"][-2] == 1
    assert out2["series"]["conf"][-1] == 1
    assert out2["series"]["rt"][-1] == 0
    assert out2["series"]["c"][-2] == 999.0


def test_session_tick_then_append_islast_matches_full_replay() -> None:
    """Confirm-on-append must not treat the previous bar as islast when more bars follow."""
    src = """
//@version=5
indicator("sess islast")
var int f = 0
once barstate.islast
    f := f + 1
plot(barstate.islast ? 1 : 0, "last")
plot(barstate.islastconfirmedhistory ? 1 : 0, "lch")
plot(f, "f")
plot(close, "c")
"""
    rt = Runtime(symbol="TEST")
    sess = rt.create_session(src, _bars(5), mode="interpret")
    tick = dict(_bars(5)[-1])
    tick["close"] = 999.0
    sess.update_last_bar(tick)
    out = sess.append_bars(_bars(1, offset=5))
    assert "error" not in out, out.get("error")
    revised = _bars(5)
    revised[-1] = dict(tick)
    full = Runtime(symbol="TEST").run(src, revised + _bars(1, offset=5), mode="interpret")
    assert "error" not in full, full.get("error")
    assert out["series"]["last"] == full["series"]["last"]
    assert out["series"]["lch"] == full["series"]["lch"]
    assert out["series"]["f"] == full["series"]["f"]
    assert out["series"]["last"][-2] == 0
    assert out["series"]["last"][-1] == 1
    assert out["series"]["f"][-1] == 1


def test_session_strategy_hist_overwrite_on_confirm() -> None:
    """Confirm must overwrite the last strategy series slot, not append a duplicate."""
    src = """
//@version=6
strategy("sess hist")
if bar_index == 0
    strategy.entry("L", strategy.long, 1)
plot(strategy.position_size, "ps")
plot(strategy.position_size[1], "ps1")
plot(strategy.position_size[2], "ps2")
"""
    rt = Runtime(symbol="TEST")
    sess = rt.create_session(src, _bars(5), mode="interpret")
    tick = dict(_bars(5)[-1])
    tick["close"] = 999.0
    sess.update_last_bar(tick)
    out = sess.append_bars(_bars(1, offset=5))
    assert "error" not in out, out.get("error")
    revised = _bars(5)
    revised[-1] = dict(tick)
    full = Runtime(symbol="TEST").run(src, revised + _bars(1, offset=5), mode="interpret")
    assert "error" not in full, full.get("error")
    assert out["series"]["ps"] == full["series"]["ps"]
    assert out["series"]["ps1"] == full["series"]["ps1"]
    assert out["series"]["ps2"] == full["series"]["ps2"]


def test_session_once_restored_on_update_last_bar() -> None:
    """``once`` on the forming bar re-runs after rollback, then commits on append."""
    src = """
//@version=5
indicator("sess once")
var int f = 0
once barstate.islast
    f := f + 1
plot(f, "f")
plot(barstate.isconfirmed ? 1 : 0, "conf")
"""
    rt = Runtime(symbol="TEST")
    sess = rt.create_session(src, _bars(3), mode="interpret")
    assert sess.result()["series"]["f"][-1] == 1
    tick = dict(_bars(3)[-1])
    tick["close"] = 500.0
    out1 = sess.update_last_bar(tick)
    assert "error" not in out1, out1.get("error")
    assert out1["series"]["f"][-1] == 1
    assert out1["series"]["conf"][-1] == 0
    out2 = sess.append_bars(_bars(1, offset=3))
    assert "error" not in out2, out2.get("error")
    # Full replay: once barstate.islast fires only on the true last bar.
    assert len(out2["series"]["f"]) == 4
    assert out2["series"]["f"][-2] == 0
    assert out2["series"]["f"][-1] == 1
    assert out2["series"]["conf"][-2] == 1
