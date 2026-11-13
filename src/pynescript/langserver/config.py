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

"""Advertised LSP server capabilities and semantic-token legend.

:func:`get_server_capabilities` mirrors the providers this server implements.
pygls 2 does **not** send that object on the wire: after the user
``initialize`` handler returns, it rebuilds ``ServerCapabilities`` from
registered feature options. Semantic tokens are omitted unless the
``textDocument/semanticTokens/*`` handlers are registered with a
:class:`~lsprotocol.types.SemanticTokensLegend` (see
:func:`semantic_tokens_legend`). Code actions expose Convert-to-v6 and the
W001 QuickFix.

Semantic token type/modifier order in :func:`semantic_token_types` /
:func:`semantic_token_modifiers` **must** stay aligned with indices used by
:mod:`pynescript.langserver.features.semantic_tokens`.
"""

from __future__ import annotations

from typing import Any

from lsprotocol import types as lsp


def get_server_capabilities() -> lsp.ServerCapabilities:
    """Return :class:`lsprotocol.types.ServerCapabilities` for ``initialize``.

    Sync mode is incremental open/close/change with save text. Completion
    triggers on ``.`` with resolve. Semantic tokens: full and range.
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
            workspace_diagnostics=True,
        ),
        completion_provider=lsp.CompletionOptions(
            trigger_characters=["."],
            resolve_provider=True,
        ),
        hover_provider=True,
        signature_help_provider=lsp.SignatureHelpOptions(
            trigger_characters=["(", ","],
            retrigger_characters=[","],
        ),
        definition_provider=True,
        declaration_provider=True,
        type_definition_provider=True,
        call_hierarchy_provider=lsp.CallHierarchyOptions(),
        code_lens_provider=lsp.CodeLensOptions(resolve_provider=False),
        inline_completion_provider=True,
        references_provider=True,
        document_highlight_provider=True,
        linked_editing_range_provider=True,
        rename_provider=lsp.RenameOptions(
            prepare_provider=True,
        ),
        document_symbol_provider=lsp.DocumentSymbolOptions(
            work_done_progress=True,
        ),
        workspace_symbol_provider=lsp.WorkspaceSymbolOptions(
            work_done_progress=True,
        ),
        document_formatting_provider=True,
        document_range_formatting_provider=True,
        document_on_type_formatting_provider=lsp.DocumentOnTypeFormattingOptions(
            first_trigger_character="\n",
        ),
        folding_range_provider=True,
        selection_range_provider=True,
        color_provider=True,
        document_link_provider=lsp.DocumentLinkOptions(
            resolve_provider=True,
        ),
        code_action_provider=lsp.CodeActionOptions(
            code_action_kinds=[
                lsp.CodeActionKind.QuickFix,
                lsp.CodeActionKind.RefactorRewrite,
            ],
        ),
        execute_command_provider=lsp.ExecuteCommandOptions(
            commands=["pynescript.convertToV6"],
        ),
        inlay_hint_provider=lsp.InlayHintOptions(
            resolve_provider=False,
        ),
        # Kept in sync with the legend passed to the semantic-token feature
        # registrations. pygls rebuilds the wire capability from that legend.
        semantic_tokens_provider=lsp.SemanticTokensOptions(
            legend=semantic_tokens_legend(),
            range=True,
            full=True,
        ),
        workspace=lsp.WorkspaceOptions(
            workspace_folders=lsp.WorkspaceFoldersServerCapabilities(
                supported=True,
                change_notifications=False,
            ),
        ),
    )


def semantic_tokens_legend() -> lsp.SemanticTokensLegend:
    """Legend passed as the semantic-token feature options.

    pygls 2 treats this object (not :class:`~lsprotocol.types.SemanticTokensOptions`)
    as the registration options for ``textDocument/semanticTokens/full``,
    ``/full/delta``, and ``/range``. It then advertises
    ``semanticTokensProvider`` with this legend and sets ``full`` / ``range``
    from which of those methods are registered. Registering the handlers
    without this legend drops the capability from ``initialize``.
    """
    return lsp.SemanticTokensLegend(
        token_types=list(semantic_token_types()),
        token_modifiers=list(semantic_token_modifiers()),
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
        # Custom types contributed by the VS Code extension (package.json
        # semanticTokenTypes). Names must stay ``series`` and ``simple``.
        "series",
        "simple",
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
    """Return document selector filters (``*.pine`` / ``*.pinev5`` / ``*.pinev6``)."""
    return [
        {
            "language": "pinescript",
            "pattern": "**/*.pyne",
        },
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
        {
            "language": "pinescript",
            "pattern": "**/*.pinescript",
        },
    ]
