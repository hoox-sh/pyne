"""Direct unit tests for pure helpers in ``pynescript.compiler.numba_builtins``.

Calls njit TA kernels and Python coercion helpers directly on tiny numpy
arrays (no script compilation), so this file stays fast (<60s).
"""

from __future__ import annotations

import numpy as np
import pytest

from pynescript.compiler import numba_builtins as nb


def f64(values):
    return np.asarray(values, dtype=np.float64)


def test_sma_basic():
    arr = f64([1, 2, 3, 4, 5])
    assert nb.numba_sma(arr, 3, 4) == pytest.approx(4.0)


def test_sma_warmup_is_nan():
    arr = f64([1, 2, 3, 4, 5])
    assert nb.numba_sma(arr, 3, 1) != nb.numba_sma(arr, 3, 1)
    assert np.isnan(nb.numba_sma(arr, 0, 4))
    assert np.isnan(nb.numba_sma(arr, -2, 4))


def test_sma_nan_poison():
    arr = f64([1.0, np.nan, 3.0])
    assert np.isnan(nb.numba_sma(arr, 3, 2))


def test_ema_linear_series():
    arr = f64([1, 2, 3, 4, 5])
    assert nb.numba_ema(arr, 3, 4) == pytest.approx(4.0)


def test_ema_constant_and_warmup():
    arr = f64([5, 5, 5, 5, 5])
    assert nb.numba_ema(arr, 3, 4) == pytest.approx(5.0)
    assert np.isnan(nb.numba_ema(arr, 3, 1))
    assert np.isnan(nb.numba_ema(arr, 0, 4))


def test_rma_constant():
    arr = f64([2, 2, 2, 2])
    assert nb.numba_rma(arr, 2, 3) == pytest.approx(2.0)
    assert np.isnan(nb.numba_rma(arr, 2, 0))


def test_rsi_all_gains_is_100():
    arr = f64([1, 2, 3, 4])
    assert nb.numba_rsi(arr, 3, 3) == pytest.approx(100.0)


def test_rsi_all_losses_is_0():
    arr = f64([4, 3, 2, 1])
    assert nb.numba_rsi(arr, 3, 3) == pytest.approx(0.0)


def test_rsi_warmup_is_nan():
    arr = f64([1, 2, 3, 4])
    assert np.isnan(nb.numba_rsi(arr, 3, 2))


def test_highest_lowest_basic():
    arr = f64([1, 3, 2, 5, 4])
    assert nb.numba_highest(arr, 3, 4) == pytest.approx(5.0)
    assert nb.numba_lowest(arr, 3, 4) == pytest.approx(2.0)


def test_highest_lowest_warmup_and_nan_skip():
    arr = f64([1, 3, 2, 5, 4])
    assert np.isnan(nb.numba_highest(arr, 3, 1))
    assert np.isnan(nb.numba_lowest(arr, 3, 1))
    arr2 = f64([np.nan, 3.0, 2.0])
    assert nb.numba_highest(arr2, 3, 2) == pytest.approx(3.0)
    assert nb.numba_lowest(arr2, 3, 2) == pytest.approx(2.0)


def test_stdev_sample():
    arr = f64([1, 2, 3])
    assert nb.numba_stdev(arr, 3, 2) == pytest.approx(1.0)
    assert np.isnan(nb.numba_stdev(arr, 1, 2))


def test_change_basic():
    arr = f64([1, 2, 5])
    assert nb.numba_change(arr, 1, 2) == pytest.approx(3.0)
    assert np.isnan(nb.numba_change(arr, 5, 2))
    assert np.isnan(nb.numba_change(arr, 0, 2))


def test_tr_basic_and_first_bar_nan():
    high = f64([10, 12])
    low = f64([8, 9])
    close = f64([9, 11])
    assert nb.numba_tr(high, low, close, 1) == pytest.approx(3.0)
    assert np.isnan(nb.numba_tr(high, low, close, 0))


def test_cum_skips_nan():
    arr = f64([1.0, np.nan, 2.0])
    assert nb.numba_cum(arr, 2) == pytest.approx(3.0)


def test_cum_expr_running():
    state = f64([0, 0, 0])
    assert nb.numba_cum_expr(state, 5.0, 0) == pytest.approx(5.0)
    assert nb.numba_cum_expr(state, np.nan, 1) == pytest.approx(5.0)
    assert nb.numba_cum_expr(state, 2.0, 2) == pytest.approx(7.0)


def test_wma_basic():
    arr = f64([1, 2, 3])
    assert nb.numba_wma(arr, 3, 2) == pytest.approx(14.0 / 6.0)
    assert np.isnan(nb.numba_wma(arr, 3, 1))


def test_roc_basic():
    arr = f64([10, 20])
    assert nb.numba_roc(arr, 1, 1) == pytest.approx(100.0)
    assert np.isnan(nb.numba_roc(arr, 5, 1))
    arr0 = f64([0, 5])
    assert np.isnan(nb.numba_roc(arr0, 1, 1))


def test_sum_basic():
    arr = f64([1, 2, 3, 4, 5])
    assert nb.numba_sum(arr, 3, 4) == pytest.approx(12.0)
    assert np.isnan(nb.numba_sum(arr, 3, 1))


