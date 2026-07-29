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

"""LSP feature handlers (one module per capability area).

Each submodule exposes public ``handle_*`` functions that the server wires in
:meth:`~pynescript.langserver.server.PynescriptLanguageServer.setup_method_handlers`.
Handlers take lsprotocol params plus document source (and URI when needed);
they do not talk to pygls directly.

Modules:

- :mod:`.completion` — ``textDocument/completion``, ``completionItem/resolve``
- :mod:`.hover` — ``textDocument/hover``
- :mod:`.diagnostics` — lint → LSP diagnostic conversion helpers
- :mod:`.formatting` — ``textDocument/formatting``, ``rangeFormatting``
- :mod:`.definitions` — ``textDocument/definition``
- :mod:`.references` — ``textDocument/references``
- :mod:`.symbols` — ``textDocument/documentSymbol``
- :mod:`.semantic_tokens` — ``textDocument/semanticTokens/full``
- :mod:`.inlay_hints` — ``textDocument/inlayHint``

This package re-exports :mod:`.diagnostics` for convenience; other features are
imported by name from :mod:`pynescript.langserver.server`.
"""

from __future__ import annotations

from pynescript.langserver.features import diagnostics

__all__ = ["diagnostics"]
