# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Compiler audit locks from 2026-11-22.

Interpret is the numeric oracle. Each test runs ``Runtime.run`` in both
modes on the snippets from ``03-compiler.md``.
"""

from __future__ import annotations

from datetime import datetime
from datetime import timezone

from pynescript.runtime import Runtime


def _is_na(value: object) -> bool:
    """True for Pine na (None or NaN). Never treats 0.0 as na."""
    if value is None:
        return True
    try:
        return value != value  # type: ignore[operator]
    except Exception:
        return False


def _bars(
    n: int = 8,
    *,
    start: float = 100.0,
    highs: list[float] | None = None,
    t0: int = 1_700_000_000_000,
    step: int = 86_400_000,
) -> list[dict[str, float | int]]:
    rows: list[dict[str, float | int]] = []
    for i in range(n):
        close = start + i
        high = highs[i] if highs is not None else close + 1.0
        rows.append(
            {
                "open": close,
                "high": high,
                "low": close - 1.0,
                "close": close,
                "volume": 1000.0,
                "time": t0 + i * step,
            }
        )
    return rows


def _run(src: str, bars: list[dict[str, float | int]]) -> tuple[dict, dict]:
    from pynescript.ast.helper import clear_parse_cache

    clear_parse_cache()
    interp = Runtime(symbol="TEST").run(src, bars, mode="interpret")
    clear_parse_cache()
    compiled = Runtime(symbol="TEST").run(src, bars, mode="compile")
    return interp, compiled


def _assert_series(interp: dict, compiled: dict, key: str, expected: list[object]) -> None:
    assert "error" not in interp, interp.get("error")
    assert "error" not in compiled, compiled.get("error")
    left = interp["series"][key]
    right = compiled["series"][key]
    assert len(left) == len(right) == len(expected)
    for i, (want, a, b) in enumerate(zip(expected, left, right, strict=True)):
        if _is_na(want):
            assert _is_na(a), f"interpret {key}[{i}]={a!r} expected na"
            assert _is_na(b), f"compile {key}[{i}]={b!r} expected na"
        else:
            assert a == want, f"interpret {key}[{i}]={a!r} expected {want!r}"
            assert b == want, f"compile {key}[{i}]={b!r} expected {want!r}"


def test_history_na_and_negative_offset_are_na() -> None:
    """``na`` is not the current bar; a negative offset is not a future bar."""
    src = """
//@version=6
indicator("hist")
off = -1
plot(close[-1], "neg")
plot(close[na], "cna")
plot(close[off], "dyn")
plot(close[0], "c0")
plot(close[1], "c1")
"""
    n = 8
    start = 100.0
    interp, compiled = _run(src, _bars(n, start=start))
    na = [None] * n
    _assert_series(interp, compiled, "neg", na)
    _assert_series(interp, compiled, "cna", na)
    _assert_series(interp, compiled, "dyn", na)
    _assert_series(interp, compiled, "c0", [start + i for i in range(n)])
    c1 = [None] + [start + i for i in range(n - 1)]
    _assert_series(interp, compiled, "c1", c1)


def test_history_na_and_negative_offset_object_mode() -> None:
    """Object mode shares the history helper; an array handle forces that mode."""
    src = """
//@version=6
indicator("histobj")
b = array.from(1, 2, 3)
off = -1
plot(close[-1], "neg")
plot(close[na], "cna")
plot(close[off], "dyn")
plot(close[1], "c1")
plot(array.get(b, 0), "b0")
"""
    n = 8
    start = 100.0
    interp, compiled = _run(src, _bars(n, start=start))
    na = [None] * n
    _assert_series(interp, compiled, "neg", na)
    _assert_series(interp, compiled, "cna", na)
    _assert_series(interp, compiled, "dyn", na)
    c1 = [None] + [start + i for i in range(n - 1)]
    _assert_series(interp, compiled, "c1", c1)
    _assert_series(interp, compiled, "b0", [1.0] * n)


def test_highestbars_index_matches_interpret() -> None:
    """``high[ta.highestbars(high, 3)]`` is na unless the offset is 0."""
    src = """
//@version=6
indicator("hh")
plot(high[ta.highestbars(high, 3)], "hh")
"""
    highs = [10.0, 50.0, 12.0, 11.0, 13.0, 9.0, 8.0, 14.0]
    interp, compiled = _run(src, _bars(8, highs=highs))
    expected: list[object] = [None, None, None, None, 13.0, None, None, 14.0]
    _assert_series(interp, compiled, "hh", expected)


def test_var_first_exec_after_bar_zero() -> None:
    """A ``var`` first reached on bar 3 captures that bar's close."""
    src = """
//@version=6
indicator("varlater")
var float x = na
if bar_index == 3
    var float y = close
    x := y
plot(x, "x")
"""
    interp, compiled = _run(src, _bars(8))
    expected: list[object] = [None, None, None, 103.0, 103.0, 103.0, 103.0, 103.0]
    _assert_series(interp, compiled, "x", expected)


