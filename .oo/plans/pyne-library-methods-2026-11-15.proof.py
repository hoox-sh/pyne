# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Assertion proof for compile fail-closed on supplied library sources."""

# ruff: noqa: S101, T201

from __future__ import annotations

from typing import Any

from pynescript.runtime import Runtime


_LIB = """//@version=6
library("Lib")
export const float FOO = 1.5
"""

_SRC = """//@version=6
indicator("axis lib")
import ns/Lib/1 as x
plot(x.FOO)
"""

_STRING_IMPORT_SRC = '''//@version=6
indicator("string")
s = """
import fake/lib/1
"""
plot(close)
'''


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


def _libs() -> list[dict[str, Any]]:
    return [{"namespace": "ns", "name": "Lib", "version": 1, "source": _LIB}]


def main() -> None:
    compiled = Runtime(symbol="TEST").run(_SRC, _bars(), mode="compile", libraries=_libs())
    assert compiled.get("error_kind") == "compile", compiled.get("error")
    message = str(compiled.get("error") or "").lower()
    assert "library imports" in message, message
    assert "interpret" in message, message
    assert not compiled.get("series"), compiled.get("series")

    auto = Runtime(symbol="TEST").run(_SRC, _bars(), mode="auto", libraries=_libs())
    assert "error" not in auto, auto.get("error")
    assert auto.get("auto_backend") == "interpret", auto.get("auto_backend")
    assert auto["series"]["plot_0"] == [1.5] * 4, auto["series"]

    # No supplied library source: preserve the existing stub/no-raise contract.
    no_lib = Runtime(symbol="TEST").run(_SRC, _bars(), mode="compile")
    assert "error" not in no_lib, no_lib.get("error")

    # A multi-line string containing an import line is not a real import.
    string_import = Runtime(symbol="TEST").run(
        _STRING_IMPORT_SRC,
        _bars(),
        mode="compile",
        libraries=_libs(),
    )
    assert "error" not in string_import, string_import.get("error")
    assert string_import["series"]["plot_0"] == [100.5, 101.5, 102.5, 103.5]

    string_auto = Runtime(symbol="TEST").run(
        _STRING_IMPORT_SRC,
        _bars(),
        mode="auto",
        libraries=_libs(),
    )
    assert "error" not in string_auto, string_auto.get("error")
    assert string_auto.get("auto_backend") == "compile", string_auto.get("compile_fallback_reason")

    print("LIBRARY_FAIL_CLOSED_OK compile_error=1 auto=1.5 no_lib_stub=1 string_import=0")


if __name__ == "__main__":
    main()
