# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Compile inlines simple exported library functions instead of stubbing."""

from __future__ import annotations

import pytest

from pynescript.runtime import Runtime


_LIB = """//@version=6
library("Lib")
export add(float a, float b) =>
    a + b
"""

_SRC = """//@version=6
indicator("inline lib")
import ns/Lib/1 as lib
plot(lib.add(close, 1.0), "sum")
"""

_UNSUPPORTED = """//@version=6
indicator("inline lib")
import ns/Lib/1 as lib
plot(lib.mul(close, 1.0), "mul")
"""


def _bars(n: int = 4) -> list[dict[str, float | int]]:
    return [
        {
            "open": 100.0 + i,
            "high": 101.0 + i,
            "low": 99.0 + i,
            "close": 100.5 + i,
            "volume": 1000.0 + i,
            "time": 1_700_000_000_000 + i * 60_000,
        }
        for i in range(n)
    ]


def _libraries() -> list[dict[str, object]]:
    return [{"namespace": "ns", "name": "Lib", "version": 1, "source": _LIB}]


def test_compile_inlines_exported_library_function() -> None:
    interp = Runtime(symbol="TEST").run(_SRC, _bars(), mode="interpret", libraries=_libraries())
    compiled = Runtime(symbol="TEST").run(_SRC, _bars(), mode="compile", libraries=_libraries())
    assert "error" not in interp, interp.get("error")
    assert "error" not in compiled, compiled.get("error")
    assert compiled["series"]["sum"] == [101.5, 102.5, 103.5, 104.5]
    assert compiled["series"]["sum"] == interp["series"]["sum"]


def test_unsupported_library_function_still_fails_closed() -> None:
    out = Runtime(symbol="TEST").run(_UNSUPPORTED, _bars(), mode="compile", libraries=_libraries())
    assert out.get("error_kind") == "compile"
    message = str(out.get("error") or "").lower()
    assert "unsupported library method" in message
    assert "interpret" in message


def test_same_library_source_two_consumers_do_not_mutate_parse_cache() -> None:
    src2 = """//@version=6
indicator("inline lib 2")
import ns/Lib/1 as lib
plot(lib.add(close, 2.0), "sum")
"""
    first = Runtime(symbol="TEST").run(_SRC, _bars(), mode="compile", libraries=_libraries())
    second = Runtime(symbol="TEST").run(src2, _bars(), mode="compile", libraries=_libraries())
    assert "error" not in first, first.get("error")
    assert "error" not in second, second.get("error")
    assert first["series"]["sum"] == [101.5, 102.5, 103.5, 104.5]
    assert second["series"]["sum"] == [102.5, 103.5, 104.5, 105.5]


_SCRIPT_ADD = """//@version=6
indicator("inline lib")
import ns/Lib/1 as lib
add(float x) =>
    10000.0
plot(lib.add(close, 1.0), "sum")
"""


def test_script_udf_same_name_does_not_capture_alias_call() -> None:
    out = Runtime(symbol="TEST").run(_SCRIPT_ADD, _bars(), mode="compile", libraries=_libraries())
    assert "error" not in out, out.get("error")
    assert out["series"]["sum"] == [101.5, 102.5, 103.5, 104.5]


_LIB_CONST = """//@version=6
library("Lib")
export const float BIAS = 1.0
export add(float a) =>
    a + BIAS
"""


def test_library_constant_use_fails_closed() -> None:
    out = Runtime(symbol="TEST").run(
        _SRC,
        _bars(),
        mode="compile",
        libraries=[{"namespace": "ns", "name": "Lib", "version": 1, "source": _LIB_CONST}],
    )
    assert out.get("error_kind") == "compile"
    assert "unsupported name bias" in str(out.get("error") or "").lower()


_LIB_INTERNAL = """//@version=6
library("Lib")
export add(float a) =>
    helper(a) + 1
helper(float a) =>
    a * 2
"""

_SRC_INTERNAL = """//@version=6
indicator("internal helper")
import ns/Lib/1 as lib
plot(lib.add(close), "x")
"""


def test_library_internal_helper_inlines() -> None:
    interp = Runtime(symbol="TEST").run(
        _SRC_INTERNAL,
        _bars(),
        mode="interpret",
        libraries=[{"namespace": "ns", "name": "Lib", "version": 1, "source": _LIB_INTERNAL}],
    )
    compiled = Runtime(symbol="TEST").run(
        _SRC_INTERNAL,
        _bars(),
        mode="compile",
        libraries=[{"namespace": "ns", "name": "Lib", "version": 1, "source": _LIB_INTERNAL}],
    )
    assert "error" not in interp, interp.get("error")
    assert "error" not in compiled, compiled.get("error")
    assert compiled["series"]["x"] == [202.0, 204.0, 206.0, 208.0]
    assert compiled["series"] == interp["series"]


_LIB_INTERNAL_CHAIN = """//@version=6
library("Lib")
export add(float a) =>
    twice(a) + 1
export twice(float a) =>
    deep(a) * 2
deep(float a) =>
    a + 0.5
"""

_SRC_INTERNAL_CHAIN = """//@version=6
indicator("internal chain")
import ns/Lib/1 as lib
plot(lib.add(close), "add")
plot(lib.twice(close), "twice")
"""


def test_library_internal_chain_and_exported_callee_inline() -> None:
    interp = Runtime(symbol="TEST").run(
        _SRC_INTERNAL_CHAIN,
        _bars(),
        mode="interpret",
        libraries=[{"namespace": "ns", "name": "Lib", "version": 1, "source": _LIB_INTERNAL_CHAIN}],
    )
    compiled = Runtime(symbol="TEST").run(
        _SRC_INTERNAL_CHAIN,
        _bars(),
        mode="compile",
        libraries=[{"namespace": "ns", "name": "Lib", "version": 1, "source": _LIB_INTERNAL_CHAIN}],
    )
    assert "error" not in interp, interp.get("error")
    assert "error" not in compiled, compiled.get("error")
    assert compiled["series"]["add"] == [203.0, 205.0, 207.0, 209.0]
    assert compiled["series"]["twice"] == [202.0, 204.0, 206.0, 208.0]
    assert compiled["series"] == interp["series"]


