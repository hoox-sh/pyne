# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Assertion proof: same-library internal calls inside inlined library bodies."""

# ruff: noqa: S101, T201

from __future__ import annotations

from typing import Any

from pynescript.runtime import Runtime


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

_LIB_CHAIN = """//@version=6
library("Lib")
export add(float a) =>
    twice(a) + 1
export twice(float a) =>
    deep(a) * 2
deep(float a) =>
    a + 0.5
"""

_SRC_CHAIN = """//@version=6
indicator("internal chain")
import ns/Lib/1 as lib
plot(lib.add(close), "add")
plot(lib.twice(close), "twice")
"""

_LIB_DEFAULTS = """//@version=6
library("Lib")
export add(float a) =>
    helper(a)
helper(float a, float k = 2.0) =>
    b = a * k
    b + 1
"""

_LIB_UNKNOWN = """//@version=6
library("Lib")
export add(float a) =>
    missing(a)
"""

_LIB_RECURSIVE = """//@version=6
library("Lib")
export add(float a) =>
    loop(a)
loop(float a) =>
    loop(a) + 1
"""

_LIB_UNUSED = """//@version=6
library("Lib")
export add(float a) =>
    a + 1
unused() =>
    ta.sma(close, 14)
"""

_LIB_METHOD_HELPER = """//@version=6
library("Lib")
export type Box
    float v
export method bump(Box this) =>
    helper(this.v)
helper(float x) =>
    x + 1
"""

_SRC_METHOD_HELPER = """//@version=6
indicator("method helper")
import ns/Lib/1 as lib
b = lib.Box.new(close)
plot(b.bump(), "x")
"""

_LIB_DEEP_CHAIN = """//@version=6
library("Lib")
export add(float a) =>
    h1(a)
h1(float a) =>
    h2(a) + 1
h2(float a) =>
    a * 2
"""

_SRC_DEEP_CHAIN = """//@version=6
indicator("deep chain")
import ns/Lib/1 as lib
plot(lib.add(close), "x")
"""

# --- previous slices (regression) -------------------------------------------

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

_LIB_FREE = """//@version=6
library("Lib")
export add(float a, float b) =>
    a + b
"""

_SRC_FREE = """//@version=6
indicator("free")
import ns/Lib/1 as lib
plot(lib.add(close, 1.0), "x")
"""

_LIB_SCALAR = """//@version=6
library("Lib")
export method scale(float this, float factor) =>
    this * factor
"""

_SRC_SCALAR = """//@version=6
indicator("scalar")
import ns/Lib/1 as lib
plot(lib.scale(close, 2.0), "x")
"""

# --- duplicate-name / bare-reference regressions ---------------------------

_LIB_DUP_HELPERS = """//@version=6
library("Lib")
export add(float a) =>
    helper(a)
helper(float a) =>
    a * 2
helper(float a, float k) =>
    a * k
"""

_LIB_DUP_EXPORTED_HELPER = """//@version=6
library("Lib")
export add(float a) =>
    dup(a)
export dup(float a) =>
    a * 2
dup(float a) =>
    a * 3
"""

_LIB_DUP_EXPORTED_ARITIES = """//@version=6
library("Lib")
export add(float a) =>
    helper(a)
export helper(float a) =>
    a * 2
export helper(float a, float k) =>
    a * k
"""

_LIB_BARE_REFERENCE = """//@version=6
library("Lib")
export add(float a) =>
    helper
helper(float a) =>
    a * 2
"""

_LIB_HELPER_METHOD_COLLISION = """//@version=6
library("Lib")
export add(float a) =>
    helper(a)
helper(float a) =>
    a * 2
export method helper(float this) =>
    this * 3
"""