def test_variance_matches_stdev_squared():
    arr = f64([1, 2, 3])
    assert nb.numba_variance(arr, 3, 2) == pytest.approx(1.0)
    assert np.isnan(nb.numba_variance(arr, 1, 2))


def test_dev_mean_abs_deviation():
    arr = f64([1, 2, 3])
    assert nb.numba_dev(arr, 3, 2) == pytest.approx(2.0 / 3.0)


def test_correlation_identical_is_one():
    arr = f64([1, 2, 3, 4])
    assert nb.numba_correlation(arr, arr, 4, 3) == pytest.approx(1.0)


def test_correlation_constant_is_nan():
    arr = f64([5, 5, 5, 5])
    other = f64([1, 2, 3, 4])
    assert np.isnan(nb.numba_correlation(arr, other, 4, 3))


def test_stoch_basic():
    src = f64([5, 5, 5])
    high = f64([10, 10, 10])
    low = f64([0, 0, 0])
    assert nb.numba_stoch(src, high, low, 3, 2) == pytest.approx(50.0)
    assert np.isnan(nb.numba_stoch(src, high, low, 3, 1))


def test_stoch_flat_range_is_50():
    src = f64([5, 5])
    band = f64([5, 5])
    assert nb.numba_stoch(src, band, band, 2, 1) == pytest.approx(50.0)


def test_cci_flat_is_zero():
    arr = f64([5, 5, 5])
    assert nb.numba_cci(arr, 3, 2) == pytest.approx(0.0)
    assert np.isnan(nb.numba_cci(arr, 3, 1))


def test_vwap_basic():
    src = f64([10, 20])
    vol = f64([1, 1])
    assert nb.numba_vwap(src, vol, 1) == pytest.approx(15.0)


def test_vwap_empty_volume_is_nan():
    src = f64([10, 20])
    vol = f64([0, 0])
    assert np.isnan(nb.numba_vwap(src, vol, 1))


def test_obv_warmup_and_accumulation():
    close = f64([10, 11, 12])
    vol = f64([100, 100, 100])
    assert nb.numba_obv(close, vol, 1) == pytest.approx(0.0)
    assert nb.numba_obv(close, vol, 2) == pytest.approx(100.0)
    close2 = f64([12, 11, 10])
    assert nb.numba_obv(close2, vol, 2) == pytest.approx(-100.0)


def test_crossover_crossunder():
    a = f64([1, 2])
    b = f64([2, 1])
    assert nb.numba_crossover(a, b, 1) is True
    assert nb.numba_crossunder(b, a, 1) is True
    assert nb.numba_crossunder(a, b, 1) is False
    c = f64([2, 1])
    d = f64([1, 2])
    assert nb.numba_crossunder(c, d, 1) is True
    assert nb.numba_crossover(a, b, 0) is False
    assert nb.numba_crossunder(a, b, 0) is False


def test_crossover_scalar():
    a = f64([1, 3])
    assert nb.numba_crossover_scalar(a, 2.0, 1) is True
    assert nb.numba_crossunder_scalar(a, 2.0, 1) is False
    assert nb.numba_crossover_scalar(a, 2.0, 0) is False
    b = f64([3, 1])
    assert nb.numba_crossunder_scalar(b, 2.0, 1) is True


def test_barssince():
    cond = f64([1, 0, 0])
    assert nb.numba_barssince(cond, 2) == pytest.approx(2.0)
    assert nb.numba_barssince(cond, 0) == pytest.approx(0.0)
    assert np.isnan(nb.numba_barssince(f64([0, 0]), 1))


def test_linreg_linear_fit():
    arr = f64([1, 2, 3, 4])
    assert nb.numba_linreg(arr, 4, 0, 3) == pytest.approx(4.0)
    assert np.isnan(nb.numba_linreg(arr, 4, 0, 2))


def test_rising_falling():
    up = f64([1, 2, 3, 4])
    assert nb.numba_rising(up, 2, 3) is True
    assert nb.numba_falling(up, 2, 3) is False
    down = f64([4, 3, 2, 1])
    assert nb.numba_falling(down, 2, 3) is True
    assert nb.numba_rising(down, 2, 3) is False
    assert nb.numba_rising(up, 9, 3) is False


def test_highestbars_lowestbars():
    arr = f64([1, 3, 2])
    assert nb.numba_highestbars(arr, 3, 2) == pytest.approx(-1.0)
    assert nb.numba_lowestbars(arr, 3, 2) == pytest.approx(-2.0)
    assert nb.numba_highestbars(arr, 3, 1) == pytest.approx(-1.0)
    assert nb.numba_highestbars(arr, 9, 2) == pytest.approx(-1.0)


def test_percentrank_top():
    arr = f64([1, 2, 3])
    assert nb.numba_percentrank(arr, 3, 2) == pytest.approx(100.0 * 2.0 / 3.0)
    assert np.isnan(nb.numba_percentrank(arr, 3, 1))


def test_median_odd_even():
    assert nb.numba_median(f64([3, 1, 2]), 3, 2) == pytest.approx(2.0)
    assert nb.numba_median(f64([4, 1, 3, 2]), 4, 3) == pytest.approx(2.5)
    assert np.isnan(nb.numba_median(f64([1, 2]), 3, 1))


