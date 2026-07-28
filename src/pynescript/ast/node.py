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

"""AST Node Class Definitions.

Auto-generated ASDL-based node classes for the Pine Script Abstract Syntax Tree.
Each node type represents a language construct:

- Script: Root module node
- FunctionDef/TypeDef/EnumDef: Definitions
- Assign/AugAssign/Return: Statements
- If/While/For: Control flow
- BinOp/UnaryOp/Compare: Expressions
- Call/Subscript/Attribute: Member access
- Constant/Name/Tuple: Literals and names
"""

from __future__ import annotations

from .grammar.asdl.generated import *  # noqa: F403
