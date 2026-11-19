# Copyright (C) 2024-2026 jango_blockchained
#
# This file is part of pynescript.
#
# pynescript is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pynescript is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""OHLCV subscripts inside user-defined functions and library exports.

Bug A — a bare OHLCV subscript inside a UDF (``f() => close[1]``) used to
return characters of the unresolved name string (``'l'`` for
``close[1]``) because the UDF machinery popped host OHLCV series from the
context on entry, leaving the raw name string for the subscript path to
slice.

Bug B — a subscripted *parameter* of a library export (``src[1]``) never
crossed the library boundary: the consumer's ``_history_names`` scan does
not see the library body, so the parameter was bound as a raw scalar and
``src[1]`` was ``na`` on every bar.

Both fixes are interpret-mode behaviors; library imports are not supported
in compile mode, so the library cases here run with ``mode="interpret"``
only.
"""

from __future__ import annotations

import math

import pytest

from pynescript.runtime import Runtime


N_BARS = 30


def _bars(n: int = N_BARS) -> list[dict]:
    """Deterministic synthetic bars; hl2 != close so mix-ups are visible."""
    bars = []
    for i in range(n):
        c = 100.0 + 3.0 * i + math.sin(i / 3.0)
        bars.append(
            {
                "open": c - 2.0,
                "high": c + 3.0,
                "low": c - 1.0,
                "close": c,
                "volume": 1000.0 + 7.0 * i,
                "time": 1_700_000_000_000 + i * 60_000,
            }
        )
    return bars


_BARS = _bars()
_CLOSE = [b["close"] for b in _BARS]
_OPEN = [b["open"] for b in _BARS]
_VOLUME = [b["volume"] for b in _BARS]
_HL2 = [(b["high"] + b["low"]) / 2.0 for b in _BARS]
_TIME = [b["time"] for b in _BARS]


def _series(src: str, libraries: list[dict] | None = None) -> list:
    out = Runtime(symbol="TEST").run(src, _BARS, mode="interpret", libraries=libraries)
    assert "error" not in out, out.get("error")
    return out["series"]["out"]


def _shifted(values: list[float], offset: int) -> list[float | None]:
    return [None] * offset + list(values[: len(values) - offset])


def _assert_series_close(actual: list, expected: list[float | None]) -> None:
    assert len(actual) == len(expected)
    for i, (a, e) in enumerate(zip(actual, expected, strict=True)):
        if e is None:
            assert a is None, f"bar {i}: expected na, got {a!r}"
        else:
            assert a is not None, f"bar {i}: expected {e}, got na"
            assert float(a) == pytest.approx(e, rel=1e-9, abs=1e-9), f"bar {i}"


# ---------------------------------------------------------------------------
# Bug A — bare OHLCV subscripts inside a UDF
# ---------------------------------------------------------------------------


def test_udf_close_subscript_matches_top_level() -> None:
    src = """//@version=6
indicator("t")
f() =>
    close[1]
plot(f(), "out")
"""
    _assert_series_close(_series(src), _shifted(_CLOSE, 1))


def test_udf_open_subscript() -> None:
    src = """//@version=6
indicator("t")
f() =>
    open[1]
plot(f(), "out")
"""
    _assert_series_close(_series(src), _shifted(_OPEN, 1))


def test_udf_volume_subscript() -> None:
    src = """//@version=6
indicator("t")
f() =>
    volume[1]
plot(f(), "out")
"""
    _assert_series_close(_series(src), _shifted(_VOLUME, 1))


def test_udf_hl2_subscript() -> None:
    src = """//@version=6
indicator("t")
f() =>
    hl2[1]
plot(f(), "out")
"""
    _assert_series_close(_series(src), _shifted(_HL2, 1))


def test_udf_time_subscript() -> None:
    src = """//@version=6
indicator("t")
f() =>
    time[1]
plot(f(), "out")
"""
    _assert_series_close(_series(src), _shifted(_TIME, 1))


def test_udf_close_subscript_two() -> None:
    src = """//@version=6
indicator("t")
f() =>
    close[2]
plot(f(), "out")
"""
    _assert_series_close(_series(src), _shifted(_CLOSE, 2))


def test_udf_close_plus_close_subscript() -> None:
    src = """//@version=6
indicator("t")
f() =>
    close + close[1]
plot(f(), "out")
"""
    expected: list[float | None] = [None] + [_CLOSE[i] + _CLOSE[i - 1] for i in range(1, len(_CLOSE))]
    _assert_series_close(_series(src), expected)


def test_udf_local_series_still_tracked_per_call() -> None:
    # ``k`` is assigned in the body and subscripted — it stays a per-call-site
    # series local (must not be mistaken for a host OHLCV free variable).
    src = """//@version=6
indicator("t")
f() =>
    k = close
    k[1]
plot(f(), "out")
"""
    _assert_series_close(_series(src), _shifted(_CLOSE, 1))


def test_udf_unresolved_name_subscript_is_na_not_string_slice() -> None:
    # An unresolvable name must never be sliced as a string ('nope'[1] == 'o').
    src = """//@version=6
