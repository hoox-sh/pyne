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

"""Coverage for official TV matrix.* surface + related v6 gaps."""

from __future__ import annotations

import math

import pytest

from pynescript.ast import helper
from pynescript.ast.evaluator import NodeLiteralEvaluator
from pynescript.ast.evaluator.builtins.matrix import Matrix


def test_matrix_linear_algebra_det_inv_trace():
    m = Matrix(2, 2, 0.0)
    m.set(0, 0, 1.0)
    m.set(0, 1, 2.0)
    m.set(1, 0, 3.0)
    m.set(1, 1, 4.0)
    assert math.isclose(m.det(), -2.0, abs_tol=1e-9)
    assert math.isclose(m.trace(), 5.0, abs_tol=1e-9)
    inv = m.inv()
    product = m.mult(inv)
    assert math.isclose(product.get(0, 0), 1.0, abs_tol=1e-9)
    assert math.isclose(product.get(1, 1), 1.0, abs_tol=1e-9)


def test_matrix_predicates_and_sort():
    m = Matrix(2, 2, 0.0)
    m.set(0, 0, 1.0)
    m.set(1, 1, 1.0)
    assert m.is_square()
    assert m.is_identity()
    assert m.is_diagonal()
    assert m.is_symmetric()

    m2 = Matrix(3, 2, 0.0)
    m2.set(0, 0, 3)
    m2.set(0, 1, 30)
    m2.set(1, 0, 1)
    m2.set(1, 1, 10)
    m2.set(2, 0, 2)
    m2.set(2, 1, 20)
    m2.sort(0, "ascending")
    assert m2.get(0, 0) == 1
    assert m2.get(1, 0) == 2
    assert m2.get(2, 0) == 3
    idx = m2.sort_indices(0, "descending")
    assert idx == [2, 1, 0]


def test_matrix_eval_dispatch_det_and_avg():
    e = NodeLiteralEvaluator()
    src = (
        "matrix.det(matrix.new(2, 2, 0.0))"  # zero matrix det = 0
    )
    # Build via Python and dispatch
    m = Matrix(2, 2, 0.0)
    m.set(0, 0, 2.0)
    m.set(1, 1, 3.0)
    handler = e._build_builtin_map()["matrix.det"]
    assert math.isclose(handler([m]), 6.0, abs_tol=1e-9)
    avg_h = e._build_builtin_map()["matrix.avg"]
    assert math.isclose(avg_h([m]), 1.25, abs_tol=1e-9)


def test_runtime_error_raises():
    e = NodeLiteralEvaluator()
    ast = helper.parse("runtime.error('stop')", mode="eval")
    with pytest.raises(RuntimeError, match="stop"):
        e.visit(ast.body)


def test_input_text_area_returns_value():
    e = NodeLiteralEvaluator()
    ast = helper.parse("input.text_area('notes here', 'Notes')", mode="eval")
    assert e.visit(ast.body) == "notes here"
    assert e._input_declarations[0]["type"] == "text_area"


def test_ta_percentile_functions():
    e = NodeLiteralEvaluator()
    series = [1.0, 2.0, 3.0, 4.0, 5.0]
    lin = e._build_builtin_map()["ta.percentile_linear_interpolation"]
    near = e._build_builtin_map()["ta.percentile_nearest_rank"]
    assert lin([series, 5, 50]) == 3.0
    assert near([series, 5, 50]) == 3.0


def test_order_ascending_descending_constants():
    """TV order.* used by array/matrix.sort must resolve (not na)."""
    e = NodeLiteralEvaluator()
    e.evaluate_script(
        """
//@version=5
indicator("order-const")
a = order.ascending
d = order.descending
"""
    )
    assert e.context["a"] == 1
    assert e.context["d"] == -1


def test_matrix_sort_order_descending_numeric():
    e = NodeLiteralEvaluator()
    e.evaluate_script(
        """
//@version=5
indicator("m-sort-desc")
m = matrix.new<float>(3, 1, 0.0)
matrix.set(m, 0, 0, 1.0)
matrix.set(m, 1, 0, 3.0)
matrix.set(m, 2, 0, 2.0)
matrix.sort(m, 0, order.descending)
a0 = matrix.get(m, 0, 0)
a1 = matrix.get(m, 1, 0)
a2 = matrix.get(m, 2, 0)
"""
    )
    assert (e.context["a0"], e.context["a1"], e.context["a2"]) == (3.0, 2.0, 1.0)


def test_matrix_sort_udt_sort_field():
    """matrix.sort with UDT cells + sort_field must not crash / must key field."""
    e = NodeLiteralEvaluator()
    e.evaluate_script(
        """
//@version=5
indicator("m-udt-sort")
type Item
    float v = 0.0
m = matrix.new<Item>(3, 1)
matrix.set(m, 0, 0, Item.new(5.0))
matrix.set(m, 1, 0, Item.new(1.0))
matrix.set(m, 2, 0, Item.new(3.0))
matrix.sort(m, 0, order.ascending, "v")
t0 = matrix.get(m, 0, 0)
t1 = matrix.get(m, 1, 0)
t2 = matrix.get(m, 2, 0)
idx = matrix.sort_indices(m, 0, order.descending, "v")
"""
    )
    assert e.context["t0"].get_field("v") == 1.0
    assert e.context["t1"].get_field("v") == 3.0
    assert e.context["t2"].get_field("v") == 5.0
    # After ascending sort, descending indices of sorted matrix: last→first
    assert e.context["idx"] == [2, 1, 0]


