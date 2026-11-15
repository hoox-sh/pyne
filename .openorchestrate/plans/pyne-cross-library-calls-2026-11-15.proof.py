# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Assertion proof: cross-library calls between supplied libraries."""

# ruff: noqa: S101, T201

from __future__ import annotations

from typing import Any

from pynescript.runtime import Runtime


_LIB_B = """//@version=6
library("LibB")
export twice(float x) =>
    x * 2
"""

_LIB_A = """//@version=6
library("LibA")
import ns/LibB/1 as b
export add(float x) =>
    b.twice(x) + 1
"""

_SRC_AB = """//@version=6
indicator("cross library")
import ns/LibA/1 as a
plot(a.add(close), "x")
"""

_SRC_BOTH = """//@version=6
indicator("cross library both")
import ns/LibA/1 as a
import ns/LibB/1 as b2
plot(a.add(close), "add")
plot(b2.twice(close), "twice")
"""

_LIB_C = """//@version=6
library("LibC")
export deep(float x) =>
    x + 0.5
"""

_LIB_B_NEST = """//@version=6
library("LibB")
import ns/LibC/1 as c
export twice(float x) =>
    c.deep(x) * 2
"""

_SRC_NEST = """//@version=6
indicator("nested libs")
import ns/LibA/1 as a
plot(a.add(close), "x")
"""

_LIB_A_CYCLE = """//@version=6
library("LibA")
import ns/LibB/1 as b
export add(float x) =>
    b.twice(x) + 1
"""

_LIB_B_CYCLE = """//@version=6
library("LibB")
import ns/LibA/1 as a
export twice(float x) =>
    a.add(x)
"""

_LIB_A_UNKNOWN = """//@version=6
library("LibA")
import ns/LibB/1 as b
export add(float x) =>
    b.missing(x)
"""

# --- alias-collision regressions -------------------------------------------

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

_LIB_PARAM_SHADOW = """//@version=6
library("LibA")
import ns/LibB/1 as b
export add(float b) =>
    b.fn()
"""

# --- previous slices (regression) -------------------------------------------

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

_LIB_UDT = """//@version=6
library("Lib")
export type Box
    float v
export method bump(Box this) =>
    this.v + 1
"""

