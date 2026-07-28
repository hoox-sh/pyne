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

"""Pynescript Language Server.

Provides Language Server Protocol (LSP) support for Pine Script,
enabling professional IDE integration in VS Code, Neovim, Zed, and more.

Usage:
    python -m pynescript.langserver
    pynescript lsp
"""

from __future__ import annotations

from pynescript.langserver.server import PynescriptLanguageServer
from pynescript.langserver.workspace import TextDocumentState
from pynescript.langserver.workspace import Workspace


__version__ = "0.1.0"
__all__ = [
    "PynescriptLanguageServer",
    "TextDocumentState",
    "Workspace",
]