_LIB_INTERNAL_DEFAULTS = """//@version=6
library("Lib")
export add(float a) =>
    helper(a)
helper(float a, float k = 2.0) =>
    b = a * k
    b + 1
"""


def test_library_internal_helper_defaults_and_locals() -> None:
    out = Runtime(symbol="TEST").run(
        _SRC_INTERNAL,
        _bars(),
        mode="compile",
        libraries=[{"namespace": "ns", "name": "Lib", "version": 1, "source": _LIB_INTERNAL_DEFAULTS}],
    )
    assert "error" not in out, out.get("error")
    assert out["series"]["x"] == [202.0, 204.0, 206.0, 208.0]


_LIB_EXPORT_DEFAULT = """//@version=6
library("Lib")
export helper(float a, float k = 2.0) =>
    a * k
"""

_SRC_EXPORT_DEFAULT = """//@version=6
indicator("export default")
import ns/Lib/1 as lib
plot(lib.helper(close), "x")
"""


def test_exported_library_default_arg_direct_call() -> None:
    """Direct ``lib.helper(close)`` must bind the declared ``k=2.0`` default."""
    libraries = [{"namespace": "ns", "name": "Lib", "version": 1, "source": _LIB_EXPORT_DEFAULT}]
    interp = Runtime(symbol="TEST").run(_SRC_EXPORT_DEFAULT, _bars(), mode="interpret", libraries=libraries)
    compiled = Runtime(symbol="TEST").run(_SRC_EXPORT_DEFAULT, _bars(), mode="compile", libraries=libraries)
    assert "error" not in interp, interp.get("error")
    assert "error" not in compiled, compiled.get("error")
    assert compiled["series"]["x"] == [201.0, 203.0, 205.0, 207.0]
    assert compiled["series"]["x"] == interp["series"]["x"]


_LIB_DEFAULT_A = """//@version=6
library("A")
export scale(float a, float k = 2.0) =>
    a * k
"""

_LIB_DEFAULT_B = """//@version=6
library("B")
import ns/A/1 as a
export twice(float x) =>
    a.scale(x)
"""

_SRC_CROSS_DEFAULT = """//@version=6
indicator("cross default")
import ns/B/1 as b
plot(b.twice(close), "x")
"""


def test_exported_library_default_arg_cross_library_call() -> None:
    """Cross-library ``b.twice(close)`` must bind A's declared ``k=2.0``."""
    libraries = [
        {"namespace": "ns", "name": "A", "version": 1, "source": _LIB_DEFAULT_A},
        {"namespace": "ns", "name": "B", "version": 1, "source": _LIB_DEFAULT_B},
    ]
    interp = Runtime(symbol="TEST").run(_SRC_CROSS_DEFAULT, _bars(), mode="interpret", libraries=libraries)
    compiled = Runtime(symbol="TEST").run(_SRC_CROSS_DEFAULT, _bars(), mode="compile", libraries=libraries)
    assert "error" not in interp, interp.get("error")
    assert "error" not in compiled, compiled.get("error")
    assert compiled["series"]["x"] == [201.0, 203.0, 205.0, 207.0]
    assert compiled["series"]["x"] == interp["series"]["x"]


_LIB_TA_SMA = """//@version=6
library("Lib")
export ind(float src) =>
    ta.sma(src, 3)
"""

_LIB_TA_EMA = """//@version=6
library("Lib")
export ind(float src) =>
    ta.ema(src, 3)
"""

_LIB_TA_RSI = """//@version=6
library("Lib")
export ind(float src) =>
    ta.rsi(src, 3)
"""

_SRC_TA_LIB = """//@version=6
indicator("lib ta")
import ns/Lib/1 as lib
plot(lib.ind(close), "x")
"""


def _ta_libraries(source: str) -> list[dict[str, object]]:
    return [{"namespace": "ns", "name": "Lib", "version": 1, "source": source}]


def _assert_ta_series(actual: list[object], expected: list[object]) -> None:
    assert len(actual) == len(expected)
    for got, want in zip(actual, expected, strict=True):
        if want is None or (isinstance(want, float) and want != want):
            assert got is None or (isinstance(got, float) and got != got), (got, want)
        else:
            assert got == pytest.approx(float(want)), (got, want)


def test_library_ta_sma_inline_matches_interpret() -> None:
    """``ta.sma`` inside an inlined library body matches interpret."""
    interp = Runtime(symbol="TEST").run(
        _SRC_TA_LIB,
        _bars(8),
        mode="interpret",
        libraries=_ta_libraries(_LIB_TA_SMA),
    )
    compiled = Runtime(symbol="TEST").run(
        _SRC_TA_LIB,
        _bars(8),
        mode="compile",
        libraries=_ta_libraries(_LIB_TA_SMA),
    )
    assert "error" not in interp, interp.get("error")
    assert "error" not in compiled, compiled.get("error")
    _assert_ta_series(compiled["series"]["x"], interp["series"]["x"])


def test_library_ta_ema_inline_matches_interpret() -> None:
    """``ta.ema`` inside an inlined library body matches interpret."""
    interp = Runtime(symbol="TEST").run(
        _SRC_TA_LIB,
        _bars(8),
        mode="interpret",
        libraries=_ta_libraries(_LIB_TA_EMA),
    )
    compiled = Runtime(symbol="TEST").run(
        _SRC_TA_LIB,
        _bars(8),
        mode="compile",
        libraries=_ta_libraries(_LIB_TA_EMA),
    )
    assert "error" not in interp, interp.get("error")
    assert "error" not in compiled, compiled.get("error")
    _assert_ta_series(compiled["series"]["x"], interp["series"]["x"])


def test_library_unknown_ta_fails_closed() -> None:
    """A ta.* outside the audited allowlist stays fail-closed."""
    out = Runtime(symbol="TEST").run(
        _SRC_TA_LIB,
        _bars(8),
        mode="compile",
        libraries=_ta_libraries(_LIB_TA_RSI),
    )
    assert out.get("error_kind") == "compile", out
    assert "unsupported ta function ta.rsi" in str(out.get("error") or "").lower()


_LIB_MISSING_REQUIRED = """//@version=6
library("Lib")
export helper(float a, float k) =>
    a * k
"""

