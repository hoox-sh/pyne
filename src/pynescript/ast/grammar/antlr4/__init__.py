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

"""ANTLR4 Lexer, Parser, and Infrastructure.

Components:
- lexer: PinescriptLexer - tokenizes Pine Script source code
- parser: PinescriptParser - builds parse trees from tokens
- visitor: PinescriptParserVisitor - traverses parse trees
- listener: PinescriptParserListener - event-based parse tree traversal
- error_listener: PinescriptErrorListener - custom error handling
- generated: Auto-generated ANTLR files (do not edit manually)
"""

from __future__ import annotations
