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

"""pygls Language Server for Pine Script.

:class:`PynescriptLanguageServer` owns a :class:`~pynescript.langserver.workspace.Workspace`
(open documents, AST, lint) and registers LSP method handlers in
:meth:`PynescriptLanguageServer.setup_method_handlers`.

**Lifecycle / sync**

- ``initialize`` / ``initialized`` / ``shutdown``
- ``textDocument/didOpen|didChange|didClose|didSave`` — update workspace,
  publish diagnostics
- ``textDocument/diagnostic`` and ``workspace/diagnostic`` — pull diagnostics

**Feature handlers** (delegated to :mod:`pynescript.langserver.features`)

- completion (+ resolve), hover, signatureHelp, definition, references
- documentHighlight, linkedEditingRange, prepareRename, rename (open workspace documents)
- documentSymbol, workspace/symbol
- formatting / rangeFormatting / onTypeFormatting
- inlayHint (display-only), semanticTokens/full, semanticTokens/range, foldingRange, selectionRange
- documentColor / colorPresentation (``#hex`` literals)
- documentLink (+ resolve tooltip) (``http(s)`` URLs in comments and string literals)
- codeAction (Convert-to-v6 + W001 QuickFix) + ``pynescript.convertToV6`` executeCommand

Advertised capabilities come from :func:`pynescript.langserver.config.get_server_capabilities`
— only list methods that have implementations here.

Entry: :func:`pynescript.langserver.__main__.main` or construct this class and
call ``start_io()``.
"""

from __future__ import annotations

import asyncio
import logging
import os

from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from pathlib import Path
from typing import Any
from typing import cast
from urllib.parse import unquote
from urllib.parse import urlparse

from lsprotocol import types as lsp
from pygls.lsp.server import LanguageServer

from pynescript.__about__ import __version__
from pynescript.langserver import config
from pynescript.langserver.features import completion as completion_feature
from pynescript.langserver.features import convert as convert_feature
from pynescript.langserver.features import definitions as definitions_feature
from pynescript.langserver.features import document_color as document_color_feature
from pynescript.langserver.features import document_link as document_link_feature
from pynescript.langserver.features import folding as folding_feature
from pynescript.langserver.features import formatting as formatting_feature
from pynescript.langserver.features import highlight as highlight_feature
from pynescript.langserver.features import hover as hover_feature
from pynescript.langserver.features import inlay_hints as inlay_hints_feature
from pynescript.langserver.features import linked_editing as linked_editing_feature
from pynescript.langserver.features import references as references_feature
from pynescript.langserver.features import rename as rename_feature
from pynescript.langserver.features import selection_range as selection_range_feature
from pynescript.langserver.features import semantic_tokens as semantic_tokens_feature
from pynescript.langserver.features import signature_help as signature_help_feature
from pynescript.langserver.features import symbols as symbols_feature
from pynescript.langserver.protocol.utils import convert_positions
from pynescript.langserver.workspace import Workspace
from pynescript.langserver.workspace_index import WorkspaceIndex


logger = logging.getLogger(__name__)

_DEBOUNCE_MS_DEFAULT = 250
# Above this many characters, parse off-loop even on open/save so a
# pathological script cannot freeze completion/hover for seconds.
_SYNC_PARSE_MAX_DEFAULT = 40_000

# Sentinel for feature-cache misses (distinct from a cached ``None`` result).
_MISSING = object()

# Server-side defaults. The VS Code extension overrides these through
# ``initializationOptions`` / ``workspace/didChangeConfiguration``.
_DEFAULT_SETTINGS: dict[str, Any] = {
    "formattingEnabled": True,
    "snippetsEnabled": True,
    "diagnosticsEnabled": True,
    "styleDiagnostics": False,
    "semanticDiagnostics": False,
    "inlayHintsTypes": True,
    "inlayHintsParameters": True,
    "completionUserSymbols": True,
}


def _debounce_seconds() -> float:
    """Debounce window for diagnostics after ``didChange`` (``PYNESCRIPT_LSP_DEBOUNCE_MS``)."""
    raw = os.environ.get("PYNESCRIPT_LSP_DEBOUNCE_MS", "").strip()
    if raw:
        try:
            return max(0, int(raw)) / 1000
        except ValueError:
            pass
    return _DEBOUNCE_MS_DEFAULT / 1000