_LIB_REQUIRED_BEFORE_DEFAULT = """//@version=6
library("Lib")
export helper(float a, float b, float k = 2.0) =>
    a * b * k
"""

_SRC_LIB_MISSING = """//@version=6
indicator("lib missing")
import ns/Lib/1 as lib
plot(lib.helper(close), "x")
"""


def test_library_missing_required_arg_both_hosts() -> None:
    """Compile preserves the short-call TypeError; interpret stays na."""
    interp = Runtime(symbol="TEST").run(
        _SRC_LIB_MISSING,
        _bars(4),
        mode="interpret",
        libraries=_ta_libraries(_LIB_MISSING_REQUIRED),
    )
    compiled = Runtime(symbol="TEST").run(
        _SRC_LIB_MISSING,
        _bars(4),
        mode="compile",
        libraries=_ta_libraries(_LIB_MISSING_REQUIRED),
    )
    assert "error" not in interp, interp.get("error")
    assert all(v is None for v in interp["series"]["x"])
    assert compiled.get("error_kind") == "runtime", compiled
    message = str(compiled.get("error") or "")
    assert "missing 1 required positional argument" in message, message
    assert "'k'" in message, message


def test_library_required_before_default_both_hosts() -> None:
    """A required arg before a default still raises the short-call TypeError."""
    interp = Runtime(symbol="TEST").run(
        _SRC_LIB_MISSING,
        _bars(4),
        mode="interpret",
        libraries=_ta_libraries(_LIB_REQUIRED_BEFORE_DEFAULT),
    )
    compiled = Runtime(symbol="TEST").run(
        _SRC_LIB_MISSING,
        _bars(4),
        mode="compile",
        libraries=_ta_libraries(_LIB_REQUIRED_BEFORE_DEFAULT),
    )
    assert "error" not in interp, interp.get("error")
    assert all(v is None for v in interp["series"]["x"])
    assert compiled.get("error_kind") == "runtime", compiled
    message = str(compiled.get("error") or "")
    assert "missing 2 required positional arguments" in message, message
    assert "'b'" in message and "'k'" in message, message


_LIB_XLIB_UDT_B = """//@version=6
library("B")
export type Box
    float v
export method bump(Box this) =>
    this.v + 1
"""

_LIB_XLIB_UDT_A = """//@version=6
library("A")
import ns/B/1 as b
export make(float x) =>
    b.Box.new(x).v
export make_bump(float x) =>
    b.Box.new(x).bump()
"""

_LIB_XLIB_UDT_A_ANNOT = """//@version=6
library("A")
import ns/B/1 as b
export make(float x) =>
    b.Box box = b.Box.new(x)
    box.v
"""

_SRC_XLIB_UDT = """//@version=6
indicator("xlib udt")
import ns/A/1 as a
plot(a.make(close), "v")
plot(a.make_bump(close), "b")
"""


def _xlib_udt_libraries(a_source: str) -> list[dict[str, object]]:
    return [
        {"namespace": "ns", "name": "B", "version": 1, "source": _LIB_XLIB_UDT_B},
        {"namespace": "ns", "name": "A", "version": 1, "source": a_source},
    ]


def test_cross_library_udt_constructor_and_method_inline() -> None:
    """A may import B's UDT, construct it, and call its method."""
    interp = Runtime(symbol="TEST").run(
        _SRC_XLIB_UDT,
        _bars(),
        mode="interpret",
        libraries=_xlib_udt_libraries(_LIB_XLIB_UDT_A),
    )
    compiled = Runtime(symbol="TEST").run(
        _SRC_XLIB_UDT,
        _bars(),
        mode="compile",
        libraries=_xlib_udt_libraries(_LIB_XLIB_UDT_A),
    )
    assert "error" not in interp, interp.get("error")
    assert "error" not in compiled, compiled.get("error")
    assert compiled["series"]["v"] == [100.5, 101.5, 102.5, 103.5]
    assert compiled["series"]["b"] == [101.5, 102.5, 103.5, 104.5]
    assert compiled["series"] == interp["series"]


def test_cross_library_udt_type_annotation_fails_closed() -> None:
    """A cross-library UDT type annotation is outside this slice."""
    out = Runtime(symbol="TEST").run(
        _SRC_XLIB_UDT,
        _bars(),
        mode="compile",
        libraries=_xlib_udt_libraries(_LIB_XLIB_UDT_A_ANNOT),
    )
    assert out.get("error_kind") == "compile", out
    message = str(out.get("error") or "").lower()
    assert "unsupported name b" in message
    assert "interpret" in message


_LIB_INTERNAL_UNKNOWN = """//@version=6
library("Lib")
export add(float a) =>
    missing(a)
"""


def test_library_unknown_internal_call_fails_closed() -> None:
    out = Runtime(symbol="TEST").run(
        _SRC_INTERNAL,
        _bars(),
        mode="compile",
        libraries=[{"namespace": "ns", "name": "Lib", "version": 1, "source": _LIB_INTERNAL_UNKNOWN}],
    )
    assert out.get("error_kind") == "compile"
    assert "unsupported function missing" in str(out.get("error") or "").lower()


_LIB_INTERNAL_RECURSIVE = """//@version=6
library("Lib")
export add(float a) =>
    loop(a)
loop(float a) =>
    loop(a) + 1
"""


def test_library_recursive_helper_fails_closed() -> None:
    out = Runtime(symbol="TEST").run(
        _SRC_INTERNAL,
        _bars(),
        mode="compile",
        libraries=[{"namespace": "ns", "name": "Lib", "version": 1, "source": _LIB_INTERNAL_RECURSIVE}],
    )
    assert out.get("error_kind") == "compile"
    assert "recursive library function loop" in str(out.get("error") or "").lower()


_LIB_INTERNAL_UNUSED = """//@version=6
library("Lib")
export add(float a) =>
    a + 1
unused() =>
    ta.sma(close, 14)
"""


def test_library_unreachable_unsupported_helper_is_ignored() -> None:
    out = Runtime(symbol="TEST").run(
        _SRC_INTERNAL,
        _bars(),
        mode="compile",
        libraries=[{"namespace": "ns", "name": "Lib", "version": 1, "source": _LIB_INTERNAL_UNUSED}],
    )
    assert "error" not in out, out.get("error")
    assert out["series"]["x"] == [101.5, 102.5, 103.5, 104.5]


