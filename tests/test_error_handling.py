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

"""Round 6 AGENT 08 — hardened Runtime / evaluator error handling regressions.

Covers:
- Classified error payloads (error_kind / error_type / error_bar)
- Body TypeError no longer soft-fails to empty/na in the bar loop
- runtime.error surfaces as runtime kind
- request.* still soft-fails to mock data when no feed is wired
- Parse failures are parse-kind, not silent success
"""

from __future__ import annotations

import pytest

from backend.runtime import ERROR_KIND_PARSE
from backend.runtime import ERROR_KIND_RUNTIME
from backend.runtime import Runtime
from tests.fixtures.parity.ohlcv import OHLCV


def _bars(n: int = 10) -> list[dict]:
    return list(OHLCV[:n]) if len(OHLCV) >= n else list(OHLCV)


class TestRuntimeErrorClassification:
    def test_parse_error_kind(self) -> None:
        rt = Runtime()
        # Unclosed string / garbage → parser raises
        out = rt.run("indicator('x')\nplot(close\n", _bars(), mode="interpret")
        assert "error" in out
        assert out.get("error_kind") == ERROR_KIND_PARSE
        assert "Parse Error" in out["error"]
        # Must not look like a successful empty plot run
        assert "plots" not in out or out.get("error")

    def test_unknown_mode_kind(self) -> None:
        rt = Runtime()
        out = rt.run("indicator('x')\nplot(close)", _bars(), mode="not_a_mode")
        assert out.get("error_kind") == "mode"
        assert "Unknown mode" in out["error"]

    def test_runtime_error_builtin_classified(self) -> None:
        src = """
//@version=5
indicator("err")
runtime.error("halted by design")
plot(close)
"""
        rt = Runtime()
        out = rt.run(src, _bars(), mode="interpret")
        assert "error" in out
        assert out.get("error_kind") == ERROR_KIND_RUNTIME
        assert out.get("error_type") == "RuntimeError"
        assert out.get("error_bar") == 0
        assert "halted by design" in out["error"]
        assert "index 0" in out["error"]

    def test_unknown_builtin_fail_closed(self) -> None:
        src = """
//@version=5
indicator("missing")
plot(totally_not_a_builtin_xyz(close))
"""
        rt = Runtime()
        out = rt.run(src, _bars(), mode="interpret")
        assert "error" in out
        assert out.get("error_kind") == ERROR_KIND_RUNTIME
        assert "plots" not in out or out.get("error")
        assert "Unknown built-in" in out["error"] or "error" in out["error"].lower()


class TestBodyTypeErrorFailClosed:
    """TypeError raised *inside* a callable must surface, not become silent na."""

    def test_python_udf_body_typeerror_surfaces(self) -> None:
        # Pine arithmetic soft-maps many bad ops to ``na``; this pins the call
        # dispatch path: body TypeError propagates, signature mismatch → None.
        from pynescript.ast.evaluator import NodeLiteralEvaluator
        from pynescript.ast.helper import parse

        def boom(a: object) -> object:
            return a + "x"  # type: ignore[operator]

        def wrong_arity(a: object, b: object) -> object:
            return a  # type: ignore[return-value]

        ev = NodeLiteralEvaluator()
        ev.context["boom"] = boom
        ev.context["wrong_arity"] = wrong_arity

        with pytest.raises(TypeError):
            ev.visit(parse("boom(1)", mode="eval").body)

        # Signature mismatch still soft-fails to na (overload / extension path)
        assert ev.visit(parse("wrong_arity(1)", mode="eval").body) is None

    def test_array_arg_error_surfaces_via_runtime(self) -> None:
        # ValueError from array.get must fail closed (classified runtime error).
        src = """
//@version=5
indicator("arr err")
f() =>
    a = array.from(1.0, 2.0)
    array.get(a, a)
plot(f())
"""
        rt = Runtime()
        out = rt.run(src, _bars(), mode="interpret")
        assert "error" in out, f"expected fail-closed, got success: {list(out.keys())}"
        assert out.get("error_kind") == ERROR_KIND_RUNTIME
        assert out.get("error_type") == "ValueError"
        assert "plots" not in out

    def test_happy_path_still_ok(self) -> None:
        src = """
//@version=5
indicator("ok")
plot(close)
"""
        rt = Runtime()
        out = rt.run(src, _bars(), mode="interpret")
        assert "error" not in out, out.get("error")
        assert out.get("count", 0) > 0


class TestRequestSoftFailPreserved:
    def test_request_security_without_feed_returns_mock(self) -> None:
        """Missing mock data / feed must soft-fail (not hard error)."""
        src = """
//@version=5
indicator("req")
v = request.security("UNKNOWN_SYM_XYZ", "D", close)
plot(v)
"""
        rt = Runtime()
        out = rt.run(src, _bars(), mode="interpret")
        assert "error" not in out, out.get("error")
        series = out.get("series") or {}
        # Some plot title present with non-empty values (mock prices)
        assert series or out.get("plots")


class TestTypeErrorHelper:
    def test_type_error_from_callee_detection(self) -> None:
        from pynescript.ast.evaluator.expressions import _type_error_from_callee

        def outer_sig():
            def inner(a, b):
                return a + b

            try:
                inner(1)  # wrong arity — signature TypeError
            except TypeError as e:
                return _type_error_from_callee(e)
            return None

        def outer_body():
            def inner(a):
                return a + "x"  # body TypeError

            try:
                inner(1)
            except TypeError as e:
                return _type_error_from_callee(e)
            return None

        assert outer_sig() is False
        assert outer_body() is True


class TestStrategyDeclarationFailClosed:
    def test_bad_initial_capital_surfaces(self) -> None:
        # strategy() with non-numeric initial_capital → float() ValueError
        # must not soft-swallow and leave StrategyState misconfigured.
        src = """
//@version=5
strategy("bad cap", overlay=true, initial_capital="not_a_number")
strategy.entry("L", strategy.long)
plot(close)
"""
        rt = Runtime()
        out = rt.run(src, _bars(), mode="interpret")
        assert "error" in out, f"expected fail-closed on bad capital, got: {list(out.keys())}"
        assert out.get("error_kind") == ERROR_KIND_RUNTIME
        assert out.get("error_type") in ("ValueError", "TypeError")
