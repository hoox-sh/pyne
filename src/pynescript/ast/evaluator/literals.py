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

"""Literal evaluation: constants and tuple/list-like constructors.

Pine **na** appears as a :class:`~pynescript.ast.node.Constant` whose
``value`` is Python ``None``. Color hex literals use ``kind="#"``; other
kinds are rejected.
"""

from __future__ import annotations

from typing import Any

from pynescript.ast import node as ast


class LiteralEvaluator:
    """Mixin: evaluate ``Constant`` and ``Tuple`` AST nodes to Python values."""

    def visit_Constant(self, node: ast.Constant):
        """Return the stored literal (numbers, strings, bools, ``None``/na, colors).

        Args:
            node: Constant with ``value`` and optional ``kind``

        Returns:
            The Python value (``None`` means Pine na)

        Raises:
            ValueError: If ``kind`` is set to anything other than ``"#"`` (color)
        """
        # Hot path: plain numeric / bool / str / None literals have kind=None.
        kind = node.kind
        if kind is None:
            return node.value
        # Allow color literals (kind="#")
        if kind != "#":
            msg = f"unexpected constant kind: {kind!s}"
            raise ValueError(msg)
        return node.value

    def visit_Tuple(self, node: ast.Tuple) -> Any:
        """Evaluate each element; return a **list** (mutable Pine sequences).

        Args:
            node: Tuple with ``elts``

        Returns:
            List of evaluated elements (not a Python ``tuple``)
        """
        # Evaluate each element in the tuple and return as a list
        # (PineScript uses lists for dynamic sequences)
        return [self.visit(elt) for elt in node.elts]  # type: ignore[attr-defined]