def test_wpr_basic_and_warmup():
    high = f64([10, 10])
    low = f64([0, 0])
    close = f64([9, 5])
    assert nb.numba_wpr(high, low, close, 2, 1) == pytest.approx(-50.0)
    assert nb.numba_wpr(high, low, close, 2, 0) == pytest.approx(0.0)


def test_cmo_all_up():
    arr = f64([1, 2, 3])
    assert nb.numba_cmo(arr, 2, 2) == pytest.approx(100.0)
    assert np.isnan(nb.numba_cmo(arr, 2, 1))


def test_macd_constant_series_is_zero():
    arr = f64([5.0] * 20)
    macd, sig, hist = nb.numba_macd(arr, 2, 5, 3, 10)
    assert macd == pytest.approx(0.0)
    assert sig == pytest.approx(0.0)
    assert hist == pytest.approx(0.0)


def test_macd_warmup_is_nan():
    arr = f64([5.0] * 20)
    _macd, sig, hist = nb.numba_macd(arr, 2, 5, 3, 3)
    assert np.isnan(sig)
    assert np.isnan(hist)


def test_bb_constant_series():
    arr = f64([5.0] * 5)
    upper, mid, lower = nb.numba_bb(arr, 3, 2.0, 4)
    assert mid == pytest.approx(5.0)
    assert upper == pytest.approx(5.0)
    assert lower == pytest.approx(5.0)


def test_bb_warmup_is_nan():
    arr = f64([5.0] * 5)
    upper, mid, lower = nb.numba_bb(arr, 3, 2.0, 1)
    assert np.isnan(mid) and np.isnan(upper) and np.isnan(lower)


def test_nz_and_safe_div_mod():
    assert nb.numba_nz(np.nan, 7.0) == pytest.approx(7.0)
    assert nb.numba_nz(3.0, 7.0) == pytest.approx(3.0)
    assert nb.numba_nz(None, 7.0) == pytest.approx(7.0)
    assert nb.numba_safe_div(6.0, 3.0) == pytest.approx(2.0)
    assert np.isnan(nb.numba_safe_div(1.0, 0.0))
    assert np.isnan(nb.numba_safe_div(1.0, None))
    assert nb.numba_safe_mod(5.0, 3.0) == pytest.approx(2.0)
    assert np.isnan(nb.numba_safe_mod(1.0, 0.0))


def test_abs_max_min_scalars():
    assert nb.numba_abs(-3.0) == pytest.approx(3.0)
    assert np.isnan(nb.numba_abs(None))
    assert nb.numba_max(3.0, np.nan) == pytest.approx(3.0)
    assert np.isnan(nb.numba_max(np.nan, np.nan))
    assert nb.numba_min(3.0, np.nan) == pytest.approx(3.0)
    assert np.isnan(nb.numba_min(np.nan, np.nan))
    assert nb.numba_max(1.0, 2.0) == pytest.approx(2.0)
    assert nb.numba_min(1.0, 2.0) == pytest.approx(1.0)


def test_pine_eq_ne():
    assert nb.numba_pine_eq(1.0, 1.0) is True
    assert nb.numba_pine_eq(1.0, 2.0) is False
    assert nb.numba_pine_eq(np.nan, np.nan) is True
    assert nb.numba_pine_eq(np.nan, 1.0) is False
    assert nb.numba_pine_ne(1.0, 2.0) is True
    assert nb.numba_pine_ne(1.0, 1.0) is False
    assert nb.numba_pine_ne(np.nan, np.nan) is False


def test_valuewhen_basic():
    cond = f64([1, 0, 1])
    src = f64([10, 20, 30])
    assert nb.numba_valuewhen(cond, src, 0, 2) == pytest.approx(30.0)
    assert nb.numba_valuewhen(cond, src, 1, 2) == pytest.approx(10.0)
    assert np.isnan(nb.numba_valuewhen(f64([0, 0]), src[:2], 0, 1))


def test_pivothigh_pivotlow():
    arr = f64([1, 3, 2, 1, 0])
    assert nb.numba_pivothigh(arr, 1, 1, 2) == pytest.approx(3.0)
    assert np.isnan(nb.numba_pivothigh(arr, 1, 1, 1))
    trough = f64([5, 3, 1, 2, 4])
    assert nb.numba_pivotlow(trough, 1, 1, 3) == pytest.approx(1.0)
    assert np.isnan(nb.numba_pivotlow(trough, 1, 1, 1))
    assert np.isnan(nb.numba_pivothigh(arr, None, 1, 2))


def test_sma_inc_matches_batch():
    arr = f64([1, 2, 3, 4, 5])
    st = f64([np.nan, np.nan])
    out = [nb.numba_sma_inc(arr, 3, i, st) for i in range(5)]
    assert np.isnan(out[1])
    assert out[4] == pytest.approx(nb.numba_sma(arr, 3, 4))


def test_ema_inc_matches_batch():
    arr = f64([1, 2, 3, 4, 5])
    st = f64([np.nan, np.nan])
    out = [nb.numba_ema_inc(arr, 3, i, st) for i in range(5)]
    assert np.isnan(out[1])
    assert out[4] == pytest.approx(nb.numba_ema(arr, 3, 4))


