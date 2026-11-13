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

"""Code lens — actionable context on the script declaration.

One lens row above ``indicator(...)`` / ``strategy(...)`` / ``library(...)``:

- **Convert to v6** when the buffer is not already v6 (client command
  ``pynescript.convertToV6``).
- **Smoke /run** when the editor reports Pro enabled (client command
  ``pynescript.runOnPro``).

Lenses are deliberately client-command based: the server does not execute them,
so other LSP clients can ignore a command they do not register.
"""

from __future__ import annotations

import re

from typing import Any

from lsprotocol import types as lsp

from pynescript.ast import NodeVisitor
from pynescript.ast import node as ast
from pynescript.langserver.analysis import ensure_symbol_index
from pynescript.langserver.features._ranges import node_to_range
from pynescript.util.pine_convert import detect_version


_DECLARATIONS = frozenset({"indicator", "strategy", "library"})
_DECLARATION_RE = re.compile(r"^\s*(indicator|strategy|library)\s*\(")
COMMAND_CONVERT_V6 = "pynescript.convertToV6"
COMMAND_SMOKE_RUN = "pynescript.runOnPro"


class _DeclarationCollector(NodeVisitor):
    """Collect top-level script declaration calls, not function bodies."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[ast.Call] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Script declarations inside a user function are not the header."""
        return

    def visit_Call(self, node: ast.Call) -> None:
        """Record ``indicator`` / ``strategy`` / ``library`` calls."""
        func = node.func
        if isinstance(func, ast.Name) and (func.id or "") in _DECLARATIONS:
            self.calls.append(node)


def handle_code_lens(
    params: lsp.CodeLensParams,
    source: str | None,
    uri: str,
    tree: Any | None = ...,
    *,
    analysis: Any | None = None,
    pro_enabled: bool = False,
) -> list[lsp.CodeLens]:
    """Return script-header code lenses for *source*.

    Falls back to a line scan when the buffer does not parse (the header is
    usually intact while the user is mid-edit below it).
    """
    if not source:
        return []
    index = ensure_symbol_index(source, tree, analysis)
    ranges: list[lsp.Range] = []
    if index is not None:
        collector = _DeclarationCollector()
        collector.visit(index.tree)
        for call in collector.calls:
            rng = node_to_range(call)
            if rng is not None:
                ranges.append(rng)
    else:
        ranges = _scan_declaration_ranges(source)

    version = detect_version(source)
    lenses: list[lsp.CodeLens] = []
    for rng in ranges:
        if version != 6:
            lenses.append(
                lsp.CodeLens(
                    range=rng,
                    command=lsp.Command(
                        title="Convert to v6",
                        command=COMMAND_CONVERT_V6,
                    ),
                )
            )
        if pro_enabled:
            lenses.append(
                lsp.CodeLens(
                    range=rng,
                    command=lsp.Command(
                        title="Smoke /run",
                        command=COMMAND_SMOKE_RUN,
                    ),
                )
            )
    return lenses


def _scan_declaration_ranges(source: str) -> list[lsp.Range]:
    """Line-scan fallback for ``indicator`` / ``strategy`` / ``library``."""
    ranges: list[lsp.Range] = []
    for line_index, line in enumerate(source.split("\n")):
        match = _DECLARATION_RE.match(line)
        if match is None:
            continue
        ranges.append(
            lsp.Range(
                start=lsp.Position(line=line_index, character=match.start(1)),
                end=lsp.Position(line=line_index, character=len(line)),
            )
        )
    return ranges