_SRC_UDT = """//@version=6
indicator("udt")
import ns/Lib/1 as lib
b = lib.Box.new(close)
plot(b.bump(), "x")
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


def _libs(*sources: str) -> list[dict[str, Any]]:
    names = ["LibA", "LibB", "LibC"]
    return [
        {"namespace": "ns", "name": name, "version": 1, "source": source}
        for name, source in zip(names, sources, strict=False)
    ]


def _run(src: str, libraries: list[dict[str, Any]], mode: str = "compile") -> dict[str, Any]:
    return Runtime(symbol="TEST").run(src, _bars(), mode=mode, libraries=libraries)


def _error(out: dict[str, Any], *needles: str) -> str:
    assert out.get("error_kind") == "compile", out.get("error")
    message = str(out.get("error") or "").lower()
    for needle in needles:
        assert needle in message, message
    return message


def main() -> None:
    # 1. A's export calls B's export; compile equals interpret.
    interp = _run(_SRC_AB, _libs(_LIB_A, _LIB_B), mode="interpret")
    compiled = _run(_SRC_AB, _libs(_LIB_A, _LIB_B))
    assert "error" not in interp, interp.get("error")
    assert "error" not in compiled, compiled.get("error")
    assert compiled["series"]["x"] == [202.0, 204.0, 206.0, 208.0]
    assert compiled["series"] == interp["series"]

    # 2. Alias scoping: the consumer's own alias for B coexists with A's.
    both = _run(_SRC_BOTH, _libs(_LIB_A, _LIB_B))
    assert "error" not in both, both.get("error")
    assert both["series"]["add"] == [202.0, 204.0, 206.0, 208.0]
    assert both["series"]["twice"] == [201.0, 203.0, 205.0, 207.0]

    # 3. Two-level nesting (A -> B -> C).
    nest = _run(_SRC_NEST, _libs(_LIB_A, _LIB_B_NEST, _LIB_C))
    assert "error" not in nest, nest.get("error")
    assert nest["series"]["x"] == [203.0, 205.0, 207.0, 209.0]

    # 4. Missing target source fails closed.
    _error(_run(_SRC_AB, _libs(_LIB_A)), "library source not supplied", "libb")

    # 5. A <-> B cycle fails closed.
    _error(_run(_SRC_AB, _libs(_LIB_A_CYCLE, _LIB_B_CYCLE)), "recursive library import", "liba")

    # 6. Unknown export fails closed.
    _error(_run(_SRC_AB, _libs(_LIB_A_UNKNOWN, _LIB_B)), "unsupported library method", "missing")

    # 6b. Two targets that used to share a synthetic alias stay distinct.
    tuple_libs = [
        {"namespace": "ns", "name": "LibA", "version": 1, "source": _LIB_TUPLE_A},
        {"namespace": "a", "name": "b_c", "version": 1, "source": _LIB_TUPLE_B1},
        {"namespace": "a_b", "name": "c", "version": 1, "source": _LIB_TUPLE_B2},
    ]
    tuple_out = _run(_SRC_TUPLE, tuple_libs)
    assert "error" not in tuple_out, tuple_out.get("error")
    assert tuple_out["series"]["x"] == [302.0, 304.0, 306.0, 308.0]

    # 6c. A consumer alias equal to the old synthetic name must not hijack.
    alias_libs = [
        {"namespace": "ns", "name": "LibA", "version": 1, "source": _LIB_CROSS_A_FN},
        {"namespace": "ns", "name": "LibB", "version": 1, "source": _LIB_CROSS_B_FN},
        {"namespace": "ns", "name": "LibD", "version": 1, "source": _LIB_CONSUMER_D},
    ]
    alias_out = _run(_SRC_CONSUMER_ALIAS, alias_libs)
    assert "error" not in alias_out, alias_out.get("error")
    assert alias_out["series"]["add"] == [202.0, 204.0, 206.0, 208.0]
    assert alias_out["series"]["d"] == [200.5, 201.5, 202.5, 203.5]

    # 6d. A parameter shadowing the import alias fails closed.
    _error(_run(_SRC_AB, _libs(_LIB_PARAM_SHADOW, _LIB_CROSS_B_FN)), "unsupported namespace b")

    # 6e. A library's own local alias cannot collide with a synthetic.
    local_libs = [
        {"namespace": "ns", "name": "LibA", "version": 1, "source": _LIB_LOCAL_A},
        {"namespace": "ns", "name": "LibC", "version": 1, "source": _LIB_LOCAL_C},
        {"namespace": "ns", "name": "LibB", "version": 1, "source": _LIB_LOCAL_B},
    ]
    local_out = _run(_SRC_LOCAL_ALIAS, local_libs)
    assert "error" not in local_out, local_out.get("error")
    assert local_out["series"]["x"] == [1202.0, 1204.0, 1206.0, 1208.0]

    # 6f. Incoming __xlib_1 after A fails closed; before A the allocator skips.
    _error(_run(_SRC_INCOMING_AFTER, alias_libs), "import alias __xlib_1 collides")
    before = _run(_SRC_INCOMING_BEFORE, alias_libs)
    assert "error" not in before, before.get("error")
    assert before["series"]["add"] == [202.0, 204.0, 206.0, 208.0]
    assert before["series"]["d"] == [200.5, 201.5, 202.5, 203.5]

    # 7. Previous slices unchanged.
    internal = _run(_SRC_INTERNAL, [{"namespace": "ns", "name": "Lib", "version": 1, "source": _LIB_INTERNAL}])
    assert "error" not in internal, internal.get("error")
    assert internal["series"]["x"] == [202.0, 204.0, 206.0, 208.0]
    udt = _run(_SRC_UDT, [{"namespace": "ns", "name": "Lib", "version": 1, "source": _LIB_UDT}])
    assert "error" not in udt, udt.get("error")
    assert udt["series"]["x"] == [101.5, 102.5, 103.5, 104.5]

    # 8. No supplied library source keeps the legacy stub contract.
    no_lib = Runtime(symbol="TEST").run(_SRC_AB, _bars(), mode="compile")
    assert "error" not in no_lib, no_lib.get("error")

    print(
        "CROSS_LIBRARY_OK call=202.0 alias_add=202.0 alias_twice=201.0 nest=203.0 "
        "missing=1 cycle=1 unknown=1 same_lib=202.0 udt=101.5 "
        "tuple_collision=302.0 consumer_alias=202.0 param_shadow=1 "
        "local_alias=1202.0 incoming_after=1 incoming_before=202.0 no_lib=1"
    )


if __name__ == "__main__":
    main()
