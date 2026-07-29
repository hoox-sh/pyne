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

"""Server capability definitions.

Declares which LSP features the Pynescript Language Server supports.
"""

from __future__ import annotations

from typing import Any

from lsprotocol import types as lsp


def get_server_capabilities() -> lsp.ServerCapabilities:
    """Return the server capabilities declaration.

    This defines which LSP methods the server responds to.
    Update this as features are implemented.
    """
    return lsp.ServerCapabilities(
        text_document_sync=lsp.TextDocumentSyncOptions(
            open_close=True,
            change=lsp.TextDocumentSyncKind.Incremental,
            will_save=False,
            will_save_wait_until=False,
            save=lsp.SaveOptions(include_text=True),
        ),
        diagnostic_provider=lsp.DiagnosticOptions(
            identifier="pynescript-diagnostics",
            inter_file_dependencies=False,
            workspace_diagnostics=False,
        ),
        completion_provider=lsp.CompletionOptions(
            trigger_characters=["."],
            resolve_provider=True,
        ),
        hover_provider=True,
        definition_provider=True,
        references_provider=True,
        document_symbol_provider=lsp.DocumentSymbolOptions(
            work_done_progress=True,
        ),
        workspace_symbol_provider=lsp.WorkspaceSymbolOptions(
            work_done_progress=True,
        ),
        document_formatting_provider=True,
        document_range_formatting_provider=True,
        inlay_hint_provider=lsp.InlayHintOptions(
            resolve_provider=False,
        ),
        # Legend indices must match semantic_tokens.TOKEN_TYPES order.
        semantic_tokens_provider=lsp.SemanticTokensOptions(
            legend=lsp.SemanticTokensLegend(
                token_types=list(semantic_token_types()),
                token_modifiers=list(semantic_token_modifiers()),
            ),
            range=False,
            full=True,
        ),
        # signatureHelp / codeAction intentionally omitted until handlers exist.
    )


def semantic_token_types() -> tuple[str, ...]:
    """Token types advertised to clients (keep in sync with semantic_tokens.py)."""
    return (
        "namespace",
        "type",
        "class",
        "function",
        "method",
        "variable",
        "parameter",
        "property",
        "keyword",
        "string",
        "number",
        "operator",
        "comment",
    )


def semantic_token_modifiers() -> tuple[str, ...]:
    """Token modifiers advertised to clients."""
    return (
        "declaration",
        "definition",
        "readonly",
        "defaultLibrary",
    )


def get_filter_options() -> Any:
    """Return file filters for the language server."""
    return [
        {
            "language": "pinescript",
            "pattern": "**/*.pine",
        },
        {
            "language": "pinescript",
            "pattern": "**/*.pinev5",
        },
        {
            "language": "pinescript",
            "pattern": "**/*.pinev6",
        },
    ]
