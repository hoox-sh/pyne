# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

"""Pynescript Language Server implementation using pygls.

This module implements the Language Server Protocol for Pine Script,
providing IDE features like diagnostics, completion, and hover.
"""

from __future__ import annotations

import logging

from typing import Any

from lsprotocol import types as lsp
from pygls.lsp.server import LanguageServer

from pynescript.langserver import config
from pynescript.langserver.features import completion as completion_feature
from pynescript.langserver.features import definitions as definitions_feature
from pynescript.langserver.features import formatting as formatting_feature
from pynescript.langserver.features import hover as hover_feature
from pynescript.langserver.features import references as references_feature
from pynescript.langserver.features import symbols as symbols_feature
from pynescript.langserver.workspace import Workspace


logger = logging.getLogger(__name__)


class PynescriptLanguageServer(LanguageServer):
    """Pynescript Language Server.

    Implements the Language Server Protocol for Pine Script,
    enabling IDE integration in VS Code, Neovim, and other editors.
    """

    def __init__(self) -> None:
        super().__init__(
            name="Pynescript",
            version="0.1.0",
        )

        self.pine_workspace = Workspace()

        self.setup_method_handlers()

    def setup_method_handlers(self) -> None:
        """Register LSP method handlers."""

        @self.feature(lsp.TEXT_DOCUMENT_DID_OPEN)
        def did_open(params: lsp.DidOpenTextDocumentParams) -> None:
            """Handle text document open."""
            uri = params.text_document.uri
            source = params.text_document.text or ""
            version = params.text_document.version

            self.pine_workspace.put_document(uri, source, version)

            doc = self.pine_workspace.get_document(uri)
            if doc:
                lsp_diags = self.pine_workspace._lint_warnings_to_diagnostics(doc)
                self.text_document_publish_diagnostics(lsp.PublishDiagnosticsParams(uri=uri, diagnostics=lsp_diags))

            logger.info(f"Opened document: {uri}")

        @self.feature(lsp.TEXT_DOCUMENT_DID_CHANGE)
        def did_change(params: lsp.DidChangeTextDocumentParams) -> None:
            """Handle text document changes."""
            uri = params.text_document.uri
            version = params.text_document.version
            changes = params.content_changes

            doc = self.pine_workspace.update_document(uri, list(changes), version)

            lsp_diags = self.pine_workspace._lint_warnings_to_diagnostics(doc)
            self.text_document_publish_diagnostics(lsp.PublishDiagnosticsParams(uri=uri, diagnostics=lsp_diags))

            logger.debug(f"Changed document: {uri} (v{version})")

        @self.feature(lsp.TEXT_DOCUMENT_DID_CLOSE)
        def did_close(params: lsp.DidCloseTextDocumentParams) -> None:
            """Handle text document close."""
            uri = params.text_document.uri
            self.pine_workspace.remove_document(uri)
            self.text_document_publish_diagnostics(lsp.PublishDiagnosticsParams(uri=uri, diagnostics=[]))
            logger.info(f"Closed document: {uri}")

        @self.feature(lsp.TEXT_DOCUMENT_DID_SAVE)
        def did_save(params: lsp.DidSaveTextDocumentParams) -> None:
            """Handle text document save."""
            uri = params.text_document.uri
            doc = self.pine_workspace.get_document(uri)
            if doc:
                lsp_diags = self.pine_workspace._lint_warnings_to_diagnostics(doc)
                self.text_document_publish_diagnostics(lsp.PublishDiagnosticsParams(uri=uri, diagnostics=lsp_diags))
            logger.info(f"Saved document: {uri}")

        @self.feature(lsp.INITIALIZE)
        def initialize(params: lsp.InitializeParams) -> lsp.InitializeResult:
            """Handle server initialization."""
            logger.info(f"Initialize request from {params.client_info}")

            if params.workspace_folders:
                for folder in params.workspace_folders:
                    logger.info(f"Workspace folder: {folder.uri}")

            capabilities = config.get_server_capabilities()

            return lsp.InitializeResult(
                capabilities=capabilities,
                server_info=lsp.ServerInfo(
                    name="Pynescript Language Server",
                    version="0.1.0",
                ),
            )

        @self.feature(lsp.INITIALIZED)
        def initialized(params: lsp.InitializedParams) -> None:
            """Handle server initialization complete."""
            logger.info("Server initialized and ready")

        @self.feature(lsp.SHUTDOWN)
        def shutdown(params: Any) -> None:
            """Handle shutdown request."""
            logger.info("Shutdown requested")

        # Note: EXIT is handled by the base class via lsp_exit

        @self.feature(lsp.TEXT_DOCUMENT_DIAGNOSTIC)
        def text_document_diagnostic(
            params: lsp.DocumentDiagnosticParams,
        ) -> lsp.DocumentDiagnosticReport:
            """Handle pull diagnostics (LSP 3.16+)."""
            uri = params.text_document.uri
            doc = self.pine_workspace.get_document(uri)

            if not doc:
                return lsp.RelatedFullDocumentDiagnosticReport(
                    kind=lsp.DocumentDiagnosticReportKind.Full,
                    result_id=None,
                    items=[],
                )

            lsp_diags = self.pine_workspace._lint_warnings_to_diagnostics(doc)

            return lsp.RelatedFullDocumentDiagnosticReport(
                kind=lsp.DocumentDiagnosticReportKind.Full,
                result_id=f"{uri}-{doc.version}",
                items=lsp_diags,
            )

        @self.feature(lsp.WORKSPACE_DIAGNOSTIC)
        def workspace_diagnostics(
            params: lsp.WorkspaceDiagnosticParams,
        ) -> lsp.WorkspaceDiagnosticReport:
            """Handle workspace diagnostics pull."""
            all_diags = self.pine_workspace.get_all_diagnostics()

            items = []
            for doc_uri, diags in all_diags.items():
                items.append(
                    lsp.WorkspaceFullDocumentDiagnosticReport(
                        uri=doc_uri,
                        items=diags,
                        kind=lsp.DocumentDiagnosticReportKind.Full,
                        version=None,
                    )
                )

            return lsp.WorkspaceDiagnosticReport(items=items)

        @self.feature(lsp.WORKSPACE_SYMBOL)
        def workspace_symbol(
            params: lsp.WorkspaceSymbolParams,
        ) -> list[lsp.SymbolInformation]:
            """Handle workspace symbol search."""
            query = params.query.lower() if params.query else ""
            results = []

            for uri, doc in self.pine_workspace.documents.items():
                if doc.ast:
                    symbols = _collect_workspace_symbols(doc, uri)
                    for sym in symbols:
                        if query in sym.name.lower():
                            results.append(sym)

            return results

        @self.feature(lsp.WORKSPACE_EXECUTE_COMMAND)
        def execute_command(params: lsp.ExecuteCommandParams) -> Any:
            """Handle workspace execute command."""
            logger.info(f"Execute command: {params.command}")
            return None

        @self.feature(lsp.TEXT_DOCUMENT_COMPLETION)
        def text_completion(
            params: lsp.CompletionParams,
        ) -> lsp.CompletionList:
            """Handle textDocument/completion request."""
            uri = params.text_document.uri
            source = self.pine_workspace.get_source(uri)
            return completion_feature.handle_completion(params, source)

        @self.feature(lsp.COMPLETION_ITEM_RESOLVE)
        def completion_resolve(
            params: lsp.CompletionItem,
        ) -> lsp.CompletionItem:
            """Handle completionItem/resolve request."""
            return completion_feature.handle_completion_resolve(params)

        @self.feature(lsp.TEXT_DOCUMENT_HOVER)
        def text_hover(
            params: lsp.HoverParams,
        ) -> lsp.Hover | None:
            """Handle textDocument/hover request."""
            uri = params.text_document.uri
            source = self.pine_workspace.get_source(uri)
            return hover_feature.handle_hover(params, source)

        @self.feature(lsp.TEXT_DOCUMENT_DEFINITION)
        def text_definition(
            params: lsp.DefinitionParams,
        ) -> list[lsp.Location] | None:
            """Handle textDocument/definition request."""
            uri = params.text_document.uri
            source = self.pine_workspace.get_source(uri)
            return definitions_feature.handle_definition(params, source, uri)

        @self.feature(lsp.TEXT_DOCUMENT_REFERENCES)
        def text_references(
            params: lsp.ReferenceParams,
        ) -> list[lsp.Location]:
            """Handle textDocument/references request."""
            uri = params.text_document.uri
            source = self.pine_workspace.get_source(uri)
            return references_feature.handle_references(params, source, uri)

        @self.feature(lsp.TEXT_DOCUMENT_DOCUMENT_SYMBOL)
        def text_document_symbol(
            params: lsp.DocumentSymbolParams,
        ) -> list[lsp.DocumentSymbol]:
            """Handle textDocument/documentSymbol request."""
            uri = params.text_document.uri
            source = self.pine_workspace.get_source(uri)
            return symbols_feature.handle_document_symbols(params, source, uri)

        @self.feature(lsp.TEXT_DOCUMENT_FORMATTING)
        def text_formatting(
            params: lsp.DocumentFormattingParams,
        ) -> list[lsp.TextEdit] | None:
            """Handle textDocument/formatting request."""
            uri = params.text_document.uri
            source = self.pine_workspace.get_source(uri)
            return formatting_feature.handle_formatting(params, source)

        @self.feature(lsp.TEXT_DOCUMENT_RANGE_FORMATTING)
        def text_range_formatting(
            params: lsp.DocumentRangeFormattingParams,
        ) -> list[lsp.TextEdit] | None:
            """Handle textDocument/rangeFormatting request."""
            uri = params.text_document.uri
            source = self.pine_workspace.get_source(uri)
            return formatting_feature.handle_range_formatting(params, source)


