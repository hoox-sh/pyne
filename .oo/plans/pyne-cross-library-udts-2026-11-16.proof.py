# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Proof: cross-library UDT constructor/method; annotations/cycles fail closed."""

from __future__ import annotations

# ruff: noqa: S101, T201
import sys

from pynescript.runtime import Runtime

sys.path.insert(0, "tests")
import test_compiler_library_inline as t  # noqa: E402


def main() -> None:
    interp = Runtime(symbol="TEST").run(
        t._SRC_XLIB_UDT,
        t._bars(),
        mode="interpret",
        libraries=t._xlib_udt_libraries(t._LIB_XLIB_UDT_A),
    )
    compiled = Runtime(symbol="TEST").run(
        t._SRC_XLIB_UDT,
        t._bars(),
        mode="compile",
        libraries=t._xlib_udt_libraries(t._LIB_XLIB_UDT_A),
    )
    assert "error" not in interp, interp.get("error")
    assert "error" not in compiled, compiled.get("error")
    assert compiled["series"]["v"] == [100.5, 101.5, 102.5, 103.5]
    assert compiled["series"]["b"] == [101.5, 102.5, 103.5, 104.5]
    assert compiled["series"] == interp["series"]

    annot = Runtime(symbol="TEST").run(
        t._SRC_XLIB_UDT,
        t._bars(),
        mode="compile",
        libraries=t._xlib_udt_libraries(t._LIB_XLIB_UDT_A_ANNOT),
    )
    assert annot.get("error_kind") == "compile", annot
    assert "unsupported name b" in str(annot.get("error") or "").lower()

    cycle = Runtime(symbol="TEST").run(
        t._SRC_CROSS_AB,
        t._bars(),
        mode="compile",
        libraries=t._cross_libs(t._LIB_CROSS_A_CYCLE, t._LIB_CROSS_B_CYCLE),
    )
    assert cycle.get("error_kind") == "compile", cycle
    assert "recursive library import" in str(cycle.get("error") or "").lower()

    print("XLIB_UDT_OK ctor=1 method=1 annot=fail_closed cycle=fail_closed")


if __name__ == "__main__":
    main()