def test_cum_inc_matches_batch():
    arr = f64([1.0, np.nan, 2.0, 3.0])
    st = f64([np.nan, np.nan])
    out = [nb.numba_cum_inc(arr, i, st) for i in range(4)]
    assert out[3] == pytest.approx(nb.numba_cum(arr, 3))


def test_safe_float():
    assert np.isnan(nb.safe_float(None))
    assert nb.safe_float(True) == pytest.approx(1.0)  # noqa: FBT003
    assert nb.safe_float(False) == pytest.approx(0.0)  # noqa: FBT003
    assert nb.safe_float(3) == pytest.approx(3.0)
    assert nb.safe_float("3.5") == pytest.approx(3.5)
    assert np.isnan(nb.safe_float(""))
    assert np.isnan(nb.safe_float("abc"))
    assert np.isnan(nb.safe_float("#FF0000"))
    assert np.isnan(nb.safe_float({"a": 1}))
    assert np.isnan(nb.safe_float([]))
    assert nb.safe_float([1, 2]) == pytest.approx(1.0)
    assert np.isnan(nb.safe_float(np.array([])))


def test_na_num():
    assert np.isnan(nb.na_num(None))
    assert nb.na_num(3.5) == pytest.approx(3.5)
    assert nb.na_num(3) == 3
    assert nb.na_num(True) == pytest.approx(1.0)  # noqa: FBT003


def test_safe_int():
    assert nb.safe_int(np.nan) == 0
    assert nb.safe_int(None) == 0
    assert nb.safe_int(3.9) == 3
    assert nb.safe_int("7") == 7


def test_pine_int():
    assert nb.pine_int(3.9) == pytest.approx(3.0)
    assert nb.pine_int(-3.9) == pytest.approx(-3.0)
    assert np.isnan(nb.pine_int(np.nan))
    assert np.isnan(nb.pine_int(None))
    assert np.isnan(nb.pine_int(float("inf")))


def test_pine_bool():
    assert nb.pine_bool(None) is False
    assert nb.pine_bool(float("nan")) is False
    assert nb.pine_bool(0.0) is False
    assert nb.pine_bool(2.5) is True
    assert nb.pine_bool("") is False
    assert nb.pine_bool("x") is True


def test_pine_string():
    assert nb.pine_string(None) == "na"
    assert nb.pine_string(float("nan")) == "na"
    assert nb.pine_string(True) == "true"  # noqa: FBT003
    assert nb.pine_string(False) == "false"  # noqa: FBT003
    assert nb.pine_string(5) == "5"


def test_safe_period_len_iter():
    assert nb.safe_period(np.nan) == 0
    assert nb.safe_period(None) == 0
    assert nb.safe_period("5") == 5
    assert nb.safe_period(3.9) == 3
    assert nb.safe_len(None) == 0
    assert nb.safe_len([1, 2]) == 2
    assert nb.safe_len("ab") == 2
    assert nb.safe_len(5) == 0
    assert nb.safe_len(np.zeros(3)) == 3
    assert nb.safe_iter(None) == ()
    assert nb.safe_iter(5) == ()
    assert list(nb.safe_iter([1, 2])) == [1, 2]


def test_safe_iter_pairs():
    assert nb.safe_iter_pairs(None) == ()
    assert dict(nb.safe_iter_pairs({"a": 1})) == {"a": 1}
    assert list(nb.safe_iter_pairs([10, 20])) == [(0, 10), (1, 20)]
    assert nb.safe_iter_pairs("ab") == ()


def test_safe_sum_max_min():
    assert nb.safe_sum(None) == pytest.approx(0.0)
    assert nb.safe_sum([1, 2, 3]) == pytest.approx(6.0)
    assert nb.safe_sum(5) == pytest.approx(5.0)
    assert nb.safe_max([1, 2, 3]) == pytest.approx(3.0)
    assert nb.safe_min([1, 2, 3]) == pytest.approx(1.0)
    assert np.isnan(nb.safe_max(None))
    assert np.isnan(nb.safe_min([]))


def test_nz_py_and_pine_add_tonumber():
    assert nb.nz_py(None, 9.0) == pytest.approx(9.0)
    assert nb.nz_py(float("nan"), 9.0) == pytest.approx(9.0)
    assert nb.nz_py("a", 9.0) == "a"
    assert nb.nz_py(5, 9.0) == 5
    assert nb.pine_add("a", 1) == "a1"
    assert nb.pine_add(1, 2) == 3
    assert nb.safe_tonumber("3.5") == pytest.approx(3.5)
    assert np.isnan(nb.safe_tonumber(""))
    assert np.isnan(nb.safe_tonumber("abc"))
    assert np.isnan(nb.safe_tonumber(None))


def test_array_mode_range():
    assert nb.array_mode([1, 2, 2, 3]) == 2
    assert np.isnan(nb.array_mode([1, 2, 3]))
    assert np.isnan(nb.array_mode([]))
    assert np.isnan(nb.array_mode(None))
    assert nb.array_range([1, 2, 5]) == pytest.approx(4.0)
    assert np.isnan(nb.array_range([]))
    assert np.isnan(nb.array_range(None))


def test_array_abs_every_some():
    out = nb.array_abs([1, -2, None])
    assert out[0] == pytest.approx(1.0)
    assert out[1] == pytest.approx(2.0)
    assert np.isnan(out[2])
    assert nb.array_abs(None) == []
    assert nb.array_every([1, 2]) is True
    assert nb.array_every([1, 0]) is False
    assert nb.array_some([0, 1]) is True
    assert nb.array_some([0, 0]) is False
    assert nb.array_some(None) is False


