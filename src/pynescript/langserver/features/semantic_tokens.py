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

"""Basic semantic tokens provider (stub + partial implementation).

Marks builtins, keywords, etc. for better syntax highlighting in supporting editors.
"""

from __future__ import annotations

import lsprotocol.types as lsp

from pynescript.ast import helper as ast_helper


def handle_semantic_tokens(
    params: lsp.SemanticTokensParams,
    source: str | None,
) -> lsp.SemanticTokens | None:
    """Handle textDocument/semanticTokens/full request.

    Returns a simple token list. Full implementation would use a proper
    visitor to produce delta tokens etc.
    """
    if not source:
        return lsp.SemanticTokens(data=[])

    try:
        tree = ast_helper.parse(source)
    except Exception:
        return lsp.SemanticTokens(data=[])

    # Very basic: for now return empty. Real version would walk and emit
    # (line, col, len, token_type, modifiers) encoded.
    # This at least registers the capability without crashing.
    return lsp.SemanticTokens(data=[])
