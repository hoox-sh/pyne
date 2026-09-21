"""Coverage tests for under-covered evaluator builtins and helpers.

Direct-call style (no Pine runtime loop): fast unit tests over Matrix,
numeric/string/color/ticker builtins, name resolution, the AST transformer,
``ta.sum``, and pure study helpers. Pine-style errors surface as ValueError.
"""

from __future__ import annotations

import math

from types import SimpleNamespace

import pytest

from pynescript.ast import helper
from pynescript.ast import node as ast
from pynescript.ast.evaluator import NodeLiteralEvaluator
from pynescript.ast.evaluator.builtins.color import Color
from pynescript.ast.evaluator.builtins.color import _parse_color_string
from pynescript.ast.evaluator.builtins.color import color_b
from pynescript.ast.evaluator.builtins.color import color_from_gradient
from pynescript.ast.evaluator.builtins.color import color_g
from pynescript.ast.evaluator.builtins.color import color_new
from pynescript.ast.evaluator.builtins.color import color_r
from pynescript.ast.evaluator.builtins.color import color_rgb
from pynescript.ast.evaluator.builtins.color import color_t
from pynescript.ast.evaluator.builtins.color import register_color_functions
from pynescript.ast.evaluator.builtins.matrix import Matrix
from pynescript.ast.evaluator.builtins.ticker import TickerInfo
from pynescript.ast.evaluator.builtins.ticker import _as_float_default
from pynescript.ast.evaluator.builtins.ticker import _as_int_or_none
from pynescript.ast.evaluator.builtins.ticker import _looks_like_number
from pynescript.ast.evaluator.builtins.ticker import extract_prefix
from pynescript.ast.evaluator.builtins.ticker import extract_ticker
from pynescript.ast.evaluator.builtins.ticker import register_ticker_functions
from pynescript.ast.evaluator.builtins.ticker import split_symbol
from pynescript.ast.evaluator.builtins.ticker import ticker_heikinashi
from pynescript.ast.evaluator.builtins.ticker import ticker_inherit
from pynescript.ast.evaluator.builtins.ticker import ticker_kagi
from pynescript.ast.evaluator.builtins.ticker import ticker_linebreak
from pynescript.ast.evaluator.builtins.ticker import ticker_modify
from pynescript.ast.evaluator.builtins.ticker import ticker_new
from pynescript.ast.evaluator.builtins.ticker import ticker_pointfigure
from pynescript.ast.evaluator.builtins.ticker import ticker_renko
from pynescript.ast.evaluator.builtins.ticker import ticker_standard
from pynescript.ast.evaluator.builtins.ticker import tickerid_v4
from pynescript.ast.evaluator.names import ast_qualified_name
from pynescript.ast.transformer import NodeTransformer
from pynescript.optimize.study import _bar_open_time
from pynescript.optimize.study import _mean_stats
from pynescript.optimize.study import _score_window
from pynescript.optimize.study import _slice_bars
from pynescript.optimize.study import _test_run_bars
from pynescript.optimize.study import is_strategy_script
from pynescript.optimize.study import run_once
from pynescript.optimize.study import run_study
from pynescript.optimize.types import ParamSpec
from pynescript.optimize.types import SearchSpace
from pynescript.optimize.types import StrategyStats
from pynescript.optimize.types import ValidationSpec


def _ev(**ctx: object) -> NodeLiteralEvaluator:
    return NodeLiteralEvaluator(context=dict(ctx))


def _eval_src(ev: NodeLiteralEvaluator, src: str) -> object:
    return ev.visit(helper.parse(src, mode="eval").body)


