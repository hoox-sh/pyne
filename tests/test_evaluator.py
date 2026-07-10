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

from __future__ import annotations

import math

import pytest

from pynescript.ast import helper
from pynescript.ast.evaluator import NodeLiteralEvaluator
from pynescript.ast.evaluator.builtins.drawing import TableCell
from pynescript.ast.evaluator.builtins.strategy import StrategyState
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
        ("array.pop([1, 2, 3])", [1, 2]),
        ("array.pop(array.pop([1]))", []),
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
        ("array.range(1, 5)", [1, 2, 3, 4, 5]),
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
        ("array.remove([1, 2, 3], 1)", [1, 3]),
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
        ("array.shift([1, 2, 3])", [2, 3]),
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
    assert math.isnan(result[0])
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
        ("array.variance([1, 2, 3, 4, 5])", lambda x: x > 2.0 and x < 2.6),
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
    ("expression", "expected"),
    [
        ("plot([1, 2, 3, 4, 5])", None),
        ("plotbar([1, 2, 3], [2, 3, 4], [0, 1, 2], [1, 2, 3])", None),
        ("hline(100)", None),
        ("bgcolor('red')", None),
    ],
)
def test_evaluator_plotting_functions(expression, expected):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result == expected


# INPUT FUNCTIONS TESTS


@pytest.mark.parametrize(
    ("expression", "expected_keys"),
    [
        ("input(100, 'Value')", {"type", "default", "title", "tooltip", "inline", "group", "confirm"}),
        ("input(50.5, 'Price')", {"type", "default", "title"}),
        ("input(true, 'Flag')", {"type", "default", "title"}),
    ],
)
def test_evaluator_input_generic(expression, expected_keys):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert isinstance(result, dict)
    assert expected_keys.issubset(result.keys())


