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

"""Syntax errors raised by the Pine Script parser and related tools.

:func:`pynescript.ast.helper.parse` raises :class:`SyntaxError` (this module's
class, not :class:`builtins.SyntaxError`) when lexing or parsing fails. The
exception carries optional :class:`SyntaxErrorDetails` and formats a caret
under the offending source line in ``str(exc)``.

These names intentionally mirror the stdlib for familiarity; import from
``pynescript.ast.error`` (or the package re-export) to avoid shadowing.
"""

from __future__ import annotations

from io import StringIO
from typing import NamedTuple


class SyntaxErrorDetails(NamedTuple):
    """Location payload for a :class:`SyntaxError`.

    Attributes:
        filename: Source path or label (e.g. ``"<unknown>"``).
        lineno: 1-based line number.
        offset: 0-based column of the error start.
        text: Full source line (or excerpt) containing the error.
        end_lineno: Optional 1-based end line for multi-line spans.
        end_offset: Optional 0-based end column.
    """

    filename: str
    lineno: int
    offset: int
    text: str
    end_lineno: int | None = None
    end_offset: int | None = None


class SyntaxError(Exception):  # noqa: A001
    """Pine Script syntax error with optional source location context.

    Attributes:
        message: Short error description.
        details: :class:`SyntaxErrorDetails` when location was provided.
    """

    def __init__(self, message: str, *details: SyntaxErrorDetails | object) -> None:
        """Create an error with *message* and optional location *details*.

        *details* may be a single :class:`SyntaxErrorDetails`, or the same
        fields unpacked (``filename, lineno, offset, text[, end_lineno, end_offset]``).
        """
        self.message = message
        if details:
            if len(details) == 1 and isinstance(details[0], SyntaxErrorDetails):
                self.details = details[0]
            else:
                self.details = SyntaxErrorDetails(*details)

    def __str__(self) -> str:
        """Human-readable message including file, line, and caret underline."""
        f = StringIO()
        code = self.details.text.lstrip()
        offset = self.details.offset + len(code) - len(self.details.text)
        f.write(self.message)
        f.write("\n")
        f.write(f'  File "{self.details.filename}", line {self.details.lineno}\n')
        f.write(f"    {code}")
        f.write("    ")
        f.write(" " * offset)
        f.write("^")
        return f.getvalue()


class IndentationError(SyntaxError):  # noqa: A001
    """Syntax error specifically about indentation (subclass of :class:`SyntaxError`)."""

    pass


__all__ = [
    "IndentationError",
    "SyntaxError",
    "SyntaxErrorDetails",
]
