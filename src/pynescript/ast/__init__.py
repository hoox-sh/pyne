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

"""Pine Script abstract syntax tree package.

Parse source, walk or rewrite trees, dump/unparse, and handle syntax errors.

Re-exported public surface
--------------------------
From :mod:`pynescript.ast.helper` (see that module for full contracts):

* :func:`parse` — ``str`` source → :class:`~pynescript.ast.node.Script` /
  :class:`~pynescript.ast.node.Expression` (``mode`` ``"exec"`` / ``"eval"``)
* :func:`unparse` — AST → Pine source (semantic round-trip, not byte-identical)
* :func:`dump`, :func:`literal_eval`, :func:`walk`
* :func:`iter_fields`, :func:`iter_child_nodes`
* :func:`copy_location`, :func:`fix_missing_locations`, :func:`increment_lineno`
* :func:`get_source_segment`

From :mod:`pynescript.ast.node`: all ASDL node types (``AST``, ``Script``, …).

From :mod:`pynescript.ast.error`: :class:`SyntaxError`, :class:`IndentationError`,
:class:`SyntaxErrorDetails` (raised by :func:`parse` on invalid syntax).

From :mod:`pynescript.ast.visitor` / :mod:`pynescript.ast.transformer`:
:class:`NodeVisitor`, :class:`NodeTransformer`.

Related modules (import directly; not star-exported here)
---------------------------------------------------------
* :mod:`pynescript.ast.linter` — :func:`~pynescript.ast.linter.lint_script`, etc.
* :mod:`pynescript.ast.type_system` — Pine type modeling for the evaluator
* :mod:`pynescript.ast.collector` — :class:`~pynescript.ast.collector.StatementCollector`
* :mod:`pynescript.ast.evaluator` — runtime evaluation

Encoding: pass Unicode ``str`` to :func:`parse` (decode files as UTF-8).
"""

from __future__ import annotations

# ruff: noqa: F403
from .error import *
from .helper import *
from .node import *
from .transformer import *
from .visitor import *
