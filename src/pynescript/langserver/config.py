# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

"""Server capability definitions.

Declares which LSP features the Pynescript Language Server supports.
"""

from __future__ import annotations

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
        signature_help_provider=lsp.SignatureHelpOptions(
            trigger_characters=["(", ","],
            retrigger_characters=[","],
        ),
        code_action_provider=lsp.CodeActionOptions(
            code_action_kinds=[
                lsp.CodeActionKind.QuickFix,
                lsp.CodeActionKind.Refactor,
                lsp.CodeActionKind.SourceOrganizeImports,
            ],
        ),
    )


from typing import Any


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
