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

"""Pine Script AST node types (ASDL-generated, re-exported).

All concrete node classes live in
:mod:`pynescript.ast.grammar.asdl.generated.PinescriptASTNode` and are
re-exported here so callers can use ``from pynescript.ast.node import …``
or ``from pynescript.ast import node as ast``.

Base contract
-------------
* :class:`AST` — root base; every node has class-level ``_fields`` (child /
  data field names) and ``_attributes`` (location metadata when present).
* Statement/expression nodes typically carry ``lineno``, ``col_offset``,
  ``end_lineno``, ``end_col_offset`` (1-based lines; 0-based byte columns).
* Nodes are dataclasses; construct with keyword field values as needed.

Main kinds (non-exhaustive)
---------------------------
* Modules: ``Script`` (exec root), ``Expression`` (eval root)
* Definitions: ``FunctionDef`` (optional ``returns`` type spec), ``TypeDef``, ``EnumDef``
* Statements: ``Assign``, ``ReAssign``, ``AugAssign``, ``Import``, ``Expr``,
  ``Break``, ``Continue``
* Control / blocks (as expressions in Pine): ``If``, ``While``, ``ForTo``,
  ``ForIn``, ``Switch``, ``Once``, ``Case``
* Expressions: ``BinOp``, ``UnaryOp``, ``BoolOp``, ``Compare``, ``Conditional``,
  ``Call``, ``Attribute``, ``Subscript``, ``Name``, ``Constant``, ``Tuple``, …
* Type markers: ``Qualify``, ``Specialize``; qualifiers ``Const``, ``Input``,
  ``Simple``, ``Series``; decl modes ``Var``, ``VarIp``

Do not edit the generated module under ``grammar/asdl/generated/`` by hand;
regenerate from the ASDL resource when the grammar changes.
"""

from __future__ import annotations

from .grammar.asdl.generated import *  # noqa: F403