def test_array_percentiles():
    assert nb.array_percentile_linear_interpolation([1, 2, 3, 4], 50) == pytest.approx(2.5)
    assert nb.array_percentile_nearest_rank([1, 2, 3, 4], 50) == pytest.approx(2.0)
    assert nb.array_percentrank([1, 2, 3, 4], 3) == pytest.approx(200.0 / 3.0)
    assert np.isnan(nb.array_percentile_linear_interpolation([], 50))
    assert np.isnan(nb.array_percentrank([], 1))


def test_array_standardize_normalized_sort_indices():
    std = nb.array_standardize([1, 2, 3])
    assert std == pytest.approx([-1.22474487, 0.0, 1.22474487])
    assert nb.array_standardize(None) == []
    norm = nb.array_normalized([0, 5, 10])
    assert norm == pytest.approx([0.0, 0.5, 1.0])
    assert nb.array_sort_indices([30, 10, 20]) == [1, 2, 0]
    assert nb.array_sort_indices([30, 10, 20], order="descending") == [0, 2, 1]


def test_matrix_basics():
    m = [[1, 2], [3, 4]]
    assert nb.matrix_get(m, 1, 0) == 3
    assert np.isnan(nb.matrix_get(m, 9, 0))
    assert nb.matrix_rows(m) == 2
    assert nb.matrix_columns(m) == 2
    assert nb.matrix_rows(5.0) == 0
    nb.matrix_set(m, 0, 0, 99)
    assert m[0][0] == 99
    assert nb.matrix_is_square(m) is True
    assert nb.matrix_is_square([[1, 2, 3]]) is False


def test_matrix_mutators():
    m = [[1, 2], [3, 4]]
    nb.matrix_add_row(m, [5, 6])
    assert m == [[1, 2], [3, 4], [5, 6]]
    nb.matrix_add_col(m, [7, 8, 9])
    assert m[0] == [1, 2, 7]
    removed = nb.matrix_remove_row(m, 0)
    assert removed == [1, 2, 7]
    removed_col = nb.matrix_remove_col(m, 0)
    assert removed_col == [3, 5]
    m2 = [[1, 2], [3, 4]]
    nb.matrix_swap_rows(m2, 0, 1)
    assert m2 == [[3, 4], [1, 2]]
    m3 = [[1, 2, 3, 4]]
    nb.matrix_reshape(m3, 2, 2)
    assert m3 == [[1, 2], [3, 4]]
    assert nb.matrix_transpose([[1, 2], [3, 4]]) == [[1, 3], [2, 4]]


def test_map_put_all_and_contains_split():
    dest = {"a": 1}
    assert nb.map_put_all(dest, {"b": 2}) == {"a": 1, "b": 2}
    assert nb.map_put_all([1], {"b": 2}) == [1]
    assert nb.safe_contains([1, 2], 2) is True
    assert nb.safe_contains(None, 1) is False
    assert nb.safe_contains(5, 5) is False
    assert nb.str_split("a,b,c", ",") == ["a", "b", "c"]
    assert nb.str_split("abc", "") == ["a", "b", "c"]


def test_list_helpers_and_store():
    arr = [1, 2]
    nb.safe_list_append(arr, 3)
    assert arr == [1, 2, 3]
    nb.safe_list_set(arr, 0, 9)
    assert arr[0] == 9
    nb.safe_list_insert(arr, 0, 0)
    assert arr[0] == 0
    assert nb.safe_list_pop(arr, 0) == 0
    nb.safe_list_clear(arr)
    assert arr == []
    dst = f64([0, 0, 0])
    nb.store_src_py(dst, 5.0, 1)
    assert dst[1] == pytest.approx(5.0)
    nb.store_src_py(dst, "bad", 2)
    assert np.isnan(dst[2])


def test_pine_str_format_and_color():
    assert nb.pine_str_format("hi {0}", "bob") == "hi bob"
    assert nb.pine_str_format(None) == "NaN"
    assert nb.pine_str_format("{0, number}", 3.14159) == "3.14159"
    assert nb.pine_color_new("#FF0000", 0) == "rgba(255, 0, 0, 1.0)"
    assert nb.pine_color_new(None) is None


def test_chart_identity_and_raise_and_udt():
    nb.set_chart_identity(ticker="AAPL", tickerid="NASDAQ:AAPL", prefix="NASDAQ")
    assert nb.chart_ticker() == "AAPL"
    assert nb.chart_tickerid() == "NASDAQ:AAPL"
    assert nb.chart_prefix() == "NASDAQ"
    nb.set_chart_identity()
    assert nb.chart_ticker() == "SYMBOL"
    with pytest.raises(RuntimeError):
        nb.pine_raise("boom")
    assert nb.udt_get_field({"a": 1}, "a") == 1
    assert np.isnan(nb.udt_get_field(5.0, "a"))
    assert nb.udt_index({"a": 1, "b": 2}, 1) == 2
    assert np.isnan(nb.udt_index([1], 9))
    d = {"a": 1}
    assert nb.udt_set_field(d, "a", 2) == 2
    assert d["a"] == 2


