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

"""Lightweight static checks for Pine Script source.

Public API:

* :class:`LintWarning` — one finding (code, message, location, severity)
* :class:`PineLinter` — stateful linter; call :meth:`PineLinter.lint`
* :func:`lint_script` / :func:`lint_file` — one-shot helpers

Rules are heuristic (regex + :func:`~pynescript.ast.helper.parse` for syntax).
This is not a full type checker; see :mod:`pynescript.ast.type_system` for
type modeling used by the evaluator.

Rule code prefixes: ``E`` errors, ``W`` warnings (version/deprecated), ``C`` style.
"""

from __future__ import annotations

import re

from dataclasses import dataclass

from pynescript.ast import parse


@dataclass
class LintWarning:
    """A single lint finding.

    Attributes:
        code: Stable rule id (e.g. ``E001``, ``W001``, ``C002``).
        message: Human-readable description.
        line: 1-based line if known.
        column: 0-based column if known.
        severity: ``"error"`` or ``"warning"`` (default).
    """

    code: str
    message: str
    line: int | None = None
    column: int | None = None
    severity: str = "warning"

    def __str__(self) -> str:
        location = f"line {self.line}" if self.line else "unknown location"
        return f"{self.severity}: [{self.code}] {self.message} at {location}"


class PineLinter:
    """Run built-in static analysis rules on Pine Script source.

    Each :meth:`lint` call resets :attr:`warnings` and returns the new list.
    Source is expected as a decoded Unicode string (UTF-8 when loaded from disk).
    """

    def __init__(self) -> None:
        """Create a linter with an empty :attr:`warnings` list."""
        self.warnings: list[LintWarning] = []

    def lint(self, source: str, filename: str = "<input>") -> list[LintWarning]:
        """Run all rules on *source* and return findings.

        Args:
            source: Full script text.
            filename: Label passed to the parser for syntax diagnostics.

        Returns:
            List of :class:`LintWarning` (also stored on :attr:`warnings`).
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
        """Append a :class:`LintWarning` to :attr:`warnings`."""
        self.warnings.append(LintWarning(code=code, message=message, line=line, column=column, severity=severity))

    def _check_syntax(self, source: str, filename: str) -> None:
        """Parse *source*; emit ``E001`` if :func:`~pynescript.ast.helper.parse` fails."""
        try:
            parse(source, filename)
        except Exception as e:
            line: int | None = None
            column: int | None = None
            # Prefer structured location from pynescript.ast.error.SyntaxError
            details = getattr(e, "details", None)
            if details is not None:
                lineno = getattr(details, "lineno", None)
                offset = getattr(details, "offset", None)
                if isinstance(lineno, int) and lineno > 0:
                    line = lineno
                if isinstance(offset, int) and offset >= 0:
                    column = offset
            if line is None:
                # Fallback: "line N" / "line: N" in the message
                match = re.search(r"line[:\s]+(\d+)", str(e), re.IGNORECASE)
                if match:
                    line = int(match.group(1))
            # Prefer the short .message when available (avoid caret dump in chips)
            msg = getattr(e, "message", None)
            if not isinstance(msg, str) or not msg.strip():
                msg = str(e).split("\n", 1)[0].strip() or str(e)
            self._add_warning(
                code="E001",
                message=f"Syntax error: {msg}",
                line=line,
                column=column,
                severity="error",
            )

    def _check_version(self, source: str) -> None:
        """Require ``//@version=…``; warn if version is below 5 (``W001``/``W002``)."""
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
                    line=source[: version_match.start()].count("\n") + 1,
                )

    def _check_deprecated(self, source: str) -> None:
        """Flag known deprecated call/init patterns (``W101``–``W103``)."""
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
        """Heuristic naming checks for ``ta.*`` assignments (``C001``)."""
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
        """Line length, if-style, and trailing-newline style rules (``C002``–``C004``)."""
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

        # Do not strip() before the check — strip removes the trailing newline.
        if source and not source.endswith("\n"):
            self._add_warning(
                code="C004",
                message="File should end with a newline",
            )


def _to_camel(name: str) -> str:
    """Convert snake_case *name* to camelCase for suggestion messages."""
    components = name.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


def lint_script(source: str, filename: str = "<input>") -> list[LintWarning]:
    """Lint a source string; convenience wrapper around :class:`PineLinter`.

    Args:
        source: Decoded Pine Script text.
        filename: Label for diagnostics.

    Returns:
        Findings from a fresh linter instance.
    """
    linter = PineLinter()
    return linter.lint(source, filename)


def lint_file(filepath: str) -> list[LintWarning]:
    """Lint a file read as UTF-8.

    Args:
        filepath: Path to a ``.pine`` (or other) source file.

    Returns:
        Findings; *filepath* is used as the diagnostic filename.
    """
    with open(filepath, encoding="utf-8") as f:
        source = f.read()

    return lint_script(source, filepath)
