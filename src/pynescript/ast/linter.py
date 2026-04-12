# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

"""Pine Script Linter - Static analysis and validation."""

from __future__ import annotations

import re

from dataclasses import dataclass

from pynescript.ast import parse


@dataclass
class LintWarning:
    """A lint warning or error found in Pine Script code."""

    code: str
    message: str
    line: int | None = None
    column: int | None = None
    severity: str = "warning"

    def __str__(self) -> str:
        location = f"line {self.line}" if self.line else "unknown location"
        return f"{self.severity}: [{self.code}] {self.message} at {location}"


class PineLinter:
    """Linter for Pine Script code with static analysis rules."""

    def __init__(self) -> None:
        self.warnings: list[LintWarning] = []

    def lint(self, source: str, filename: str = "<input>") -> list[LintWarning]:
        """Run all linting rules on Pine Script source.

        Args:
            source: Pine Script source code
            filename: Name of the file being linted (for error messages)

        Returns:
            List of lint warnings found
        """
        self.warnings = []

        self._check_syntax(source, filename)
        self._check_version(source)
        self._check_deprecated(source)
        self._check_naming(source)
        self._check_style(source)

        return self.warnings

    def _add_warning(
        self,
        code: str,
        message: str,
        line: int | None = None,
        column: int | None = None,
        severity: str = "warning",
    ) -> None:
        """Add a lint warning."""
        self.warnings.append(LintWarning(code=code, message=message, line=line, column=column, severity=severity))

    def _check_syntax(self, source: str, filename: str) -> None:
        """Check for syntax errors by parsing."""
        try:
            parse(source, filename)
        except Exception as e:
            self._add_warning(
                code="E001",
                message=f"Syntax error: {e}",
                severity="error",
            )

    def _check_version(self, source: str) -> None:
        """Check version declaration."""
        version_match = re.search(r"//\s*@version\s*=\s*(\d+)", source)
        if not version_match:
            self._add_warning(
                code="W001",
                message="Missing @version declaration. Add '//@version=5' at the top.",
                line=1,
            )
        else:
            version = int(version_match.group(1))
            if version < 5:
                self._add_warning(
                    code="W002",
                    message=f"Pine Script v{version} is deprecated. Consider upgrading to v5 or v6.",
                    line=version_match.start(),
                )

    def _check_deprecated(self, source: str) -> None:
        """Check for deprecated patterns."""
        deprecated_patterns = [
            (r"\bsecurity\s*\(\s*'[A-Z]+:[A-Z]+'", "W101", "Use request.security() with explicit parameters"),
            (r"plot\(.*style=plot\.style_histogram", "W102", "Consider using plotcandle for better visualization"),
            (r"var\s+int\s+\w+\s*=\s*na", "W103", "Initialize with 0 instead of na for better type safety"),
        ]

        for pattern, code, message in deprecated_patterns:
            for match in re.finditer(pattern, source, re.IGNORECASE):
                line_num = source[: match.start()].count("\n") + 1
                self._add_warning(code, message, line=line_num)

    def _check_naming(self, source: str) -> None:
        """Check naming conventions."""
        lines = source.split("\n")
        for i, line in enumerate(lines, 1):
            if match := re.search(r"(\w+)\s*=\s*ta\.", line):
                var_name = match.group(1)
                if re.match(r"^[a-z]", var_name):
                    self._add_warning(
                        code="C001",
                        message=f"Variable '{var_name}' should use camelCase (e.g., '{_to_camel(var_name)}')",
                        line=i,
                    )

    def _check_style(self, source: str) -> None:
        """Check style guidelines."""
        lines = source.split("\n")
        for i, line in enumerate(lines, 1):
            if len(line.rstrip()) > 120:
                self._add_warning(
                    code="C002",
                    message=f"Line exceeds 120 characters ({len(line.rstrip())})",
                    line=i,
                )

            if re.match(r"^\s+if\s+", line):
                self._add_warning(
                    code="C003",
                    message="Avoid single-line if statements without braces",
                    line=i,
                )

        if not source.strip().endswith("\n"):
            self._add_warning(
                code="C004",
                message="File should end with a newline",
            )


def _to_camel(name: str) -> str:
    """Convert snake_case to camelCase."""
    components = name.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


def lint_script(source: str, filename: str = "<input>") -> list[LintWarning]:
    """Convenience function to lint Pine Script source.

    Args:
        source: Pine Script source code
        filename: Name of the file being linted

    Returns:
        List of lint warnings found
    """
    linter = PineLinter()
    return linter.lint(source, filename)


def lint_file(filepath: str) -> list[LintWarning]:
    """Lint a Pine Script file.

    Args:
        filepath: Path to the Pine Script file

    Returns:
        List of lint warnings found
    """
    with open(filepath, encoding="utf-8") as f:
        source = f.read()

    return lint_script(source, filepath)
