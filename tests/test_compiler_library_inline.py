# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Compile inlines simple exported library functions instead of stubbing."""

from __future__ import annotations

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


_LIB_INTERNAL_CALL = """//@version=6
library("Lib")
export helper(float a) =>
    a
export add(float a) =>
    helper(a)
"""


def test_library_internal_call_fails_closed() -> None:
    out = Runtime(symbol="TEST").run(
        _SRC,
        _bars(),
        mode="compile",
        libraries=[{"namespace": "ns", "name": "Lib", "version": 1, "source": _LIB_INTERNAL_CALL}],
    )
    assert out.get("error_kind") == "compile"
    assert "unsupported function helper" in str(out.get("error") or "").lower()


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