_LIB_DUP_HELPERS = """//@version=6
library("Lib")
export add(float a) =>
    helper(a)
helper(float a) =>
    a * 2
helper(float a, float k) =>
    a * k
"""


def test_library_duplicate_helper_names_fail_closed() -> None:
    out = Runtime(symbol="TEST").run(
        _SRC_INTERNAL,
        _bars(),
        mode="compile",
        libraries=[{"namespace": "ns", "name": "Lib", "version": 1, "source": _LIB_DUP_HELPERS}],
    )
    assert out.get("error_kind") == "compile"
    message = str(out.get("error") or "").lower()
    assert "overloaded library method" in message
    assert "helper" in message
    assert not out.get("series")


_LIB_DUP_EXPORTED_HELPER = """//@version=6
library("Lib")
export add(float a) =>
    dup(a)
export dup(float a) =>
    a * 2
dup(float a) =>
    a * 3
"""


def test_library_duplicate_exported_and_helper_names_fail_closed() -> None:
    out = Runtime(symbol="TEST").run(
        _SRC_INTERNAL,
        _bars(),
        mode="compile",
        libraries=[{"namespace": "ns", "name": "Lib", "version": 1, "source": _LIB_DUP_EXPORTED_HELPER}],
    )
    assert out.get("error_kind") == "compile"
    message = str(out.get("error") or "").lower()
    assert "overloaded library method" in message
    assert "dup" in message
    assert not out.get("series")


_LIB_DUP_EXPORTED_ARITIES = """//@version=6
library("Lib")
export add(float a) =>
    helper(a)
export helper(float a) =>
    a * 2
export helper(float a, float k) =>
    a * k
"""


def test_library_duplicate_exported_arities_fail_closed() -> None:
    out = Runtime(symbol="TEST").run(
        _SRC_INTERNAL,
        _bars(),
        mode="compile",
        libraries=[{"namespace": "ns", "name": "Lib", "version": 1, "source": _LIB_DUP_EXPORTED_ARITIES}],
    )
    assert out.get("error_kind") == "compile"
    message = str(out.get("error") or "").lower()
    assert "overloaded library method" in message
    assert "helper" in message
    assert not out.get("series")


_LIB_HELPER_METHOD_COLLISION = """//@version=6
library("Lib")
export add(float a) =>
    helper(a)
helper(float a) =>
    a * 2
export method helper(float this) =>
    this * 3
"""


def test_library_helper_and_method_same_name_fail_closed() -> None:
    out = Runtime(symbol="TEST").run(
        _SRC_INTERNAL,
        _bars(),
        mode="compile",
        libraries=[{"namespace": "ns", "name": "Lib", "version": 1, "source": _LIB_HELPER_METHOD_COLLISION}],
    )
    assert out.get("error_kind") == "compile"
    message = str(out.get("error") or "").lower()
    assert "overloaded library method" in message
    assert "helper" in message
    assert not out.get("series")


_LIB_BARE_REFERENCE = """//@version=6
library("Lib")
export add(float a) =>
    helper
helper(float a) =>
    a * 2
"""


def test_library_bare_function_reference_fails_closed() -> None:
    out = Runtime(symbol="TEST").run(
        _SRC_INTERNAL,
        _bars(),
        mode="compile",
        libraries=[{"namespace": "ns", "name": "Lib", "version": 1, "source": _LIB_BARE_REFERENCE}],
    )
    assert out.get("error_kind") == "compile"
    assert "uses unsupported name helper" in str(out.get("error") or "").lower()


_LIB_BARE_BUILTIN = """//@version=6
library("Lib")
export add(float a) =>
    abs(a)
"""


def test_library_bare_builtin_call_inlines() -> None:
    out = Runtime(symbol="TEST").run(
        _SRC_INTERNAL,
        _bars(),
        mode="compile",
        libraries=[{"namespace": "ns", "name": "Lib", "version": 1, "source": _LIB_BARE_BUILTIN}],
    )
    assert "error" not in out, out.get("error")
    assert out["series"]["x"] == [100.5, 101.5, 102.5, 103.5]


_LIB_CROSS_B = """//@version=6
library("LibB")
export twice(float x) =>
    x * 2
"""

_LIB_CROSS_A = """//@version=6
library("LibA")
import ns/LibB/1 as b
export add(float x) =>
    b.twice(x) + 1
"""

_SRC_CROSS_AB = """//@version=6
indicator("cross library")
import ns/LibA/1 as a
plot(a.add(close), "x")
"""

_SRC_CROSS_BOTH = """//@version=6
indicator("cross library both")
import ns/LibA/1 as a
import ns/LibB/1 as b2
plot(a.add(close), "add")
plot(b2.twice(close), "twice")
"""


def _cross_libs(*sources: str) -> list[dict[str, object]]:
    names = ["LibA", "LibB"]
    return [
        {"namespace": "ns", "name": name, "version": 1, "source": source}
        for name, source in zip(names, sources, strict=False)
    ]


def test_cross_library_call_inlines() -> None:
    interp = Runtime(symbol="TEST").run(
        _SRC_CROSS_AB, _bars(), mode="interpret", libraries=_cross_libs(_LIB_CROSS_A, _LIB_CROSS_B)
    )
    compiled = Runtime(symbol="TEST").run(
        _SRC_CROSS_AB, _bars(), mode="compile", libraries=_cross_libs(_LIB_CROSS_A, _LIB_CROSS_B)
    )
    assert "error" not in interp, interp.get("error")
    assert "error" not in compiled, compiled.get("error")
    assert compiled["series"]["x"] == [202.0, 204.0, 206.0, 208.0]
    assert compiled["series"] == interp["series"]


def test_cross_library_alias_scoping() -> None:
    out = Runtime(symbol="TEST").run(
        _SRC_CROSS_BOTH, _bars(), mode="compile", libraries=_cross_libs(_LIB_CROSS_A, _LIB_CROSS_B)
    )
    assert "error" not in out, out.get("error")
    assert out["series"]["add"] == [202.0, 204.0, 206.0, 208.0]
    assert out["series"]["twice"] == [201.0, 203.0, 205.0, 207.0]