def test_udf_var_first_call_after_bar_zero() -> None:
    """A UDF ``var`` initializes on the first call, then holds."""
    src = """
//@version=6
indicator("udfvar")
var float out = na
f() =>
    var float y = close
    y
if bar_index >= 3
    out := f()
plot(out, "o")
"""
    interp, compiled = _run(src, _bars(8))
    expected: list[object] = [None, None, None, 103.0, 103.0, 103.0, 103.0, 103.0]
    _assert_series(interp, compiled, "o", expected)


def test_array_negative_index_and_na_index() -> None:
    """Negative indexes count from the end; ``na`` is not element 0."""
    src = """
//@version=6
indicator("arridx")
a = array.from(10, 20, 30)
array.set(a, -1, 99)
array.set(a, na, 7)
plot(array.get(a, -1), "gneg")
plot(array.get(a, na), "gna")
plot(array.get(a, 0), "g0")
plot(array.size(na), "szna")
"""
    n = 8
    interp, compiled = _run(src, _bars(n))
    _assert_series(interp, compiled, "gneg", [99.0] * n)
    _assert_series(interp, compiled, "gna", [None] * n)
    _assert_series(interp, compiled, "g0", [10.0] * n)
    _assert_series(interp, compiled, "szna", [None] * n)


def test_array_remove_negative_and_na() -> None:
    """``array.remove(-1)`` drops the tail; ``array.remove(na)`` is a runtime error."""
    ok = """
//@version=6
indicator("rmneg")
a = array.from(10, 20, 30)
plot(array.remove(a, -1), "rm")
plot(array.size(a), "sz")
plot(array.get(a, 0), "g0")
"""
    n = 8
    interp, compiled = _run(ok, _bars(n))
    _assert_series(interp, compiled, "rm", [30.0] * n)
    _assert_series(interp, compiled, "sz", [2.0] * n)
    _assert_series(interp, compiled, "g0", [10.0] * n)

    bad = """
//@version=6
indicator("rmna")
a = array.from(10, 20, 30)
plot(array.remove(a, na), "rm")
"""
    interp_bad, compiled_bad = _run(bad, _bars(n))
    for label, out in (("interpret", interp_bad), ("compile", compiled_bad)):
        assert out.get("error_kind") == "runtime", (label, out)
        assert "array.remove takes array and valid index" in str(out.get("error"))


def test_array_covariance_matches_interpret() -> None:
    """``array.covariance`` is the population covariance, not the constant 0."""
    src = """
//@version=6
indicator("cov")
plot(array.covariance(array.from(1, 2, 3), array.from(2, 4, 6)), "cov")
"""
    interp, compiled = _run(src, _bars(4))
    assert "error" not in interp, interp.get("error")
    assert "error" not in compiled, compiled.get("error")
    for i, (a, b) in enumerate(zip(interp["series"]["cov"], compiled["series"]["cov"], strict=True)):
        assert a == b, f"bar {i} interpret={a!r} compile={b!r}"
        assert abs(float(a) - (4.0 / 3.0)) < 1e-9


def test_dayofyear_is_day_of_year() -> None:
    """14 Nov 2023 is day 318, not day-of-month 14. Leap day 2024-02-29 is 60."""
    src = """
//@version=6
indicator("doy")
plot(dayofyear(time), "doy")
"""
    t0 = 1_700_000_000_000
    bars = _bars(8, t0=t0, step=86_400_000)
    expected = []
    for row in bars:
        dt = datetime.fromtimestamp(int(row["time"]) / 1000, tz=timezone.utc)
        expected.append(float(dt.timetuple().tm_yday))
    assert expected[0] == 318.0
    interp, compiled = _run(src, bars)
    _assert_series(interp, compiled, "doy", expected)

    leap_times = [1709078400000, 1709164800000, 1709251200000]
    leap_bars = []
    for i, ms in enumerate(leap_times):
        leap_bars.append(
            {
                "open": 1.0 + i,
                "high": 2.0 + i,
                "low": 0.5,
                "close": 1.0 + i,
                "volume": 1.0,
                "time": ms,
            }
        )
    interp_l, compiled_l = _run(src, leap_bars)
    _assert_series(interp_l, compiled_l, "doy", [59.0, 60.0, 61.0])