def _bars(n: int = 10) -> list[dict[str, object]]:
    return [{"time": float(i * 60000), "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0} for i in range(n)]


def _space() -> SearchSpace:
    return SearchSpace(params=[ParamSpec(name="p", kind="int", min=1, max=2)])


class _StubRuntime:
    def __init__(self, result: object = None) -> None:
        self.result: object = {"events": []} if result is None else result

    def run(self, *args: object, **kwargs: object) -> object:
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


# ---------------------------------------------------------------------------
# matrix.py — direct Matrix behaviour
# ---------------------------------------------------------------------------


class TestMatrixCore:
    def test_negative_dims_raise(self) -> None:
        with pytest.raises(ValueError):
            Matrix(-1, 2)

    def test_getitem_bad_key_raises(self) -> None:
        m: Matrix[int] = Matrix(2, 2, 0)
        with pytest.raises(TypeError):
            m[0]  # type: ignore[index]
        with pytest.raises(TypeError):
            m[(0,)]  # type: ignore[index]

    def test_setitem_bad_key_raises(self) -> None:
        m: Matrix[int] = Matrix(2, 2, 0)
        with pytest.raises(TypeError):
            m[0] = 1  # type: ignore[index]

    def test_get_set_oob_raise(self) -> None:
        m: Matrix[int] = Matrix(2, 2, 0)
        with pytest.raises(IndexError):
            m.get(5, 0)
        with pytest.raises(IndexError):
            m.set(0, 5, 1)
        m.set(1, 1, 7)
        assert m.get(1, 1) == 7
        assert m[(1, 1)] == 7
        m[(0, 0)] = 3
        assert m.get(0, 0) == 3

    def test_dims_and_count(self) -> None:
        m: Matrix[int] = Matrix(2, 3, 0)
        assert (m.rows(), m.columns(), m.elements_count()) == (2, 3, 6)
        assert repr(m) == "matrix(2x3)"

    def test_add_row_empty_adopts_cols(self) -> None:
        m: Matrix[int] = Matrix(0, 0, None)
        m.add_row([1, 2, 3])
        assert (m.rows(), m.columns()) == (1, 3)

    def test_add_row_bad_width_and_index(self) -> None:
        m: Matrix[int] = Matrix(1, 2, 0)
        with pytest.raises(ValueError):
            m.add_row([1])
        with pytest.raises(IndexError):
            m.add_row([1, 2], index=-1)
        m.add_row([1, 2], index=0)
        assert m.rows() == 2

    def test_remove_copy_row(self) -> None:
        m: Matrix[int] = Matrix(2, 2, 0)
        m.set(0, 0, 9)
        assert m.copy_row(0) == [9, 0]
        m.remove_row(0)
        assert m.rows() == 1
        with pytest.raises(IndexError):
            m.remove_row(5)
        with pytest.raises(IndexError):
            m.copy_row(5)

    def test_row_stats(self) -> None:
        m: Matrix[object] = Matrix(1, 4, None)
        m.add_row(["a", 1, 2.0, None])
        m.remove_row(0)
        assert m.sum_row(0) == 3.0
        assert m.avg_row(0) == 1.5
        assert m.min_row(0) == 1.0
        assert m.max_row(0) == 2.0
        assert m.mode_row(0) in {"a", 1, 2.0, None}

    def test_row_stats_no_numerics(self) -> None:
        m: Matrix[object] = Matrix(1, 1, "x")
        assert m.avg_row(0) == 0
        assert m.min_row(0) is None
        assert m.max_row(0) is None

    def test_mode_row_empty(self) -> None:
        m: Matrix[object] = Matrix(0, 0, None)
        m.add_row([])
        assert m.mode_row(0) is None

    def test_fill_row_oob(self) -> None:
        m: Matrix[int] = Matrix(2, 2, 0)
        m.fill_row(1, 5)
        assert m.copy_row(1) == [5, 5]
        with pytest.raises(IndexError):
            m.fill_row(9, 1)

    def test_add_col_empty_and_errors(self) -> None:
        m: Matrix[int] = Matrix(0, 0, None)
        m.add_col([1, 2])
        assert (m.rows(), m.columns()) == (2, 1)
        with pytest.raises(ValueError):
            Matrix(2, 2, 0).add_col([1])
        with pytest.raises(IndexError):
            Matrix(2, 2, 0).add_col([1, 2], index=-1)

    def test_remove_copy_col(self) -> None:
        m: Matrix[int] = Matrix(2, 2, 1)
        assert m.copy_col(0) == [1, 1]
        m.remove_col(0)
        assert m.columns() == 1
        with pytest.raises(IndexError):
            m.remove_col(4)
        with pytest.raises(IndexError):
            m.copy_col(4)

    def test_col_row_aliases(self) -> None:
        m: Matrix[int] = Matrix(2, 2, 0)
        m.set(0, 1, 4)
        assert m.row(0) == [0, 4]
        assert m.col(1) == [4, 0]

    def test_submatrix_ok_and_bad(self) -> None:
        m: Matrix[int] = Matrix(3, 3, 1)
        sub = m.submatrix(0, 2, 0, 2)
        assert (sub.rows(), sub.columns()) == (2, 2)
        with pytest.raises(IndexError):
            m.submatrix(2, 1, 0, 1)
        with pytest.raises(IndexError):
            m.submatrix(0, 1, 2, 1)

    def test_swap_rows_cols(self) -> None:
        m: Matrix[int] = Matrix(2, 2, 0)
        m.set(0, 0, 1)
        m.swap_rows(0, 1)
        assert m.get(1, 0) == 1
        m.swap_columns(0, 1)
        assert m.get(1, 1) == 1
        with pytest.raises(IndexError):
            m.swap_rows(0, 5)
        with pytest.raises(IndexError):
            m.swap_columns(0, 5)

    def test_reverse_median_stdev_variance(self) -> None:
        m: Matrix[int] = Matrix(2, 2, 0)
        m.set(0, 0, 1)
        m.set(1, 1, 2)
        m.reverse()
        assert m.get(0, 0) == 2
        assert Matrix(0, 0, None).median() is None
        odd: Matrix[int] = Matrix(1, 3, 0)
        odd.fill(0)
        odd.set(0, 0, 3)
        odd.set(0, 1, 1)
        odd.set(0, 2, 2)
        assert odd.median() == 2.0
        assert Matrix(1, 1, 5).stdev() is None
        assert Matrix(1, 1, 5).variance() is None
        assert Matrix(1, 2, 0).stdev() == 0.0

    def test_sort_and_indices(self) -> None:
        m: Matrix[int] = Matrix(3, 1, 0)
        m.set(0, 0, 3)
        m.set(1, 0, None)
        m.set(2, 0, 1)
        m.sort(0, "descending")
        assert m.get(0, 0) == 3
        assert m.get(2, 0) is None
        idx = m.sort_indices(0, "ascending")
        assert idx[-1] == 2  # na always last
        assert Matrix(0, 0, None).sort_indices() == []
        Matrix(0, 0, None).sort()
        with pytest.raises(IndexError):
            m.sort(7)
        with pytest.raises(IndexError):
            m.sort_indices(7)

    def test_is_descending_variants(self) -> None:
        assert Matrix._is_descending(None) is False
        assert Matrix._is_descending(True) is True  # noqa: FBT003
        assert Matrix._is_descending(-1) is True
        assert Matrix._is_descending(1) is False
        assert Matrix._is_descending("descending") is True
        assert Matrix._is_descending("ascending") is False
        assert Matrix._is_descending(SimpleNamespace(name="order.descending")) is True

    def test_comparable_key_fallback(self) -> None:
        assert Matrix._comparable_key(1) == 1
        key = Matrix._comparable_key(object())
        assert isinstance(key, tuple)

    def test_fill_region_and_diagonal(self) -> None:
        m: Matrix[int] = Matrix(3, 3, 0)
        m.fill(1, 0, 2, 0, 2)
        assert m.get(0, 0) == 1
        assert m.get(2, 2) == 0
        m.fill_diagonal(9)
        assert m.get(1, 1) == 9


# ---------------------------------------------------------------------------
# matrix_evaluator.py — dispatch handlers via NodeLiteralEvaluator
# ---------------------------------------------------------------------------


class TestMatrixBuiltins:
    def test_new_variants(self) -> None:
        ev = _ev()
        assert ev._builtin_matrix_new([]).rows() == 0
        assert ev._builtin_matrix_new([None]).rows() == 0
        assert ev._builtin_matrix_new([None, 2]).rows() == 0
        m = ev._builtin_matrix_new([2, 3, 1])
        assert (m.rows(), m.columns(), m.get(0, 0)) == (2, 3, 1)
        with pytest.raises(ValueError):
            ev._builtin_matrix_new([-1, 2])

    def test_expect_matrix_list_coercion_and_errors(self) -> None:
        ev = _ev()
        m = ev._expect_matrix([[1, 2], [3, 4]], "msg")
        assert m.rows() == 2
        with pytest.raises(ValueError):
            ev._expect_matrix(None, "msg")
        with pytest.raises(ValueError):
            ev._expect_matrix("nope", "msg")

    def test_coerce_optional_and_index_helpers(self) -> None:
        ev = _ev()
        assert ev._coerce_optional_matrix(None) is None
        assert ev._coerce_optional_matrix("nope") is None
        assert ev._coerce_optional_matrix([]).rows() == 0
        assert ev._optional_int(None) is None
        assert ev._optional_int(float("nan")) is None
        assert ev._optional_int(True) == 1  # noqa: FBT003
        assert ev._optional_int(2.7) == 2
        assert ev._optional_int(SimpleNamespace(current=4)) == 4
        assert ev._optional_int("bad") is None
        with pytest.raises(ValueError):
            ev._expect_list("x", "need list")
        with pytest.raises(ValueError):
            ev._expect_list(None, "need list")

    def test_get_set_na_and_errors(self) -> None:
        ev = _ev()
        m = Matrix(2, 2, 5)
        assert ev._builtin_matrix_get([m, 0, 0]) == 5
        assert ev._builtin_matrix_get([None, 0, 0]) is None
        assert ev._builtin_matrix_get([m, None, 0]) is None
        with pytest.raises(ValueError):
            ev._builtin_matrix_get([m, 0])
        with pytest.raises(ValueError):
            ev._builtin_matrix_get([m, 9, 0])
        with pytest.raises(ValueError):
            ev._builtin_matrix_get(["x", 0, 0])
        assert ev._builtin_matrix_set([None, 0, 0, 1]) is None
        assert ev._builtin_matrix_set([m, None, 0, 1]) is None
        ev._builtin_matrix_set([m, 0, 0, 8])
        assert m.get(0, 0) == 8
        with pytest.raises(ValueError):
            ev._builtin_matrix_set([m, 0, 0])
        with pytest.raises(ValueError):
            ev._builtin_matrix_set([m, 9, 0, 1])

    def test_rows_cols_count(self) -> None:
        ev = _ev()
        m = Matrix(2, 3, 0)
        assert ev._builtin_matrix_rows([m]) == 2
        assert ev._builtin_matrix_columns([m]) == 3
        assert ev._builtin_matrix_elements_count([m]) == 6
        assert ev._builtin_matrix_rows([None]) is None
        assert ev._builtin_matrix_columns([None]) is None
        assert ev._builtin_matrix_elements_count([None]) is None
        with pytest.raises(ValueError):
            ev._builtin_matrix_rows([])

    def test_add_remove_copy_row(self) -> None:
        ev = _ev()
        m = Matrix(1, 2, 0)
        ev._builtin_matrix_add_row([m])
        assert m.rows() == 2
        ev._builtin_matrix_add_row([m, [7, 8]])
        ev._builtin_matrix_add_row([m, 0, [1, 2]])
        assert ev._builtin_matrix_copy_row([m, 0]) == [1, 2]
        ev._builtin_matrix_remove_row([m, 0])
        with pytest.raises(ValueError):
            ev._builtin_matrix_add_row([])
        with pytest.raises(ValueError):
            ev._builtin_matrix_add_row([m, [1]])
        with pytest.raises(ValueError):
            ev._builtin_matrix_remove_row([m, 9])
        with pytest.raises(ValueError):
            ev._builtin_matrix_copy_row([m, 9])

    def test_row_col_aggregates(self) -> None:
        ev = _ev()
        m = Matrix(2, 2, 0)
        m.set(0, 0, 4)
        assert ev._builtin_matrix_sum_row([m, 0]) == 4.0
        assert ev._builtin_matrix_avg_row([m, 0]) == 2.0
        assert ev._builtin_matrix_min_row([m, 0]) == 0.0
        assert ev._builtin_matrix_max_row([m, 0]) == 4.0
        assert ev._builtin_matrix_sum_col([m, 0]) == 4.0
        assert ev._builtin_matrix_avg_col([m, 0]) == 2.0
        assert ev._builtin_matrix_min_col([m, 0]) == 0.0
        assert ev._builtin_matrix_max_col([m, 0]) == 4.0
        assert ev._builtin_matrix_sum_all([m]) == 4.0
        assert ev._builtin_matrix_avg_all([m]) == 1.0
        assert ev._builtin_matrix_min_all([m]) == 0.0
        assert ev._builtin_matrix_max_all([m]) == 4.0
        assert ev._builtin_matrix_mode_all([m]) == 0
        ev._builtin_matrix_fill_row([m, 0, 9])
        ev._builtin_matrix_fill_col([m, 1, 9])
        assert m.get(0, 1) == 9

    def test_add_col_forms(self) -> None:
        ev = _ev()
        m = Matrix(2, 1, 0)
        ev._builtin_matrix_add_col([m, [1, 2]])
        assert m.columns() == 2
        ev._builtin_matrix_add_col([m, 0, [3, 4]])
        assert m.get(0, 0) == 3
        with pytest.raises(ValueError):
            ev._builtin_matrix_add_col([m, [1]])
        with pytest.raises(ValueError):
            ev._builtin_matrix_remove_col([m, 9])
        with pytest.raises(ValueError):
            ev._builtin_matrix_copy_col([m, 9])

    def test_fill_and_diagonal(self) -> None:
        ev = _ev()
        m = Matrix(2, 2, 0)
        ev._builtin_matrix_fill([m, 5])
        assert m.get(1, 1) == 5
        ev._builtin_matrix_fill([m, 1, 0, 1, 0, 1])
        assert m.get(0, 0) == 1
        assert ev._builtin_matrix_fill([None, 1]) is None
        ev._builtin_matrix_fill_diagonal([m, 7])
        assert m.get(0, 0) == 7
        with pytest.raises(ValueError):
            ev._builtin_matrix_fill_diagonal([m])

    def test_transform_ops(self) -> None:
        ev = _ev()
        m = Matrix(2, 3, 1)
        assert ev._builtin_matrix_transpose([m]).rows() == 3
        ev._builtin_matrix_reverse_rows([m])
        ev._builtin_matrix_reverse_cols([m])
        ev._builtin_matrix_reverse([m])
        assert ev._builtin_matrix_reshape([m, 3, 2]).rows() == 3
        with pytest.raises(ValueError):
            ev._builtin_matrix_reshape([m, 2, 2])
        with pytest.raises(ValueError):
            ev._builtin_matrix_transpose(["x"])

    def test_concat_copy(self) -> None:
        ev = _ev()
        a = Matrix(1, 2, 1)
        b = Matrix(1, 2, 2)
        assert ev._builtin_matrix_concat([a, b]).rows() == 2
        assert ev._builtin_matrix_concat([a, b, 1]).columns() == 4
        c = ev._builtin_matrix_copy([a])
        assert c.get(0, 0) == 1
        with pytest.raises(ValueError):
            ev._builtin_matrix_concat([a, Matrix(2, 3, 0)])
        with pytest.raises(ValueError):
            ev._builtin_matrix_concat([a])

    def test_row_col_submatrix_swap(self) -> None:
        ev = _ev()
        m = Matrix(3, 3, 0)
        m.set(0, 0, 1)
        assert ev._builtin_matrix_row([m, 0])[0] == 1
        assert ev._builtin_matrix_col([m, 0])[0] == 1
        assert ev._builtin_matrix_submatrix([m, 0, 2, 0, 2]).rows() == 2
        ev._builtin_matrix_swap_rows([m, 0, 1])
        ev._builtin_matrix_swap_columns([m, 0, 1])
        with pytest.raises(ValueError):
            ev._builtin_matrix_row([m, 9])
        with pytest.raises(ValueError):
            ev._builtin_matrix_col([m, 9])
        with pytest.raises(ValueError):
            ev._builtin_matrix_submatrix([m, 5, 1, 0, 1])
        with pytest.raises(ValueError):
            ev._builtin_matrix_swap_rows([m, 0, 9])
        with pytest.raises(ValueError):
            ev._builtin_matrix_swap_columns([m, 0, 9])

    def test_sort_median_stdev_variance(self) -> None:
        ev = _ev()
        m = Matrix(2, 2, 0)
        m.set(0, 0, 2)
        ev._builtin_matrix_sort([m, 0, "ascending"])
        assert ev._builtin_matrix_sort_indices([m, 0]) == [0, 1]
        assert ev._builtin_matrix_median([m]) == 0.0
        assert ev._builtin_matrix_stdev([m]) is not None
        assert ev._builtin_matrix_variance([m]) is not None
        with pytest.raises(ValueError):
            ev._builtin_matrix_sort([m, 9])
        with pytest.raises(ValueError):
            ev._builtin_matrix_sort_indices([m, 9])

    def test_linalg_extended(self) -> None:
        ev = _ev()
        m = Matrix(2, 2, 0)
        m.set(0, 0, 1)
        m.set(1, 1, 1)
        assert ev._call_builtin("matrix.eigenvalues", [m]) == [1.0, 1.0]
        assert ev._call_builtin("matrix.eigenvectors", [m]).rows() == 2
        assert ev._call_builtin("matrix.kron", [m, m]).rows() == 4
        assert ev._call_builtin("matrix.pow", [m, 2]).get(0, 0) == pytest.approx(1.0)
        assert ev._call_builtin("matrix.mode_row", [m, 0]) == 1
        assert ev._call_builtin("matrix.mode_col", [m, 0]) == 1
        assert ev._call_builtin("matrix.is_antidiagonal", [m]) is False
        assert ev._call_builtin("matrix.is_symmetric", [m]) is True
        assert ev._call_builtin("matrix.is_antisymmetric", [m]) is False
        assert ev._call_builtin("matrix.is_triangular", [m]) is True
        assert ev._call_builtin("matrix.is_binary", [m]) is True
        assert ev._call_builtin("matrix.is_stochastic", [m]) is True
        with pytest.raises(ValueError):
            ev._call_builtin("matrix.eigenvalues", [])
        with pytest.raises(ValueError):
            ev._call_builtin("matrix.kron", [m])
        with pytest.raises(ValueError):
            ev._call_builtin("matrix.pow", [m, "bad"])

    def test_linalg(self) -> None:
        ev = _ev()
        m = Matrix(2, 2, 0)
        m.set(0, 0, 1)
        m.set(1, 1, 1)
        assert ev._builtin_matrix_sum([m]) == 2.0
        assert ev._builtin_matrix_diff([m, m]).get(0, 0) == 0
        assert ev._builtin_matrix_mult([m, 2]).get(0, 0) == 2
        assert ev._builtin_matrix_det([m]) == 1.0
        assert ev._builtin_matrix_inv([m]).get(0, 0) == pytest.approx(1.0)
        with pytest.raises(ValueError):
            ev._builtin_matrix_sum([m, Matrix(1, 1, 0)])
        with pytest.raises(ValueError):
            ev._builtin_matrix_sum([])
        with pytest.raises(ValueError):
            ev._builtin_matrix_diff([m])
        with pytest.raises(ValueError):
            ev._builtin_matrix_mult([m, "bad"])
        with pytest.raises(ValueError):
            ev._builtin_matrix_det([Matrix(1, 2, 0)])
        with pytest.raises(ValueError):
            ev._builtin_matrix_inv([Matrix(2, 2, 0)])
        assert ev._builtin_matrix_pinv([m]).rows() == 2
        assert ev._builtin_matrix_trace([m]) == 2.0
        assert ev._builtin_matrix_rank([m]) == 2
        assert ev._builtin_matrix_is_square([m]) is True
        assert ev._builtin_matrix_is_zero([Matrix(1, 1, 0)]) is True
        assert ev._builtin_matrix_is_identity([m]) is True
        assert ev._builtin_matrix_is_diagonal([m]) is True


# ---------------------------------------------------------------------------
# numeric.py
# ---------------------------------------------------------------------------


class TestNumericBuiltins:
    def test_abs_variants(self) -> None:
        ev = _ev()
        assert ev._builtin_abs([None]) is None
        assert ev._builtin_abs([-3]) == 3
        assert ev._builtin_abs(["x"]) is None
        with pytest.raises(ValueError):
            ev._builtin_abs([])

    def test_max_min_all_na(self) -> None:
        ev = _ev()
        assert ev._builtin_math_max([None, None]) is None
        assert ev._builtin_math_min([None]) is None
        assert ev._builtin_math_max([1, None, 2]) == 2.0

    def test_sqrt_pow_log(self) -> None:
        ev = _ev()
        assert ev._builtin_math_sqrt([-1]) is None
        assert ev._builtin_math_sqrt([None]) is None
        assert ev._builtin_math_pow([2, 3]) == 8.0
        assert ev._builtin_math_pow([None, 1]) is None
        assert ev._builtin_math_log([0]) is None
        assert ev._builtin_math_log([10, 10]) == pytest.approx(1.0)
        assert ev._builtin_math_log([10, -1]) is None
        with pytest.raises(ValueError):
            ev._builtin_math_log([1, 2, 3])

    def test_round_forms(self) -> None:
        ev = _ev()
        assert ev._builtin_math_round([None]) is None
        assert ev._builtin_math_round([1.234, 1]) == pytest.approx(1.2)
        assert ev._builtin_math_round([None, 1]) is None
        with pytest.raises(ValueError):
            ev._builtin_math_round([1, 2, 3])

    def test_trig_domain_and_na(self) -> None:
        ev = _ev()
        assert ev._builtin_math_sin([0]) == 0.0
        assert ev._builtin_math_cos([None]) is None
        assert ev._builtin_math_acos([5]) is None
        assert ev._builtin_math_asin([None]) is None
        assert ev._builtin_math_tan([0]) == 0.0
        assert ev._builtin_math_exp([0]) == 1.0
        assert ev._builtin_math_log10([0]) is None
        assert ev._builtin_math_log10([100]) == 2.0
        assert ev._builtin_math_todegrees([math.pi]) == pytest.approx(180.0)
        assert ev._builtin_math_toradians([None]) is None

    def test_sign(self) -> None:
        ev = _ev()
        assert ev._builtin_math_sign([5]) == 1
        assert ev._builtin_math_sign([-5]) == -1
        assert ev._builtin_math_sign([0]) == 0
        assert ev._builtin_math_sign([None]) is None

    def test_sum_rolling_and_array(self) -> None:
        ev = _ev()
        assert ev._builtin_math_sum([[1.0, 2.0, 3.0], 2]) == 5.0
        assert ev._builtin_math_sum([[1.0, 2.0], 2.0]) == 3.0
        assert ev._builtin_math_sum([[1.0], 2]) is None
        assert ev._builtin_math_sum([[1.0, None], 2]) is None
        assert ev._builtin_math_sum([[1.0, 2.0]]) == 3.0
        with pytest.raises(ValueError):
            ev._builtin_math_sum([[1.0], 0])
        with pytest.raises(ValueError):
            ev._builtin_math_sum([5])

    def test_avg_forms(self) -> None:
        ev = _ev()
        assert ev._builtin_math_avg([[1.0, 2.0]]) == 1.5
        assert ev._builtin_math_avg([1, 2, 3]) == 2.0
        assert ev._builtin_math_avg([1, None]) is None
        with pytest.raises(ValueError):
            ev._builtin_math_avg([])
        with pytest.raises(ValueError):
            ev._builtin_math_avg([[None]])

    def test_random_forms(self) -> None:
        ev = _ev()
        assert 0.0 <= ev._builtin_math_random([]) < 1.0
        assert 0.0 <= ev._builtin_math_random([5]) <= 5.0
        assert 1.0 <= ev._builtin_math_random([1, 2]) <= 2.0
        assert ev._builtin_math_random([None, 1]) is None
        assert ev._builtin_math_random([None]) is None

    def test_isfinite(self) -> None:
        ev = _ev()
        assert ev._builtin_math_isfinite([1.0]) is True
        assert ev._builtin_math_isfinite([float("inf")]) is False
        assert ev._builtin_math_isfinite([None]) is None

    def test_na_nz_iff(self) -> None:
        ev = _ev()
        assert ev._builtin_na([]) is None
        assert ev._builtin_na([None]) is True
        assert ev._builtin_na([1]) is False
        with pytest.raises(ValueError):
            ev._builtin_na([1, 2])
        assert ev._builtin_nz([None]) == 0
        assert ev._builtin_nz([None, 5]) == 5
        assert ev._builtin_nz([3]) == 3
        with pytest.raises(ValueError):
            ev._builtin_nz([])
        assert ev._builtin_iff([True, 1, 2]) == 1
        assert ev._builtin_iff([None, 1, 2]) is None
        with pytest.raises(ValueError):
            ev._builtin_iff([True, 1])

    def test_bool_cast(self) -> None:
        ev = _ev()
        assert ev._builtin_bool([None]) is False
        assert ev._builtin_bool([True]) is True
        assert ev._builtin_bool([0]) is False
        assert ev._builtin_bool(["TRUE"]) is True
        assert ev._builtin_bool(["nope"]) is False

    def test_int_cast(self) -> None:
        ev = _ev()
        assert ev._builtin_int([None]) is None
        assert ev._builtin_int([True]) == 1
        assert ev._builtin_int([2.9]) == 2
        assert ev._builtin_int(["2.01"]) == 2
        assert ev._builtin_int(["abc"]) is None
        assert ev._builtin_int([float("nan")]) is None

    def test_float_string_fixnan_mintick(self) -> None:
        ev = _ev()
        assert ev._builtin_float([None]) is None
        assert ev._builtin_float(["1.5"]) == 1.5
        with pytest.raises(ValueError):
            ev._builtin_float(["abc"])
        assert ev._builtin_string([None]) == "na"
        assert ev._builtin_string([True]) == "true"
        assert ev._builtin_string(["s"]) == "s"
        assert ev._builtin_fixnan([None]) == 0
        assert ev._builtin_fixnan([float("nan")]) == 0
        assert ev._builtin_fixnan([3]) == 3
        assert ev._builtin_math_round_to_mintick([None]) is None
        assert ev._builtin_math_round_to_mintick([1.5]) == pytest.approx(1.5)


# ---------------------------------------------------------------------------
# strings.py
# ---------------------------------------------------------------------------


class TestStringBuiltins:
    def test_length_upper_lower(self) -> None:
        ev = _ev()
        assert ev._builtin_str_length([None]) is None
        assert ev._builtin_str_length(["abc"]) == 3
        assert ev._builtin_str_length([5]) == 1
        assert ev._builtin_str_upper([None]) is None
        assert ev._builtin_str_lower(["AB"]) == "ab"
        with pytest.raises(ValueError):
            ev._builtin_str_length([])

    def test_contains_startswith_endswith(self) -> None:
        ev = _ev()
        assert ev._builtin_str_contains(["hello", "ell"]) is True
        assert ev._builtin_str_contains([None, "x"]) is None
        assert ev._builtin_str_startswith(["hello", "he"]) is True
        assert ev._builtin_str_endswith(["hello", "lo"]) is True
        assert ev._builtin_str_endswith(["hello", None]) is None
        with pytest.raises(ValueError):
            ev._builtin_str_contains(["a"])

    def test_substring(self) -> None:
        ev = _ev()
        assert ev._builtin_str_substring(["hello", 1]) == "ello"
        assert ev._builtin_str_substring(["hello", 1, 3]) == "el"
        assert ev._builtin_str_substring([None, 1]) is None
        assert ev._builtin_str_substring(["hello", None]) is None
        with pytest.raises(ValueError):
            ev._builtin_str_substring(["hello"])

    def test_repeat(self) -> None:
        ev = _ev()
        assert ev._builtin_str_repeat(["ab", 2]) == "abab"
        assert ev._builtin_str_repeat(["ab", -1]) == ""
        assert ev._builtin_str_repeat([None, 2]) is None

    def test_replace_family(self) -> None:
        ev = _ev()
        assert ev._builtin_str_replace([None, None, None]) is None
        assert ev._builtin_str_replace(["aaa", "a", "b", 1]) == "aba"
        assert ev._builtin_str_replace(["abc", "x", "y"]) == "abc"
        assert ev._builtin_str_replace_all([None, None, None]) is None
        assert ev._builtin_str_replace_all(["aaa", "a", "b"]) == "bbb"
        with pytest.raises(ValueError):
            ev._builtin_str_replace(["a", "b"])
        assert ev._replace_nth("abc", "", "X", 1) == "aXbc"
        assert ev._replace_nth("abc", "z", "X", 0) == "abc"
        assert ev._replace_nth("abc", "a", "X", -1) == "abc"

    def test_split_trim(self) -> None:
        ev = _ev()
        assert ev._builtin_str_split([None, ","]) == [""]
        assert ev._builtin_str_split(["abc", ""]) == ["a", "b", "c"]
        assert ev._builtin_str_split(["a,b", ","]) == ["a", "b"]
        assert ev._builtin_str_split(["a b"]) == ["a", "b"]
        assert ev._builtin_str_trim([None]) is None
        assert ev._builtin_str_trim(["  x  "]) == "x"

    def test_tonumber(self) -> None:
        ev = _ev()
        assert ev._builtin_str_tonumber([None]) is None
        assert ev._builtin_str_tonumber([True]) == 1.0
        assert ev._builtin_str_tonumber([3]) == 3.0
        assert ev._builtin_str_tonumber([float("nan")]) is None
        assert ev._builtin_str_tonumber(["  "]) is None
        assert ev._builtin_str_tonumber(["1.5"]) == 1.5
        assert ev._builtin_str_tonumber(["YYYY-MM"]) is None

    def test_tostring_format(self) -> None:
        ev = _ev()
        assert ev._builtin_str_tostring([None]) == "NaN"
        assert ev._builtin_str_tostring([5, "#"]) == "5"
        assert ev._builtin_str_format([None]) == "NaN"
        assert ev._builtin_str_format(["hi {0}", "x"]) == "hi x"
        assert ev._builtin_str_format(["{0,number}", 1.5]) == "1.5"
        assert ev._builtin_str_format(["{0,number,#.##}", 1.234]) == "1.23"
        with pytest.raises(ValueError):
            ev._builtin_str_format([])

    def test_match_pos(self) -> None:
        ev = _ev()
        assert ev._builtin_str_match(["abc123", r"\d+"]) == "123"
        assert ev._builtin_str_match(["abc", r"\d+"]) is None
        assert ev._builtin_str_match([None, "x"]) is None
        assert ev._builtin_str_match(["a", "(["]) is None
        assert ev._builtin_str_pos(["hello", "ll"]) == 2
        assert ev._builtin_str_pos(["hello", None]) is None
        with pytest.raises(ValueError):
            ev._builtin_str_pos(["a"])

    def test_format_time_and_join(self) -> None:
        ev = _ev()
        out = ev._builtin_str_format_time([1609459200000])
        assert "2021" in out
        assert ev._builtin_str_format_time([float("nan")]) == "NaN"
        assert ev._builtin_str_format_time([None]) == "NaN"
        assert "2021" in ev._builtin_str_format_time([1609459200, "yyyy", "UTC"])
        assert ev._builtin_str_join([["a", None, "b"], "-"]) == "a--b"
        assert ev._builtin_str_join([None, "-"]) is None
        assert ev._builtin_str_join([[1, 2], None]) == "12"
        assert ev._builtin_str_join([SimpleNamespace(history=["a", "b"]), ","]) == "a,b"
        with pytest.raises(ValueError):
            ev._builtin_str_join([5, ","])


# ---------------------------------------------------------------------------
# color.py — direct function calls
# ---------------------------------------------------------------------------


class TestColorFunctions:
    def test_color_value(self) -> None:
        c = Color(300, -5, 10)
        assert (c.r, c.g, c.b, c.a) == (255, 0, 10, 255)
        assert c.to_hex() == "#FF000AFF"
        assert "rgba(255, 0, 10" in c.to_rgba()
        assert repr(c) == str(c) == c.to_hex()
        assert c == Color(255, 0, 10)
        assert c != Color(0, 0, 0)
        assert (c == "red") is False
        assert hash(c) == hash(Color(255, 0, 10))

    def test_color_new_forms(self) -> None:
        assert color_new(None) is None
        assert color_new([]) is None
        assert color_new([Color(1, 2, 3)]) == Color(1, 2, 3)
        assert color_new(Color(1, 2, 3)) == Color(1, 2, 3)
        assert color_new("#FF0000") == Color(255, 0, 0)
        assert color_new("#FF000080").a == 128
        assert color_new(0) is not None
        with pytest.raises(ValueError):
            color_new("notacolor!")
        assert color_new("#FF0000", 100).a == 0
        assert color_new(color="#00FF00") == Color(0, 255, 0)
        assert color_new("#FF0000", transp=50).a == 127
        assert color_new(object()) is None

    def test_parse_color_string(self) -> None:
        assert _parse_color_string("") is None
        assert _parse_color_string("red") == (0xF2, 0x36, 0x45, 255)
        assert _parse_color_string("color.blue") == (0x29, 0x62, 0xFF, 255)
        assert _parse_color_string("rgb(255,0,0)") == (255, 0, 0, 255)
        assert _parse_color_string("rgba(255,0,0,0.5)")[3] == 128
        assert _parse_color_string("rgba(1,2,3,200)") == (1, 2, 3, 200)
        assert _parse_color_string("#ZZZZZZ") is None
        assert _parse_color_string("#12345") is None

    def test_channels(self) -> None:
        c = Color(10, 20, 30, 255)
        assert color_r(c) == 10
        assert color_g("#00FF00") == 255
        assert color_b(0) == 0
        assert color_t(Color(0, 0, 0, 0)) == 100
        assert color_t(Color(0, 0, 0, 255)) == 0
        assert color_r(None) == 0
        assert color_g(True) == 0  # noqa: FBT003

    def test_rgb_and_gradient(self) -> None:
        assert color_rgb(1, 2, 3) == Color(1, 2, 3, 255)
        assert color_rgb(1, 2, 3, transp=100).a == 0
        assert color_rgb(1, 2, 3, a=10).a == 10
        lo, hi = Color(0, 0, 0), Color(255, 255, 255)
        assert color_from_gradient(5, 0, 10, lo, hi).r == 127
        assert color_from_gradient(None, 0, 10, lo, hi) == lo
        assert color_from_gradient("bad", 0, 10, lo, hi) == lo
        assert color_from_gradient(5, 5, 5, lo, hi) == lo
        assert color_from_gradient(99, 0, 10, lo, hi) == hi

    def test_register(self) -> None:
        ns: dict[str, object] = {}
        register_color_functions(ns)
        assert "color.new" in ns and "color.red" in ns and "color" in ns
        # TV v6 palette (compiler ``_color_const``), not CSS keyword hex.
        assert str(ns["color.green"]).upper().startswith("#22AB94")
        assert str(ns["color.red"]).upper().startswith("#F23645")


# ---------------------------------------------------------------------------
# ticker.py — direct function calls
# ---------------------------------------------------------------------------


class TestTickerFunctions:
    def test_ticker_info_str(self) -> None:
        t = TickerInfo("AAPL", session="extended", adjust="splits")
        assert str(t) == "AAPL"
        assert "session='extended'" in repr(t)
        assert (t + "!") == "AAPL!"
        assert ("x" + t) == "xAAPL"

    def test_new_modify(self) -> None:
        assert ticker_new("AAPL").symbol == "AAPL"
        assert ticker_new(symbol="MSFT", session="regular").session == "regular"
        base = ticker_new("AAPL", session="extended")
        assert ticker_modify(base, session="regular").session == "regular"
        assert ticker_modify("AAPL", adjust="splits").adjust == "splits"
        assert ticker_modify(base, adjustment="dividends").adjust == "dividends"
        assert ticker_modify(base, symbol="MSFT").symbol == "MSFT"

    def test_chart_tickers(self) -> None:
        assert ticker_heikinashi("AAPL").heikinashi_applied is True
        k = ticker_kagi("AAPL", 5.0, "PercentageLTP")
        assert k.kagi_applied and k.style == "PercentageLTP"
        assert ticker_linebreak("AAPL", 3).linebreak_applied is True
        r = ticker_renko("AAPL", 1.5, "PercentageLTP")
        assert r.renko_applied and r.style == "PercentageLTP"

    def test_pointfigure_forms(self) -> None:
        assert ticker_pointfigure("AAPL", 2.5).pointfigure_applied is True
        full = ticker_pointfigure("AAPL", "hl", "Traditional", 1, 3)
        assert full.source == "hl" and full.reversal == 3
        kw = ticker_pointfigure("AAPL", source="close", style="ATR", param=14, reversal=3)
        assert kw.source == "close"
        legacy_str = ticker_pointfigure("AAPL", "2.5")
        assert "2.5" in legacy_str.symbol
        assert _as_float_default(None) == 1.0
        assert _as_float_default("bad") == 1.0
        assert _as_int_or_none(None) is None
        assert _as_int_or_none("bad") is None
        assert _looks_like_number("1.5") is True
        assert _looks_like_number("hl") is False

    def test_inherit_standard_tickerid(self) -> None:
        src = ticker_new("AAPL", session="extended")
        assert ticker_inherit(src).session == "extended"
        assert ticker_inherit(src, "MSFT").symbol == "MSFT"
        assert ticker_inherit("AAPL").symbol == "AAPL"
        assert ticker_inherit(None).symbol == ""
        assert ticker_standard("AAPL").symbol == "AAPL"
        assert ticker_standard().symbol == ""
        assert ticker_standard(None).symbol == ""
        assert ticker_standard(ticker="MSFT").symbol == "MSFT"
        assert tickerid_v4("NASDAQ", "AAPL") == "NASDAQ:AAPL"
        assert tickerid_v4("AAPL") == "AAPL"
        assert tickerid_v4("NASDAQ", None) == "NASDAQ"
        assert tickerid_v4() == ""

    def test_split_extract(self) -> None:
        assert split_symbol("NASDAQ:AAPL") == ("NASDAQ", "AAPL")
        assert split_symbol("AAPL") == ("", "AAPL")
        assert split_symbol(TickerInfo("NASDAQ:AAPL")) == ("NASDAQ", "AAPL")
        assert split_symbol(None) == ("", "")
        assert split_symbol("  ") == ("", "")
        assert extract_prefix("NASDAQ:AAPL") == "NASDAQ"
        assert extract_ticker("NASDAQ:AAPL") == "AAPL"

    def test_register(self) -> None:
        ns: dict[str, object] = {}
        register_ticker_functions(ns)
        assert "ticker.new" in ns and "tickerid" in ns and "syminfo.prefix" in ns


# ---------------------------------------------------------------------------
# technical.py — ta.sum alias
# ---------------------------------------------------------------------------


class TestTechnicalAlias:
    def test_ta_sum(self) -> None:
        ev = _ev()
        assert ev._call_builtin("ta.sum", [[1.0, 2.0, 3.0], 2]) == 5.0
        with pytest.raises(ValueError):
            ev._call_builtin("ta.sum", [[1.0], 0])
        with pytest.raises(ValueError):
            ev._call_builtin("ta.sum", [[1.0], None])


# ---------------------------------------------------------------------------
# names.py — resolution
# ---------------------------------------------------------------------------


class TestNameResolution:
    def test_qualified_name(self) -> None:
        assert ast_qualified_name(helper.parse("x", mode="eval").body) == "x"
        assert ast_qualified_name(helper.parse("ta.sma", mode="eval").body) == "ta.sma"
        node = helper.parse("a.b.c", mode="eval").body
        assert ast_qualified_name(node) == "a.b.c"
        assert ast_qualified_name(helper.parse("1", mode="eval").body) is None

    def test_visit_name(self) -> None:
        ev = _ev(close=[1.0, 2.0])
        assert _eval_src(ev, "close") == [1.0, 2.0]
        assert _eval_src(_ev(), "na") is None
        assert _eval_src(_ev(), "nope_missing") == "nope_missing"

    def test_visit_attribute(self) -> None:
        ev = _ev(**{"strategy.position_size": 3})
        assert _eval_src(ev, "strategy.position_size") == 3
        ev2 = _ev(E={"A": 1})
        assert _eval_src(ev2, "E.A") == 1
        with pytest.raises(ValueError):
            _eval_src(_ev(E={"A": 1}), "E.B")
        ev3 = _ev(E="F", F={"A": 2})
        assert _eval_src(ev3, "E.A") == 2
        with pytest.raises(ValueError):
            _eval_src(_ev(E="F", F={"A": 2}), "E.B")
        assert _eval_src(_ev(), "chart.is_heikinashi") is None

    def test_attribute_instance_methods(self) -> None:
        m: Matrix[int] = Matrix(2, 2, 0)
        marker = _eval_src(_ev(m=m), "m.rows")
        assert marker[0] == "_ns_method" and marker[2] == "matrix.rows"
        arr = [1, 2, 3]
        marker2 = _eval_src(_ev(a=arr), "a.get")
        assert marker2[0] == "_array_method" and marker2[2] == "get"

    def test_host_alias(self) -> None:
        chart = SimpleNamespace(is_heikin_ashi=True)
        assert _eval_src(_ev(chart=chart), "chart.is_heikinashi") is True

    def test_subscript_series(self) -> None:
        ev = _ev(s=[1.0, 2.0, 3.0])
        assert _eval_src(ev, "s[0]") == 3.0
        assert _eval_src(ev, "s[1]") == 2.0
        assert _eval_src(ev, "s[9]") is None
        assert _eval_src(ev, "s[-1]") is None
        assert _eval_src(_ev(x=5), "x[0]") == 5
        assert _eval_src(_ev(x=5), "x[2]") is None
        assert _eval_src(_ev(x=5), "x[-1]") is None

    def test_subscript_edges(self) -> None:
        assert _eval_src(_ev(s=[1.0]), "s[na]") is None
        assert _eval_src(_ev(s=[1.0, 2.0]), "s[0.0]") == 2.0
        assert _eval_src(_ev(d={"k": 1}), 'd["k"]') == 1
        assert _eval_src(_ev(d={"k": 1}), 'd["missing"]') is None
        assert _eval_src(_ev(), "abs(1)[0]") == 1
        with pytest.raises(ValueError):
            _eval_src(_ev(m=Matrix(2, 2, 0)), "m[0]")


# ---------------------------------------------------------------------------
# transformer.py
# ---------------------------------------------------------------------------


class _DropAssign(NodeTransformer):
    def __init__(self) -> None:
        super().__init__()

    def visit_Assign(self, node: ast.AST) -> ast.AST | None:  # noqa: N802
        return None


class _DupExpr(NodeTransformer):
    def __init__(self) -> None:
        super().__init__()

    def visit_Expr(self, node: ast.AST) -> list[ast.AST]:  # noqa: N802
        return [node, node]


class _ZeroConst(NodeTransformer):
    def __init__(self) -> None:
        super().__init__()

    def visit_Constant(self, node: ast.Constant) -> ast.AST:  # noqa: N802
        return ast.Constant(value=0)


class _DropConst(NodeTransformer):
    def __init__(self) -> None:
        super().__init__()

    def visit_Constant(self, node: ast.Constant) -> None:  # noqa: N802
        return None


class TestTransformer:
    def test_remove_from_list(self) -> None:
        tree = helper.parse('indicator("T")\nx = 1\nplot(x)\n')
        kinds = [type(s).__name__ for s in tree.body]
        assert "Assign" in kinds
        _DropAssign().visit(tree)
        assert all(type(s).__name__ != "Assign" for s in tree.body)

    def test_splice_list(self) -> None:
        tree = helper.parse('indicator("T")\nplot(close)\n')
        before = len(tree.body)
        _DupExpr().visit(tree)
        assert len(tree.body) > before

    def test_replace_scalar(self) -> None:
        tree = helper.parse('indicator("T")\nx = 1\n')
        _ZeroConst().visit(tree)
        assign = next(s for s in tree.body if type(s).__name__ == "Assign")
        assert assign.value.value == 0

    def test_delete_scalar(self) -> None:
        tree = helper.parse('indicator("T")\nx = 1\n')
        assign = next(s for s in tree.body if type(s).__name__ == "Assign")
        _DropConst().visit(assign)
        assert not hasattr(assign, "value")


# ---------------------------------------------------------------------------
# optimize/study.py — pure helpers and fast study paths
# ---------------------------------------------------------------------------


class TestStudyHelpers:
    def test_is_strategy(self) -> None:
        assert is_strategy_script('strategy("S")\nplot(close)') is True
        assert is_strategy_script('indicator("I")\nplot(close)') is False
        assert is_strategy_script("") is False

    def test_mean_stats(self) -> None:
        assert _mean_stats([]) is None
        rows = [
            StrategyStats(
                total_pnl=10.0,
                win_rate=1.0,
                profit_factor=float("inf"),
                avg_trade=10.0,
                max_dd=1.0,
                wins=1,
                losses=0,
                trades=1,
            ),
            StrategyStats(
                total_pnl=0.0, win_rate=0.0, profit_factor=2.0, avg_trade=0.0, max_dd=2.0, wins=0, losses=1, trades=1
            ),
        ]
        mean = _mean_stats(rows)
        assert mean is not None and mean.trades == 2 and mean.total_pnl == 10.0
        nan_row = [StrategyStats(trades=1, profit_factor=float("nan"), win_rate=0.5)]
        assert _mean_stats(nan_row).profit_factor == 0.0
        calm = [StrategyStats(trades=0)]
        assert _mean_stats(calm).profit_factor == 0.0

    def test_slice_and_bar_time(self) -> None:
        bars = _bars(5)
        assert len(_slice_bars(bars, slice(1, 3))) == 2
        assert _bar_open_time({}) is None
        assert _bar_open_time({"time": "bad"}) is None
        assert _bar_open_time({"time": float("nan")}) is None
        assert _bar_open_time({"bar_time": 5}) == 5.0
        assert _bar_open_time({"time": 7}) == 7.0

    def test_score_window(self) -> None:
        assert _score_window(None) is None
        assert _score_window([]) is None
        assert _score_window([{"close": 1}]) is None
        assert _score_window(["x", {"time": 1}, {"time": 3}]) == (1.0, 3.0)

    def test_run_bars(self) -> None:
        bars = _bars(10)
        run, orig = _test_run_bars(bars, slice(0, 7), slice(7, 10), 0)
        assert len(run) == 3 and orig is None
        run2, orig2 = _test_run_bars(bars, slice(0, 7), slice(7, 10), 2)
        assert orig2 is not None and len(run2) >= len(orig2)

    def test_run_once(self) -> None:
        stats, err = run_once(_StubRuntime(), "s", _bars(3), {})
        assert err is None and stats is not None
        _, err2 = run_once(_StubRuntime(RuntimeError("boom")), "s", _bars(3), {})
        assert "RuntimeError" in err2
        _, err3 = run_once(_StubRuntime("weird"), "s", _bars(3), {})
        assert err3 is not None
        _, err4 = run_once(_StubRuntime({"error": "bad"}), "s", _bars(3), {})
        assert err4 == "bad"
        stats5, _ = run_once(_StubRuntime({"events": "nope"}), "s", _bars(3), {})
        assert stats5 is not None

    def test_study_error_paths(self) -> None:
        bad = run_study('indicator("I")', _bars(5), _space(), n_trials=1, runtime=_StubRuntime())
        assert bad.status == "error" and "NOT_A_STRATEGY" in bad.error
        nodata = run_study('strategy("S")', [], _space(), n_trials=1, runtime=_StubRuntime())
        assert nodata.error == "NO_DATA"
        empty = run_study('strategy("S")', _bars(5), SearchSpace(), n_trials=1, runtime=_StubRuntime())
        assert empty.error == "EMPTY_SPACE"
        badobj = run_study('strategy("S")', _bars(5), _space(), n_trials=1, objective="bogus", runtime=_StubRuntime())
        assert badobj.status == "error"
        wf = ValidationSpec(mode="walk-forward", train_bars=10, test_bars=10, step_bars=1)
        toomany = run_study('strategy("S")', _bars(500), _space(), n_trials=30, validation=wf, runtime=_StubRuntime())
        assert toomany.status == "error" and "TOO_MANY_RUNS" in toomany.error

    def test_study_success_and_cancel(self) -> None:
        bars = _bars(10)
        res = run_study(
            'strategy("S")\nplot(close)',
            bars,
            _space(),
            n_trials=1,
            validation=ValidationSpec(mode="in-sample"),
            runtime=_StubRuntime(),
        )
        assert res.status == "success" and len(res.trials) == 1
        hold = run_study(
            'strategy("S")\nplot(close)',
            bars,
            _space(),
            n_trials=1,
            validation=ValidationSpec(mode="holdout", holdout_frac=0.3),
            runtime=_StubRuntime(),
        )
        assert hold.status == "success"
        cancelled = run_study(
            'strategy("S")',
            bars,
            _space(),
            n_trials=3,
            validation=ValidationSpec(mode="in-sample"),
            runtime=_StubRuntime(),
            should_stop=lambda: True,
        )
        assert cancelled.status == "cancelled"
        zero = run_study(
            'strategy("S")',
            bars,
            _space(),
            n_trials=0,
            validation=ValidationSpec(mode="in-sample"),
            runtime=_StubRuntime(),
        )
        assert zero.n_trials == 1
