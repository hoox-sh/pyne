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
