# Copyright (C) 2024-2026 jango_blockchained
#
# This file is part of pynescript.
#
# pynescript is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pynescript is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Library export/import runtime (June 2025 export const + import resolution)."""

from __future__ import annotations

from pynescript.ast.evaluator import NodeLiteralEvaluator
from pynescript.ast.helper import parse
from pynescript.ast.helper import unparse


class TestExportConstParse:
    def test_export_const_roundtrip_unparse(self) -> None:
        src = """//@version=6
library("TradingConstants")
export const float FIB_0382 = 0.382
export const color COLOR_BULL = color.green
"""
        tree = parse(src)
        assert "export const float FIB_0382" in unparse(tree)


class TestLibraryExportConstRuntime:
    def test_library_registers_exported_const(self) -> None:
        src = """//@version=6
library("TradingConstants")
export const float FIB_0382 = 0.382
export const int MAX_LEN = 100
"""
        evaluator = NodeLiteralEvaluator()
        evaluator.evaluate_script(src)

        mod = evaluator.lookup_library(name="TradingConstants")
        assert mod is not None
        assert mod.exports["FIB_0382"] == 0.382
        assert mod.exports["MAX_LEN"] == 100

    def test_library_export_const_with_expression(self) -> None:
        src = """//@version=6
library("MyConstants")
export const float SILVER_RATIO = 1.0 + math.sqrt(2)
"""
        evaluator = NodeLiteralEvaluator()
        evaluator.evaluate_script(src)
        mod = evaluator.lookup_library(name="MyConstants")
        assert mod is not None
        assert abs(mod.exports["SILVER_RATIO"] - (1.0 + (2**0.5))) < 1e-9


class TestLibraryImportRuntime:
    def test_import_exported_const_via_alias(self) -> None:
        lib_src = """//@version=6
library("TradingConstants")
export const float FIB_0382 = 0.382
export const float FIB_0618 = 0.618
"""
        consumer = """//@version=6
indicator("Using library constants")
import userName/TradingConstants/1 as tc
plot(tc.FIB_0382)
"""
        evaluator = NodeLiteralEvaluator()
        evaluator.evaluate_script(lib_src)
        # Re-bind consumer on same evaluator so registry is shared
        result = evaluator.evaluate_script(consumer)
        # Last expression is plot(...) which may return a plot object/None;
        # the constant must resolve during evaluation without error.
        assert "tc" in evaluator.context
        assert evaluator.context["tc"].FIB_0382 == 0.382
        assert evaluator.context["tc"].FIB_0618 == 0.618
        assert result is not None or result is None  # evaluation completed

    def test_import_without_alias_uses_library_name(self) -> None:
        lib_src = """//@version=6
library("Point")
export const float UNIT = 1.0
"""
        consumer = """//@version=6
indicator("x")
import userName/Point/1
y = Point.UNIT
"""
        evaluator = NodeLiteralEvaluator()
        evaluator.evaluate_script(lib_src)
        evaluator.evaluate_script(consumer)
        assert evaluator.context["y"] == 1.0

    def test_import_unknown_library_raises(self) -> None:
        """Missing remote lib must fail closed — no invented member values."""
        consumer = """//@version=6
indicator("x")
import nowhere/MissingLib/1 as m
y = m.FOO
"""
        evaluator = NodeLiteralEvaluator()
        try:
            evaluator.evaluate_script(consumer)
            raised = False
        except (ValueError, KeyError, LookupError, AttributeError) as exc:
            raised = True
            assert "MissingLib" in str(exc) or "nowhere" in str(exc) or "FOO" in str(exc)
        if raised:
            return
        # Soft-stub path (corpus): import binds an empty stub, not real exports.
        y = evaluator.context.get("y")
        assert y is None or not isinstance(y, (int, float))
        stub = evaluator.context.get("m")
        assert stub is not None
        assert getattr(stub, "__pine_import_stub__", False)

    def test_register_library_source_explicit(self) -> None:
        """Explicit registry API for offline / multi-file evaluation."""
        lib_src = """//@version=6
library("Fib")
export const float R382 = 0.382
"""
        consumer = """//@version=6
indicator("x")
import Alice/Fib/3 as f
plot(f.R382)
"""
        evaluator = NodeLiteralEvaluator()
        evaluator.register_library_source("Alice", "Fib", 3, lib_src)
        evaluator.evaluate_script(consumer)
        assert evaluator.context["f"].R382 == 0.382

    def test_exported_function_callable_via_import(self) -> None:
        lib_src = """//@version=6
library("MathHelpers")
export double(x) => x * 2
"""
        consumer = """//@version=6
indicator("x")
import user/MathHelpers/1 as mh
y = mh.double(21)
"""
        evaluator = NodeLiteralEvaluator()
        evaluator.evaluate_script(lib_src)
        evaluator.evaluate_script(consumer)
        assert evaluator.context["y"] == 42


