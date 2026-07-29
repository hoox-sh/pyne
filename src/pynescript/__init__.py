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

"""PyneScript: Pine Script AST Parser and Code Generator.

A comprehensive Python library for parsing, analyzing, and manipulating
TradingView Pine Script code. Provides ANTLR-based parsing, AST manipulation,
evaluation, and code generation capabilities.

Main Entry Points:
  >>> from pynescript import parse, dump, unparse
  >>> ast = parse("plot(close)")  # Parse Pine Script
  >>> print(dump(ast))  # View AST structure
  >>> print(unparse(ast))  # Generate source code

Submodules:
- ast: Core AST parsing and manipulation
- ext: Extensions (Pygments lexer, Nautilus Trader integration)
- util: Utility functions
"""

from __future__ import annotations

from pynescript.__about__ import __version__


__all__ = ["__version__"]