def test_cross_library_missing_source_fails_closed() -> None:
    out = Runtime(symbol="TEST").run(_SRC_CROSS_AB, _bars(), mode="compile", libraries=_cross_libs(_LIB_CROSS_A))
    assert out.get("error_kind") == "compile"
    message = str(out.get("error") or "").lower()
    assert "library source not supplied" in message
    assert "libb" in message


_LIB_CROSS_A_CYCLE = """//@version=6
library("LibA")
import ns/LibB/1 as b
export add(float x) =>
    b.twice(x) + 1
"""

_LIB_CROSS_B_CYCLE = """//@version=6
library("LibB")
import ns/LibA/1 as a
export twice(float x) =>
    a.add(x)
"""


def test_cross_library_cycle_fails_closed() -> None:
    out = Runtime(symbol="TEST").run(
        _SRC_CROSS_AB, _bars(), mode="compile", libraries=_cross_libs(_LIB_CROSS_A_CYCLE, _LIB_CROSS_B_CYCLE)
    )
    assert out.get("error_kind") == "compile"
    message = str(out.get("error") or "").lower()
    assert "recursive library import" in message
    assert "liba" in message


_LIB_CROSS_A_UNKNOWN = """//@version=6
library("LibA")
import ns/LibB/1 as b
export add(float x) =>
    b.missing(x)
"""


def test_cross_library_unknown_export_fails_closed() -> None:
    out = Runtime(symbol="TEST").run(
        _SRC_CROSS_AB, _bars(), mode="compile", libraries=_cross_libs(_LIB_CROSS_A_UNKNOWN, _LIB_CROSS_B)
    )
    assert out.get("error_kind") == "compile"
    message = str(out.get("error") or "").lower()
    assert "unsupported library method" in message
    assert "missing" in message


_LIB_TUPLE_B1 = """//@version=6
library("b_c")
export fn(float x) =>
    x + 1
"""

_LIB_TUPLE_B2 = """//@version=6
library("c")
export fn(float x) =>
    x + 100
"""

_LIB_TUPLE_A = """//@version=6
library("LibA")
import a/b_c/1 as b1
import a_b/c/1 as b2
export add(float x) =>
    b1.fn(x) + b2.fn(x)
"""

_SRC_TUPLE = """//@version=6
indicator("tuple collision")
import ns/LibA/1 as a
plot(a.add(close), "x")
"""

_LIB_CROSS_B_FN = """//@version=6
library("LibB")
export fn(float x) =>
    x * 2
"""

_LIB_CROSS_A_FN = """//@version=6
library("LibA")
import ns/LibB/1 as b
export add(float x) =>
    b.fn(x) + 1
"""

_LIB_CONSUMER_D = """//@version=6
library("LibD")
export fn(float x) =>
    x + 100
"""

_SRC_CONSUMER_ALIAS = """//@version=6
indicator("consumer alias collision")
import ns/LibA/1 as a
import ns/LibD/1 as __xlib_ns_LibB_1
plot(a.add(close), "add")
plot(__xlib_ns_LibB_1.fn(close), "d")
"""

_LIB_PARAM_SHADOW = """//@version=6
library("LibA")
import ns/LibB/1 as b
export add(float b) =>
    b.fn()
"""


def test_cross_library_synthetic_alias_tuple_collision() -> None:
    libraries = [
        {"namespace": "ns", "name": "LibA", "version": 1, "source": _LIB_TUPLE_A},
        {"namespace": "a", "name": "b_c", "version": 1, "source": _LIB_TUPLE_B1},
        {"namespace": "a_b", "name": "c", "version": 1, "source": _LIB_TUPLE_B2},
    ]
    out = Runtime(symbol="TEST").run(_SRC_TUPLE, _bars(), mode="compile", libraries=libraries)
    assert "error" not in out, out.get("error")
    assert out["series"]["x"] == [302.0, 304.0, 306.0, 308.0]


def test_cross_library_consumer_alias_lookalike_is_scoped() -> None:
    libraries = [
        {"namespace": "ns", "name": "LibA", "version": 1, "source": _LIB_CROSS_A_FN},
        {"namespace": "ns", "name": "LibB", "version": 1, "source": _LIB_CROSS_B_FN},
        {"namespace": "ns", "name": "LibD", "version": 1, "source": _LIB_CONSUMER_D},
    ]
    out = Runtime(symbol="TEST").run(_SRC_CONSUMER_ALIAS, _bars(), mode="compile", libraries=libraries)
    assert "error" not in out, out.get("error")
    assert out["series"]["add"] == [202.0, 204.0, 206.0, 208.0]
    assert out["series"]["d"] == [200.5, 201.5, 202.5, 203.5]


_LIB_LOCAL_C = """//@version=6
library("LibC")
export fn(float x) =>
    x + 1
"""

_LIB_LOCAL_B = """//@version=6
library("LibB")
export fn(float x) =>
    x + 1000
"""

_LIB_LOCAL_A = """//@version=6
library("LibA")
import ns/LibC/1 as c
import ns/LibB/1 as __xlib_1
export add(float x) =>
    c.fn(x) + __xlib_1.fn(x)
"""

_SRC_LOCAL_ALIAS = """//@version=6
indicator("library local alias")
import ns/LibA/1 as a
plot(a.add(close), "x")
"""

_SRC_INCOMING_AFTER = """//@version=6
indicator("incoming alias after")
import ns/LibA/1 as a
import ns/LibD/1 as __xlib_1
plot(a.add(close), "add")
"""

_SRC_INCOMING_BEFORE = """//@version=6
indicator("incoming alias before")
import ns/LibD/1 as __xlib_1
import ns/LibA/1 as a
plot(a.add(close), "add")
plot(__xlib_1.fn(close), "d")
"""


def test_cross_library_local_alias_collision() -> None:
    libraries = [
        {"namespace": "ns", "name": "LibA", "version": 1, "source": _LIB_LOCAL_A},
        {"namespace": "ns", "name": "LibC", "version": 1, "source": _LIB_LOCAL_C},
        {"namespace": "ns", "name": "LibB", "version": 1, "source": _LIB_LOCAL_B},
    ]
    out = Runtime(symbol="TEST").run(_SRC_LOCAL_ALIAS, _bars(), mode="compile", libraries=libraries)
    assert "error" not in out, out.get("error")
    assert out["series"]["x"] == [1202.0, 1204.0, 1206.0, 1208.0]


