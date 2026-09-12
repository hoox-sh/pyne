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