def _sync_parse_max() -> int:
    """Max buffer size parsed synchronously on open/save (env override)."""
    raw = os.environ.get("PYNESCRIPT_LSP_SYNC_PARSE_MAX", "").strip()
    if raw:
        try:
            return max(0, int(raw))
        except ValueError:
            pass
    return _SYNC_PARSE_MAX_DEFAULT


class PynescriptLanguageServer(LanguageServer):
    """Pine Script LSP server (pygls :class:`~pygls.lsp.server.LanguageServer` subclass).

    Attributes:
        pine_workspace: In-memory document store keyed by URI. Feature handlers
            read source via :meth:`~pynescript.langserver.workspace.Workspace.get_source`.
    """

    def __init__(self) -> None:
        """Create the server, empty workspace, and register all method handlers."""
        super().__init__(
            name="Pynescript",
            version=__version__,
        )

        self.pine_workspace = Workspace(style_diagnostics=False)
        self.workspace_index = WorkspaceIndex()
        self.settings: dict[str, Any] = dict(_DEFAULT_SETTINGS)
        self._pending_diag_tasks: dict[str, asyncio.Task] = {}
        # Single worker serializes parse+lint so typing bursts cannot spawn
        # concurrent parses; keeps one warm thread-local ANTLR engine.
        self._diag_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pine-lsp-parse")

        self.setup_method_handlers()

    def _position_feature(self, feature_name: str) -> Any:
        """Register a handler that converts UTF-16 positions at the boundary.

        Feature handlers work with Python code-point columns. LSP clients send
        and expect UTF-16 columns; the wrapper converts params on the way in
        and results on the way out. URI-bearing result containers (rename
        edits, locations) use their own document's lines when available.
        """

        def decorator(func: Any) -> Any:
            @wraps(func)
            def wrapper(params: Any) -> Any:
                uri = _params_uri(params)
                doc = self.pine_workspace.get_document(uri) if uri else None
                if doc is None:
                    return func(params)
                if "\r" not in doc.source and not doc.has_astral:
                    # ASCII/LF is the common case: UTF-16 and Python columns
                    # are identical, so skip the recursive conversion.
                    return func(params)
                lines = doc.source.split("\n")
                converted = convert_positions(params, lines, to_codepoint=True)
                result = func(converted)
                return convert_positions(
                    result,
                    lines,
                    to_codepoint=False,
                    lines_for_uri=self._lines_for_uri,
                )

            return self.feature(feature_name)(wrapper)

        return decorator

    def _lines_for_uri(self, uri: str) -> list[str] | None:
        """Lines for an open document (``None`` for closed/unknown URIs)."""
        doc = self.pine_workspace.get_document(uri)
        return doc.source.split("\n") if doc else None

    def setup_method_handlers(self) -> None:
        """Register lifecycle, diagnostics, and feature LSP method handlers."""

        @self.feature(lsp.TEXT_DOCUMENT_DID_OPEN)
        def did_open(params: lsp.DidOpenTextDocumentParams) -> None:
            """Handle text document open."""
            uri = params.text_document.uri
            source = params.text_document.text or ""
            version = params.text_document.version

            large = len(source) > _sync_parse_max()
            self.pine_workspace.put_document(uri, source, version, parse=not large)

            doc = self.pine_workspace.get_document(uri)
            if doc and not large:
                lsp_diags = self.pine_workspace._lint_warnings_to_diagnostics(doc)
                self.text_document_publish_diagnostics(
                    lsp.PublishDiagnosticsParams(uri=uri, diagnostics=lsp_diags, version=doc.version)
                )
            elif doc is not None:
                self._schedule_diagnostics(uri, doc, version, delay=0.0)

            logger.info(f"Opened document: {uri}")

        @self.feature(lsp.TEXT_DOCUMENT_DID_CHANGE)
        async def did_change(params: lsp.DidChangeTextDocumentParams) -> None:
            """Handle text document changes.

            Applies edits synchronously (cheap) and schedules debounced,
            off-loop parse+lint so the event loop stays responsive during
            typing; diagnostics publish once the parse completes.
            """
            uri = params.text_document.uri
            version = params.text_document.version
            changes = params.content_changes

            # Graceful recovery: some clients send didChange without didOpen
            # (e.g. after a server restart). Treat as an empty open.
            if self.pine_workspace.get_document(uri) is None:
                self.pine_workspace.put_document(uri, "", version)

            doc = self.pine_workspace.update_document(uri, list(changes), version, relint=False)
            self._schedule_diagnostics(uri, doc, version)

            logger.debug(f"Changed document: {uri} (v{version})")

        @self.feature(lsp.TEXT_DOCUMENT_DID_CLOSE)
        def did_close(params: lsp.DidCloseTextDocumentParams) -> None:
            """Handle text document close."""
            uri = params.text_document.uri
            self._cancel_pending_diagnostics(uri)
            self.pine_workspace.remove_document(uri)
            self.text_document_publish_diagnostics(lsp.PublishDiagnosticsParams(uri=uri, diagnostics=[]))
            logger.info(f"Closed document: {uri}")

        @self.feature(lsp.TEXT_DOCUMENT_DID_SAVE)
        def did_save(params: lsp.DidSaveTextDocumentParams) -> None:
            """Handle text document save.

            Flushes any pending debounced diagnostics so the on-disk state
            is validated immediately.
            """
            uri = params.text_document.uri
            self._cancel_pending_diagnostics(uri)
            doc = self.pine_workspace.get_document(uri)
            if doc:
                if len(doc.source) > _sync_parse_max():
                    self._schedule_diagnostics(uri, doc, doc.version, delay=0.0)
                else:
                    self.pine_workspace._parse_and_lint(doc)
                    lsp_diags = self.pine_workspace._lint_warnings_to_diagnostics(doc)
                    self.text_document_publish_diagnostics(
                        lsp.PublishDiagnosticsParams(uri=uri, diagnostics=lsp_diags, version=doc.version)
                    )
            logger.info(f"Saved document: {uri}")

        @self.feature(lsp.INITIALIZE)
        def initialize(params: lsp.InitializeParams) -> lsp.InitializeResult:
            """Handle server initialization."""
            logger.info(f"Initialize request from {params.client_info}")

            roots = []
            if params.workspace_folders:
                for folder in params.workspace_folders:
                    logger.info(f"Workspace folder: {folder.uri}")
                    path = _uri_to_path(folder.uri)
                    if path is not None:
                        roots.append(path)
            elif params.root_uri:
                path = _uri_to_path(params.root_uri)
                if path is not None:
                    roots.append(path)
            self.workspace_index.set_roots(roots)

            self._apply_settings(params.initialization_options)
            capabilities = config.get_server_capabilities()

            return lsp.InitializeResult(
                capabilities=capabilities,
                server_info=lsp.ServerInfo(
                    name="Pynescript Language Server",
                    version=__version__,
                ),
            )

        @self.feature(lsp.INITIALIZED)
        def initialized(params: lsp.InitializedParams) -> None:
            """Handle server initialization complete."""
            logger.info("Server initialized and ready")

        @self.feature(lsp.WORKSPACE_DID_CHANGE_CONFIGURATION)
        def did_change_configuration(params: lsp.DidChangeConfigurationParams) -> None:
            """Apply live editor settings without restarting the server."""
            self._apply_settings(params.settings)
            # Style/diagnostics toggles should take effect immediately, not on
            # the next keystroke.
            for uri, doc in self.pine_workspace.documents.items():
                diagnostics = (
                    self.pine_workspace._lint_warnings_to_diagnostics(doc)
                    if self.settings.get("diagnosticsEnabled", True)
                    else []
                )
                self.text_document_publish_diagnostics(
                    lsp.PublishDiagnosticsParams(uri=uri, diagnostics=diagnostics, version=doc.version)
                )
            try:
                self.workspace_diagnostic_refresh(None)
            except Exception:
                logger.debug("workspace/diagnostic/refresh not supported by client", exc_info=True)

        @self.feature(lsp.WORKSPACE_DID_CHANGE_WATCHED_FILES)
        def did_change_watched_files(params: lsp.DidChangeWatchedFilesParams) -> None:
            """Invalidate cached closed-file symbols for changed paths."""
            for change in params.changes:
                path = _uri_to_path(change.uri)
                if path is not None:
                    self.workspace_index.invalidate(path)

        @self.feature(lsp.SHUTDOWN)
        def shutdown(params: Any) -> None:
            """Handle shutdown request."""
            logger.info("Shutdown requested")
            for task in list(self._pending_diag_tasks.values()):
                if not task.done():
                    task.cancel()
            self._pending_diag_tasks.clear()
            self._diag_executor.shutdown(wait=False, cancel_futures=True)

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

            lsp_diags = (
                self.pine_workspace._lint_warnings_to_diagnostics(doc)
                if self.settings.get("diagnosticsEnabled", True)
                else []
            )

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
            all_diags = (
                self.pine_workspace.get_all_diagnostics()
                if self.settings.get("diagnosticsEnabled", True)
                else {}
            )

            items = []
            for doc_uri, diags in all_diags.items():
                doc = self.pine_workspace.get_document(doc_uri)
                items.append(
                    lsp.WorkspaceFullDocumentDiagnosticReport(
                        uri=doc_uri,
                        items=diags,
                        kind=lsp.DocumentDiagnosticReportKind.Full,
                        version=doc.version if doc is not None else None,
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

            open_uris = set(self.pine_workspace.documents)
            for uri, doc in self.pine_workspace.documents.items():
                if doc.valid_ast:
                    # Per-version memo: the symbol walk is identical between edits.
                    symbols = doc.feature_cache.get("symbols", _MISSING)
                    if symbols is _MISSING:
                        symbols = symbols_feature.collect_workspace_symbols(doc, uri)
                        doc.feature_cache["symbols"] = symbols
                    for sym in symbols:
                        if query in sym.name.lower():
                            results.append(sym)

            if query:
                # Closed files under the workspace roots. Skip open buffers to
                # avoid duplicate results; the open AST is authoritative.
                for sym in self.workspace_index.search(params.query):
                    if sym.location.uri in open_uris:
                        continue
                    results.append(sym)
                    if len(results) >= 500:
                        break

            return results

        @self.feature(lsp.WORKSPACE_EXECUTE_COMMAND)
        def execute_command(params: lsp.ExecuteCommandParams) -> Any:
            """Handle workspace execute command."""
            logger.info(f"Execute command: {params.command}")
            if params.command != convert_feature.COMMAND_CONVERT_V6:
                return None
            args = list(params.arguments or [])
            uri = str(args[0]) if args else ""
            doc = self.pine_workspace.get_document(uri) if uri else None
            source = doc.source if doc else ""
            payload = convert_feature.handle_convert_to_v6(source)
            payload["uri"] = uri
            return payload

        @self._position_feature(lsp.TEXT_DOCUMENT_CODE_ACTION)
        def code_action(params: lsp.CodeActionParams) -> list[lsp.CodeAction]:
            """Offer Convert-to-v6 and lint QuickFixes for the current buffer."""
            uri = params.text_document.uri
            doc = self.pine_workspace.get_document(uri)
            source = doc.source if doc else None
            warnings = doc.diagnostics if doc else None
            return convert_feature.handle_code_action(params, source, warnings, tree=doc.valid_ast if doc else None)

        @self._position_feature(lsp.TEXT_DOCUMENT_COMPLETION)
        def text_completion(
            params: lsp.CompletionParams,
        ) -> lsp.CompletionList:
            """Handle textDocument/completion request."""
            uri = params.text_document.uri
            doc = self.pine_workspace.get_document(uri)
            if not doc:
                return completion_feature.handle_completion(params, None)
            return completion_feature.handle_completion(
                params,
                doc.source,
                tree=doc.valid_ast,
                analysis=doc.valid_analysis,
                snippets=self.settings.get("snippetsEnabled", True),
            )

        @self.feature(lsp.COMPLETION_ITEM_RESOLVE)
        def completion_resolve(
            params: lsp.CompletionItem,
        ) -> lsp.CompletionItem:
            """Handle completionItem/resolve request."""
            return completion_feature.handle_completion_resolve(params)

        @self._position_feature(lsp.TEXT_DOCUMENT_HOVER)
        def text_hover(
            params: lsp.HoverParams,
        ) -> lsp.Hover | None:
            """Handle textDocument/hover request."""
            uri = params.text_document.uri
            doc = self.pine_workspace.get_document(uri)
            if not doc:
                return hover_feature.handle_hover(params, None)
            return hover_feature.handle_hover(
                params,
                doc.source,
                tree=doc.valid_ast,
                cache=doc.feature_cache,
                analysis=doc.valid_analysis,
            )

        @self._position_feature(lsp.TEXT_DOCUMENT_SIGNATURE_HELP)
        def text_signature_help(
            params: lsp.SignatureHelpParams,
        ) -> lsp.SignatureHelp | None:
            """Handle textDocument/signatureHelp request."""
            uri = params.text_document.uri
            doc = self.pine_workspace.get_document(uri)
            if not doc:
                return signature_help_feature.handle_signature_help(params, None)
            return signature_help_feature.handle_signature_help(
                params,
                doc.source,
                tree=doc.valid_ast,
                analysis=doc.valid_analysis,
            )

        @self._position_feature(lsp.TEXT_DOCUMENT_DEFINITION)
        def text_definition(
            params: lsp.DefinitionParams,
        ) -> list[lsp.Location] | None:
            """Handle textDocument/definition request."""
            uri = params.text_document.uri
            doc = self.pine_workspace.get_document(uri)
            if not doc:
                return definitions_feature.handle_definition(params, None, uri)
            # Pass workspace AST/analysis (or None on parse failure) to skip re-parse.
            return definitions_feature.handle_definition(
                params,
                doc.source,
                uri,
                tree=doc.valid_ast,
                analysis=doc.valid_analysis,
            )

        @self._position_feature(lsp.TEXT_DOCUMENT_REFERENCES)
        def text_references(
            params: lsp.ReferenceParams,
        ) -> list[lsp.Location]:
            """Handle textDocument/references request."""
            uri = params.text_document.uri
            doc = self.pine_workspace.get_document(uri)
            if not doc:
                return references_feature.handle_references(params, None, uri)
            return references_feature.handle_references(
                params,
                doc.source,
                uri,
                tree=doc.valid_ast,
                analysis=doc.valid_analysis,
            )

        @self._position_feature(lsp.TEXT_DOCUMENT_DOCUMENT_HIGHLIGHT)
        def text_document_highlight(
            params: lsp.DocumentHighlightParams,
        ) -> list[lsp.DocumentHighlight]:
            """Handle textDocument/documentHighlight request."""
            uri = params.text_document.uri
            doc = self.pine_workspace.get_document(uri)
            if not doc:
                return highlight_feature.handle_document_highlight(params, None)
            return highlight_feature.handle_document_highlight(
                params,
                doc.source,
                tree=doc.valid_ast,
                analysis=doc.valid_analysis,
            )

        @self._position_feature(lsp.TEXT_DOCUMENT_LINKED_EDITING_RANGE)
        def text_linked_editing_range(
            params: lsp.LinkedEditingRangeParams,
        ) -> lsp.LinkedEditingRanges | None:
            """Handle textDocument/linkedEditingRange request."""
            uri = params.text_document.uri
            doc = self.pine_workspace.get_document(uri)
            if not doc:
                return linked_editing_feature.handle_linked_editing_range(params, None)
            return linked_editing_feature.handle_linked_editing_range(
                params,
                doc.source,
                tree=doc.valid_ast,
                analysis=doc.valid_analysis,
            )

        @self._position_feature(lsp.TEXT_DOCUMENT_PREPARE_RENAME)
        def text_prepare_rename(
            params: lsp.PrepareRenameParams,
        ) -> lsp.Range | None:
            """Handle textDocument/prepareRename request."""
            uri = params.text_document.uri
            doc = self.pine_workspace.get_document(uri)
            if not doc:
                return rename_feature.handle_prepare_rename(params, None)
            return rename_feature.handle_prepare_rename(
                params,
                doc.source,
                tree=doc.valid_ast,
                analysis=doc.valid_analysis,
            )

        @self._position_feature(lsp.TEXT_DOCUMENT_RENAME)
        def text_rename(
            params: lsp.RenameParams,
        ) -> lsp.WorkspaceEdit | None:
            """Handle textDocument/rename across currently open documents."""
            uri = params.text_document.uri
            doc = self.pine_workspace.get_document(uri)
            if not doc:
                return rename_feature.handle_rename(params, None, uri)
            return rename_feature.handle_rename(
                params,
                doc.source,
                uri,
                tree=doc.valid_ast,
                workspace=self.pine_workspace,
                analysis=doc.valid_analysis,
            )

        @self._position_feature(lsp.TEXT_DOCUMENT_DOCUMENT_SYMBOL)
        def text_document_symbol(
            params: lsp.DocumentSymbolParams,
        ) -> list[lsp.DocumentSymbol]:
            """Handle textDocument/documentSymbol request."""
            uri = params.text_document.uri
            doc = self.pine_workspace.get_document(uri)
            if not doc:
                return symbols_feature.handle_document_symbols(params, None, uri)
            return symbols_feature.handle_document_symbols(params, doc.source, uri, tree=doc.valid_ast)

        @self._position_feature(lsp.TEXT_DOCUMENT_FORMATTING)
        def text_formatting(
            params: lsp.DocumentFormattingParams,
        ) -> list[lsp.TextEdit] | None:
            """Handle textDocument/formatting request."""
            if self.settings.get("formattingEnabled", True) is False:
                return []
            uri = params.text_document.uri
            doc = self.pine_workspace.get_document(uri)
            if not doc:
                return formatting_feature.handle_formatting(params, None)
            return formatting_feature.handle_formatting(params, doc.source, tree=doc.valid_ast)

        @self._position_feature(lsp.TEXT_DOCUMENT_RANGE_FORMATTING)
        def text_range_formatting(
            params: lsp.DocumentRangeFormattingParams,
        ) -> list[lsp.TextEdit] | None:
            """Handle textDocument/rangeFormatting request."""
            if self.settings.get("formattingEnabled", True) is False:
                return []
            uri = params.text_document.uri
            doc = self.pine_workspace.get_document(uri)
            if not doc:
                return formatting_feature.handle_range_formatting(params, None)
            return formatting_feature.handle_range_formatting(params, doc.source, tree=doc.valid_ast)

        @self._position_feature(lsp.TEXT_DOCUMENT_ON_TYPE_FORMATTING)
        def text_on_type_formatting(
            params: lsp.DocumentOnTypeFormattingParams,
        ) -> list[lsp.TextEdit] | None:
            """Handle textDocument/onTypeFormatting request."""
            if self.settings.get("formattingEnabled", True) is False:
                return []
            uri = params.text_document.uri
            doc = self.pine_workspace.get_document(uri)
            if not doc:
                return formatting_feature.handle_on_type_formatting(params, None)
            return formatting_feature.handle_on_type_formatting(params, doc.source, tree=doc.valid_ast)

        @self._position_feature(lsp.TEXT_DOCUMENT_INLAY_HINT)
        def text_inlay_hints(
            params: lsp.InlayHintParams,
        ) -> list[lsp.InlayHint] | None:
            """Handle textDocument/inlayHint request."""
            uri = params.text_document.uri
            doc = self.pine_workspace.get_document(uri)
            if not doc:
                return inlay_hints_feature.handle_inlay_hints(params, None)
            # Range-dependent: cache by the requested range for this version.
            cache_key = (
                params.range.start.line,
                params.range.start.character,
                params.range.end.line,
                params.range.end.character,
                self.settings.get("inlayHintsTypes", True),
                self.settings.get("inlayHintsParameters", True),
            )
            cached = doc.feature_cache.get("inlay_hints")
            if isinstance(cached, tuple) and cached[0] == cache_key:
                return cast(list[lsp.InlayHint] | None, cached[1])
            result = inlay_hints_feature.handle_inlay_hints(
                params,
                doc.source,
                tree=doc.valid_ast,
                analysis=doc.valid_analysis,
                show_types=self.settings.get("inlayHintsTypes", True),
                show_parameters=self.settings.get("inlayHintsParameters", True),
            )
            doc.feature_cache["inlay_hints"] = (cache_key, result)
            return result

        @self._position_feature(lsp.TEXT_DOCUMENT_FOLDING_RANGE)
        def text_folding_range(
            params: lsp.FoldingRangeParams,
        ) -> list[lsp.FoldingRange]:
            """Handle textDocument/foldingRange request."""
            uri = params.text_document.uri
            doc = self.pine_workspace.get_document(uri)
            if not doc:
                return folding_feature.handle_folding_range(params, None)
            cached = doc.feature_cache.get("folding_range", _MISSING)
            if cached is not _MISSING:
                return cast(list[lsp.FoldingRange], cached)
            result = folding_feature.handle_folding_range(params, doc.source, tree=doc.valid_ast)
            doc.feature_cache["folding_range"] = result
            return result

        @self._position_feature(lsp.TEXT_DOCUMENT_SELECTION_RANGE)
        def text_selection_range(
            params: lsp.SelectionRangeParams,
        ) -> list[lsp.SelectionRange]:
            """Handle textDocument/selectionRange request."""
            uri = params.text_document.uri
            doc = self.pine_workspace.get_document(uri)
            if not doc:
                return selection_range_feature.handle_selection_range(params, None)
            return selection_range_feature.handle_selection_range(params, doc.source, tree=doc.valid_ast)

        @self._position_feature(lsp.TEXT_DOCUMENT_DOCUMENT_COLOR)
        def text_document_color(
            params: lsp.DocumentColorParams,
        ) -> list[lsp.ColorInformation]:
            """Handle textDocument/documentColor request."""
            uri = params.text_document.uri
            doc = self.pine_workspace.get_document(uri)
            if not doc:
                return document_color_feature.handle_document_color(params, None)
            cached = doc.feature_cache.get("document_color", _MISSING)
            if cached is not _MISSING:
                return cast(list[lsp.ColorInformation], cached)
            result = document_color_feature.handle_document_color(params, doc.source, tree=doc.valid_ast)
            doc.feature_cache["document_color"] = result
            return result

        @self._position_feature(lsp.TEXT_DOCUMENT_COLOR_PRESENTATION)
        def text_color_presentation(
            params: lsp.ColorPresentationParams,
        ) -> list[lsp.ColorPresentation]:
            """Handle textDocument/colorPresentation request."""
            uri = params.text_document.uri
            doc = self.pine_workspace.get_document(uri)
            source = doc.source if doc else None
            return document_color_feature.handle_color_presentation(params, source)

        @self._position_feature(lsp.TEXT_DOCUMENT_DOCUMENT_LINK)
        def text_document_link(
            params: lsp.DocumentLinkParams,
        ) -> list[lsp.DocumentLink]:
            """Handle textDocument/documentLink request."""
            uri = params.text_document.uri
            doc = self.pine_workspace.get_document(uri)
            if not doc:
                return document_link_feature.handle_document_link(params, None)
            cached = doc.feature_cache.get("document_link", _MISSING)
            if cached is not _MISSING:
                return cast(list[lsp.DocumentLink], cached)
            result = document_link_feature.handle_document_link(params, doc.source, tree=doc.valid_ast)
            doc.feature_cache["document_link"] = result
            return result

        @self.feature(lsp.DOCUMENT_LINK_RESOLVE)
        def document_link_resolve(params: lsp.DocumentLink) -> lsp.DocumentLink:
            """Handle documentLink/resolve request (fill tooltip)."""
            return document_link_feature.handle_document_link_resolve(params)

        @self._position_feature(lsp.TEXT_DOCUMENT_SEMANTIC_TOKENS_FULL)
        def text_semantic_tokens(
            params: lsp.SemanticTokensParams,
        ) -> lsp.SemanticTokens | None:
            """Handle textDocument/semanticTokens/full request."""
            uri = params.text_document.uri
            doc = self.pine_workspace.get_document(uri)
            if not doc:
                return semantic_tokens_feature.handle_semantic_tokens(params, None)
            # Pure function of (source, tree): memoize per document version.
            cached = doc.feature_cache.get("semantic_tokens", _MISSING)
            if cached is not _MISSING:
                return cast(lsp.SemanticTokens | None, cached)
            result = semantic_tokens_feature.handle_semantic_tokens(
                params,
                doc.source,
                tree=doc.valid_ast,
                analysis=doc.valid_analysis,
            )
            doc.feature_cache["semantic_tokens"] = result
            return result

        @self._position_feature(lsp.TEXT_DOCUMENT_SEMANTIC_TOKENS_RANGE)
        def text_semantic_tokens_range(
            params: lsp.SemanticTokensRangeParams,
        ) -> lsp.SemanticTokens | None:
            """Handle textDocument/semanticTokens/range request."""
            uri = params.text_document.uri
            doc = self.pine_workspace.get_document(uri)
            if not doc:
                return semantic_tokens_feature.handle_semantic_tokens_range(params, None)
            return semantic_tokens_feature.handle_semantic_tokens_range(
                params,
                doc.source,
                tree=doc.valid_ast,
                analysis=doc.valid_analysis,
            )

    def _apply_settings(self, options: Any) -> None:
        """Merge initialization/configuration options into live server settings.

        Accepts either a flat camelCase map (the extension's
        ``initializationOptions``) or a nested ``pynescript`` object with
        dotted setting keys (VS Code's configuration payload).
        """
        if not isinstance(options, dict):
            return
        raw: dict[str, Any] = options
        nested = options.get("pynescript")
        if isinstance(nested, dict):
            raw = {**options, **nested}

        def pick(camel: str, dotted: str, default: Any) -> Any:
            if camel in raw:
                return raw[camel]
            if dotted in raw:
                return raw[dotted]
            # Partial configuration payload: keep the previous value.
            return self.settings.get(camel, default)

        self.settings["formattingEnabled"] = bool(pick("formattingEnabled", "formatting.enabled", True))
        self.settings["snippetsEnabled"] = bool(pick("snippetsEnabled", "completion.snippets", True))
        self.settings["diagnosticsEnabled"] = bool(pick("diagnosticsEnabled", "diagnostics.enabled", True))
        self.settings["styleDiagnostics"] = bool(pick("styleDiagnostics", "diagnostics.style", False))
        self.settings["semanticDiagnostics"] = bool(pick("semanticDiagnostics", "diagnostics.semantic", False))
        self.settings["inlayHintsTypes"] = bool(pick("inlayHintsTypes", "inlayHints.types", True))
        self.settings["inlayHintsParameters"] = bool(pick("inlayHintsParameters", "inlayHints.parameters", True))
        self.settings["completionUserSymbols"] = bool(pick("completionUserSymbols", "completion.userSymbols", True))

        self.pine_workspace.style_diagnostics = self.settings["styleDiagnostics"]
        self.pine_workspace.semantic_diagnostics = self.settings["semanticDiagnostics"]
        logger.debug("Applied LSP settings: %s", self.settings)

    def _schedule_diagnostics(
        self,
        uri: str,
        doc: Any,
        version: int | None = None,
        *,
        delay: float | None = None,
    ) -> None:
        """Schedule (or re-schedule) a debounced parse+lint+publish for *uri*."""
        pending = self._pending_diag_tasks.get(uri)
        if pending is not None and not pending.done():
            pending.cancel()
        expected = doc.version if version is None else version
        wait = _debounce_seconds() if delay is None else delay
        self._pending_diag_tasks[uri] = asyncio.ensure_future(
            self._publish_diagnostics_after(uri, doc, expected, delay=wait)
        )

    def _cancel_pending_diagnostics(self, uri: str) -> None:
        """Drop any pending debounced diagnostics task for *uri*."""
        pending = self._pending_diag_tasks.pop(uri, None)
        if pending is not None and not pending.done():
            pending.cancel()

    async def _publish_diagnostics_after(
        self,
        uri: str,
        doc: Any,
        expected_version: int | None = None,
        *,
        delay: float | None = None,
    ) -> None:
        """Debounce, parse+lint off the event loop, then publish diagnostics.

        A newer edit can arrive while the executor is parsing. In that case the
        parse result is discarded (see ``Workspace._parse_and_lint``) and no
        diagnostics are published for the stale version.
        """
        try:
            await asyncio.sleep(_debounce_seconds() if delay is None else delay)
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(self._diag_executor, self.pine_workspace._parse_and_lint, doc)
            if expected_version is not None and doc.version != expected_version:
                return
            if self.settings.get("diagnosticsEnabled", True) is False:
                lsp_diags: list[lsp.Diagnostic] = []
            else:
                lsp_diags = self.pine_workspace._lint_warnings_to_diagnostics(doc)
            self.text_document_publish_diagnostics(
                lsp.PublishDiagnosticsParams(uri=uri, diagnostics=lsp_diags, version=doc.version)
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Debounced diagnostics failed for %s", uri)
        finally:
            if self._pending_diag_tasks.get(uri) is asyncio.current_task():
                self._pending_diag_tasks.pop(uri, None)


def _params_uri(params: Any) -> str | None:
    """Document URI from any ``textDocument``-bearing LSP params object."""
    text_document = getattr(params, "text_document", None)
    return getattr(text_document, "uri", None)


def _uri_to_path(uri: str) -> Path | None:
    """Convert a ``file://`` URI to a local path, or ``None``."""
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return None
    path = unquote(parsed.path)
    if parsed.netloc and parsed.netloc not in ("", "localhost"):
        path = f"//{parsed.netloc}{path}"
    if len(path) >= 3 and path[0] == "/" and path[2] == ":":
        path = path[1:]
    return Path(path)


def _collect_workspace_symbols(doc: Any, uri: str) -> list[lsp.SymbolInformation]:
    """Collect symbols from a document for workspace symbol search.

    Delegates to :func:`pynescript.langserver.features.symbols.collect_workspace_symbols`
    so document and workspace outlines share exact ranges, methods, imports,
    and container names.
    """
    return symbols_feature.collect_workspace_symbols(doc, uri)