def test_timeframe_change_and_timestamps():
    times = f64([0, 60000])
    assert nb.numba_timeframe_change(times, 0, 60000.0) is True
    assert nb.numba_timeframe_change(times, 1, 60000.0) is True
    assert nb.numba_timeframe_change(times, 1, 0.0) is False
    assert nb.numba_days_from_civil(1970, 1, 1) == 0
    assert nb.numba_timestamp(1970, 1, 1) == pytest.approx(0.0)
    assert nb.numba_timestamp("GMT+3", 2020, 1, 1) == nb.numba_timestamp(2020, 1, 1)


def test_numba_store_and_store_src():
    arr = f64([0, 0, 0])
    assert nb.numba_store(arr, 1, 7.0) == pytest.approx(7.0)
    assert arr[1] == pytest.approx(7.0)
    dst = f64([0, 0, 0])
    nb.numba_store_src(dst, 4.0, 2)
    assert dst[2] == pytest.approx(4.0)
    nb.numba_store_src(dst, np.nan, 0)
    assert np.isnan(dst[0])


def test_numba_utc_parts_epoch_and_nan():
    parts = nb.numba_utc_parts(0.0)
    assert parts == (1970.0, 1.0, 1.0, 0.0, 0.0, 0.0, 5.0)
    assert nb.numba_utc_parts(float("nan")) == parts


def test_numba_synthetic_time():
    out = nb.numba_synthetic_time(3)
    assert list(out) == pytest.approx([0.0, 60000.0, 120000.0])


def test_ta_wrappers_and_series():
    assert nb._series_f64(None) is None
    assert list(nb._series_f64(5)) == pytest.approx([5.0])
    assert np.isnan(nb.ta_wad(1.0, 2.0))
    assert np.isnan(nb.ta_iii(1.0, 2.0))
    assert np.isnan(nb.ta_wvad(5.0))
    assert np.isnan(nb.ta_wvad(1.0, 2.0, 3.0))
    h = [10.0, 11.0, 12.0]
    low = [9.0, 10.0, 11.0]
    c = [9.5, 10.5, 11.5]
    v = [100.0, 100.0, 100.0]
    assert np.isfinite(nb.ta_wad(h, low, c, v, 2))
    assert np.isfinite(nb.ta_iii(h, low, c, 2))
    assert np.isfinite(nb.ta_wvad(h, low, c, v, 2, 2))
    assert nb.input_bool(None) is False
    assert nb.input_bool(0) is False
    assert nb.input_bool(1) is True


def test_array_sort_and_fill():
    arr = [3, 1, 2]
    assert nb.array_sort(arr) == [1, 2, 3]
    assert nb.array_sort([3, 1, 2], order="descending") == [3, 2, 1]
    got = nb.array_sort([2, float("nan"), 1])
    assert got[0] == 1 and got[1] == 2 and got[2] != got[2]
    assert nb.array_sort(5.0) == 5.0
    mixed = [1, "a"]
    assert nb.array_sort(mixed) == [1, "a"]
    rows = [{"x": 2}, {"x": 1}]
    assert nb.array_sort(rows, sort_field="x") == [{"x": 1}, {"x": 2}]
    a = [0, 0, 0, 0]
    assert nb.array_fill(a, 9, 1, 3) == [0, 9, 9, 0]
    assert nb.array_fill([1, 2], 0) == [0, 0]
    assert nb.array_fill(5.0, 0) == 5.0
    m = [[1, 2], [3, 4]]
    assert nb.array_fill(m, 0) == [[0, 0], [0, 0]]
    assert nb.array_fill([1, 2, 3], 9, 2, 1) == [1, 2, 3]


def test_binary_search_variants():
    arr = [1, 2, 2, 3]
    assert nb.array_binary_search(arr, 2) in (1, 2)
    assert nb.array_binary_search(arr, 9) == -1
    assert nb.array_binary_search_leftmost(arr, 2) == 1
    assert nb.array_binary_search_rightmost(arr, 2) == 2
    assert nb.array_binary_search(5.0, 1) == -1
    assert nb.array_binary_search_leftmost(arr, 9) == -1
    assert nb.array_binary_search_rightmost(arr, 9) == -1
    assert nb._key_lt(None, 1) is False
    assert nb._key_lt(1, None) is True
    assert nb._key_lt(float("nan"), 1) is False
    assert nb._key_eq(None, None) is True
    assert nb._key_eq(None, 1) is False
    assert nb._key_eq(float("nan"), float("nan")) is False
    assert nb._resolve_search_field([1, 2], None) is None
    assert nb._resolve_search_field([{"__type__": "T", "x": 1}], None) == 0
    assert nb._search_elem_key(5, None) == 5


