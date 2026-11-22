# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Assertion proof: exported library UDT type, constructor and receiver method."""

# ruff: noqa: S101, T201

from __future__ import annotations

from typing import Any

from pynescript.runtime import Runtime


_LIB_UDT = """//@version=6
library("Lib")
export type Box
    float v
    float pad = 2.0
export method bump(Box this) =>
    this.v + 1
"""

_SRC_UDT = """//@version=6
indicator("inline udt")
import ns/Lib/1 as lib
b = lib.Box.new(close)
plot(b.v, "v")
plot(b.pad, "pad")
plot(b.bump(), "b")
"""

_SRC_UDT_ALIAS = """//@version=6
indicator("inline udt alias")
import ns/Lib/1 as lib
b = lib.Box.new(close)
plot(lib.bump(b), "b")
"""

_SRC_UDT_WRONG_RECEIVER = """//@version=6
indicator("inline udt wrong receiver")
import ns/Lib/1 as lib
plot(lib.bump(close), "b")
"""

_SRC_UDT_WRONG_RECEIVER_INSTANCE = """//@version=6
indicator("inline udt wrong receiver instance")
import ns/Lib/1 as lib
plot(close.bump(), "b")
"""

_LIB_UDT_NESTED = """//@version=6
library("Lib")
export type Inner
    float x
export type Outer
    Inner inner
"""

_SRC_UDT_NESTED = """//@version=6
indicator("nested udt")
import ns/Lib/1 as lib
o = lib.Outer.new(1.0)
plot(o.inner, "x")
"""

_SRC_SCRIPT_TYPE_COLLISION = """//@version=6
indicator("collision")
import ns/Lib/1 as lib
type Box
    float w
plot(lib.Box.new(close).v, "v")
"""

_LIB_UDT_BODY = """//@version=6
library("Lib")
export type Box
    float v
export const float BIAS = 1.0
export method bump(Box this) =>
    this.v + BIAS
"""

_LIB_UDT_COLOR = """//@version=6
library("Lib")
export type C
    color c
    float v
export method col(C this) =>
    this.v + 1
"""

_SRC_UDT_COLOR = """//@version=6
indicator("inline udt color")
import ns/Lib/1 as lib
x = lib.C.new(color.red, close)
plot(x.col(), "x")
"""

_LIB_UDT_BUILTIN_NAME = """//@version=6
library("Lib")
export type Box
    float v
export method plot(Box this) =>
    this.v + 1
"""

_SRC_UDT_BUILTIN_NAME = """//@version=6
indicator("inline udt builtin name")
import ns/Lib/1 as lib
b = lib.Box.new(close)
plot(b.plot(), "x")
"""

# --- regressions from the previous slices -----------------------------------

_LIB_FREE = """//@version=6
library("Lib")
export add(float a, float b) =>
    a + b
"""

_SRC_FREE = """//@version=6
indicator("inline lib")
import ns/Lib/1 as lib
plot(lib.add(close, 1.0), "sum")
"""

_LIB_SCALAR_METHOD = """//@version=6
library("Lib")
export method scale(float this, float factor) =>
    this * factor
"""

_SRC_SCALAR_METHOD = """//@version=6
indicator("inline method")
import ns/Lib/1 as lib
plot(lib.scale(close, 2.0), "x")
"""

_LIB_METHOD_OVERLOAD = """//@version=6
library("Lib")
type Box
    float v
export method scale(float this, float k) =>
    this * k
export method scale(Box this) =>
    this.v
"""

