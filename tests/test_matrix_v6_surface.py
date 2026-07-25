# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# SPDX-License-Identifier: LGPL-3.0-or-later

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