def test_cross_library_incoming_alias_after_a_fails_closed() -> None:
    libraries = [
        {"namespace": "ns", "name": "LibA", "version": 1, "source": _LIB_CROSS_A_FN},
        {"namespace": "ns", "name": "LibB", "version": 1, "source": _LIB_CROSS_B_FN},
        {"namespace": "ns", "name": "LibD", "version": 1, "source": _LIB_CONSUMER_D},
    ]
    out = Runtime(symbol="TEST").run(_SRC_INCOMING_AFTER, _bars(), mode="compile", libraries=libraries)
    assert out.get("error_kind") == "compile"
    message = str(out.get("error") or "").lower()
    assert "import alias __xlib_1 collides" in message
    assert not out.get("series")


def test_cross_library_incoming_alias_before_a_is_skipped() -> None:
    libraries = [
        {"namespace": "ns", "name": "LibA", "version": 1, "source": _LIB_CROSS_A_FN},
        {"namespace": "ns", "name": "LibB", "version": 1, "source": _LIB_CROSS_B_FN},
        {"namespace": "ns", "name": "LibD", "version": 1, "source": _LIB_CONSUMER_D},
    ]
    out = Runtime(symbol="TEST").run(_SRC_INCOMING_BEFORE, _bars(), mode="compile", libraries=libraries)
    assert "error" not in out, out.get("error")
    assert out["series"]["add"] == [202.0, 204.0, 206.0, 208.0]
    assert out["series"]["d"] == [200.5, 201.5, 202.5, 203.5]


def test_cross_library_parameter_shadowing_fails_closed() -> None:
    out = Runtime(symbol="TEST").run(
        _SRC_CROSS_AB,
        _bars(),
        mode="compile",
        libraries=_cross_libs(_LIB_PARAM_SHADOW, _LIB_CROSS_B_FN),
    )
    assert out.get("error_kind") == "compile"
    message = str(out.get("error") or "").lower()
    assert "unsupported namespace b" in message
    assert not out.get("series")


def test_library_nopython_recovery_passes_libraries(monkeypatch) -> None:
    """Object-mode recovery must re-emit with libraries and no disk IR key."""
    from types import SimpleNamespace

    from pynescript.compiler import engine

    class TypingError(Exception):
        pass

    class FakeCompiled:
        object_mode = False

        def execute(self, *_args, **_kwargs):
            raise TypingError("cannot determine Numba type")

    seen: dict[str, object] = {}

    def fake_transpile(source, *, force_object_mode=False, libraries=None):
        seen["libraries"] = libraries
        seen["force_object_mode"] = force_object_mode
        return ("code", [], ["plot"], True, [])

    def fake_exec(source, code, titles, object_mode, *, ir_key=None, **kwargs):
        seen["ir_key"] = ir_key
        return SimpleNamespace(object_mode=True)

    monkeypatch.setattr(engine, "_transpile_once", fake_transpile)
    monkeypatch.setattr(engine, "_exec_generated", fake_exec)

    libraries = [{"namespace": "ns", "name": "Lib", "version": 1, "source": _LIB}]
    recovered, _ = engine._warm_numeric_or_fallback(
        "src",
        FakeCompiled(),
        ir_key="ir",
        libraries=libraries,
    )
    assert seen["libraries"] is libraries
    assert seen["force_object_mode"] is True
    assert seen["ir_key"] is None
    assert recovered.object_mode is True


_LIB_PLOT = """//@version=6
library("Lib")
export plot(float a) =>
    a + 1
"""

_SRC_LIB_PLOT = """//@version=6
indicator("inline plot")
import ns/Lib/1 as lib
plot(lib.plot(close), "x")
"""

_LIB_ALERT = """//@version=6
library("Lib")
export alert(float a) =>
    a + 1
"""

_SRC_LIB_ALERT = """//@version=6
indicator("inline alert")
import ns/Lib/1 as lib
plot(lib.alert(close), "x")
"""


def test_library_export_named_plot_is_not_builtin_plot() -> None:
    out = Runtime(symbol="TEST").run(
        _SRC_LIB_PLOT,
        _bars(),
        mode="compile",
        libraries=[{"namespace": "ns", "name": "Lib", "version": 1, "source": _LIB_PLOT}],
    )
    assert "error" not in out, out.get("error")
    assert out["series"]["x"] == [101.5, 102.5, 103.5, 104.5]


def test_library_export_named_alert_is_not_builtin_alert() -> None:
    out = Runtime(symbol="TEST").run(
        _SRC_LIB_ALERT,
        _bars(),
        mode="compile",
        libraries=[{"namespace": "ns", "name": "Lib", "version": 1, "source": _LIB_ALERT}],
    )
    assert "error" not in out, out.get("error")
    assert out["series"]["x"] == [101.5, 102.5, 103.5, 104.5]


_LIB_METHOD = """//@version=6
library("Lib")
export method scale(float this, float factor) =>
    this * factor
"""

_SRC_LIB_METHOD = """//@version=6
indicator("inline method")
import ns/Lib/1 as lib
plot(lib.scale(close, 2.0), "x")
"""

_LIB_UDT_METHOD = """//@version=6
library("Lib")
export type Box
    float v
export method bump(Box this) =>
    this.v + 1
"""

_SRC_LIB_UDT_METHOD = """//@version=6
indicator("inline udt method")
import ns/Lib/1 as lib
plot(lib.bump(close), "x")
"""


def test_library_scalar_receiver_method_inlines() -> None:
    out = Runtime(symbol="TEST").run(
        _SRC_LIB_METHOD,
        _bars(),
        mode="compile",
        libraries=[{"namespace": "ns", "name": "Lib", "version": 1, "source": _LIB_METHOD}],
    )
    assert "error" not in out, out.get("error")
    assert out["series"]["x"] == [201.0, 203.0, 205.0, 207.0]


_LIB_UDT = """//@version=6
library("Lib")
export type Box
    float v
    float pad = 2.0
export method bump(Box this) =>
    this.v + 1
"""

