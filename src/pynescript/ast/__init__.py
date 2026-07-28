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

"""Pine Script AST (Abstract Syntax Tree) manipulation module.

Core public API for parsing, analyzing, and transforming Pine Script code:

Key Functions:
- parse(source, filename, mode): Parse Pine Script source into AST
- dump(node, ...): Generate string representation of AST
- unparse(node): Convert AST back to source code
- literal_eval(node_or_string): Evaluate literal expressions
- walk(node): Depth-first traversal of AST nodes
- copy_location(new_node, old_node): Copy position info between nodes

Key Classes:
- All AST node classes (Script, FunctionDef, Assign, etc.)
- Error handling and visitors
"""

from __future__ import annotations

# ruff: noqa: F403
from .error import *
from .helper import *
from .node import *
from .transformer import *
from .visitor import *
