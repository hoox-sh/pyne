# Copyright (C) 2024-2026 jango_blockchained
#
# This file is part of pynescript.
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Round 8 Agent 10 — expression / control-flow parity goldens.

Covers soft string concat, na arithmetic, switch subject-na, if-block return
value, and period-or-none soft paths that historically caused Runtime FAIL or
wrong dual-mode values.
"""

from __future__ import annotations

import operator

import pytest

from pynescript.ast.evaluator.builtins.base import pine_period_or_none
from pynescript.ast.evaluator.expressions import _elementwise_binary
from pynescript.ast.evaluator.expressions import _pine_soft_str
from pynescript.ast.evaluator.expressions import _switch_case_matches


def _bars(n: int = 5) -> list[dict]:
    out: list[dict] = []
    t = 1_700_000_000_000
    for i in range(n):
        out.append(
            {
                "time": t + i * 86_400_000,
                "open": 100.0 + i,
                "high": 101.0 + i,
                "low": 99.0 + i,
                "close": 100.5 + i,
                "volume": 1000.0 + i,
            }
        )
    return out


def _run(src: str, bars: list[dict] | None = None) -> dict:
    from backend.runtime import Runtime

    return Runtime().run(src, bars if bars is not None else _bars(), mode="interpret")


def _last_plot(result: dict):
    assert "error" not in result, result.get("error")
    plots = result.get("plots")
    if isinstance(plots, dict):
        series = next(iter(plots.values()))
        return series[-1]
    return plots[-1]


# ---------------------------------------------------------------------------
# Soft concat / na arithmetic (unit, no Runtime)
# ---------------------------------------------------------------------------


class TestElementwiseSoftConcat:
    def test_str_plus_number(self) -> None:
        assert _elementwise_binary(operator.add, "ISIN: ", 12.5) == "ISIN: 12.5"
        assert _elementwise_binary(operator.add, 12, "x") == "12x"

    def test_str_plus_bool_lowercase(self) -> None:
        assert _pine_soft_str(True) == "true"
        assert _pine_soft_str(False) == "false"
        assert _elementwise_binary(operator.add, "flag=", True) == "flag=true"
        assert _elementwise_binary(operator.add, False, "!") == "false!"

    def test_str_plus_na_propagates(self) -> None:
        assert _elementwise_binary(operator.add, "x", None) is None
        assert _elementwise_binary(operator.add, None, "x") is None

    def test_str_plus_list_elementwise(self) -> None:
        assert _elementwise_binary(operator.add, "v=", [1, 2]) == ["v=1", "v=2"]

    def test_na_arithmetic(self) -> None:
        assert _elementwise_binary(operator.add, 1.0, None) is None
        assert _elementwise_binary(operator.mul, None, 2) is None
        assert _elementwise_binary(operator.truediv, 1, None) is None
        assert _elementwise_binary(operator.sub, None, None) is None


class TestSwitchCaseMatchHelper:
    def test_boolean_switch(self) -> None:
        assert _switch_case_matches(False, None, True) is True
        assert _switch_case_matches(False, None, False) is False
        assert _switch_case_matches(False, None, 1) is True

    def test_subject_na_only_matches_na(self) -> None:
        assert _switch_case_matches(True, None, None) is True
        assert _switch_case_matches(True, None, 1) is False
        assert _switch_case_matches(True, None, True) is False

    def test_subject_equality(self) -> None:
        assert _switch_case_matches(True, 0, 0) is True
        assert _switch_case_matches(True, False, False) is True
        assert _switch_case_matches(True, "b", "b") is True
        assert _switch_case_matches(True, "b", "a") is False


class TestPeriodOrNone:
    @staticmethod
    def _err(msg: str) -> None:
        raise ValueError(msg)

    def test_int_fast(self) -> None:
        assert pine_period_or_none(14, "p", self._err) == 14

    def test_na_and_nan(self) -> None:
        assert pine_period_or_none(None, "p", self._err) is None
        assert pine_period_or_none(float("nan"), "p", self._err) is None

    def test_identifier_string_soft(self) -> None:
        assert pine_period_or_none("length", "p", self._err) is None
        assert pine_period_or_none("rsiLen", "p", self._err) is None
        assert pine_period_or_none("", "p", self._err) is None

    def test_numeric_string(self) -> None:
        assert pine_period_or_none("14", "p", self._err) == 14
        assert pine_period_or_none(" 14.0 ", "p", self._err) == 14

    def test_nan_inf_strings_soft(self) -> None:
        assert pine_period_or_none("nan", "p", self._err) is None
        assert pine_period_or_none("inf", "p", self._err) is None

    def test_list_last_sample(self) -> None:
        assert pine_period_or_none([None, 20], "p", self._err) == 20
        assert pine_period_or_none([None], "p", self._err) is None


# ---------------------------------------------------------------------------
# Runtime goldens (interpret)
# ---------------------------------------------------------------------------


class TestRuntimeSwitchNa:
    def test_switch_subject_na_takes_default(self) -> None:
        src = """//@version=5