_SRC_LIB_UDT = """//@version=6
indicator("inline udt")
import ns/Lib/1 as lib
b = lib.Box.new(close)
plot(b.v, "v")
plot(b.pad, "pad")
plot(b.bump(), "b")
"""

_SRC_LIB_UDT_ALIAS_CALL = """//@version=6
indicator("inline udt alias")
import ns/Lib/1 as lib
b = lib.Box.new(close)
plot(lib.bump(b), "b")
"""


def _lib_udt(source: str = _LIB_UDT) -> list[dict[str, object]]:
    return [{"namespace": "ns", "name": "Lib", "version": 1, "source": source}]


def test_library_udt_type_constructor_and_method_inline() -> None:
    interp = Runtime(symbol="TEST").run(_SRC_LIB_UDT, _bars(), mode="interpret", libraries=_lib_udt())
    compiled = Runtime(symbol="TEST").run(_SRC_LIB_UDT, _bars(), mode="compile", libraries=_lib_udt())
    assert "error" not in interp, interp.get("error")
    assert "error" not in compiled, compiled.get("error")
    assert compiled["series"]["v"] == [100.5, 101.5, 102.5, 103.5]
    assert compiled["series"]["pad"] == [2.0, 2.0, 2.0, 2.0]
    assert compiled["series"]["b"] == [101.5, 102.5, 103.5, 104.5]
    assert compiled["series"] == interp["series"]


_LIB_UDT_ARITH_DEFAULT = """//@version=6
library("Lib")
export type Box
    float v
    float pad = 1 + 1
"""

_SRC_LIB_UDT_ARITH_DEFAULT = """//@version=6
indicator("udt arith default")
import ns/Lib/1 as lib
b = lib.Box.new(close)
plot(b.pad, "pad")
"""


def test_library_udt_arithmetic_field_default_matches_interpret() -> None:
    """Pure literal arithmetic (``1 + 1``) binds as the omitted field."""
    libraries = _lib_udt(_LIB_UDT_ARITH_DEFAULT)
    interp = Runtime(symbol="TEST").run(_SRC_LIB_UDT_ARITH_DEFAULT, _bars(), mode="interpret", libraries=libraries)
    compiled = Runtime(symbol="TEST").run(_SRC_LIB_UDT_ARITH_DEFAULT, _bars(), mode="compile", libraries=libraries)
    assert "error" not in interp, interp.get("error")
    assert "error" not in compiled, compiled.get("error")
    assert compiled["series"]["pad"] == [2.0, 2.0, 2.0, 2.0]
    assert compiled["series"] == interp["series"]


def test_library_udt_method_alias_form_inlines() -> None:
    out = Runtime(symbol="TEST").run(_SRC_LIB_UDT_ALIAS_CALL, _bars(), mode="compile", libraries=_lib_udt())
    assert "error" not in out, out.get("error")
    assert out["series"]["b"] == [101.5, 102.5, 103.5, 104.5]


_LIB_UDT_PARAM_FN = """//@version=6
library("Lib")
export type Box
    float v
export twice(Box b) =>
    b.v * 2
"""

_SRC_LIB_UDT_TYPED = """//@version=6
indicator("inline udt typed")
import ns/Lib/1 as lib
lib.Box b = lib.Box.new(close)
plot(b.v, "v")
plot(lib.twice(b), "x")
"""


def test_library_udt_typed_declaration_and_udt_param_inline() -> None:
    interp = Runtime(symbol="TEST").run(
        _SRC_LIB_UDT_TYPED, _bars(), mode="interpret", libraries=_lib_udt(_LIB_UDT_PARAM_FN)
    )
    compiled = Runtime(symbol="TEST").run(
        _SRC_LIB_UDT_TYPED, _bars(), mode="compile", libraries=_lib_udt(_LIB_UDT_PARAM_FN)
    )
    assert "error" not in interp, interp.get("error")
    assert "error" not in compiled, compiled.get("error")
    assert compiled["series"]["v"] == [100.5, 101.5, 102.5, 103.5]
    assert compiled["series"]["x"] == [201.0, 203.0, 205.0, 207.0]
    assert compiled["series"] == interp["series"]


_LIB_UDT_COLOR = """//@version=6
library("Lib")
export type C
    color c
    float v
export method col(C this) =>
    this.v + 1
"""

_SRC_LIB_UDT_COLOR = """//@version=6
indicator("inline udt color")
import ns/Lib/1 as lib
x = lib.C.new(color.red, close)
plot(x.col(), "x")
"""


def test_library_udt_color_field_variable_is_not_stringy() -> None:
    interp = Runtime(symbol="TEST").run(
        _SRC_LIB_UDT_COLOR, _bars(), mode="interpret", libraries=_lib_udt(_LIB_UDT_COLOR)
    )
    compiled = Runtime(symbol="TEST").run(
        _SRC_LIB_UDT_COLOR, _bars(), mode="compile", libraries=_lib_udt(_LIB_UDT_COLOR)
    )
    assert "error" not in interp, interp.get("error")
    assert "error" not in compiled, compiled.get("error")
    assert compiled["series"]["x"] == [101.5, 102.5, 103.5, 104.5]
    assert compiled["series"] == interp["series"]


_LIB_UDT_BUILTIN_NAME = """//@version=6
library("Lib")
export type Box
    float v
export method plot(Box this) =>
    this.v + 1
"""

_SRC_LIB_UDT_BUILTIN_NAME = """//@version=6
indicator("inline udt builtin name")
import ns/Lib/1 as lib
b = lib.Box.new(close)
plot(b.plot(), "x")
"""

_SRC_LIB_UDT_BUILTIN_NAME_ALIAS = """//@version=6
indicator("inline udt builtin name alias")
import ns/Lib/1 as lib
b = lib.Box.new(close)
plot(lib.plot(b), "x")
"""


def test_library_udt_method_named_like_builtin_dispatches() -> None:
    out = Runtime(symbol="TEST").run(
        _SRC_LIB_UDT_BUILTIN_NAME, _bars(), mode="compile", libraries=_lib_udt(_LIB_UDT_BUILTIN_NAME)
    )
    assert "error" not in out, out.get("error")
    assert out["series"]["x"] == [101.5, 102.5, 103.5, 104.5]

    alias_out = Runtime(symbol="TEST").run(
        _SRC_LIB_UDT_BUILTIN_NAME_ALIAS, _bars(), mode="compile", libraries=_lib_udt(_LIB_UDT_BUILTIN_NAME)
    )
    assert "error" not in alias_out, alias_out.get("error")
    assert alias_out["series"]["x"] == [101.5, 102.5, 103.5, 104.5]