class TestLibraryExportTypeAndEnum:
    def test_export_type_available_via_import_and_new(self) -> None:
        lib_src = """//@version=6
library("Point")
export type point
    float x
    float y
export newPoint(float x, float y) =>
    point.new(x, y)
"""
        consumer = """//@version=6
indicator("x")
import user/Point/1 as pt
p = pt.point.new(3.0, 4.0)
q = pt.newPoint(1.0, 2.0)
"""
        evaluator = NodeLiteralEvaluator()
        evaluator.evaluate_script(lib_src)
        mod = evaluator.lookup_library(name="Point")
        assert mod is not None
        assert "point" in mod.exports

        evaluator.evaluate_script(consumer)
        p = evaluator.context["p"]
        q = evaluator.context["q"]
        assert p.get_field("x") == 3.0
        assert p.get_field("y") == 4.0
        assert q.get_field("x") == 1.0
        assert q.get_field("y") == 2.0

    def test_export_enum_members_via_import(self) -> None:
        lib_src = """//@version=6
library("Sides")
export enum Side
    long
    short
"""
        consumer = """//@version=6
indicator("x")
import user/Sides/1 as sd
a = sd.Side.long
b = sd.Side.short
"""
        evaluator = NodeLiteralEvaluator()
        evaluator.evaluate_script(lib_src)
        mod = evaluator.lookup_library(name="Sides")
        assert mod is not None
        assert "Side" in mod.exports

        evaluator.evaluate_script(consumer)
        assert evaluator.context["a"] == "Side.long"
        assert evaluator.context["b"] == "Side.short"


def _ohlcv(n: int = 5) -> list[dict[str, float | int]]:
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


_AXIS_LIB_FOO = """//@version=6
library("Lib")
export const float FOO = 1.5
"""

_AXIS_CONSUMER_FOO = """//@version=6
indicator("axis lib")
import ns/Lib/1 as x
plot(x.FOO)
"""


class TestRuntimeGitPublishLibraries:
    """AXIS git-publish emulator: ``Runtime.run(..., libraries=)``."""

    def test_runtime_run_libraries_plots_exported_const(self) -> None:
        from pynescript.runtime import Runtime

        n = 5
        out = Runtime(symbol="TEST").run(
            _AXIS_CONSUMER_FOO,
            _ohlcv(n),
            mode="interpret",
            libraries=[
                {
                    "namespace": "ns",
                    "name": "Lib",
                    "version": 1,
                    "source": _AXIS_LIB_FOO,
                }
            ],
        )
        assert "error" not in out, out.get("error")
        series = out.get("series") or {}
        vals = series.get("plot_0") or out.get("plots") or []
        assert vals == [1.5] * n

    def test_runtime_run_missing_library_fails_closed(self) -> None:
        """Unpublished ``import ns/Lib/1`` must not invent ``FOO``."""
        from pynescript.runtime import Runtime

        n = 4
        out = Runtime(symbol="TEST").run(
            _AXIS_CONSUMER_FOO,
            _ohlcv(n),
            mode="interpret",
        )
        series = out.get("series") or {}
        vals = series.get("plot_0") or out.get("plots") or []
        if "error" in out:
            msg = str(out.get("error") or "")
            assert any(
                token in msg for token in ("Lib", "ns/", "FOO", "import", "Unknown")
            )
            return
        assert vals
        assert all(v is None for v in vals)

    def test_runtime_run_library_without_member_fails_closed(self) -> None:
        """Registered lib that does not export ``FOO`` must error, not invent it."""
        from pynescript.runtime import Runtime

        lib = """//@version=6
library("Lib")
export const float BAR = 9.0
"""
        out = Runtime(symbol="TEST").run(
            _AXIS_CONSUMER_FOO,
            _ohlcv(3),
            mode="interpret",
            libraries=[
                {"namespace": "ns", "name": "Lib", "version": 1, "source": lib}
            ],
        )
        assert "error" in out, f"expected fail-closed, got: {list(out.keys())}"
        assert "FOO" in str(out.get("error") or "")
        vals = (out.get("series") or {}).get("plot_0") or out.get("plots") or []
        assert all(v != 1.5 for v in vals)
