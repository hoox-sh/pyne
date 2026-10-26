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

"""Unit coverage for ``pynescript.langserver.server.PynescriptLanguageServer``.

Invokes nested handlers registered in ``setup_method_handlers`` via
``server.protocol.fm.features`` — no stdio LSP transport.
"""

from __future__ import annotations

import asyncio

from typing import Any

import pytest

from lsprotocol import types as lsp

from pynescript.langserver.server import PynescriptLanguageServer
from pynescript.langserver.server import _debounce_seconds


URI = "file:///server-cov.pine"
SRC = '//@version=5\nindicator("T")\nlength = 14\nplot(close)\n'


def _handler(server: PynescriptLanguageServer, method: str):
    return server.protocol.fm.features[method]


@pytest.fixture()
def server(monkeypatch: pytest.MonkeyPatch):
    """Language server with publish-diagnostics captured into a list."""
    monkeypatch.setenv("PYNESCRIPT_LSP_DEBOUNCE_MS", "0")
    published: list[lsp.PublishDiagnosticsParams] = []
    srv = PynescriptLanguageServer()
    monkeypatch.setattr(
        srv,
        "text_document_publish_diagnostics",
        lambda params: published.append(params),
    )
    srv._published = published  # type: ignore[attr-defined]
    try:
        yield srv
    finally:
        for task in list(srv._pending_diag_tasks.values()):
            if not task.done():
                task.cancel()
        srv._diag_executor.shutdown(wait=False, cancel_futures=True)


def _open(server: PynescriptLanguageServer, uri: str = URI, text: str = SRC, version: int = 1) -> None:
    _handler(server, lsp.TEXT_DOCUMENT_DID_OPEN)(
        lsp.DidOpenTextDocumentParams(
            text_document=lsp.TextDocumentItem(
                uri=uri,
                language_id="pine",
                version=version,
                text=text,
            )
        )
    )


