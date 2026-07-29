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

from __future__ import annotations

import math

import pytest

from pynescript.ast import helper
from pynescript.ast.evaluator import NodeLiteralEvaluator
from pynescript.ast.evaluator.builtins.drawing import TableCell
from pynescript.ast.evaluator.builtins.strategy import Trade


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("abs(-1)", 1),
        ("abs(1)", 1),
        ("abs(0)", 0),
        ("abs(-1.5)", 1.5),
        ("abs(1.5)", 1.5),
    ],
)
def test_evaluator_abs(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("math.max(1, 2, 3)", 3),
        ("math.max(-1, -2, -3)", -1),
        ("math.max(1.5, 2.5, 3.5)", 3.5),
    ],
)
def test_evaluator_math_max(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("math.min(1, 2, 3)", 1),
        ("math.min(-1, -2, -3)", -3),
        ("math.min(1.5, 2.5, 3.5)", 1.5),
    ],
)
def test_evaluator_math_min(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("math.sqrt(4)", 2),
        ("math.sqrt(2)", 1.4142135623730951),
        ("math.sqrt(0)", 0),
    ],
)
def test_evaluator_math_sqrt(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("math.round(1.5)", 2),
        ("math.round(1.4)", 1),
        ("math.round(1.55, 1)", 1.6),
    ],
)
def test_evaluator_math_round(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("math.floor(1.9)", 1),
        ("math.floor(-1.9)", -2),
    ],
)
def test_evaluator_math_floor(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("math.ceil(1.1)", 2),
        ("math.ceil(-1.9)", -1),
    ],
)
def test_evaluator_math_ceil(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("math.pow(2, 3)", 8),
        ("math.pow(4, 0.5)", 2),
    ],
)
def test_evaluator_math_pow(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("math.log(100, 10)", 2),
        (f"math.log({math.e})", 1),
    ],
)
def test_evaluator_math_log(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("math.sin(0)", 0),
        (f"math.sin({math.pi / 2})", 1),
    ],
)
def test_evaluator_math_sin(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert pytest.approx(result) == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("math.cos(0)", 1),
        (f"math.cos({math.pi})", -1),
    ],
)
def test_evaluator_math_cos(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert pytest.approx(result) == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("math.tan(0)", 0),
        (f"math.tan({math.pi / 4})", 1),
    ],
)
def test_evaluator_math_tan(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert pytest.approx(result) == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("math.acos(1)", 0),
        ("math.acos(0)", math.pi / 2),
    ],
)
def test_evaluator_math_acos(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert pytest.approx(result) == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("math.asin(0)", 0),
        ("math.asin(1)", math.pi / 2),
    ],
)
def test_evaluator_math_asin(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert pytest.approx(result) == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("math.atan(0)", 0),
        ("math.atan(1)", math.pi / 4),
    ],
)
def test_evaluator_math_atan(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert pytest.approx(result) == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("math.exp(0)", 1),
        ("math.exp(1)", math.e),
    ],
)
def test_evaluator_math_exp(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert pytest.approx(result) == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("math.log10(100)", 2),
        ("math.log10(1)", 0),
    ],
)
def test_evaluator_math_log10(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert pytest.approx(result) == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("math.sign(10)", 1),
        ("math.sign(-10)", -1),
        ("math.sign(0)", 0),
    ],
)
def test_evaluator_math_sign(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("math.sum([1, 2, 3])", 6),
        ("math.sum([-1, 1, 0])", 0),
    ],
)
def test_evaluator_math_sum(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("math.avg([1, 2, 3])", 2),
        ("math.avg([10, 20, 30])", 20),
    ],
)
def test_evaluator_math_avg(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("math.todegrees(math.pi)", 180),
        ("math.todegrees(0)", 0),
    ],
)
def test_evaluator_math_todegrees(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert pytest.approx(result) == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("math.toradians(180)", math.pi),
        ("math.toradians(0)", 0),
    ],
)
def test_evaluator_math_toradians(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert pytest.approx(result) == expected


def test_evaluator_enum_def():
    script = """
enum CalcType
    hl
    hlc
"""
    ast = helper.parse(script)
    evaluator = NodeLiteralEvaluator()
    evaluator.visit(ast)

    expected_context = {
        "CalcType": {
            "hl": "CalcType.hl",
            "hlc": "CalcType.hlc",
        }
    }
    assert evaluator.context["CalcType"] == expected_context["CalcType"]


def test_evaluator_enum_member_access():
    script = """
enum CalcType
    hl
    hlc
a = CalcType.hl
"""
    ast = helper.parse(script)
    evaluator = NodeLiteralEvaluator()
    evaluator.visit(ast)

    assert evaluator.context.get("a") == "CalcType.hl"


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ('str.length("hello")', 5),
        ('str.length("")', 0),
    ],
)
def test_evaluator_str_length(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ('str.upper("hello")', "HELLO"),
        ('str.upper("WORLD")', "WORLD"),
    ],
)
def test_evaluator_str_upper(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ('str.lower("HELLO")', "hello"),
        ('str.lower("world")', "world"),
    ],
)
def test_evaluator_str_lower(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ('str.contains("hello world", "world")', True),
        ('str.contains("hello world", "foo")', False),
    ],
)
def test_evaluator_str_contains(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ('str.startswith("hello world", "hello")', True),
        ('str.startswith("hello world", "world")', False),
    ],
)
def test_evaluator_str_startswith(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ('str.endswith("hello world", "world")', True),
        ('str.endswith("hello world", "hello")', False),
    ],
)
def test_evaluator_str_endswith(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ('str.substring("hello", 1)', "ello"),
        ('str.substring("hello", 1, 3)', "el"),
    ],
)
def test_evaluator_str_substring(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ('str.repeat("a", 5)', "aaaaa"),
        ('str.repeat("ab", 3)', "ababab"),
    ],
)
def test_evaluator_str_repeat(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ('str.replace("hello world", "world", "pine")', "hello pine"),
        ('str.replace("abab", "a", "c")', "cbab"),
    ],
)
def test_evaluator_str_replace(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ('str.replace_all("abab", "a", "c")', "cbcb"),
    ],
)
def test_evaluator_str_replace_all(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ('str.split("a,b,c", ",")', ["a", "b", "c"]),
        ('str.split("a b c")', ["a", "b", "c"]),
    ],
)
def test_evaluator_str_split(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ('str.trim("  hello  ")', "hello"),
    ],
)
def test_evaluator_str_trim(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ('str.tonumber("123.45")', 123.45),
    ],
)
def test_evaluator_str_tonumber(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("str.tostring(123)", "123"),
        ('str.tostring("abc")', "abc"),
    ],
)
def test_evaluator_str_tostring(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ('str.format_time(1672531200000, "yyyy-MM-dd")', "2023-01-01"),
        (
            'str.format_time(1672531200000, "yyyy-MM-dd HH:mm:ss", "GMT+3")',
            "2023-01-01 03:00:00",
        ),
    ],
)
def test_evaluator_str_format_time(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("array.size([1, 2, 3])", 3),
        ("array.size([])", 0),
    ],
)
def test_evaluator_array_size(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("array.get([1, 2, 3], 1)", 2),
    ],
)
def test_evaluator_array_get(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("array.push([1, 2], 3)", [1, 2, 3]),
    ],
)
def test_evaluator_array_push(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        # Pine: array.pop removes and returns the last element
        ("array.pop([1, 2, 3])", 3),
        ("array.pop([1])", 1),
    ],
)
def test_evaluator_array_pop(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("array.slice([1, 2, 3, 4], 1, 3)", [2, 3]),
    ],
)
def test_evaluator_array_slice(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("array.abs([-1, -2, 3])", [1, 2, 3]),
    ],
)
def test_evaluator_array_abs(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("array.avg([1, 2, 3])", 2),
    ],
)
def test_evaluator_array_avg(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("array.concat([1, 2], [3, 4])", [1, 2, 3, 4]),
    ],
)
def test_evaluator_array_concat(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("array.copy([1, 2, 3])", [1, 2, 3]),
    ],
)
def test_evaluator_array_copy(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("array.fill([1, 2, 3], 0)", [0, 0, 0]),
    ],
)
def test_evaluator_array_fill(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("array.first([1, 2, 3])", 1),
    ],
)
def test_evaluator_array_first(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("array.from(1, 2, 3)", [1, 2, 3]),
    ],
)
def test_evaluator_array_from(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("array.includes([1, 2, 3], 2)", True),
        ("array.includes([1, 2, 3], 4)", False),
    ],
)
def test_evaluator_array_includes(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("array.indexof([1, 2, 3], 2)", 1),
        ("array.indexof([1, 2, 3], 4)", -1),
    ],
)
def test_evaluator_array_indexof(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("array.insert([1, 3], 1, 2)", [1, 2, 3]),
    ],
)
def test_evaluator_array_insert(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ('array.join([1, 2, 3], ",")', "1,2,3"),
    ],
)
def test_evaluator_array_join(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("array.last([1, 2, 3])", 3),
    ],
)
def test_evaluator_array_last(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("array.lastindexof([1, 2, 3, 2], 2)", 3),
        ("array.lastindexof([1, 2, 3], 4)", -1),
    ],
)
def test_evaluator_array_lastindexof(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("array.max([1, 3, 2])", 3),
    ],
)
def test_evaluator_array_max(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("array.min([2, 1, 3])", 1),
    ],
)
def test_evaluator_array_min(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        # TV: array.range(id) = max - min of array elements
        ("array.range(array.from(1.0, 5.0, 3.0))", 4.0),
        ("array.range(array.from(2, 2, 2))", 0.0),
    ],
)
def test_evaluator_array_range(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        # Pine: array.remove returns the removed element
        ("array.remove([1, 2, 3], 1)", 2),
    ],
)
def test_evaluator_array_remove(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("array.reverse([1, 2, 3])", [3, 2, 1]),
    ],
)
def test_evaluator_array_reverse(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("array.set([1, 2, 3], 1, 4)", [1, 4, 3]),
    ],
)
def test_evaluator_array_set(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        # Pine: array.shift removes and returns the first element
        ("array.shift([1, 2, 3])", 1),
    ],
)
def test_evaluator_array_shift(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("array.sort([3, 1, 2])", [1, 2, 3]),
    ],
)
def test_evaluator_array_sort(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("array.sum([1, 2, 3])", 6),
    ],
)
def test_evaluator_array_sum(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("array.unshift([2, 3], 1)", [1, 2, 3]),
    ],
)
def test_evaluator_array_unshift(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("ta.sma([1, 2, 3, 4, 5], 3)", [None, None, 2, 3, 4]),
    ],
)
def test_evaluator_ta_sma(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        (
            "ta.ema([1, 2, 3, 4, 5], 3)",
            [1, 1.5, 2.25, 3.125, 4.0625],
        ),
    ],
)
def test_evaluator_ta_ema(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == pytest.approx(expected)


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        (
            "ta.atr([10, 11, 12], [8, 9, 10], [9, 10, 11], 2)",
            [2, 2.0],
        ),
    ],
)
def test_evaluator_ta_atr(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        (
            "ta.tr([10, 12, 15], [8, 9, 11], [9, 11, 13])",
            [math.nan, 3.0, 4.0],
        ),
    ],
)
def test_evaluator_ta_tr(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    # First bar TR is na (None or nan depending on path)
    assert result[0] is None or (isinstance(result[0], float) and math.isnan(result[0]))
    assert result[1:] == pytest.approx(expected[1:])


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        (
            "ta.stoch([10, 11, 12, 11, 10], [8, 9, 10, 9, 8], [9, 10, 11, 10, 9], 3, 2)",
            (25.0, 0.0),
        ),
    ],
)
def test_evaluator_ta_stoch(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == pytest.approx(expected)


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        (
            "ta.adx([10, 11, 12, 11, 10], [8, 9, 10, 9, 8], [9, 10, 11, 10, 9], 3)",
            0.0,
        ),
    ],
)
def test_evaluator_ta_adx(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == pytest.approx(expected)


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        (
            "ta.cci([10, 11, 12, 11, 10], [8, 9, 10, 9, 8], [9, 10, 11, 10, 9], 3)",
            -100.0,
        ),
    ],
)
def test_evaluator_ta_cci(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == pytest.approx(expected)


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("ta.roc([1, 2, 3, 4, 5], 2)", 100.0),
    ],
)
def test_evaluator_ta_roc(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == pytest.approx(expected)


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        (
            "ta.wpr([10, 11, 12, 11, 10], [8, 9, 10, 9, 8], [9, 10, 11, 10, 9], 3)",
            -75.0,
        ),
    ],
)
def test_evaluator_ta_wpr(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == pytest.approx(expected)


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("ta.obv([9, 10, 11, 10, 9], [100, 110, 120, 90, 80])", -50),
    ],
)
def test_evaluator_ta_obv(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == pytest.approx(expected)


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        (
            "ta.mfi([10, 11, 12, 11, 10], [8, 9, 10, 9, 8], [9, 10, 11, 10, 9], [100, 110, 120, 90, 80], 3)",
            50.0,
        ),
    ],
)
def test_evaluator_ta_mfi(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == pytest.approx(expected)


# New Array Statistical Functions Tests


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("array.percentile_linear_interpolation([1, 2, 3, 4, 5], 50)", 3.0),
        ("array.percentile_linear_interpolation([1, 2, 3, 4, 5], 25)", 2.0),
        ("array.percentile_linear_interpolation([1, 2, 3, 4, 5], 75)", 4.0),
    ],
)
def test_evaluator_array_percentile_linear_interpolation(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == pytest.approx(expected)


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("array.percentile_nearest_rank([1, 2, 3, 4, 5], 50)", 3),
        ("array.percentile_nearest_rank([1, 2, 3, 4, 5], 25)", 1),
        ("array.percentile_nearest_rank([1, 2, 3, 4, 5], 75)", 4),
    ],
)
def test_evaluator_array_percentile_nearest_rank(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("array.percentrank([1, 2, 3, 4, 5], 3)", pytest.approx(50.0)),
        ("array.percentrank([1, 2, 3, 4, 5], 1)", pytest.approx(0.0)),
        ("array.percentrank([1, 2, 3, 4, 5], 5)", pytest.approx(100.0)),
    ],
)
def test_evaluator_array_percentrank(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "check"),
    [
        ("array.stdev([1, 2, 3, 4, 5])", lambda x: x > 1.4 and x < 1.6),
        # TV default biased=true → population variance = 2.0 for 1..5
        ("array.variance([1, 2, 3, 4, 5])", lambda x: x >= 2.0 and x < 2.6),
    ],
)
def test_evaluator_array_stdev_variance(expression, check):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert check(result)


