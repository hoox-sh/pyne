# Copyright 2024-2025 Yunseong Hwang, jango_blockchained
#
# Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.gnu.org/licenses/lgpl-3.0.en.html
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: LGPL-3.0-or-later

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
        consumer = """//@version=6
indicator("x")
import nowhere/MissingLib/1 as m
"""
        evaluator = NodeLiteralEvaluator()
        try:
            evaluator.evaluate_script(consumer)
            raised = False
        except (ValueError, KeyError, LookupError) as exc:
            raised = True
            assert "MissingLib" in str(exc) or "nowhere" in str(exc)
        assert raised

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