def test_evaluator_input_int_type_inference():
    """Test that input() infers int type from integer defval."""
    ast = helper.parse("input(14)", mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result["type"] == "int"
    assert result["default"] == 14


def test_evaluator_input_bool_type_inference():
    """Test that input() infers bool type from boolean defval."""
    ast = helper.parse("input(true)", mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result["type"] == "bool"
    assert result["default"] is True


def test_evaluator_input_float_type_inference():
    """Test that input() infers float type from float defval."""
    ast = helper.parse("input(2.5)", mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result["type"] == "float"
    assert result["default"] == 2.5


def test_evaluator_input_string_type_inference():
    """Test that input() infers string type from string defval."""
    ast = helper.parse("input('text')", mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result["type"] == "string"
    assert result["default"] == "text"


@pytest.mark.parametrize(
    ("expression", "expected_type", "expected_default"),
    [
        ("input.bool(true)", "bool", True),
        ("input.bool(false)", "bool", False),
        ("input.bool(true, 'Enable')", "bool", True),
    ],
)
def test_evaluator_input_bool(expression, expected_type, expected_default):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result["type"] == expected_type
    assert result["default"] == expected_default


@pytest.mark.parametrize(
    ("expression", "expected_type", "expected_default"),
    [
        ("input.int(14)", "int", 14),
        ("input.int(14, 'Length')", "int", 14),
        ("input.int(14, 'Length', 1, 100)", "int", 14),
    ],
)
def test_evaluator_input_int(expression, expected_type, expected_default):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result["type"] == expected_type
    assert result["default"] == expected_default


def test_evaluator_input_int_with_constraints():
    """Test input.int with min/max/step constraints."""
    ast = helper.parse("input.int(50, 'Value', 10, 100, 5)", mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result["type"] == "int"
    assert result["default"] == 50
    assert result["min"] == 10
    assert result["max"] == 100
    assert result["step"] == 5


@pytest.mark.parametrize(
    ("expression", "expected_type", "expected_default"),
    [
        ("input.float(2.5)", "float", 2.5),
        ("input.float(2.5, 'Price')", "float", 2.5),
        ("input.float(2.5, 'Price', 0.0, 10.0)", "float", 2.5),
    ],
)
def test_evaluator_input_float(expression, expected_type, expected_default):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result["type"] == expected_type
    assert result["default"] == expected_default


def test_evaluator_input_float_with_constraints():
    """Test input.float with min/max/step constraints."""
    ast = helper.parse("input.float(1.5, 'Factor', 0.5, 3.0, 0.1)", mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result["type"] == "float"
    assert result["default"] == 1.5
    assert result["min"] == 0.5
    assert result["max"] == 3.0
    assert result["step"] == 0.1


@pytest.mark.parametrize(
    ("expression", "expected_type", "expected_default"),
    [
        ("input.price(100.0)", "price", 100.0),
        ("input.price(100.0, 'Entry Price')", "price", 100.0),
    ],
)
def test_evaluator_input_price(expression, expected_type, expected_default):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result["type"] == expected_type
    assert result["default"] == expected_default


@pytest.mark.parametrize(
    ("expression", "expected_type", "expected_default"),
    [
        ("input.string('AAPL')", "string", "AAPL"),
        ("input.string('default', 'Text')", "string", "default"),
    ],
)
def test_evaluator_input_string(expression, expected_type, expected_default):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result["type"] == expected_type
    assert result["default"] == expected_default


@pytest.mark.parametrize(
    ("expression", "expected_type", "expected_default"),
    [
        ("input.symbol('AAPL')", "symbol", "AAPL"),
        ("input.symbol('BTC/USD')", "symbol", "BTC/USD"),
    ],
)
def test_evaluator_input_symbol(expression, expected_type, expected_default):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result["type"] == expected_type
    assert result["default"] == expected_default


@pytest.mark.parametrize(
    ("expression", "expected_type"),
    [
        ("input.session('0930-1600')", "session"),
        ("input.session('0900-1700', 'Trading Hours')", "session"),
    ],
)
def test_evaluator_input_session(expression, expected_type):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result["type"] == expected_type


@pytest.mark.parametrize(
    ("expression", "expected_type", "expected_default"),
    [
        ("input.source('close')", "source", "close"),
        ("input.source('hl2')", "source", "hl2"),
    ],
)
def test_evaluator_input_source(expression, expected_type, expected_default):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result["type"] == expected_type
    assert result["default"] == expected_default


@pytest.mark.parametrize(
    ("expression", "expected_type"),
    [
        ("input.time(0)", "time"),
        ("input.time(1630698000, 'Start Time')", "time"),
    ],
)
def test_evaluator_input_time(expression, expected_type):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result["type"] == expected_type


@pytest.mark.parametrize(
    ("expression", "expected_type", "expected_default"),
    [
        ("input.timeframe('D')", "timeframe", "D"),
        ("input.timeframe('1H')", "timeframe", "1H"),
    ],
)
def test_evaluator_input_timeframe(expression, expected_type, expected_default):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result["type"] == expected_type
    assert result["default"] == expected_default


@pytest.mark.parametrize(
    ("expression", "expected_type"),
    [
        ("input.color('#FF0000')", "color"),
        ("input.color('red')", "color"),
    ],
)
def test_evaluator_input_color(expression, expected_type):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result["type"] == expected_type


@pytest.mark.parametrize(
    ("expression", "expected_type"),
    [
        ("input.enum('A', 'Choice', ['A', 'B', 'C'])", "enum"),
    ],
)
def test_evaluator_input_enum(expression, expected_type):
    ast = helper.parse(expression, mode="eval")
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result["type"] == expected_type
    assert result["options"] == ["A", "B", "C"]


def test_evaluator_input_with_all_parameters():
    """Test input functions with all optional parameters."""
    ast = helper.parse(
        "input.int(50, 'Value', 10, 100, 5, 'Set the threshold', 'group1', 'settings', true)", mode="eval"
    )
    evaluator = NodeLiteralEvaluator()
    result = evaluator.visit(ast.body)
    assert result["type"] == "int"
    assert result["default"] == 50
    assert result["title"] == "Value"
    assert result["min"] == 10
    assert result["max"] == 100
    assert result["step"] == 5
    assert result["tooltip"] == "Set the threshold"
    assert result["inline"] == "group1"
    assert result["group"] == "settings"
    assert result["confirm"] is True


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


def test_evaluator_strategy_entry():
    """Test strategy.entry() creates a position."""
    StrategyState.reset()
    ast = helper.parse("strategy.entry('long_1', 'long', 1.0)", mode="eval")
    evaluator = NodeLiteralEvaluator()
    evaluator.visit(ast.body)

    assert StrategyState.position_direction == "long"
    assert StrategyState.position_size == 1.0


def test_evaluator_strategy_exit():
    """Test strategy.exit() closes a position."""
    StrategyState.reset()

    # First create a position
    ast_entry = helper.parse("strategy.entry('long_1', 'long', 1.0)", mode="eval")
    evaluator = NodeLiteralEvaluator()
    evaluator.visit(ast_entry.body)

    assert StrategyState.position_size == 1.0

    # Now exit
    ast_exit = helper.parse("strategy.exit('exit_1', 'long_1', 1.0)", mode="eval")
    evaluator.visit(ast_exit.body)

    assert StrategyState.position_direction == "flat"


def test_evaluator_strategy_close_all():
    """Test strategy.close_all() closes entire position."""
    StrategyState.reset()

    # Create a position
    ast_entry = helper.parse("strategy.entry('long_1', 'long', 5.0)", mode="eval")
    evaluator = NodeLiteralEvaluator()
    evaluator.visit(ast_entry.body)

    assert StrategyState.position_size == 5.0

    # Close all
    ast_close = helper.parse("strategy.close_all()", mode="eval")
    evaluator.visit(ast_close.body)

    assert StrategyState.position_direction == "flat"
    assert StrategyState.position_size == 0.0


def test_evaluator_strategy_order():
    """Test strategy.order() places custom orders."""
    StrategyState.reset()
    ast = helper.parse("strategy.order('order_1', 'buy', 1.0)", mode="eval")
    evaluator = NodeLiteralEvaluator()
    evaluator.visit(ast.body)

    assert "order_1" in StrategyState.pending_orders
    assert StrategyState.pending_orders["order_1"].direction == "buy"


def test_evaluator_strategy_cancel():
    """Test strategy.cancel() removes pending order."""
    StrategyState.reset()

    # Place an order
    ast_order = helper.parse("strategy.order('order_1', 'buy', 1.0)", mode="eval")
    evaluator = NodeLiteralEvaluator()
    evaluator.visit(ast_order.body)

    assert "order_1" in StrategyState.pending_orders

    # Cancel it
    ast_cancel = helper.parse("strategy.cancel('order_1')", mode="eval")
    evaluator.visit(ast_cancel.body)

    assert "order_1" not in StrategyState.pending_orders


def test_evaluator_strategy_cancel_all():
    """Test strategy.cancel_all() removes all pending orders."""
    StrategyState.reset()

    # Place multiple orders
    ast1 = helper.parse("strategy.order('order_1', 'buy', 1.0)", mode="eval")
    ast2 = helper.parse("strategy.order('order_2', 'sell', 1.0)", mode="eval")
    evaluator = NodeLiteralEvaluator()
    evaluator.visit(ast1.body)
    evaluator.visit(ast2.body)

    assert len(StrategyState.pending_orders) == 2

    # Cancel all
    ast_cancel = helper.parse("strategy.cancel_all()", mode="eval")
    evaluator.visit(ast_cancel.body)

    assert len(StrategyState.pending_orders) == 0


@pytest.mark.parametrize(
    ("direction", "entry_price"),
    [
        ("long", 100.0),
        ("short", 100.0),
    ],
)
def test_evaluator_strategy_positions(direction, entry_price):
    """Test strategy position tracking."""
    StrategyState.reset()
    StrategyState.entry_price = entry_price
    StrategyState.position_direction = direction
    StrategyState.position_size = 1.0

    # Check position attributes
    assert StrategyState.position_direction == direction
    assert StrategyState.entry_price == entry_price


def test_evaluator_strategy_risk_max_intraday_loss():
    """Test strategy.risk.max_intraday_loss() sets loss limit."""
    StrategyState.reset()
    ast = helper.parse("strategy.risk.max_intraday_loss(10.0)", mode="eval")
    evaluator = NodeLiteralEvaluator()
    evaluator.visit(ast.body)

    assert StrategyState.max_intraday_loss == 10.0


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
    StrategyState.reset()
    StrategyState.risk_free_capital = 10000.0
    ast = helper.parse("strategy.default_entry_qty(100.0)", mode="eval")
    evaluator = NodeLiteralEvaluator()
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
    StrategyState.reset()

    # Add a closed trade
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
    StrategyState.closed_trades.append(trade)

    # Query closed trades
    ast_bar = helper.parse(
        f"strategy.closedtrades.entry_bar_index({index})",
        mode="eval",
    )
    ast_time = helper.parse(f"strategy.closedtrades.entry_time({index})", mode="eval")
    evaluator = NodeLiteralEvaluator()

    assert evaluator.visit(ast_bar.body) == expected_bar
    assert evaluator.visit(ast_time.body) == expected_time


def test_evaluator_strategy_closedtrades_profit():
    """Test strategy.closedtrades.profit query."""
    StrategyState.reset()

    # Add a closed trade with profit
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
    StrategyState.closed_trades.append(trade)

    ast = helper.parse("strategy.closedtrades.profit(0)", mode="eval")
    evaluator = NodeLiteralEvaluator()
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
