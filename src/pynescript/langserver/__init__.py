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

"""Pine Script Language Server Protocol (LSP) package.

pygls-based server for editors (VS Code extension, Neovim, Zed, etc.).

**How to start**

- Console script: ``pynescript-lsp`` → :func:`pynescript.langserver.__main__.main`
- Module: ``python -m pynescript.langserver`` (stdio by default)

**Public re-exports**

- :class:`~pynescript.langserver.server.PynescriptLanguageServer` — server class
- :class:`~pynescript.langserver.workspace.Workspace` — open-document store
- :class:`~pynescript.langserver.workspace.TextDocumentState` — per-URI state

**Layout**

- :mod:`pynescript.langserver.server` — method registration / lifecycle
- :mod:`pynescript.langserver.config` — advertised capabilities + token legend
- :mod:`pynescript.langserver.workspace` — parse/lint cache for open docs
- :mod:`pynescript.langserver.features` — request handlers (completion, hover, …)
- :mod:`pynescript.langserver.providers` — builtin metadata + completion items

Requires the ``[lsp]`` extra (``pygls``, ``lsprotocol``). Server identity
``version`` uses :data:`pynescript.__version__` from :mod:`pynescript.__about__`;
the module-level ``__version__`` below is a package-local constant for the
langserver subpackage only.
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