def test_matrix_new_empty_and_add_row_at_index():
    """TV matrix.new<T>() 0×0 + add_row/col at index 0 with array payload."""
    e = NodeLiteralEvaluator()
    e.evaluate_script(
        """
//@version=5
indicator("m-empty")
m = matrix.new<int>()
a = array.from(1, 3)
matrix.add_row(m, 0, a)
r = matrix.rows(m)
c = matrix.columns(m)
v00 = matrix.get(m, 0, 0)
v01 = matrix.get(m, 0, 1)
m2 = matrix.new<int>()
b = array.from(1, 3)
matrix.add_col(m2, 0, b)
r2 = matrix.rows(m2)
c2 = matrix.columns(m2)
w00 = matrix.get(m2, 0, 0)
w10 = matrix.get(m2, 1, 0)
"""
    )
    assert e.context["r"] == 1
    assert e.context["c"] == 2
    assert e.context["v00"] == 1
    assert e.context["v01"] == 3
    assert e.context["r2"] == 2
    assert e.context["c2"] == 1
    assert e.context["w00"] == 1
    assert e.context["w10"] == 3


def test_matrix_add_row_inserts_not_only_appends():
    """matrix.add_row(id, row, array) inserts at row index."""
    e = NodeLiteralEvaluator()
    e.evaluate_script(
        """
//@version=5
indicator("m-insert")
m = matrix.new<float>(2, 2, 0.0)
matrix.set(m, 0, 0, 1.0)
matrix.set(m, 1, 0, 2.0)
matrix.add_row(m, 0, array.from(9.0, 8.0))
r0 = matrix.get(m, 0, 0)
r1 = matrix.get(m, 1, 0)
r2 = matrix.get(m, 2, 0)
rows = matrix.rows(m)
"""
    )
    assert e.context["rows"] == 3
    assert e.context["r0"] == 9.0
    assert e.context["r1"] == 1.0
    assert e.context["r2"] == 2.0


def test_array_sort_udt_sort_field():
    """array.sort / sort_indices honor sort_field by UDT field name."""
    e = NodeLiteralEvaluator()
    e.evaluate_script(
        """
//@version=5
indicator("a-udt-sort")
type Item
    float v = 0.0
    int id = 0
a = array.new<Item>(0)
array.push(a, Item.new(2.0, 30))
array.push(a, Item.new(2.0, 10))
array.push(a, Item.new(1.0, 20))
array.sort(a, order.ascending, "id")
i0 = array.get(a, 0)
i1 = array.get(a, 1)
i2 = array.get(a, 2)
b = array.new<Item>(0)
array.push(b, Item.new(3.0, 1))
array.push(b, Item.new(1.0, 2))
array.push(b, Item.new(2.0, 3))
idx = array.sort_indices(b, order.ascending, "v")
array.sort(b, sort_field="v")
bv0 = array.get(b, 0)
"""
    )
    assert e.context["i0"].get_field("id") == 10
    assert e.context["i1"].get_field("id") == 20
    assert e.context["i2"].get_field("id") == 30
    assert e.context["idx"] == [1, 2, 0]
    assert e.context["bv0"].get_field("v") == 1.0


def test_array_binary_search_udt_sort_field():
    """August 2026: binary_search* on UDT arrays honor sort_field (name / index)."""
    e = NodeLiteralEvaluator()
    e.evaluate_script(
        """
//@version=6
indicator("a-udt-bsearch")
type Item
    float v = 0.0
    int id = 0
a = array.new<Item>(0)
array.push(a, Item.new(1.0, 10))
array.push(a, Item.new(2.0, 20))
array.push(a, Item.new(2.0, 30))
array.push(a, Item.new(3.0, 40))
array.sort(a, order.ascending, "id")
by_name = array.binary_search(a, 20, "id")
by_idx = array.binary_search(a, 40, 1)
by_kw = array.binary_search(a, 10, sort_field="id")
missing = array.binary_search(a, 99, "id")
// default sort_field is 0 (first field, `v`) — array is sorted by id, so
// search `v` only after re-sorting by that field.
array.sort(a, order.ascending, "v")
by_default = array.binary_search(a, 3.0)
left = array.binary_search_leftmost(a, 2.0, "v")
right = array.binary_search_rightmost(a, 2.0, "v")
left_miss = array.binary_search_leftmost(a, 9.0, "v")
right_miss = array.binary_search_rightmost(a, 9.0, "v")
// search by passing a UDT whose compared field is the key
needle = Item.new(1.0, 99)
by_obj = array.binary_search(a, needle, "v")
"""
    )
    assert e.context["by_name"] == 1
    assert e.context["by_idx"] == 3
    assert e.context["by_kw"] == 0
    assert e.context["missing"] == -1
    assert e.context["by_default"] == 3
    assert e.context["left"] == 1
    assert e.context["right"] == 2
    assert e.context["left_miss"] == -1
    assert e.context["right_miss"] == -1
    assert e.context["by_obj"] == 0


def test_array_binary_search_udt_method_form():
    """Method form ``id.binary_search(value, sort_field)`` on a UDT array."""
    e = NodeLiteralEvaluator()
    e.evaluate_script(
        """
//@version=6
indicator("a-udt-bsearch-method")
type Item
    int id = 0
    float v = 0.0
a = array.from(Item.new(10, 1.0), Item.new(20, 2.0), Item.new(30, 3.0))
array.sort(a, sort_field="id")
hit = a.binary_search(20, "id")
miss = a.binary_search(99, "id")
left = a.binary_search_leftmost(20, sort_field="id")
"""
    )
    assert e.context["hit"] == 1
    assert e.context["miss"] == -1
    assert e.context["left"] == 1
