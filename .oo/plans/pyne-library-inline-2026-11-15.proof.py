# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Assertion proof for minimal exported-library function inlining."""

# ruff: noqa: S101, T201

from __future__ import annotations

from typing import Any

from pynescript.runtime import Runtime


_LIB = """//@version=6
library("Lib")
export add(float a, float b) =>
    a + b
"""

_LIB2 = """//@version=6
library("Lib")
export add(float a, float b) =>
    a - b
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

_SRC2 = """//@version=6
indicator("inline lib 2")
import ns/Lib/1 as lib
plot(lib.add(close, 2.0), "sum")
"""

_SCRIPT_ADD = """//@version=6
indicator("inline lib")
import ns/Lib/1 as lib
add(float x) =>
    10000.0
plot(lib.add(close, 1.0), "sum")
"""

_LIB_CONST = """//@version=6
library("Lib")
export const float BIAS = 1.0
export add(float a) =>
    a + BIAS
"""

_LIB_INTERNAL_CALL = """//@version=6
library("Lib")
export helper(float a) =>
    a
export add(float a) =>
    helper(a)
"""

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
type Box
    float v
export method bump(Box this) =>
    this.v + 1
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

_SRC_LIB_METHOD_OVERLOAD = """//@version=6
indicator("inline method overload")
import ns/Lib/1 as lib
plot(lib.scale(close, 2.0), "x")
"""


_SRC_LIB_UDT_METHOD = """//@version=6
indicator("inline udt method")
import ns/Lib/1 as lib
plot(lib.bump(close), "x")
"""


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


def _libs(source: str = _LIB) -> list[dict[str, Any]]:
    return [{"namespace": "ns", "name": "Lib", "version": 1, "source": source}]


def main() -> None:
    interp = Runtime(symbol="TEST").run(_SRC, _bars(), mode="interpret", libraries=_libs())
    compiled = Runtime(symbol="TEST").run(_SRC, _bars(), mode="compile", libraries=_libs())
    assert "error" not in interp, interp.get("error")
    assert "error" not in compiled, compiled.get("error")
    assert compiled["series"]["sum"] == [101.5, 102.5, 103.5, 104.5]
    assert compiled["series"]["sum"] == interp["series"]["sum"]

    # Parse-cache safety: a second consumer with the same library source.
    reuse = Runtime(symbol="TEST").run(_SRC2, _bars(), mode="compile", libraries=_libs())
    assert "error" not in reuse, reuse.get("error")
    assert reuse["series"]["sum"] == [102.5, 103.5, 104.5, 105.5]

    # Different source for the same import identity must not reuse the first IR.
    compiled2 = Runtime(symbol="TEST").run(_SRC, _bars(), mode="compile", libraries=_libs(_LIB2))
    assert "error" not in compiled2, compiled2.get("error")
    assert compiled2["series"]["sum"] == [99.5, 100.5, 101.5, 102.5]

    # A script UDF named ``add`` must not capture ``lib.add``.
    same_name = Runtime(symbol="TEST").run(_SCRIPT_ADD, _bars(), mode="compile", libraries=_libs())
    assert "error" not in same_name, same_name.get("error")
    assert same_name["series"]["sum"] == [101.5, 102.5, 103.5, 104.5]

    unsupported = Runtime(symbol="TEST").run(
        _UNSUPPORTED,
        _bars(),
        mode="compile",
        libraries=_libs(),
    )
    assert unsupported.get("error_kind") == "compile", unsupported.get("error")
    assert "unsupported library method" in str(unsupported.get("error") or "").lower()

    const_lib = Runtime(symbol="TEST").run(
        _SRC,
        _bars(),
        mode="compile",
        libraries=_libs(_LIB_CONST),
    )
    assert const_lib.get("error_kind") == "compile", const_lib.get("error")
    assert "unsupported name bias" in str(const_lib.get("error") or "").lower()

    internal_call = Runtime(symbol="TEST").run(
        _SRC,
        _bars(),
        mode="compile",
        libraries=_libs(_LIB_INTERNAL_CALL),
    )
    assert internal_call.get("error_kind") == "compile", internal_call.get("error")
    assert "unsupported function helper" in str(internal_call.get("error") or "").lower()

    # Builtin-named exports must resolve as library calls, not builtins.
    plot_lib = Runtime(symbol="TEST").run(
        _SRC_LIB_PLOT,
        _bars(),
        mode="compile",
        libraries=_libs(_LIB_PLOT),
    )
    assert "error" not in plot_lib, plot_lib.get("error")
    assert plot_lib["series"]["x"] == [101.5, 102.5, 103.5, 104.5]

    alert_lib = Runtime(symbol="TEST").run(
        _SRC_LIB_ALERT,
        _bars(),
        mode="compile",
        libraries=_libs(_LIB_ALERT),
    )
    assert "error" not in alert_lib, alert_lib.get("error")
    assert alert_lib["series"]["x"] == [101.5, 102.5, 103.5, 104.5]

    method = Runtime(symbol="TEST").run(
        _SRC_LIB_METHOD,
        _bars(),
        mode="compile",
        libraries=_libs(_LIB_METHOD),
    )
    assert "error" not in method, method.get("error")
    assert method["series"]["x"] == [201.0, 203.0, 205.0, 207.0]

    udt_method = Runtime(symbol="TEST").run(
        _SRC_LIB_UDT_METHOD,
        _bars(),
        mode="compile",
        libraries=_libs(_LIB_UDT_METHOD),
    )
    assert udt_method.get("error_kind") == "compile", udt_method.get("error")
    assert "unsupported library method" in str(udt_method.get("error") or "").lower()

    method_overload = Runtime(symbol="TEST").run(
        _SRC_LIB_METHOD_OVERLOAD,
        _bars(),
        mode="compile",
        libraries=_libs(_LIB_METHOD_OVERLOAD),
    )
    assert method_overload.get("error_kind") == "compile", method_overload.get("error")
    assert "overloaded library method" in str(method_overload.get("error") or "").lower()

    # No supplied library source: preserve the legacy stub/no-raise contract.
    no_lib = Runtime(symbol="TEST").run(_SRC, _bars(), mode="compile")
    assert "error" not in no_lib, no_lib.get("error")

    print(
        "LIBRARY_INLINE_OK sum=101.5 reuse=1 same_name=1 const=1 internal=1 "
        "plot_collision=1 alert_collision=1 method=201.0 udt_method=1 overload=1 "
        "unsupported=1 no_lib=1"
    )


if __name__ == "__main__":
    main()
