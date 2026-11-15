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
    out = Runtime(symbol="TEST").run(
        _SRC_LIB_UDT_NESTED, _bars(), mode="compile", libraries=_lib_udt(_LIB_UDT_NESTED)
    )
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
    out = Runtime(symbol="TEST").run(
        _SRC_SCRIPT_TYPE_COLLISION, _bars(), mode="compile", libraries=_lib_udt()
    )
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