async def _drain_diags(server: PynescriptLanguageServer, timeout: float = 2.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        pending = [t for t in server._pending_diag_tasks.values() if not t.done()]
        if not pending:
            return
        await asyncio.wait(pending, timeout=0.05)
    for task in list(server._pending_diag_tasks.values()):
        if not task.done():
            task.cancel()


# ---------------------------------------------------------------------------
# _debounce_seconds env edges
# ---------------------------------------------------------------------------


class TestDebounceSecondsEdges:
    def test_empty_and_whitespace_fall_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PYNESCRIPT_LSP_DEBOUNCE_MS", "")
        assert _debounce_seconds() == pytest.approx(0.25)
        monkeypatch.setenv("PYNESCRIPT_LSP_DEBOUNCE_MS", "   ")
        assert _debounce_seconds() == pytest.approx(0.25)

    def test_zero_and_positive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PYNESCRIPT_LSP_DEBOUNCE_MS", "0")
        assert _debounce_seconds() == 0.0
        monkeypatch.setenv("PYNESCRIPT_LSP_DEBOUNCE_MS", "500")
        assert _debounce_seconds() == pytest.approx(0.5)

    def test_floatish_invalid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PYNESCRIPT_LSP_DEBOUNCE_MS", "12.5")
        assert _debounce_seconds() == pytest.approx(0.25)


# ---------------------------------------------------------------------------
# Lifecycle: initialize / initialized / shutdown
# ---------------------------------------------------------------------------


class TestLifecycle:
    def test_initialize_with_folders(self, server: PynescriptLanguageServer) -> None:
        result = _handler(server, lsp.INITIALIZE)(
            lsp.InitializeParams(
                process_id=None,
                capabilities=lsp.ClientCapabilities(),
                client_info=lsp.ClientInfo(name="cov", version="0"),
                workspace_folders=[lsp.WorkspaceFolder(uri="file:///ws", name="ws")],
            )
        )
        assert isinstance(result, lsp.InitializeResult)
        assert result.server_info is not None
        assert result.server_info.name == "Pynescript Language Server"
        assert result.capabilities is not None

    def test_initialize_without_folders(self, server: PynescriptLanguageServer) -> None:
        result = _handler(server, lsp.INITIALIZE)(
            lsp.InitializeParams(
                process_id=1,
                capabilities=lsp.ClientCapabilities(),
            )
        )
        assert isinstance(result.capabilities, lsp.ServerCapabilities)

    def test_initialized_and_shutdown(self, server: PynescriptLanguageServer) -> None:
        assert _handler(server, lsp.INITIALIZED)(lsp.InitializedParams()) is None
        assert _handler(server, lsp.SHUTDOWN)(None) is None


# ---------------------------------------------------------------------------
# Document sync: open / change / close / save
# ---------------------------------------------------------------------------


class TestDocumentSync:
    def test_did_open_publishes(self, server: PynescriptLanguageServer) -> None:
        _open(server)
        doc = server.pine_workspace.get_document(URI)
        assert doc is not None
        assert doc.source == SRC
        assert server._published  # type: ignore[attr-defined]
        assert server._published[-1].uri == URI  # type: ignore[attr-defined]

    def test_did_change_missing_doc_recovery(self, server: PynescriptLanguageServer) -> None:
        async def _run() -> None:
            uri = "file:///recovered.pine"
            await _handler(server, lsp.TEXT_DOCUMENT_DID_CHANGE)(
                lsp.DidChangeTextDocumentParams(
                    text_document=lsp.VersionedTextDocumentIdentifier(uri=uri, version=3),
                    content_changes=[
                        lsp.TextDocumentContentChangeWholeDocument(text=SRC),
                    ],
                )
            )
            await _drain_diags(server)
            doc = server.pine_workspace.get_document(uri)
            assert doc is not None
            assert doc.version == 3
            assert SRC.strip() in doc.source or doc.source == SRC

        asyncio.run(_run())

    def test_did_change_existing_reschedules(self, server: PynescriptLanguageServer) -> None:
        async def _run() -> None:
            _open(server)
            server._published.clear()  # type: ignore[attr-defined]
            await _handler(server, lsp.TEXT_DOCUMENT_DID_CHANGE)(
                lsp.DidChangeTextDocumentParams(
                    text_document=lsp.VersionedTextDocumentIdentifier(uri=URI, version=2),
                    content_changes=[
                        lsp.TextDocumentContentChangeWholeDocument(
                            text='//@version=5\nindicator("U")\n'
                        ),
                    ],
                )
            )
            # Second change cancels the first pending task.
            await _handler(server, lsp.TEXT_DOCUMENT_DID_CHANGE)(
                lsp.DidChangeTextDocumentParams(
                    text_document=lsp.VersionedTextDocumentIdentifier(uri=URI, version=3),
                    content_changes=[
                        lsp.TextDocumentContentChangeWholeDocument(text=SRC),
                    ],
                )
            )
            await _drain_diags(server)
            doc = server.pine_workspace.get_document(URI)
            assert doc is not None
            assert doc.version == 3
            assert any(p.uri == URI for p in server._published)  # type: ignore[attr-defined]

        asyncio.run(_run())

    def test_did_close_clears_and_cancels(self, server: PynescriptLanguageServer) -> None:
        async def _run() -> None:
            _open(server)
            await _handler(server, lsp.TEXT_DOCUMENT_DID_CHANGE)(
                lsp.DidChangeTextDocumentParams(
                    text_document=lsp.VersionedTextDocumentIdentifier(uri=URI, version=2),
                    content_changes=[
                        lsp.TextDocumentContentChangeWholeDocument(text=SRC),
                    ],
                )
            )
            server._published.clear()  # type: ignore[attr-defined]
            _handler(server, lsp.TEXT_DOCUMENT_DID_CLOSE)(
                lsp.DidCloseTextDocumentParams(
                    text_document=lsp.TextDocumentIdentifier(uri=URI),
                )
            )
            assert server.pine_workspace.get_document(URI) is None
            assert URI not in server._pending_diag_tasks
            assert server._published[-1].diagnostics == []  # type: ignore[attr-defined]

        asyncio.run(_run())

    def test_did_save_with_and_without_doc(self, server: PynescriptLanguageServer) -> None:
        _open(server)
        server._published.clear()  # type: ignore[attr-defined]
        _handler(server, lsp.TEXT_DOCUMENT_DID_SAVE)(
            lsp.DidSaveTextDocumentParams(
                text_document=lsp.TextDocumentIdentifier(uri=URI),
            )
        )
        assert any(p.uri == URI for p in server._published)  # type: ignore[attr-defined]

        # Missing document: no publish, no crash.
        before = len(server._published)  # type: ignore[attr-defined]
        _handler(server, lsp.TEXT_DOCUMENT_DID_SAVE)(
            lsp.DidSaveTextDocumentParams(
                text_document=lsp.TextDocumentIdentifier(uri="file:///absent.pine"),
            )
        )
        assert len(server._published) == before  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Pull diagnostics
# ---------------------------------------------------------------------------


class TestPullDiagnostics:
    def test_text_document_diagnostic_missing_and_present(self, server: PynescriptLanguageServer) -> None:
        missing = _handler(server, lsp.TEXT_DOCUMENT_DIAGNOSTIC)(
            lsp.DocumentDiagnosticParams(
                text_document=lsp.TextDocumentIdentifier(uri="file:///gone.pine"),
            )
        )
        assert missing.kind == lsp.DocumentDiagnosticReportKind.Full
        assert missing.items == []
        assert missing.result_id is None

        _open(server)
        present = _handler(server, lsp.TEXT_DOCUMENT_DIAGNOSTIC)(
            lsp.DocumentDiagnosticParams(
                text_document=lsp.TextDocumentIdentifier(uri=URI),
            )
        )
        assert present.kind == lsp.DocumentDiagnosticReportKind.Full
        assert present.result_id is not None
        assert present.result_id.startswith(URI)

    def test_workspace_diagnostics(self, server: PynescriptLanguageServer) -> None:
        empty = _handler(server, lsp.WORKSPACE_DIAGNOSTIC)(
            lsp.WorkspaceDiagnosticParams(previous_result_ids=[])
        )
        assert empty.items == []

        _open(server)
        _open(server, uri="file:///other.pine", text='indicator("no version")\n')
        report = _handler(server, lsp.WORKSPACE_DIAGNOSTIC)(
            lsp.WorkspaceDiagnosticParams(previous_result_ids=[])
        )
        uris = {item.uri for item in report.items}
        assert URI in uris
        assert "file:///other.pine" in uris


# ---------------------------------------------------------------------------
# Schedule / cancel / publish-after edges
# ---------------------------------------------------------------------------


class TestScheduleCancelDiagnostics:
    def test_cancel_pending_and_noop(self, server: PynescriptLanguageServer) -> None:
        async def _run() -> None:
            _open(server)
            doc = server.pine_workspace.get_document(URI)
            server._schedule_diagnostics(URI, doc)
            assert URI in server._pending_diag_tasks
            server._cancel_pending_diagnostics(URI)
            assert URI not in server._pending_diag_tasks
            # Cancel again (noop) and unknown URI.
            server._cancel_pending_diagnostics(URI)
            server._cancel_pending_diagnostics("file:///never.pine")

        asyncio.run(_run())

    def test_publish_after_exception_swallowed(self, server: PynescriptLanguageServer, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _run() -> None:
            _open(server)
            doc = server.pine_workspace.get_document(URI)

            def _boom(_doc: Any) -> None:
                msg = "parse boom"
                raise RuntimeError(msg)

            monkeypatch.setattr(server.pine_workspace, "_parse_and_lint", _boom)
            await server._publish_diagnostics_after(URI, doc)
            # Task key cleaned in finally when it matches current task — direct
            # await means current_task may still match; either way no raise.

        asyncio.run(_run())

    def test_publish_after_cancelled(self, server: PynescriptLanguageServer, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _run() -> None:
            monkeypatch.setenv("PYNESCRIPT_LSP_DEBOUNCE_MS", "50")
            _open(server)
            doc = server.pine_workspace.get_document(URI)
            task = asyncio.ensure_future(server._publish_diagnostics_after(URI, doc))
            await asyncio.sleep(0)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# Feature handlers + cache (_MISSING) paths
# ---------------------------------------------------------------------------


class TestFeatureHandlersAndCache:
    def _pos_params(self, cls: type, line: int = 2, character: int = 0, **extra: Any):
        kwargs: dict[str, Any] = {
            "text_document": lsp.TextDocumentIdentifier(uri=URI),
            "position": lsp.Position(line=line, character=character),
        }
        kwargs.update(extra)
        return cls(**kwargs)

    def test_workspace_symbol_cache_and_query(self, server: PynescriptLanguageServer) -> None:
        _open(server)
        h = _handler(server, lsp.WORKSPACE_SYMBOL)
        all_syms = h(lsp.WorkspaceSymbolParams(query=""))
        assert any(s.name == "length" for s in all_syms)
        # Second call hits feature_cache["symbols"].
        again = h(lsp.WorkspaceSymbolParams(query="LENGTH"))
        assert any(s.name == "length" for s in again)
        none = h(lsp.WorkspaceSymbolParams(query="zzzz_no_match"))
        assert none == []

        # Document without AST skipped for symbols.
        server.pine_workspace.put_document("file:///broken.pine", "@@@", version=1)
        assert isinstance(h(lsp.WorkspaceSymbolParams(query="")), list)

    def test_execute_command_and_code_action(self, server: PynescriptLanguageServer) -> None:
        _open(server, text='indicator("old")\n')
        unknown = _handler(server, lsp.WORKSPACE_EXECUTE_COMMAND)(
            lsp.ExecuteCommandParams(command="pynescript.unknown", arguments=[])
        )
        assert unknown is None
        payload = _handler(server, lsp.WORKSPACE_EXECUTE_COMMAND)(
            lsp.ExecuteCommandParams(
                command="pynescript.convertToV6",
                arguments=[URI],
            )
        )
        assert isinstance(payload, dict)
        assert payload.get("uri") == URI

        empty_payload = _handler(server, lsp.WORKSPACE_EXECUTE_COMMAND)(
            lsp.ExecuteCommandParams(command="pynescript.convertToV6", arguments=[])
        )
        assert empty_payload.get("uri") == ""

        actions = _handler(server, lsp.TEXT_DOCUMENT_CODE_ACTION)(
            lsp.CodeActionParams(
                text_document=lsp.TextDocumentIdentifier(uri=URI),
                range=lsp.Range(
                    start=lsp.Position(line=0, character=0),
                    end=lsp.Position(line=0, character=1),
                ),
                context=lsp.CodeActionContext(diagnostics=[]),
            )
        )
        assert isinstance(actions, list)
        # Missing doc
        assert (
            _handler(server, lsp.TEXT_DOCUMENT_CODE_ACTION)(
                lsp.CodeActionParams(
                    text_document=lsp.TextDocumentIdentifier(uri="file:///nope.pine"),
                    range=lsp.Range(
                        start=lsp.Position(line=0, character=0),
                        end=lsp.Position(line=0, character=1),
                    ),
                    context=lsp.CodeActionContext(diagnostics=[]),
                )
            )
            is not None
        )

    def test_completion_hover_signature_definition_refs(self, server: PynescriptLanguageServer) -> None:
        _open(server)
        comp = _handler(server, lsp.TEXT_DOCUMENT_COMPLETION)(
            self._pos_params(lsp.CompletionParams, line=3, character=5)
        )
        assert isinstance(comp, lsp.CompletionList)
        assert (
            _handler(server, lsp.TEXT_DOCUMENT_COMPLETION)(
                lsp.CompletionParams(
                    text_document=lsp.TextDocumentIdentifier(uri="file:///missing.pine"),
                    position=lsp.Position(line=0, character=0),
                )
            )
            is not None
        )

        item = lsp.CompletionItem(label="sma")
        assert _handler(server, lsp.COMPLETION_ITEM_RESOLVE)(item) is not None

        hover = _handler(server, lsp.TEXT_DOCUMENT_HOVER)(
            self._pos_params(lsp.HoverParams, line=3, character=5)
        )
        _ = hover
        _handler(server, lsp.TEXT_DOCUMENT_HOVER)(
            lsp.HoverParams(
                text_document=lsp.TextDocumentIdentifier(uri="file:///missing.pine"),
                position=lsp.Position(line=0, character=0),
            )
        )

        _handler(server, lsp.TEXT_DOCUMENT_SIGNATURE_HELP)(
            self._pos_params(lsp.SignatureHelpParams, line=3, character=5)
        )
        _handler(server, lsp.TEXT_DOCUMENT_SIGNATURE_HELP)(
            lsp.SignatureHelpParams(
                text_document=lsp.TextDocumentIdentifier(uri="file:///missing.pine"),
                position=lsp.Position(line=0, character=0),
            )
        )

        _handler(server, lsp.TEXT_DOCUMENT_DEFINITION)(
            self._pos_params(lsp.DefinitionParams, line=2, character=1)
        )
        _handler(server, lsp.TEXT_DOCUMENT_DEFINITION)(
            lsp.DefinitionParams(
                text_document=lsp.TextDocumentIdentifier(uri="file:///missing.pine"),
                position=lsp.Position(line=0, character=0),
            )
        )

        refs = _handler(server, lsp.TEXT_DOCUMENT_REFERENCES)(
            lsp.ReferenceParams(
                text_document=lsp.TextDocumentIdentifier(uri=URI),
                position=lsp.Position(line=2, character=1),
                context=lsp.ReferenceContext(include_declaration=True),
            )
        )
        assert isinstance(refs, list)
        _handler(server, lsp.TEXT_DOCUMENT_REFERENCES)(
            lsp.ReferenceParams(
                text_document=lsp.TextDocumentIdentifier(uri="file:///missing.pine"),
                position=lsp.Position(line=0, character=0),
                context=lsp.ReferenceContext(include_declaration=True),
            )
        )

    def test_highlight_linked_rename_symbols_format(self, server: PynescriptLanguageServer) -> None:
        _open(server)
        for method, cls in [
            (lsp.TEXT_DOCUMENT_DOCUMENT_HIGHLIGHT, lsp.DocumentHighlightParams),
            (lsp.TEXT_DOCUMENT_LINKED_EDITING_RANGE, lsp.LinkedEditingRangeParams),
            (lsp.TEXT_DOCUMENT_PREPARE_RENAME, lsp.PrepareRenameParams),
        ]:
            _handler(server, method)(self._pos_params(cls, line=2, character=1))
            _handler(server, method)(
                cls(
                    text_document=lsp.TextDocumentIdentifier(uri="file:///missing.pine"),
                    position=lsp.Position(line=0, character=0),
                )
            )

        _handler(server, lsp.TEXT_DOCUMENT_RENAME)(
            lsp.RenameParams(
                text_document=lsp.TextDocumentIdentifier(uri=URI),
                position=lsp.Position(line=2, character=1),
                new_name="len2",
            )
        )
        _handler(server, lsp.TEXT_DOCUMENT_RENAME)(
            lsp.RenameParams(
                text_document=lsp.TextDocumentIdentifier(uri="file:///missing.pine"),
                position=lsp.Position(line=0, character=0),
                new_name="x",
            )
        )

        _handler(server, lsp.TEXT_DOCUMENT_DOCUMENT_SYMBOL)(
            lsp.DocumentSymbolParams(text_document=lsp.TextDocumentIdentifier(uri=URI))
        )
        _handler(server, lsp.TEXT_DOCUMENT_DOCUMENT_SYMBOL)(
            lsp.DocumentSymbolParams(
                text_document=lsp.TextDocumentIdentifier(uri="file:///missing.pine")
            )
        )

        fmt = lsp.FormattingOptions(tab_size=4, insert_spaces=True)
        _handler(server, lsp.TEXT_DOCUMENT_FORMATTING)(
            lsp.DocumentFormattingParams(
                text_document=lsp.TextDocumentIdentifier(uri=URI),
                options=fmt,
            )
        )
        _handler(server, lsp.TEXT_DOCUMENT_FORMATTING)(
            lsp.DocumentFormattingParams(
                text_document=lsp.TextDocumentIdentifier(uri="file:///missing.pine"),
                options=fmt,
            )
        )
        rng = lsp.Range(start=lsp.Position(line=0, character=0), end=lsp.Position(line=2, character=0))
        _handler(server, lsp.TEXT_DOCUMENT_RANGE_FORMATTING)(
            lsp.DocumentRangeFormattingParams(
                text_document=lsp.TextDocumentIdentifier(uri=URI),
                range=rng,
                options=fmt,
            )
        )
        _handler(server, lsp.TEXT_DOCUMENT_RANGE_FORMATTING)(
            lsp.DocumentRangeFormattingParams(
                text_document=lsp.TextDocumentIdentifier(uri="file:///missing.pine"),
                range=rng,
                options=fmt,
            )
        )
        _handler(server, lsp.TEXT_DOCUMENT_ON_TYPE_FORMATTING)(
            lsp.DocumentOnTypeFormattingParams(
                text_document=lsp.TextDocumentIdentifier(uri=URI),
                position=lsp.Position(line=1, character=0),
                ch="\n",
                options=fmt,
            )
        )
        _handler(server, lsp.TEXT_DOCUMENT_ON_TYPE_FORMATTING)(
            lsp.DocumentOnTypeFormattingParams(
                text_document=lsp.TextDocumentIdentifier(uri="file:///missing.pine"),
                position=lsp.Position(line=0, character=0),
                ch="\n",
                options=fmt,
            )
        )

    def test_inlay_folding_color_link_semantic_cache(self, server: PynescriptLanguageServer) -> None:
        src = '//@version=5\nindicator("T")\nlength = 14\n// https://example.com\nc = #ff0000\n'
        _open(server, text=src)
        doc = server.pine_workspace.get_document(URI)
        assert doc is not None

        full_range = lsp.Range(
            start=lsp.Position(line=0, character=0),
            end=lsp.Position(line=20, character=0),
        )

        # Inlay hints — miss then hit cache.
        ih = _handler(server, lsp.TEXT_DOCUMENT_INLAY_HINT)(
            lsp.InlayHintParams(
                text_document=lsp.TextDocumentIdentifier(uri=URI),
                range=full_range,
            )
        )
        assert "inlay_hints" in doc.feature_cache
        assert (
            _handler(server, lsp.TEXT_DOCUMENT_INLAY_HINT)(
                lsp.InlayHintParams(
                    text_document=lsp.TextDocumentIdentifier(uri=URI),
                    range=full_range,
                )
            )
            is ih
        )
        _handler(server, lsp.TEXT_DOCUMENT_INLAY_HINT)(
            lsp.InlayHintParams(
                text_document=lsp.TextDocumentIdentifier(uri="file:///missing.pine"),
                range=full_range,
            )
        )
        if ih:
            _handler(server, lsp.INLAY_HINT_RESOLVE)(ih[0])

        fr = _handler(server, lsp.TEXT_DOCUMENT_FOLDING_RANGE)(
            lsp.FoldingRangeParams(text_document=lsp.TextDocumentIdentifier(uri=URI))
        )
        assert "folding_range" in doc.feature_cache
        assert (
            _handler(server, lsp.TEXT_DOCUMENT_FOLDING_RANGE)(
                lsp.FoldingRangeParams(text_document=lsp.TextDocumentIdentifier(uri=URI))
            )
            is fr
        )
        _handler(server, lsp.TEXT_DOCUMENT_FOLDING_RANGE)(
            lsp.FoldingRangeParams(
                text_document=lsp.TextDocumentIdentifier(uri="file:///missing.pine")
            )
        )

        _handler(server, lsp.TEXT_DOCUMENT_SELECTION_RANGE)(
            lsp.SelectionRangeParams(
                text_document=lsp.TextDocumentIdentifier(uri=URI),
                positions=[lsp.Position(line=2, character=1)],
            )
        )
        _handler(server, lsp.TEXT_DOCUMENT_SELECTION_RANGE)(
            lsp.SelectionRangeParams(
                text_document=lsp.TextDocumentIdentifier(uri="file:///missing.pine"),
                positions=[lsp.Position(line=0, character=0)],
            )
        )

        colors = _handler(server, lsp.TEXT_DOCUMENT_DOCUMENT_COLOR)(
            lsp.DocumentColorParams(text_document=lsp.TextDocumentIdentifier(uri=URI))
        )
        assert "document_color" in doc.feature_cache
        assert (
            _handler(server, lsp.TEXT_DOCUMENT_DOCUMENT_COLOR)(
                lsp.DocumentColorParams(text_document=lsp.TextDocumentIdentifier(uri=URI))
            )
            is colors
        )
        _handler(server, lsp.TEXT_DOCUMENT_DOCUMENT_COLOR)(
            lsp.DocumentColorParams(
                text_document=lsp.TextDocumentIdentifier(uri="file:///missing.pine")
            )
        )
        _handler(server, lsp.TEXT_DOCUMENT_COLOR_PRESENTATION)(
            lsp.ColorPresentationParams(
                text_document=lsp.TextDocumentIdentifier(uri=URI),
                color=lsp.Color(red=1.0, green=0.0, blue=0.0, alpha=1.0),
                range=lsp.Range(
                    start=lsp.Position(line=4, character=4),
                    end=lsp.Position(line=4, character=11),
                ),
            )
        )
        _handler(server, lsp.TEXT_DOCUMENT_COLOR_PRESENTATION)(
            lsp.ColorPresentationParams(
                text_document=lsp.TextDocumentIdentifier(uri="file:///missing.pine"),
                color=lsp.Color(red=1.0, green=0.0, blue=0.0, alpha=1.0),
                range=lsp.Range(
                    start=lsp.Position(line=0, character=0),
                    end=lsp.Position(line=0, character=1),
                ),
            )
        )

        links = _handler(server, lsp.TEXT_DOCUMENT_DOCUMENT_LINK)(
            lsp.DocumentLinkParams(text_document=lsp.TextDocumentIdentifier(uri=URI))
        )
        assert "document_link" in doc.feature_cache
        assert (
            _handler(server, lsp.TEXT_DOCUMENT_DOCUMENT_LINK)(
                lsp.DocumentLinkParams(text_document=lsp.TextDocumentIdentifier(uri=URI))
            )
            is links
        )
        _handler(server, lsp.TEXT_DOCUMENT_DOCUMENT_LINK)(
            lsp.DocumentLinkParams(
                text_document=lsp.TextDocumentIdentifier(uri="file:///missing.pine")
            )
        )
        if links:
            _handler(server, lsp.DOCUMENT_LINK_RESOLVE)(links[0])

        tokens = _handler(server, lsp.TEXT_DOCUMENT_SEMANTIC_TOKENS_FULL)(
            lsp.SemanticTokensParams(text_document=lsp.TextDocumentIdentifier(uri=URI))
        )
        assert "semantic_tokens" in doc.feature_cache
        assert (
            _handler(server, lsp.TEXT_DOCUMENT_SEMANTIC_TOKENS_FULL)(
                lsp.SemanticTokensParams(text_document=lsp.TextDocumentIdentifier(uri=URI))
            )
            is tokens
        )
        _handler(server, lsp.TEXT_DOCUMENT_SEMANTIC_TOKENS_FULL)(
            lsp.SemanticTokensParams(
                text_document=lsp.TextDocumentIdentifier(uri="file:///missing.pine")
            )
        )
        _handler(server, lsp.TEXT_DOCUMENT_SEMANTIC_TOKENS_RANGE)(
            lsp.SemanticTokensRangeParams(
                text_document=lsp.TextDocumentIdentifier(uri=URI),
                range=full_range,
            )
        )
        _handler(server, lsp.TEXT_DOCUMENT_SEMANTIC_TOKENS_RANGE)(
            lsp.SemanticTokensRangeParams(
                text_document=lsp.TextDocumentIdentifier(uri="file:///missing.pine"),
                range=full_range,
            )
        )