_LIB_BARE_BUILTIN = """//@version=6
library("Lib")
export add(float a) =>
    abs(a)
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


def _run(src: str, source: str, mode: str = "compile") -> dict[str, Any]:
    return Runtime(symbol="TEST").run(
        src,
        _bars(),
        mode=mode,
        libraries=[{"namespace": "ns", "name": "Lib", "version": 1, "source": source}],
    )


def _error(out: dict[str, Any], *needles: str) -> str:
    assert out.get("error_kind") == "compile", out.get("error")
    message = str(out.get("error") or "").lower()
    for needle in needles:
        assert needle in message, message
    return message


def main() -> None:
    # 1. Non-exported helper.
    interp = _run(_SRC_INTERNAL, _LIB_INTERNAL, mode="interpret")
    helper = _run(_SRC_INTERNAL, _LIB_INTERNAL)
    assert "error" not in interp, interp.get("error")
    assert "error" not in helper, helper.get("error")
    assert helper["series"]["x"] == [202.0, 204.0, 206.0, 208.0]
    assert helper["series"] == interp["series"]

    # 2. Chain through an exported callee; both entry points resolve.
    chain = _run(_SRC_CHAIN, _LIB_CHAIN)
    assert "error" not in chain, chain.get("error")
    assert chain["series"]["add"] == [203.0, 205.0, 207.0, 209.0]
    assert chain["series"]["twice"] == [202.0, 204.0, 206.0, 208.0]

    # 3. Helper defaults and locals.
    defaults = _run(_SRC_INTERNAL, _LIB_DEFAULTS)
    assert "error" not in defaults, defaults.get("error")
    assert defaults["series"]["x"] == [202.0, 204.0, 206.0, 208.0]

    # 4. Unknown callee still fails closed.
    _error(_run(_SRC_INTERNAL, _LIB_UNKNOWN), "unsupported function missing")

    # 5. Recursive graph fails closed.
    _error(_run(_SRC_INTERNAL, _LIB_RECURSIVE), "recursive library function loop")

    # 6. Unreachable unsupported helper is inert.
    unused = _run(_SRC_INTERNAL, _LIB_UNUSED)
    assert "error" not in unused, unused.get("error")
    assert unused["series"]["x"] == [101.5, 102.5, 103.5, 104.5]

    # 7. UDT method body calling a helper.
    method_helper = _run(_SRC_METHOD_HELPER, _LIB_METHOD_HELPER)
    assert "error" not in method_helper, method_helper.get("error")
    assert method_helper["series"]["x"] == [101.5, 102.5, 103.5, 104.5]

    # 8. Two-level non-exported chain.
    deep = _run(_SRC_DEEP_CHAIN, _LIB_DEEP_CHAIN)
    assert "error" not in deep, deep.get("error")
    assert deep["series"]["x"] == [202.0, 204.0, 206.0, 208.0]

    # 9. Previous slices unchanged.
    udt = _run(_SRC_UDT, _LIB_UDT)
    assert "error" not in udt, udt.get("error")
    assert udt["series"]["x"] == [101.5, 102.5, 103.5, 104.5]
    free = _run(_SRC_FREE, _LIB_FREE)
    assert "error" not in free, free.get("error")
    assert free["series"]["x"] == [101.5, 102.5, 103.5, 104.5]
    scalar = _run(_SRC_SCALAR, _LIB_SCALAR)
    assert "error" not in scalar, scalar.get("error")
    assert scalar["series"]["x"] == [201.0, 203.0, 205.0, 207.0]

    # 9b. Duplicate same-library names fail closed (no silent miscompile).
    for dup_source, dup_name in (
        (_LIB_DUP_HELPERS, "helper"),
        (_LIB_DUP_EXPORTED_HELPER, "dup"),
        (_LIB_DUP_EXPORTED_ARITIES, "helper"),
    ):
        _error(_run(_SRC_INTERNAL, dup_source), "overloaded library method", dup_name)

    # 9c. Bare local function reference fails closed; bare builtin inlines.
    _error(_run(_SRC_INTERNAL, _LIB_BARE_REFERENCE), "uses unsupported name helper")
    bare_builtin = _run(_SRC_INTERNAL, _LIB_BARE_BUILTIN)
    assert "error" not in bare_builtin, bare_builtin.get("error")
    assert bare_builtin["series"]["x"] == [100.5, 101.5, 102.5, 103.5]

    # 9d. A local helper and an exported method cannot share a name.
    _error(_run(_SRC_INTERNAL, _LIB_HELPER_METHOD_COLLISION), "overloaded library method", "helper")

    # 10. No supplied library source keeps the legacy stub contract.
    no_lib = Runtime(symbol="TEST").run(_SRC_INTERNAL, _bars(), mode="compile")
    assert "error" not in no_lib, no_lib.get("error")

    print(
        "LIBRARY_INTERNAL_OK helper=202.0 chain=203.0 twice=202.0 defaults=202.0 "
        "unknown=1 recursive=1 unused=1 method_helper=101.5 deep_chain=202.0 "
        "udt=101.5 free=101.5 scalar=201.0 dup=3 bare_ref=1 bare_builtin=100.5 "
        "helper_method=1 no_lib=1"
    )


if __name__ == "__main__":
    main()