_SRC_METHOD_OVERLOAD = """//@version=6
indicator("inline method overload")
import ns/Lib/1 as lib
plot(lib.scale(close, 2.0), "x")
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


def _libs(source: str = _LIB_UDT) -> list[dict[str, Any]]:
    return [{"namespace": "ns", "name": "Lib", "version": 1, "source": source}]


def _run(src: str, source: str = _LIB_UDT, mode: str = "compile") -> dict[str, Any]:
    return Runtime(symbol="TEST").run(src, _bars(), mode=mode, libraries=_libs(source))


def _error(out: dict[str, Any], *needles: str) -> str:
    assert out.get("error_kind") == "compile", out.get("error")
    message = str(out.get("error") or "").lower()
    for needle in needles:
        assert needle in message, message
    return message


def main() -> None:
    # 1. Type + constructor + field default + UDT-receiver method.
    interp = _run(_SRC_UDT, mode="interpret")
    compiled = _run(_SRC_UDT)
    assert "error" not in interp, interp.get("error")
    assert "error" not in compiled, compiled.get("error")
    assert compiled["series"]["v"] == [100.5, 101.5, 102.5, 103.5]
    assert compiled["series"]["pad"] == [2.0, 2.0, 2.0, 2.0]
    assert compiled["series"]["b"] == [101.5, 102.5, 103.5, 104.5]
    assert compiled["series"] == interp["series"]

    # 2. Alias form ``lib.method(instance)``.
    alias = _run(_SRC_UDT_ALIAS)
    assert "error" not in alias, alias.get("error")
    assert alias["series"]["b"] == [101.5, 102.5, 103.5, 104.5]

    # 3. Non-scalar field: constructor fails closed with the reason.
    _error(_run(_SRC_UDT_NESTED, _LIB_UDT_NESTED), "outer", "non-scalar type inner", "interpret")

    # 4. Script type colliding with an imported library type.
    _error(_run(_SRC_SCRIPT_TYPE_COLLISION), "box", "collides")

    # 5. UDT method body outside the allowlist.
    _error(_run(_SRC_UDT, _LIB_UDT_BODY), "bump", "unsupported name bias")

    # 6. Wrong receiver, alias and instance forms.
    _error(_run(_SRC_UDT_WRONG_RECEIVER), "receiver")
    _error(_run(_SRC_UDT_WRONG_RECEIVER_INSTANCE), "receiver")

    # 7. Checker C3: a color field must not make the UDT variable stringy.
    color = _run(_SRC_UDT_COLOR, _LIB_UDT_COLOR)
    assert "error" not in color, color.get("error")
    assert color["series"]["x"] == [101.5, 102.5, 103.5, 104.5]

    # 8. Checker C4: an instance method named like a builtin must win.
    builtin_name = _run(_SRC_UDT_BUILTIN_NAME, _LIB_UDT_BUILTIN_NAME)
    assert "error" not in builtin_name, builtin_name.get("error")
    assert builtin_name["series"]["x"] == [101.5, 102.5, 103.5, 104.5]

    # 9. Regression: free-function inlining and parse-cache isolation.
    free = _run(_SRC_FREE, _LIB_FREE)
    assert "error" not in free, free.get("error")
    assert free["series"]["sum"] == [101.5, 102.5, 103.5, 104.5]
    free2 = _run(
        """//@version=6
indicator("inline lib 2")
import ns/Lib/1 as lib
plot(lib.add(close, 2.0), "sum")
""",
        _LIB_FREE,
    )
    assert "error" not in free2, free2.get("error")
    assert free2["series"]["sum"] == [102.5, 103.5, 104.5, 105.5]

    # 10. Regression: scalar-receiver method and scalar+UDT overload fail-closed.
    scalar = _run(_SRC_SCALAR_METHOD, _LIB_SCALAR_METHOD)
    assert "error" not in scalar, scalar.get("error")
    assert scalar["series"]["x"] == [201.0, 203.0, 205.0, 207.0]
    _error(_run(_SRC_METHOD_OVERLOAD, _LIB_METHOD_OVERLOAD), "overloaded library method")

    # 11. Regression: no supplied library source keeps the legacy stub contract.
    no_lib = Runtime(symbol="TEST").run(_SRC_UDT, _bars(), mode="compile")
    assert "error" not in no_lib, no_lib.get("error")

    print(
        "LIBRARY_UDT_OK ctor=1 field=100.5 default=2.0 method=101.5 alias=101.5 "
        "nested=1 collision=1 body=1 receiver=1 color=101.5 builtin_name=101.5 "
        "free=101.5 scalar_method=201.0 overload=1 parse_cache=1 no_lib=1"
    )


if __name__ == "__main__":
    main()