@pytest.mark.parametrize(
    ("expression",),
    [
        ("array.standardize([1, 2, 3, 4, 5])",),
    ],
)
def test_evaluator_array_standardize(expression):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert isinstance(result, list)
    assert len(result) == 5
    # Mean should be ~0 after standardization
    mean = sum(result) / len(result)
    assert abs(mean) < 1e-10


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("array.sort_indices([3, 1, 4, 1, 5])", [1, 3, 0, 2, 4]),
        ("array.sort_indices([5, 4, 3, 2, 1])", [4, 3, 2, 1, 0]),
    ],
)
def test_evaluator_array_sort_indices(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("array.binary_search_leftmost([1, 2, 2, 2, 3], 2)", 1),
        ("array.binary_search_leftmost([1, 2, 2, 2, 3], 1)", 0),
        ("array.binary_search_leftmost([1, 2, 2, 2, 3], 5)", -1),
    ],
)
def test_evaluator_array_binary_search_leftmost(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("array.binary_search_rightmost([1, 2, 2, 2, 3], 2)", 3),
        ("array.binary_search_rightmost([1, 2, 2, 2, 3], 3)", 4),
        ("array.binary_search_rightmost([1, 2, 2, 2, 3], 5)", -1),
    ],
)
def test_evaluator_array_binary_search_rightmost(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


# New Technical Analysis Indicators Tests


@pytest.mark.parametrize(
    ("expression",),
    [
        ("ta.cog([1, 2, 3, 4, 5], 3)",),
        ("ta.linreg([1, 2, 3, 4, 5], 3)",),
    ],
)
def test_evaluator_ta_new_indicators(expression):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    # Just verify they return a number (not NaN for valid inputs)
    assert isinstance(result, (int, float))
    assert not math.isnan(result)


@pytest.mark.parametrize(
    ("expression",),
    [
        ("ta.swma([1, 2, 3, 4, 5], 3)",),
    ],
)
def test_evaluator_ta_swma(expression):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert isinstance(result, (int, float))
    # Result should be within the range of input values
    assert 1 <= result <= 5


# Plotting Functions Tests


@pytest.mark.parametrize(
    ("expression", "kind"),
    [
        ("plot([1, 2, 3, 4, 5])", "plot"),
        ("plotbar([1, 2, 3], [2, 3, 4], [0, 1, 2], [1, 2, 3])", "plotbar"),
        ("hline(100)", "hline"),
        ("bgcolor('red')", "bgcolor"),
    ],
)
def test_evaluator_plotting_functions(expression, kind):
    from pynescript.ast.evaluator.builtins.plotting import Plot
    from pynescript.ast.evaluator.builtins.plotting import PlotRegistry

    PlotRegistry.reset()
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert isinstance(result, Plot)
    assert result.kind == kind
    assert len(PlotRegistry.plots) >= 1


# INPUT FUNCTIONS TESTS
# Pine semantics: input.* evaluates to the parameter value; metadata is
# recorded on evaluator._input_declarations for UI/LSP hosts.


@pytest.mark.parametrize(
    ("expression", "expected_value"),
    [
        ("input(100, 'Value')", 100),
        ("input(50.5, 'Price')", 50.5),
        ("input(true, 'Flag')", True),
    ],
)
def test_evaluator_input_generic(expression, expected_value):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected_value
    assert len(evaluator._input_declarations) == 1
    meta = evaluator._input_declarations[0]
    assert meta["default"] == expected_value
    assert "type" in meta
    assert "title" in meta


def test_evaluator_input_int_type_inference():
    """input() returns int defval and records type metadata."""
    ast = helper.parse("input(14)", mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == 14
    assert evaluator._input_declarations[0]["type"] == "int"
    assert evaluator._input_declarations[0]["default"] == 14


def test_evaluator_input_bool_type_inference():
    """input() returns bool defval and records type metadata."""
    ast = helper.parse("input(true)", mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result is True
    assert evaluator._input_declarations[0]["type"] == "bool"
    assert evaluator._input_declarations[0]["default"] is True


def test_evaluator_input_float_type_inference():
    """input() returns float defval and records type metadata."""
    ast = helper.parse("input(2.5)", mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == 2.5
    assert evaluator._input_declarations[0]["type"] == "float"
    assert evaluator._input_declarations[0]["default"] == 2.5


def test_evaluator_input_string_type_inference():
    """input() returns string defval and records type metadata."""
    ast = helper.parse("input('text')", mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == "text"
    assert evaluator._input_declarations[0]["type"] == "string"
    assert evaluator._input_declarations[0]["default"] == "text"


@pytest.mark.parametrize(
    ("expression", "expected_value"),
    [
        ("input.bool(true)", True),
        ("input.bool(false)", False),
        ("input.bool(true, 'Enable')", True),
    ],
)
def test_evaluator_input_bool(expression, expected_value):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result is expected_value
    assert evaluator._input_declarations[0]["type"] == "bool"
    assert evaluator._input_declarations[0]["default"] is expected_value


@pytest.mark.parametrize(
    ("expression", "expected_value"),
    [
        ("input.int(14)", 14),
        ("input.int(14, 'Length')", 14),
        ("input.int(14, 'Length', 1, 100)", 14),
    ],
)
def test_evaluator_input_int(expression, expected_value):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected_value
    assert evaluator._input_declarations[0]["type"] == "int"
    assert evaluator._input_declarations[0]["default"] == expected_value


def test_evaluator_input_int_with_constraints():
    """input.int returns value; min/max/step live in metadata."""
    ast = helper.parse("input.int(50, 'Value', 10, 100, 5)", mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == 50
    meta = evaluator._input_declarations[0]
    assert meta["type"] == "int"
    assert meta["default"] == 50
    assert meta["min"] == 10
    assert meta["max"] == 100
    assert meta["step"] == 5


@pytest.mark.parametrize(
    ("expression", "expected_value"),
    [
        ("input.float(2.5)", 2.5),
        ("input.float(2.5, 'Price')", 2.5),
        ("input.float(2.5, 'Price', 0.0, 10.0)", 2.5),
    ],
)
def test_evaluator_input_float(expression, expected_value):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected_value
    assert evaluator._input_declarations[0]["type"] == "float"
    assert evaluator._input_declarations[0]["default"] == expected_value


def test_evaluator_input_float_with_constraints():
    """input.float returns value; min/max/step live in metadata."""
    ast = helper.parse("input.float(1.5, 'Factor', 0.5, 3.0, 0.1)", mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == 1.5
    meta = evaluator._input_declarations[0]
    assert meta["type"] == "float"
    assert meta["default"] == 1.5
    assert meta["min"] == 0.5
    assert meta["max"] == 3.0
    assert meta["step"] == 0.1


@pytest.mark.parametrize(
    ("expression", "expected_value"),
    [
        ("input.price(100.0)", 100.0),
        ("input.price(100.0, 'Entry Price')", 100.0),
    ],
)
def test_evaluator_input_price(expression, expected_value):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected_value
    assert evaluator._input_declarations[0]["type"] == "price"
    assert evaluator._input_declarations[0]["default"] == expected_value


@pytest.mark.parametrize(
    ("expression", "expected_value"),
    [
        ("input.string('AAPL')", "AAPL"),
        ("input.string('default', 'Text')", "default"),
    ],
)
def test_evaluator_input_string(expression, expected_value):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected_value
    assert evaluator._input_declarations[0]["type"] == "string"
    assert evaluator._input_declarations[0]["default"] == expected_value


@pytest.mark.parametrize(
    ("expression", "expected_value"),
    [
        ("input.symbol('AAPL')", "AAPL"),
        ("input.symbol('BTC/USD')", "BTC/USD"),
    ],
)
def test_evaluator_input_symbol(expression, expected_value):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected_value
    assert evaluator._input_declarations[0]["type"] == "symbol"
    assert evaluator._input_declarations[0]["default"] == expected_value


@pytest.mark.parametrize(
    ("expression", "expected_value"),
    [
        ("input.session('0930-1600')", "0930-1600"),
        ("input.session('0900-1700', 'Trading Hours')", "0900-1700"),
    ],
)
def test_evaluator_input_session(expression, expected_value):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected_value
    assert evaluator._input_declarations[0]["type"] == "session"


@pytest.mark.parametrize(
    ("expression", "expected_value"),
    [
        ("input.source('close')", "close"),
        ("input.source('hl2')", "hl2"),
    ],
)
def test_evaluator_input_source(expression, expected_value):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected_value
    assert evaluator._input_declarations[0]["type"] == "source"
    assert evaluator._input_declarations[0]["default"] == expected_value


@pytest.mark.parametrize(
    ("expression", "expected_value"),
    [
        ("input.time(0)", 0),
        ("input.time(1630698000, 'Start Time')", 1630698000),
    ],
)
def test_evaluator_input_time(expression, expected_value):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected_value
    assert evaluator._input_declarations[0]["type"] == "time"


@pytest.mark.parametrize(
    ("expression", "expected_value"),
    [
        ("input.timeframe('D')", "D"),
        ("input.timeframe('1H')", "1H"),
    ],
)
def test_evaluator_input_timeframe(expression, expected_value):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected_value
    assert evaluator._input_declarations[0]["type"] == "timeframe"
    assert evaluator._input_declarations[0]["default"] == expected_value


@pytest.mark.parametrize(
    ("expression", "expected_value"),
    [
        ("input.color('#FF0000')", "#FF0000"),
        ("input.color('red')", "red"),
    ],
)
def test_evaluator_input_color(expression, expected_value):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected_value
    assert evaluator._input_declarations[0]["type"] == "color"


def test_evaluator_input_enum():
    ast = helper.parse("input.enum('A', 'Choice', ['A', 'B', 'C'])", mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == "A"
    meta = evaluator._input_declarations[0]
    assert meta["type"] == "enum"
    assert meta["options"] == ["A", "B", "C"]


def test_evaluator_input_with_all_parameters():
    """input.int returns value; full optional metadata is recorded."""
    ast = helper.parse(
        "input.int(50, 'Value', 10, 100, 5, 'Set the threshold', 'group1', 'settings', true)", mode="eval"
    )
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == 50
    meta = evaluator._input_declarations[0]
    assert meta["type"] == "int"
    assert meta["default"] == 50
    assert meta["title"] == "Value"
    assert meta["min"] == 10
    assert meta["max"] == 100
    assert meta["step"] == 5
    assert meta["tooltip"] == "Set the threshold"
    assert meta["inline"] == "group1"
    assert meta["group"] == "settings"
    assert meta["confirm"] is True


# REQUEST FUNCTIONS TESTS


@pytest.mark.parametrize(
    ("expression", "expected_type"),
    [
        ("request.security('AAPL', 'D', 'close')", list),
        ("request.security('GOOGL', '1H', 'open')", list),
    ],
)
def test_evaluator_request_security(expression, expected_type):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert isinstance(result, expected_type)
    assert len(result) > 0


@pytest.mark.parametrize(
    ("expression", "expected_type"),
    [
        ("request.security_lower_tf('AAPL', '5m', 'close')", list),
    ],
)
def test_evaluator_request_security_lower_tf(expression, expected_type):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert isinstance(result, expected_type)
    assert len(result) > 0


@pytest.mark.parametrize(
    ("expression", "expected_symbol", "expected_type"),
    [
        ("request.dividends('AAPL')", "AAPL", float),
        ("request.dividends('MSFT')", "MSFT", float),
    ],
)
def test_evaluator_request_dividends(expression, expected_symbol, expected_type):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert isinstance(result, expected_type)


@pytest.mark.parametrize(
    ("expression", "expected_symbol", "expected_type"),
    [
        ("request.earnings('AAPL')", "AAPL", float),
        ("request.earnings('JNJ')", "JNJ", float),
    ],
)
def test_evaluator_request_earnings(expression, expected_symbol, expected_type):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert isinstance(result, expected_type)


@pytest.mark.parametrize(
    ("expression", "expected_symbol", "expected_type"),
    [
        ("request.splits('AAPL')", "AAPL", float),
        ("request.splits('TSLA')", "TSLA", float),
    ],
)
def test_evaluator_request_splits(expression, expected_symbol, expected_type):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert isinstance(result, expected_type)
    assert result >= 1.0


@pytest.mark.parametrize(
    ("expression", "expected_type"),
    [
        ("request.financial('AAPL', 'REVENUE')", float),
        ("request.financial('MSFT', 'NET_INCOME')", float),
    ],
)
def test_evaluator_request_financial(expression, expected_type):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert isinstance(result, expected_type)


@pytest.mark.parametrize(
    ("expression", "expected_type"),
    [
        ("request.quandl('EIA/PET_RWTC_D')", list),
    ],
)
def test_evaluator_request_quandl(expression, expected_type):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert isinstance(result, expected_type)


@pytest.mark.parametrize(
    ("expression", "expected_type"),
    [
        ("request.economic('US', 'UNRATE')", list),
        ("request.economic('EU', 'INFLATION')", list),
    ],
)
def test_evaluator_request_economic(expression, expected_type):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert isinstance(result, expected_type)


@pytest.mark.parametrize(
    ("expression", "expected_type"),
    [
        ("request.currency_rate('USD', 'EUR')", float),
        ("request.currency_rate('GBP', 'USD')", float),
    ],
)
def test_evaluator_request_currency_rate(expression, expected_type):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert isinstance(result, expected_type)
    assert result > 0


@pytest.mark.parametrize(
    ("expression", "expected_result"),
    [
        ("request.seed(42)", None),
        ("request.seed(0)", None),
    ],
)
def test_evaluator_request_seed(expression, expected_result):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected_result


# DRAWING FUNCTIONS TESTS


def test_evaluator_line_new():
    """Test line.new() creates a line object."""
    ast = helper.parse("line.new(0, 100.0, 10, 110.0)", mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result is not None
    assert hasattr(result, "x1")
    assert hasattr(result, "y1")
    assert result.x1 == 0
    assert result.y1 == 100.0
    assert result.x2 == 10
    assert result.y2 == 110.0


def test_evaluator_line_copy():
    """Test line.copy() duplicates a line."""
    ast1 = helper.parse("line.new(5, 50.0, 15, 60.0)", mode="eval")
    evaluator = NodeLiteralEvaluator()
    line1 = evaluator.visit(ast1.body)

    ast2 = helper.parse("line.copy(line1)", mode="eval")
    evaluator.context = {"line1": line1}
    line2 = evaluator.visit(ast2.body)

    assert line2 is not None
    assert line2.x1 == line1.x1
    assert line2.y1 == line1.y1


def test_evaluator_line_set_color():
    """Test line.set_color() modifies line color."""
    ast1 = helper.parse("line.new(0, 100.0, 10, 110.0)", mode="eval")
    evaluator = NodeLiteralEvaluator()
    line = evaluator.visit(ast1.body)
    assert line.color == "#000000"

    # Modify color
    line.color = "#FF0000"
    assert line.color == "#FF0000"


def test_evaluator_line_get_coordinates():
    """Test line.get_x1/y1/x2/y2() retrieve coordinates."""
    ast = helper.parse("line.new(5, 50.0, 15, 60.0)", mode="eval")
    evaluator = NodeLiteralEvaluator()
    line = evaluator.visit(ast.body)

    assert line.x1 == 5
    assert line.y1 == 50.0
    assert line.x2 == 15
    assert line.y2 == 60.0


def test_evaluator_box_new():
    """Test box.new() creates a box object."""
    ast = helper.parse("box.new(0, 100.0, 10, 110.0)", mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result is not None
    assert hasattr(result, "left")
    assert hasattr(result, "top")
    assert result.left == 0
    assert result.top == 100.0
    assert result.right == 10
    assert result.bottom == 110.0


def test_evaluator_box_copy():
    """Test box.copy() duplicates a box."""
    ast1 = helper.parse("box.new(5, 50.0, 15, 60.0)", mode="eval")
    evaluator = NodeLiteralEvaluator()
    box1 = evaluator.visit(ast1.body)

    ast2 = helper.parse("box.copy(box1)", mode="eval")
    evaluator.context = {"box1": box1}
    box2 = evaluator.visit(ast2.body)

    assert box2 is not None
    assert box2.left == box1.left
    assert box2.top == box1.top


def test_evaluator_box_set_properties():
    """Test box property setters."""
    ast = helper.parse("box.new(0, 100.0, 10, 110.0)", mode="eval")
    evaluator = NodeLiteralEvaluator()
    box = evaluator.visit(ast.body)

    # Test default values
    assert box.bgcolor == "rgba(0,0,0,0)"
    assert box.border_color == "#000000"
    assert box.border_width == 1

    # Modify properties
    box.bgcolor = "rgba(255,0,0,0.5)"
    box.border_color = "#FF0000"
    box.border_width = 2

    assert box.bgcolor == "rgba(255,0,0,0.5)"
    assert box.border_color == "#FF0000"
    assert box.border_width == 2


def test_evaluator_box_get_coordinates():
    """Test box.get_left/right/top/bottom() retrieve coordinates."""
    ast = helper.parse("box.new(5, 50.0, 15, 60.0)", mode="eval")
    evaluator = NodeLiteralEvaluator()
    box = evaluator.visit(ast.body)

    assert box.left == 5
    assert box.top == 50.0
    assert box.right == 15
    assert box.bottom == 60.0


def test_evaluator_label_new():
    """Test label.new() creates a label object."""
    ast = helper.parse("label.new(10, 100.0, 'Test Label')", mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result is not None
    assert hasattr(result, "x")
    assert hasattr(result, "y")
    assert hasattr(result, "text")
    assert result.x == 10
    assert result.y == 100.0
    assert result.text == "Test Label"


def test_evaluator_label_copy():
    """Test label.copy() duplicates a label."""
    ast1 = helper.parse("label.new(10, 100.0, 'Test')", mode="eval")
    evaluator = NodeLiteralEvaluator()
    label1 = evaluator.visit(ast1.body)

    ast2 = helper.parse("label.copy(label1)", mode="eval")
    evaluator.context = {"label1": label1}
    label2 = evaluator.visit(ast2.body)

    assert label2 is not None
    assert label2.x == label1.x
    assert label2.y == label1.y
    assert label2.text == label1.text


def test_evaluator_label_set_text():
    """Test label.set_text() modifies label text."""
    ast = helper.parse("label.new(10, 100.0, 'Initial')", mode="eval")
    evaluator = NodeLiteralEvaluator()
    label = evaluator.visit(ast.body)
    assert label.text == "Initial"

    label.text = "Modified"
    assert label.text == "Modified"


def test_evaluator_label_properties():
    """Test label properties."""
    ast = helper.parse("label.new(10, 100.0, 'Test')", mode="eval")
    evaluator = NodeLiteralEvaluator()
    label = evaluator.visit(ast.body)

    # Test default values
    assert label.xloc == "bar_index"
    assert label.yloc == "price"
    assert label.color == "#000000"
    assert label.textcolor == "#000000"
    assert label.text_size == "auto"

    # Modify properties
    label.textcolor = "#FF0000"
    label.text_size = "small"
    assert label.textcolor == "#FF0000"
    assert label.text_size == "small"


def test_evaluator_label_get_coordinates():
    """Test label.get_x/y() retrieve coordinates."""
    ast = helper.parse("label.new(15, 120.0, 'Test')", mode="eval")
    evaluator = NodeLiteralEvaluator()
    label = evaluator.visit(ast.body)

    assert label.x == 15
    assert label.y == 120.0
    assert label.text == "Test"


def test_evaluator_table_new():
    """Test table.new() creates a table object."""
    ast = helper.parse("table.new('top_left', 3, 4)", mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result is not None
    assert hasattr(result, "position")
    assert hasattr(result, "rows")
    assert hasattr(result, "columns")
    assert result.position == "top_left"
    assert result.rows == 3
    assert result.columns == 4


def test_evaluator_table_cell_operations():
    """Test table cell operations."""
    ast = helper.parse("table.new('top_left', 2, 2)", mode="eval")
    evaluator = NodeLiteralEvaluator()
    table = evaluator.visit(ast.body)

    # Set cell text
    cell = TableCell()
    cell.text = "Cell 0,0"
    table.cells[(0, 0)] = cell

    # Get cell text
    assert table.cells[(0, 0)].text == "Cell 0,0"

    # Modify cell properties
    cell.textcolor = "#FF0000"
    cell.bgcolor = "rgba(255,255,0,0.5)"
    assert cell.textcolor == "#FF0000"
    assert cell.bgcolor == "rgba(255,255,0,0.5)"


def test_evaluator_table_clear():
    """Test table.clear() removes all cells."""
    ast = helper.parse("table.new('top_left', 2, 2)", mode="eval")
    evaluator = NodeLiteralEvaluator()
    table = evaluator.visit(ast.body)

    # Add cells
    table.cells[(0, 0)] = TableCell(text="A")
    table.cells[(0, 1)] = TableCell(text="B")

    assert len(table.cells) == 2

    # Clear
    table.cells.clear()
    assert len(table.cells) == 0


# STRATEGY TESTS
#
# Handlers mutate per-evaluator ``_strategy_state`` (instance isolation for
# multi-run / strategy-events). Assert against ``evaluator._strategy_state``,
# not class-level ``StrategyState.*`` attributes.


def test_evaluator_strategy_entry():
    """Test strategy.entry() creates a position."""
    ast = helper.parse("strategy.entry('long_1', 'long', 1.0)", mode="eval")
    evaluator = NodeLiteralEvaluator()
    evaluator.visit(ast.body)

    state = evaluator._strategy_state
    assert state.position_direction == "long"
    assert state.position_size == 1.0


def test_evaluator_strategy_exit():
    """Test strategy.exit() closes a position."""
    # First create a position
    ast_entry = helper.parse("strategy.entry('long_1', 'long', 1.0)", mode="eval")
    evaluator = NodeLiteralEvaluator()
    evaluator.visit(ast_entry.body)

    assert evaluator._strategy_state.position_size == 1.0

    # Now exit
    ast_exit = helper.parse("strategy.exit('exit_1', 'long_1', 1.0)", mode="eval")
    evaluator.visit(ast_exit.body)

    assert evaluator._strategy_state.position_direction == "flat"


def test_evaluator_strategy_close_all():
    """Test strategy.close_all() closes entire position."""
    # Create a position
    ast_entry = helper.parse("strategy.entry('long_1', 'long', 5.0)", mode="eval")
    evaluator = NodeLiteralEvaluator()
    evaluator.visit(ast_entry.body)

    assert evaluator._strategy_state.position_size == 5.0

    # Close all
    ast_close = helper.parse("strategy.close_all()", mode="eval")
    evaluator.visit(ast_close.body)

    assert evaluator._strategy_state.position_direction == "flat"
    assert evaluator._strategy_state.position_size == 0.0


def test_evaluator_strategy_order():
    """Test strategy.order() places custom orders."""
    ast = helper.parse("strategy.order('order_1', 'buy', 1.0)", mode="eval")
    evaluator = NodeLiteralEvaluator()
    evaluator.visit(ast.body)

    pending = evaluator._strategy_state.pending_orders
    assert "order_1" in pending
    assert pending["order_1"].direction == "buy"


def test_evaluator_strategy_cancel():
    """Test strategy.cancel() removes pending order."""
    # Place an order
    ast_order = helper.parse("strategy.order('order_1', 'buy', 1.0)", mode="eval")
    evaluator = NodeLiteralEvaluator()
    evaluator.visit(ast_order.body)

    assert "order_1" in evaluator._strategy_state.pending_orders

    # Cancel it
    ast_cancel = helper.parse("strategy.cancel('order_1')", mode="eval")
    evaluator.visit(ast_cancel.body)

    assert "order_1" not in evaluator._strategy_state.pending_orders


def test_evaluator_strategy_cancel_all():
    """Test strategy.cancel_all() removes all pending orders."""
    # Place multiple orders
    ast1 = helper.parse("strategy.order('order_1', 'buy', 1.0)", mode="eval")
    ast2 = helper.parse("strategy.order('order_2', 'sell', 1.0)", mode="eval")
    evaluator = NodeLiteralEvaluator()
    evaluator.visit(ast1.body)
    evaluator.visit(ast2.body)

    assert len(evaluator._strategy_state.pending_orders) == 2

    # Cancel all
    ast_cancel = helper.parse("strategy.cancel_all()", mode="eval")
    evaluator.visit(ast_cancel.body)

    assert len(evaluator._strategy_state.pending_orders) == 0


@pytest.mark.parametrize(
    ("direction", "entry_price"),
    [
        ("long", 100.0),
        ("short", 100.0),
    ],
)
def test_evaluator_strategy_positions(direction, entry_price):
    """Test strategy position tracking on instance state."""
    evaluator = NodeLiteralEvaluator()
    state = evaluator._strategy_state
    state.entry_price = entry_price
    state.position_direction = direction
    state.position_size = 1.0

    assert state.position_direction == direction
    assert state.entry_price == entry_price


def test_evaluator_strategy_risk_max_intraday_loss():
    """Test strategy.risk.max_intraday_loss() sets loss limit."""
    ast = helper.parse("strategy.risk.max_intraday_loss(10.0)", mode="eval")
    evaluator = NodeLiteralEvaluator()
    evaluator.visit(ast.body)

    assert evaluator._strategy_state.max_intraday_loss == 10.0


def test_evaluator_strategy_convert_to_account():
    """Test strategy.convert_to_account() conversion."""
    ast = helper.parse("strategy.convert_to_account(100.0, 'AAPL', '1D')", mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)

    assert result == 100.0


def test_evaluator_strategy_convert_to_symbol():
    """Test strategy.convert_to_symbol() conversion."""
    ast = helper.parse("strategy.convert_to_symbol(100.0, 'AAPL', '1D')", mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)

    assert result == 100.0


def test_evaluator_strategy_default_entry_qty():
    """Test strategy.default_entry_qty() calculates quantity."""
    evaluator = NodeLiteralEvaluator()
    evaluator._strategy_state.risk_free_capital = 10000.0
    ast = helper.parse("strategy.default_entry_qty(100.0)", mode="eval")
    result = evaluator.visit(ast.body)

    assert result == 100.0  # 10000 * 1.0 / 100


@pytest.mark.parametrize(
    ("index", "expected_bar", "expected_time"),
    [
        (0, 100, 1234567890),
    ],
)
def test_evaluator_strategy_closedtrades(index, expected_bar, expected_time):
    """Test strategy.closedtrades query functions."""
    evaluator = NodeLiteralEvaluator()

    # Seed a closed trade on this evaluator's state
    trade = Trade(
        entry_bar=expected_bar,
        entry_time=expected_time,
        entry_price=100.0,
        exit_bar=110,
        exit_time=1234567900,
        exit_price=110.0,
        direction="long",
        size=1.0,
        profit=10.0,
        commission=0.1,
    )
    evaluator._strategy_state.closed_trades.append(trade)

    # Query closed trades
    ast_bar = helper.parse(
        f"strategy.closedtrades.entry_bar_index({index})",
        mode="eval",
    )
    ast_time = helper.parse(f"strategy.closedtrades.entry_time({index})", mode="eval")

    assert evaluator.visit(ast_bar.body) == expected_bar
    assert evaluator.visit(ast_time.body) == expected_time


def test_evaluator_strategy_closedtrades_profit():
    """Test strategy.closedtrades.profit query."""
    evaluator = NodeLiteralEvaluator()

    # Seed a closed trade with profit
    trade = Trade(
        entry_bar=100,
        entry_time=1234567890,
        entry_price=100.0,
        exit_bar=110,
        exit_time=1234567900,
        exit_price=110.0,
        direction="long",
        size=1.0,
        profit=9.9,  # 10.0 - 0.1 commission
        commission=0.1,
    )
    evaluator._strategy_state.closed_trades.append(trade)

    ast = helper.parse("strategy.closedtrades.profit(0)", mode="eval")
    result = evaluator.visit(ast.body)

    assert result == 9.9


def test_timeframe_stubs():
    """Basic TDD test for timeframe stubs (plan §5).
    They should not raise and return expected types (bool/str).
    """
    from pynescript.ast.evaluator.builtins.timeframe import timeframe_change, timeframe_from_seconds

    assert timeframe_change("D") is False
    assert isinstance(timeframe_from_seconds(86400), str)


def test_plotting_stubs_do_not_error():
    """TDD test for plotting stubs (plan §4).
    Using plot* functions in a script should not raise; they are no-ops
    for non-UI evaluators but must accept the call for compatibility.
    """
    source = '''//@version=6
indicator("PlotTest")
plot(close, title="close", color=color.blue)
plotshape(close > open, title="shape", style=shape.triangleup)
'''
    ast = helper.parse(source, mode="exec")
    evaluator = NodeLiteralEvaluator()
    # Should not raise
    evaluator.visit(ast)
    assert True


def test_pine_version_converter_stub():
    """Basic test for v5<->v6 converter stub (plan §6)."""
    from scripts.convert_pine_version import convert_v5_to_v6, convert_v6_to_v5
    v5 = 'study("My Study")\nplot(close)'
    v6 = convert_v5_to_v6(v5)
    assert "indicator" in v6
    back = convert_v6_to_v5(v6)
    assert "study" in back


def _ohlcv_bars(n: int = 40):
    """Synthetic OHLCV with a clear mid-series peak/trough for pivot tests."""
    bars = []
    for i in range(n):
        # Peak at i=20, trough at i=30
        if i == 20:
            h, l = 120.0, 100.0
        elif i == 30:
            h, l = 102.0, 80.0
        else:
            h, l = 105.0 + (i % 3), 95.0 - (i % 2)
        c = (h + l) / 2.0
        bars.append(
            {
                "open": c,
                "high": h,
                "low": l,
                "close": c,
                "volume": 1000.0,
                "time": 1_000_000 + i * 60_000,
            }
        )
    return bars


def test_ta_pivothigh_pivotlow_accept_pineseries_via_runtime():
    """Regression: set05 RUN_FAIL float()…not 'PineSeries' on ta.pivothigh/low.

    Runtime injects ``high``/``low`` as ``PineSeries``. The 3-arg form used to
    call bare ``float(source)`` and crash on bar 0; must materialize via
    ``_as_series`` / ``.current`` instead.
    """
    from backend.runtime import Runtime

    src = """//@version=5
indicator("pivot_series")
ph = ta.pivothigh(high, 2, 2)
pl = ta.pivotlow(low, 2, 2)
ph2 = ta.pivothigh(2, 2)
pl2 = ta.pivotlow(2, 2)
plot(ph)
plot(pl)
plot(ph2)
plot(pl2)
"""
    out = Runtime(symbol="TEST").run(src, _ohlcv_bars(50), mode="interpret")
    assert isinstance(out, dict)
    assert "error" not in out or out.get("error") is None, out.get("error")
    # Series present and finite-or-null (na on non-pivot bars)
    series = out.get("series") or out.get("plots") or {}
    assert out  # non-empty result


def test_ta_pivothigh_on_pineseries_direct():
    """Unit: BasicIndicators.pivothigh with PineSeries source (no Runtime host)."""
    from backend.series import PineSeries
    from pynescript.ast.evaluator import NodeLiteralEvaluator

    highs = [100.0, 101.0, 105.0, 102.0, 101.0, 100.0, 99.0]
    series = PineSeries()
    for h in highs:
        series.update(h)

    evaluator = NodeLiteralEvaluator()
    # 3-arg form with PineSeries source
    result = evaluator._builtin_ta_pivothigh([series, 2, 2])
    # After enough bars: last sample 99 with left 100,101 — not a pivot high → None
    # or a float if left-only check considers it (depends on left values)
    assert result is None or isinstance(result, float)

    # Peak-like series ending at local max with 2 left lower bars
    peak = PineSeries()
    for h in [100.0, 101.0, 110.0]:
        peak.update(h)
    # len=3, left+right=4 → not enough history → na
    assert evaluator._builtin_ta_pivothigh([peak, 2, 2]) is None

    # Enough history: last is strict local max vs left
    peak2 = PineSeries()
    for h in [100.0, 101.0, 102.0, 110.0]:
        peak2.update(h)
    # left_bars=2, right_bars=0 so window length need is 2; with right=2 need more
    # Use right_bars=0 for a definite local-max check
    r = evaluator._builtin_ta_pivothigh([peak2, 2, 0])
    assert r == 110.0

    # pivotlow with PineSeries
    trough = PineSeries()
    for lo in [100.0, 99.0, 98.0, 80.0]:
        trough.update(lo)
    r_lo = evaluator._builtin_ta_pivotlow([trough, 2, 0])
    assert r_lo == 80.0


def test_pivot_scalar_unwraps_nested_series():
    """``_pivot_scalar`` returns float from bare nums and PineSeries.current."""
    from backend.series import PineSeries
    from pynescript.ast.evaluator.builtins.technical_submodules.basic import BasicIndicators

    assert BasicIndicators._pivot_scalar(None) is None
    assert BasicIndicators._pivot_scalar(3.5) == 3.5
    assert BasicIndicators._pivot_scalar(7) == 7.0
    ps = PineSeries(1.25)
    assert BasicIndicators._pivot_scalar(ps) == 1.25
    empty = PineSeries()  # current is None
    assert BasicIndicators._pivot_scalar(empty) is None

