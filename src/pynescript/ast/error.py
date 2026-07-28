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

"""Pine Script Syntax Error Reporting.

Custom exception classes with source code context for helpful error messages.
Includes line/column information and visual indicators of error location.
"""

from __future__ import annotations

from io import StringIO
from typing import NamedTuple


class SyntaxErrorDetails(NamedTuple):
    """Detailed information about a syntax error location.

    Attributes:
        filename: Path to the file where error occurred
        lineno: Line number (1-indexed)
        offset: Column offset (0-indexed)
        text: The source code line
        end_lineno: End line number (for multi-line errors)
        end_offset: End column offset
    """
    filename: str
    lineno: int
    offset: int
    text: str
    end_lineno: int | None = None
    end_offset: int | None = None


class SyntaxError(Exception):  # noqa: A001
    """Pine Script syntax error with source code context.

    Provides detailed error reporting with line/column information
    and visual indicators of the error location.
    """

    def __init__(self, message: str, *details):
        """Initialize syntax error with message and optional location details.

        Args:
            message: Error message
            *details: Either a SyntaxErrorDetails tuple or individual components
                     (filename, lineno, offset, text, end_lineno, end_offset)
        """
        self.message = message
        if details:
            if len(details) == 1 and isinstance(details[0], SyntaxErrorDetails):
                self.details = details[0]
            else:
                self.details = SyntaxErrorDetails(*details)

    def __str__(self):
        """Generate formatted error message with source code excerpt."""
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
    """Indentation-related syntax error in Pine Script."""
    pass


__all__ = [
    "IndentationError",
    "SyntaxError",
    "SyntaxErrorDetails",
]