def _collect_workspace_symbols(doc: Any, uri: str) -> list[lsp.SymbolInformation]:
    """Collect symbols from a document for workspace symbol search."""
    from pynescript.ast import node as ast

    results = []

    def visit(node: Any) -> None:
        if isinstance(node, ast.FunctionDef):
            results.append(
                lsp.SymbolInformation(
                    name=node.name or "<anonymous>",
                    kind=lsp.SymbolKind.Function,
                    location=lsp.Location(
                        uri=uri,
                        range=lsp.Range(
                            start=lsp.Position(line=max(0, node.lineno - 1), character=0),
                            end=lsp.Position(line=max(0, node.lineno - 1), character=0),
                        ),
                    ),
                )
            )
        elif isinstance(node, ast.TypeDef):
            results.append(
                lsp.SymbolInformation(
                    name=node.name or "<anonymous>",
                    kind=lsp.SymbolKind.Class,
                    location=lsp.Location(
                        uri=uri,
                        range=lsp.Range(
                            start=lsp.Position(line=max(0, node.lineno - 1), character=0),
                            end=lsp.Position(line=max(0, node.lineno - 1), character=0),
                        ),
                    ),
                )
            )
        elif isinstance(node, ast.Assign):
            if isinstance(node.target, ast.Name):
                results.append(
                    lsp.SymbolInformation(
                        name=node.target.id,
                        kind=lsp.SymbolKind.Variable,
                        location=lsp.Location(
                            uri=uri,
                            range=lsp.Range(
                                start=lsp.Position(line=max(0, node.target.lineno - 1), character=0),
                                end=lsp.Position(line=max(0, node.target.lineno - 1), character=0),
                            ),
                        ),
                    )
                )

        for child in getattr(node, "_fields", []):
            child_node = getattr(node, child, None)
            if isinstance(child_node, list):
                for item in child_node:
                    if hasattr(item, "_fields"):
                        visit(item)
            elif hasattr(child_node, "_fields"):
                visit(child_node)

    if hasattr(doc, "ast") and doc.ast:
        visit(doc.ast)

    return results