def test_library_udt_method_named_like_builtin_dispatches_interpret() -> None:
    out = Runtime(symbol="TEST").run(
        _SRC_LIB_UDT_BUILTIN_NAME, _bars(), mode="interpret", libraries=_lib_udt(_LIB_UDT_BUILTIN_NAME)
    )
    assert "error" not in out, out.get("error")
    assert out["series"]["x"] == [101.5, 102.5, 103.5, 104.5]

    alias_out = Runtime(symbol="TEST").run(
        _SRC_LIB_UDT_BUILTIN_NAME_ALIAS, _bars(), mode="interpret", libraries=_lib_udt(_LIB_UDT_BUILTIN_NAME)
    )
    assert "error" not in alias_out, alias_out.get("error")
    assert alias_out["series"]["x"] == [101.5, 102.5, 103.5, 104.5]


_LIB_UDT_NESTED = """//@version=6
library("Lib")
export type Inner
    float x
export type Outer
    Inner inner
"""

_SRC_LIB_UDT_NESTED = """//@version=6
indicator("nested udt")
import ns/Lib/1 as lib
o = lib.Outer.new(1.0)
plot(o.inner, "x")
"""


def test_library_udt_with_udt_field_fails_closed() -> None:
    out = Runtime(symbol="TEST").run(_SRC_LIB_UDT_NESTED, _bars(), mode="compile", libraries=_lib_udt(_LIB_UDT_NESTED))
    assert out.get("error_kind") == "compile"
    message = str(out.get("error") or "").lower()
    assert "outer" in message
    assert "interpret" in message


_SRC_SCRIPT_TYPE_COLLISION = """//@version=6
indicator("collision")
import ns/Lib/1 as lib
type Box
    float w
plot(lib.Box.new(close).v, "v")
"""


def test_script_type_colliding_with_library_type_fails_closed() -> None:
    out = Runtime(symbol="TEST").run(_SRC_SCRIPT_TYPE_COLLISION, _bars(), mode="compile", libraries=_lib_udt())
    assert out.get("error_kind") == "compile"
    message = str(out.get("error") or "").lower()
    assert "box" in message
    assert "collides" in message


_LIB_UDT_UNSUPPORTED_BODY = """//@version=6
library("Lib")
export type Box
    float v
export const float BIAS = 1.0
export method bump(Box this) =>
    this.v + BIAS
"""


def test_library_udt_method_unsupported_body_fails_closed() -> None:
    out = Runtime(symbol="TEST").run(
        _SRC_LIB_UDT, _bars(), mode="compile", libraries=_lib_udt(_LIB_UDT_UNSUPPORTED_BODY)
    )
    assert out.get("error_kind") == "compile"
    message = str(out.get("error") or "").lower()
    assert "bump" in message
    assert "unsupported name bias" in message


def test_library_udt_method_wrong_receiver_fails_closed() -> None:
    alias_out = Runtime(symbol="TEST").run(
        _SRC_LIB_UDT_METHOD, _bars(), mode="compile", libraries=_lib_udt(_LIB_UDT_METHOD)
    )
    assert alias_out.get("error_kind") == "compile"
    assert "receiver" in str(alias_out.get("error") or "").lower()

    instance_src = """//@version=6
indicator("inline udt wrong receiver")
import ns/Lib/1 as lib
plot(close.bump(), "b")
"""
    instance_out = Runtime(symbol="TEST").run(
        instance_src, _bars(), mode="compile", libraries=_lib_udt(_LIB_UDT_METHOD)
    )
    assert instance_out.get("error_kind") == "compile"
    assert "receiver" in str(instance_out.get("error") or "").lower()


_LIB_METHOD_OVERLOAD = """//@version=6
library("Lib")
type Box
    float v
export method scale(float this, float k) =>
    this * k
export method scale(Box this) =>
    this.v
"""

_SRC_LIB_METHOD_OVERLOAD = """//@version=6
indicator("inline method overload")
import ns/Lib/1 as lib
plot(lib.scale(close, 2.0), "x")
"""


def test_scalar_and_udt_method_overload_fails_closed() -> None:
    out = Runtime(symbol="TEST").run(
        _SRC_LIB_METHOD_OVERLOAD,
        _bars(),
        mode="compile",
        libraries=[{"namespace": "ns", "name": "Lib", "version": 1, "source": _LIB_METHOD_OVERLOAD}],
    )
    assert out.get("error_kind") == "compile"
    message = str(out.get("error") or "").lower()
    assert "overloaded library method" in message
    assert "scale" in message


_LIB_KW = """//@version=6
library("Lib")
export mix(float a, float k = 2.0, float m = 10.0) =>
    a * k + m
"""

_SRC_LIB_KW = """//@version=6
indicator("lib kw")
import ns/Lib/1 as lib
plot(lib.mix(close, m=1.0), "skip")
plot(lib.mix(a=close, k=4.0), "named")
"""


def test_library_call_keyword_arg_matches_interpret() -> None:
    """Inlined ``lib.mix`` keyword args bind by name and keep other defaults."""
    libraries = [{"namespace": "ns", "name": "Lib", "version": 1, "source": _LIB_KW}]
    interp = Runtime(symbol="TEST").run(_SRC_LIB_KW, _bars(), mode="interpret", libraries=libraries)
    compiled = Runtime(symbol="TEST").run(_SRC_LIB_KW, _bars(), mode="compile", libraries=libraries)
    assert "error" not in interp, interp.get("error")
    assert "error" not in compiled, compiled.get("error")
    # close * k + m. ``m=1.0`` leaves k at 2.0; ``k=4.0`` leaves m at 10.0.
    assert compiled["series"]["skip"] == [202.0, 204.0, 206.0, 208.0]
    assert compiled["series"]["named"] == [412.0, 416.0, 420.0, 424.0]
    assert compiled["series"] == interp["series"]