indicator("t")
x = switch na
    1 => 10
    2 => 20
    => 99
plot(x)
"""
        assert _last_plot(_run(src)) == 99

    def test_switch_float_na_matches_na_arm(self) -> None:
        src = """//@version=5
indicator("t")
x = switch float(na)
    na => 1
    1.0 => 2
    => 3
plot(x)
"""
        assert _last_plot(_run(src)) == 1

    def test_switch_subject_zero_not_bool_mode(self) -> None:
        src = """//@version=5
indicator("t")
x = switch 0
    0 => 5
    1 => 6
    => 7
plot(x)
"""
        assert _last_plot(_run(src)) == 5

    def test_switch_boolean_form(self) -> None:
        src = """//@version=5
indicator("t")
x = switch
    false => 1
    true => 2
    => 3
plot(x)
"""
        assert _last_plot(_run(src)) == 2

    def test_switch_false_subject(self) -> None:
        src = """//@version=5
indicator("t")
x = switch false
    true => 1
    false => 2
    => 3
plot(x)
"""
        assert _last_plot(_run(src)) == 2


class TestRuntimeIfBlock:
    def test_if_expr_basic(self) -> None:
        src = """//@version=5
indicator("t")
x = if close >= open
    1
else
    0
plot(x)
"""
        assert _last_plot(_run(src)) in (0, 1)

    def test_if_na_test_takes_else(self) -> None:
        src = """//@version=5
indicator("t")
x = if na
    1
else
    2
plot(x)
"""
        assert _last_plot(_run(src)) == 2

    def test_if_trailing_assign_returns_value(self) -> None:
        """Last statement assign yields assigned value (UDF/if convention)."""
        src = """//@version=5
indicator("t")
x = if true
    1
    y = 2
plot(x)
"""
        assert _last_plot(_run(src)) == 2

    def test_nested_if_expr(self) -> None:
        src = """//@version=5
indicator("t")
x = if true
    if true
        42
plot(nz(x, -1))
"""
        assert _last_plot(_run(src)) == 42


class TestRuntimeSoftConcatAndNaArith:
    def test_str_plus_number_runtime(self) -> None:
        src = """//@version=5
indicator("t")
s = "ISIN: " + 12.5
plot(str.length(s))
"""
        assert int(_last_plot(_run(src))) == len("ISIN: 12.5")

    def test_str_plus_bool_runtime(self) -> None:
        src = """//@version=5
indicator("t")
s = "flag=" + true
plot(str.length(s))
"""
        assert int(_last_plot(_run(src))) == len("flag=true")

    def test_str_plus_na_is_na(self) -> None:
        src = """//@version=5
indicator("t")
s = "x" + na
plot(na(s) ? 1 : 0)
"""
        assert _last_plot(_run(src)) == 1

    def test_na_arithmetic_runtime(self) -> None:
        src = """//@version=5
indicator("t")
a = close + na
b = na * 2.0
c = 1.0 / na
plot(nz(a, 0) + nz(b, 0) + nz(c, 0))
"""
        assert _last_plot(_run(src)) == 0

    def test_warmup_na_plus_scalar(self) -> None:
        src = """//@version=5
indicator("t")
v = ta.sma(close, 50)
plot(nz(v + 1.0, -1))
"""
        # With only 5 bars, SMA is na → nz → -1
        assert _last_plot(_run(src, _bars(5))) == -1


class TestRuntimePeriodOrNone:
    def test_ta_sma_na_length(self) -> None:
        src = """//@version=5
indicator("t")
length = na
plot(nz(ta.sma(close, length), 0))
"""
        assert _last_plot(_run(src)) == 0


class TestRuntimeUtilityBare:
    def test_year_month_timestamp(self) -> None:
        src = """//@version=5
indicator("t")
plot(year(timestamp(2020, 3, 15, 0, 0)))
"""
        assert _last_plot(_run(src)) == 2020

    def test_offset_bare(self) -> None:
        src = """//@version=5
indicator("t")
plot(nz(offset(close, 1), 0))
"""
        r = _run(src, _bars(5))
        # bar 4 close=104.5; offset 1 → bar 3 close=103.5
        assert _last_plot(r) == pytest.approx(103.5)

    def test_timestamp_month_zero(self) -> None:
        src = """//@version=5
indicator("t")
plot(timestamp(2020, 0, 1, 0, 0) > 0 ? 1 : 0)
"""
        assert _last_plot(_run(src)) == 1