def test_matrix_linalg():
    m = [[1, 2], [3, 4]]
    assert nb.matrix_det(m) == pytest.approx(-2.0)
    assert np.isnan(nb.matrix_det([[1, 2, 3]]))
    assert np.isnan(nb.matrix_det(5.0))
    assert nb.matrix_det([]) == pytest.approx(1.0)
    np.testing.assert_allclose(nb.matrix_inv(m), [[-2.0, 1.0], [1.5, -0.5]])
    assert nb.matrix_inv([[1, 2, 3]]) == []
    assert nb.matrix_inv([[1, 1], [1, 1]]) == []
    assert nb.matrix_pinv([[1, 2], [3, 4]]) is not None
    assert nb.matrix_pinv(5.0) == []
    assert nb.matrix_median([[3, 1], [2, 4]]) == pytest.approx(2.5)
    assert np.isnan(nb.matrix_median([]))
    assert nb.matrix_mode([[1, 2], [2, 3]]) == 2
    assert nb.matrix_elements_count(m) == 4
    assert nb.matrix_elements_count(5.0) == 0
    assert nb.matrix_concat([[1]], [[2]], axis=0) == [[1], [2]]
    assert nb.matrix_concat([[1]], [[2]], axis=1) == [[1, 2]]
    assert nb.matrix_concat([[1, 2]], [[3]], axis=0) == []
    assert nb.matrix_concat([[1]], [[2], [3]], axis=1) == []
    assert nb.matrix_mult(m, 2.0) == [[2.0, 4.0], [6.0, 8.0]]
    assert nb.matrix_mult(m, [[1], [1]]) == [[3.0], [7.0]]
    assert nb.matrix_mult(5.0, 2.0) == []
    assert nb.matrix_mult(m, float("nan")) == []
    assert nb.matrix_mult(m, [1, 1]) == [3.0, 7.0]
    assert nb.matrix_diff(m, m) == [[0.0, 0.0], [0.0, 0.0]]
    assert nb.matrix_diff(m, [[1]]) == []
    assert nb.matrix_kron([[1, 0], [0, 1]], [[1, 2]]) == [[1, 2, 0, 0], [0, 0, 1, 2]]
    assert nb.matrix_kron(5.0, [[1]]) == []
    np.testing.assert_allclose(nb.matrix_pow([[1, 1], [1, 0]], 2), [[2.0, 1.0], [1.0, 1.0]])
    assert nb.matrix_pow([[1, 2, 3]], 2) == []
    assert nb.matrix_pow(m, -1) == []
    assert nb.matrix_is_zero([[0, 0], [0, 0]]) is True
    assert nb.matrix_is_zero(m) is False
    assert nb.matrix_is_zero(5.0) is False
    assert nb.matrix_is_identity([[1, 0], [0, 1]]) is True
    assert nb.matrix_is_identity(m) is False
    assert nb.matrix_is_antidiagonal([[0, 1], [2, 0]]) is True
    assert nb.matrix_is_antidiagonal(m) is False
    assert nb.matrix_is_antidiagonal(5.0) is False


def test_sequence_from_series():
    assert nb.sequence_from_series([1, 2, 3]) == pytest.approx([1.0, 2.0, 3.0])
    assert nb.sequence_from_series([1, 2, 3], length=2) == pytest.approx([2.0, 3.0])
    assert nb.sequence_from_series([1, 2, 3], direction_forward=False) == pytest.approx([3.0, 2.0, 1.0])
    assert nb.sequence_from_series(np.array([1.0, 2.0])) == pytest.approx([1.0, 2.0])
    assert nb.sequence_from_series(5.0) == pytest.approx([5.0])
    assert nb.sequence_from_series([]) == []
    assert nb.sequence_from_series([1, 2, 3], shift=9) == []


def test_safe_float_extra_branches():
    assert nb.safe_float(np.array([2.5, 3.0])) == pytest.approx(2.5)
    assert nb.safe_float(np.asarray(7.0)) == pytest.approx(7.0)
    assert np.isnan(nb.safe_float(lambda: 1))
    assert nb.safe_float((9, 10)) == pytest.approx(9.0)
    assert np.isnan(nb.safe_float("Round"))
    assert np.isnan(nb.safe_float("1.2.3"))


def test_safe_iter_extra_branches():
    a = np.array([1.0, 2.0])
    assert list(nb.safe_iter(a)) == pytest.approx([1.0, 2.0])
    assert nb.safe_iter(np.asarray(5.0)) == ()
    assert nb.safe_iter({1, 2}) == {1, 2}
    assert nb.safe_iter("ab") == "ab"
    pairs = np.array([[1, 2], [3, 4]])
    assert np.asarray(nb.safe_iter_pairs(pairs)).tolist() == [[1, 2], [3, 4]]
    assert list(nb.safe_iter_pairs((1, 2))) == [(0, 1), (1, 2)]
    assert nb.safe_iter_pairs(5) == ()


def test_udt_and_list_edge_cases():
    arr = np.array([10.0, 20.0])
    assert nb.udt_index(arr, 1) == pytest.approx(20.0)
    assert np.isnan(nb.udt_index(arr, 9))
    assert np.isnan(nb.udt_index(5.0, 0))
    assert nb.udt_set_field(5.0, "a", 1) == 1
    assert nb.udt_get_field({"a": 1}, "b", "dflt") == "dflt"
    lst = [1, 2, 3]
    assert nb.safe_list_set(lst, None, 9) == [1, 2, 3]
    assert nb.safe_list_set(lst, -1, 9) == [1, 2, 3]
    assert nb.safe_list_set(lst, "x", 9) == [1, 2, 3]
    assert nb.safe_list_set(5.0, 0, 9) == 5.0
    grown = [1]
    nb.safe_list_set(grown, 3, 9)
    assert grown == [1, None, None, 9]
    assert nb.safe_list_set([1], 10**9, 9) == [1]
    assert nb.safe_list_append(5.0, 1) == 5.0
    assert np.isnan(nb.safe_list_pop([], None))
    assert np.isnan(nb.safe_list_pop(5.0))
    assert np.isnan(nb.safe_list_pop([1], 9))
    assert nb.safe_list_pop([1, 2]) == 2
    assert nb.safe_list_insert([1], None, 9) == [1]
    assert nb.safe_list_insert([1], -2, 9) == [1]
    assert nb.safe_list_insert(5.0, 0, 9) == 5.0
    assert nb.safe_list_clear([1, 2]) is None
    assert nb.safe_list_clear(5.0) is None


