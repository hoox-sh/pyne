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

"""Tests for Pine Script linter."""

from __future__ import annotations

from pynescript.ast.linter import lint_script


class TestPineLinter:
    """Test cases for PineLinter."""

    def test_no_issues(self) -> None:
        """Test clean code passes (allowing trailing newline warning)."""
        code = """//@version=5
indicator("Test")
plot(ta.sma(close, 14))

"""
        warnings = lint_script(code)
        codes = [w.code for w in warnings]
        assert "E001" not in codes
        assert "W001" not in codes
        assert "W002" not in codes

    def test_missing_version(self) -> None:
        """Test missing version warning."""
        code = 'indicator("Test")'
        warnings = lint_script(code)
        codes = [w.code for w in warnings]
        assert "W001" in codes

    def test_old_version(self) -> None:
        """Test old version warning."""
        code = """//@version=3
indicator("Test")
"""
        warnings = lint_script(code)
        codes = [w.code for w in warnings]
        assert "W002" in codes

    def test_long_line(self) -> None:
        """Test long line warning."""
        code = """//@version=5
indicator("Test")
plot(ta.sma(close, 14), title="This is a very very very very very very very very very very very very very very very very very very very very very long line")
"""
        warnings = lint_script(code)
        codes = [w.code for w in warnings]
        assert "C002" in codes

    def test_syntax_error(self) -> None:
        """Test syntax error detection."""
        code = """//@version=5
indicator("Test"
plot(close)
"""
        warnings = lint_script(code)
        codes = [w.code for w in warnings]
        assert "E001" in codes

    def test_naming_convention(self) -> None:
        """Test naming convention warning."""
        code = """//@version=5
indicator("Test")
sma_value = ta.sma(close, 14)
"""
        warnings = lint_script(code)
        codes = [w.code for w in warnings]
        assert "C001" in codes

    def test_multiple_warnings(self) -> None:
        """Test multiple warnings from different rules."""
        code = """//@version=3
indicator("Test")
sma_value = ta.sma(close, 14)
"""
        warnings = lint_script(code)
        codes = [w.code for w in warnings]
        assert "W002" in codes
        assert "C001" in codes


class TestRetiredRules:
    """Retired codes (C003, W102, W103) are never emitted — D-07."""

    def test_c003_retired_indented_if(self) -> None:
        """Indented ``if`` blocks — the old C003 trigger — are clean."""
        code = """//@version=6
indicator("Test")
if barstate.isfirst
    if close > open
        x = 1
"""
        assert "C003" not in [w.code for w in lint_script(code)]

    def test_c003_retired_single_line_if(self) -> None:
        """Even single-line ``if`` forms emit no C003 (Pine has no braces)."""
        code = """//@version=6
indicator("Test")
if close > open
    x = 1
"""
        assert "C003" not in [w.code for w in lint_script(code)]

    def test_w102_retired_histogram_plot(self) -> None:
        """Histogram-style plots are legitimate — no plotcandle nudge."""
        code = """//@version=6
indicator("Test")
plot(close, style=plot.style_histogram)
"""
        assert "W102" not in [w.code for w in lint_script(code)]

    def test_w103_retired_na_init(self) -> None:
        """``var int x = na`` is idiomatic — no coerce-to-0 nudge."""
        code = """//@version=6
indicator("Test")
var int x = na
"""
        assert "W103" not in [w.code for w in lint_script(code)]

    def test_retired_codes_absent_kitchen_sink(self) -> None:
        """No retired code on a script exercising all three old triggers."""
        code = """//@version=6
indicator("Test")
var int x = na
plot(close, style=plot.style_histogram)
if barstate.islast
    x := 1
"""
        codes = [w.code for w in lint_script(code)]
        assert "C003" not in codes
        assert "W102" not in codes
        assert "W103" not in codes
