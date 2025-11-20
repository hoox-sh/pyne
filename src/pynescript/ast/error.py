# Copyright 2024-2025 jango_blockchained
#
# Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.gnu.org/licenses/lgpl-3.0.en.html
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: LGPL-3.0-or-later

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
