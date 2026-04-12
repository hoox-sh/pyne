# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

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
