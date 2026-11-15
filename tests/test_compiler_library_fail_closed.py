# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Compile must not silently stub imported library calls to na."""

from __future__ import annotations

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


def test_compile_library_import_fails_closed() -> None:
    out = Runtime(symbol="TEST").run(_SRC, _bars(), mode="compile", libraries=_libraries())
    assert out.get("error_kind") == "compile"
    message = str(out.get("error") or "").lower()
    assert "library imports" in message
    assert "interpret" in message
    assert not out.get("series")


def test_auto_library_import_still_uses_interpret() -> None:
    out = Runtime(symbol="TEST").run(_SRC, _bars(), mode="auto", libraries=_libraries())
    assert "error" not in out, out.get("error")
    assert out.get("auto_backend") == "interpret"
    assert out["series"]["plot_0"] == [1.5] * 4


_STRING_IMPORT_SRC = '''//@version=6
indicator("string")
s = """
import fake/lib/1
"""
plot(close)
'''


def test_multiline_string_import_is_not_a_real_import() -> None:
    """A string containing an import line must not trigger compile fail-closed."""
    out = Runtime(symbol="TEST").run(
        _STRING_IMPORT_SRC,
        _bars(),
        mode="compile",
        libraries=_libraries(),
    )
    assert "error" not in out, out.get("error")
    assert out["series"]["plot_0"] == [100.5, 101.5, 102.5, 103.5]


def test_multiline_string_import_keeps_auto_compile_eligible() -> None:
    """Shared AST detector keeps ``_compile_eligible`` from false rejection."""
    out = Runtime(symbol="TEST").run(
        _STRING_IMPORT_SRC,
        _bars(),
        mode="auto",
        libraries=_libraries(),
    )
    assert "error" not in out, out.get("error")
    assert out.get("auto_backend") == "compile", out.get("compile_fallback_reason")