def test_str_format_extra_kinds():
    assert nb.pine_str_format("{0, integer}", 3.9) == "3"
    assert nb.pine_str_format("{0, number, 0.00}", 3.14159) == "3.14"
    assert nb.pine_str_format("{9}", "a") == ""
    assert nb.pine_str_format("{0}", None) == "NaN"
    assert nb.pine_str_format("{x}", "a") == "{x}"
    assert nb.pine_add(None, None) == "NoneNone"


def test_color_helpers_extra():
    assert nb._parse_color_rgba("#FF0000") == (255, 0, 0, 255)
    assert nb._parse_color_rgba("rgba(1, 2, 3, 0.5)") == (1, 2, 3, 128)
    assert nb._parse_color_rgba(None) is None
    assert nb._parse_color_rgba("junk") is None
    assert nb.pine_color_new("#FF0000", 100) == "rgba(255, 0, 0, 0.0)"
    assert nb.pine_color_new("notacolor") == "notacolor"
    assert nb.pine_color_new("#FF0000", float("nan")) == "rgba(255, 0, 0, 1.0)"


def test_timeframe_change_at_guards():
    assert nb.timeframe_change_at([0, 1], -1, "D") is False
    assert nb.timeframe_change_at([0, 1], 9, "D") is False
    assert nb.timeframe_change_at([0, 1], "x", "D") is False
    assert nb.timeframe_change_at(5.0, 0, "D") is False
    assert isinstance(nb.timeframe_change_at([0, 86400000], 1, "D"), bool)


def test_valuewhen_object_path_and_cond():
    cond = np.array([1, 0, 1], dtype=object)
    src = np.array(["a", "b", "c"], dtype=object)
    assert nb.numba_valuewhen(cond, src, 0, 2) == "c"
    assert nb.numba_valuewhen(cond, src, 1, 2) == "a"
    assert nb._valuewhen_cond_true(None) is False
    assert nb._valuewhen_cond_true("x") is True
    assert nb._valuewhen_cond_true(0) is False
    assert np.isnan(nb.numba_pivothigh([1, 3, 2], 1, 1, 2))


def test_safe_sum_max_min_nested_and_descending():
    assert nb.safe_sum([[1, 2], [3]]) == pytest.approx(6.0)
    assert nb.safe_max([[1, 5], [3]]) == pytest.approx(5.0)
    assert nb.safe_min([[4, 1], [3]]) == pytest.approx(1.0)
    assert nb._pine_is_descending(True) is True  # noqa: FBT003
    assert nb._pine_is_descending(-1) is True
    assert nb._pine_is_descending("desc") is True
    assert nb._pine_is_descending(None) is False
    assert nb._pine_is_descending("asc") is False
    nb.set_chart_identity(ticker=None, tickerid=None, prefix=None)
    assert nb.chart_ticker() == "SYMBOL"
    assert nb.chart_tickerid() == "SYMBOL"
    assert nb.chart_prefix() == ""
    nb.set_chart_identity()


def test_matrix_row_col_index_and_swap_columns():
    m = [[1, 2], [3, 4]]
    nb.matrix_add_row(m, 0, [9, 9])
    assert m[0] == [9, 9]
    e = []
    nb.matrix_add_col(e, [1, 2])
    assert e == [[1], [2]]
    m2 = [[1, 2], [3, 4]]
    nb.matrix_swap_columns(m2, 0, 1)
    assert m2 == [[2, 1], [4, 3]]
    assert nb.matrix_swap_columns(m2, 0, 9) == m2
    assert nb.matrix_remove_row([[1]], 5) == []
    assert nb.matrix_remove_col([[1]], 5) == []
    assert nb.matrix_remove_row(5.0) == []
    assert nb._matrix_ncols(5.0) == 0
    assert nb._matrix_ensure(5.0) == []
    assert nb.array_sort_indices([3, float("nan"), 1]) == [2, 0, 1]


def test_udt_sort_key_branches():
    assert nb._udt_sort_key({"__type__": "T", "x": 7}, None) == 7
    assert nb._udt_sort_key({"x": 7}, "x") == 7
    assert nb._udt_sort_key({"x": 7}, 0) == 7
    assert nb._udt_sort_key(5, "x") == 5

    class _Stub:
        def get_field(self, name):
            return "v:" + name

    assert nb._udt_sort_key(_Stub(), "f") == "v:f"
    assert nb._udt_sort_key(_Stub(), None) is not None
    assert nb._is_sort_na(None) is True
    assert nb._is_sort_na(float("nan")) is True
    assert nb._is_sort_na(3) is False