indicator("t")
f() =>
    definitelyNotDefined[1]
plot(f(), "out")
"""
    _assert_series_close(_series(src), [None] * len(_CLOSE))


def test_top_level_subscript_unchanged() -> None:
    src = """//@version=6
indicator("t")
plot(close[1], "out")
"""
    _assert_series_close(_series(src), _shifted(_CLOSE, 1))


def test_inline_udf_param_subscript_matches_library_shape() -> None:
    # Regression guard: inline export-style UDF with a subscripted parameter.
    src = """//@version=6
indicator("t")
f(float src) =>
    src[1]
plot(f(close), "out")
"""
    _assert_series_close(_series(src), _shifted(_CLOSE, 1))


def test_global_series_via_local_alias() -> None:
    src = """//@version=6
indicator("t")
x = close
f() =>
    x[1]
plot(f(), "out")
"""
    _assert_series_close(_series(src), _shifted(_CLOSE, 1))


def test_udf_bare_ohlcv_still_resolves() -> None:
    src = """//@version=6
indicator("t")
f() =>
    close
plot(f(), "out")
"""
    _assert_series_close(_series(src), _CLOSE)


# ---------------------------------------------------------------------------
# Bug B — subscripted parameters across the library boundary
# ---------------------------------------------------------------------------

_LIB = {
    "namespace": "user",
    "name": "HistLib",
    "version": 1,
    "source": """//@version=6
library("HistLib")
export shifted(float src) =>
    src[1]
export shifted2(float src) =>
    src[2]
export smoothed(float src) =>
    ta.sma(src, 3)
export smoothed_prev(float src) =>
    ta.sma(src, 3)[1]
export hl2_prev() =>
    hl2[1]
""",
}


def _lib(name: str = "HistLib") -> list[dict]:
    return [dict(_LIB, name=name)]


def test_library_param_subscript_matches_inline() -> None:
    src = """//@version=6
indicator("t")
import user/HistLib/1 as lib
plot(lib.shifted(close), "out")
"""
    _assert_series_close(_series(src, _lib()), _shifted(_CLOSE, 1))


def test_library_param_subscript_offset_two() -> None:
    src = """//@version=6
indicator("t")
import user/HistLib/1 as lib
plot(lib.shifted2(close), "out")
"""
    _assert_series_close(_series(src, _lib()), _shifted(_CLOSE, 2))


def test_library_ta_sma_param_matches_inline() -> None:
    lib_src = """//@version=6
indicator("t")
import user/HistLib/1 as lib
plot(lib.smoothed(close), "out")
"""
    inline_src = """//@version=6
indicator("t")
plot(ta.sma(close, 3), "out")
"""
    lib_out = _series(lib_src, _lib())
    inline_out = _series(inline_src)
    assert len(lib_out) == len(inline_out)
    for i, (a, b) in enumerate(zip(lib_out, inline_out, strict=True)):
        if b is None:
            assert a is None, f"bar {i}: expected na, got {a!r}"
        else:
            assert a is not None, f"bar {i}: expected {b}, got na"
            assert float(a) == pytest.approx(float(b), rel=1e-9, abs=1e-9), f"bar {i}"


def test_library_ta_sma_subscript_matches_inline() -> None:
    lib_src = """//@version=6
indicator("t")
import user/HistLib/1 as lib
plot(lib.smoothed_prev(close), "out")
"""
    inline_src = """//@version=6
indicator("t")
plot(ta.sma(close, 3)[1], "out")
"""
    lib_out = _series(lib_src, _lib())
    inline_out = _series(inline_src)
    assert len(lib_out) == len(inline_out)
    for i, (a, b) in enumerate(zip(lib_out, inline_out, strict=True)):
        if b is None:
            assert a is None, f"bar {i}: expected na, got {a!r}"
        else:
            assert a is not None, f"bar {i}: expected {b}, got na"
            assert float(a) == pytest.approx(float(b), rel=1e-9, abs=1e-9), f"bar {i}"


def test_consumer_local_subscript_still_works() -> None:
    # The documented workaround must keep working (control case).
    src = """//@version=6
indicator("t")
import user/HistLib/1 as lib
x = close
plot(x[1], "out")
"""
    _assert_series_close(_series(src, _lib()), _shifted(_CLOSE, 1))


def test_library_host_series_subscript_inside_body() -> None:
    # Free host series (not a parameter) referenced with [1] inside a library body.
    src = """//@version=6
indicator("t")
import user/HistLib/1 as lib
plot(lib.hl2_prev(), "out")
"""
    _assert_series_close(_series(src, _lib()), _shifted(_HL2, 1))


def test_library_subscript_after_pinned_assignment() -> None:
    # Consumer binds the library result to a var; series must survive both bars.
    src = """//@version=6
indicator("t")
import user/HistLib/1 as lib
var float prev = na
prev := lib.shifted(close)
plot(prev, "out")
"""
    _assert_series_close(_series(src, _lib()), _shifted(_CLOSE, 1))
