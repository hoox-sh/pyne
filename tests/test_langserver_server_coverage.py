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


def _drive_generator(gen: Any) -> Any:
    """Run a pygls builtin generator handler to its ``InitializeResult``."""
    try:
        handler, args, kwargs = next(gen)
    except StopIteration as stop:
        return stop.value
    while True:
        result = handler(*(args or ()), **(kwargs or {}))
        try:
            handler, args, kwargs = gen.send(result)
        except StopIteration as stop:
            return stop.value


@pytest.fixture()
def server(monkeypatch: pytest.MonkeyPatch):
    """Language server with publish-diagnostics captured into a list."""
    monkeypatch.setenv("PYNESCRIPT_LSP_DEBOUNCE_MS", "0")
    published: list[lsp.PublishDiagnosticsParams] = []
    srv = PynescriptLanguageServer()
    monkeypatch.setattr(
        srv,
        "text_document_publish_diagnostics",
        published.append,
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

    def test_pygls_initialize_advertises_semantic_token_legend(self, server: PynescriptLanguageServer) -> None:
        """Drive pygls' builtin initialize, which rebuilds capabilities.

        The user ``initialize`` handler's ``ServerCapabilities`` are discarded.
        Semantic tokens are advertised only when the full/range handlers were
        registered with a ``SemanticTokensLegend``.
        """
        from pynescript.__about__ import __version__
        from pynescript.langserver.config import semantic_token_modifiers
        from pynescript.langserver.config import semantic_token_types

        params = lsp.InitializeParams(
            process_id=None,
            capabilities=lsp.ClientCapabilities(
                text_document=lsp.TextDocumentClientCapabilities(
                    semantic_tokens=lsp.SemanticTokensClientCapabilities(
                        requests=lsp.ClientSemanticTokensRequestOptions(range=True, full=True),
                        token_types=[],
                        token_modifiers=[],
                        formats=[lsp.TokenFormat.Relative],
                    )
                )
            ),
            client_info=lsp.ClientInfo(name="handshake", version="0"),
        )
        builtin = server.protocol.fm.builtin_features[lsp.INITIALIZE]
        result = _drive_generator(builtin(params))
        assert isinstance(result, lsp.InitializeResult)
        assert result.server_info is not None
        assert result.server_info.version == __version__ == "0.7.0"

        provider = result.capabilities.semantic_tokens_provider
        assert isinstance(provider, lsp.SemanticTokensOptions)
        assert list(provider.legend.token_types) == list(semantic_token_types())
        assert list(provider.legend.token_types[-2:]) == ["series", "simple"]
        assert list(provider.legend.token_modifiers) == list(semantic_token_modifiers())
        assert provider.full is True
        assert provider.range is True

    def test_pyne_lsp_version_flag(self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
        from pynescript.__about__ import __version__
        from pynescript.langserver.__main__ import main

        monkeypatch.setattr("sys.argv", ["pyne-lsp", "--version"])
        main()
        assert capsys.readouterr().out.strip() == __version__ == "0.7.0"


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
                        lsp.TextDocumentContentChangeWholeDocument(text='//@version=5\nindicator("U")\n'),
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
        async def _run() -> None:
            missing = await _handler(server, lsp.TEXT_DOCUMENT_DIAGNOSTIC)(
                lsp.DocumentDiagnosticParams(
                    text_document=lsp.TextDocumentIdentifier(uri="file:///gone.pine"),
                )
            )
            assert missing.kind == lsp.DocumentDiagnosticReportKind.Full
            assert missing.items == []
            assert missing.result_id is None

            _open(server)
            present = await _handler(server, lsp.TEXT_DOCUMENT_DIAGNOSTIC)(
                lsp.DocumentDiagnosticParams(
                    text_document=lsp.TextDocumentIdentifier(uri=URI),
                )
            )
            assert present.kind == lsp.DocumentDiagnosticReportKind.Full
            assert present.result_id is not None
            assert present.result_id.startswith(URI)

        asyncio.run(_run())

    def test_pull_after_change_is_not_stale(self, server: PynescriptLanguageServer) -> None:
        """A pull that races the debounced parse must not serve old findings."""

        async def _run() -> None:
            uri = "file:///stale-pull.pine"
            broken = '//@version=6\nindicator("T")\nplot(ta.\n'
            fixed = '//@version=6\nindicator("T")\nplot(close)\n'
            _open(server, uri=uri, text=broken)
            before = await _handler(server, lsp.TEXT_DOCUMENT_DIAGNOSTIC)(
                lsp.DocumentDiagnosticParams(text_document=lsp.TextDocumentIdentifier(uri=uri))
            )
            assert [d.code for d in before.items] == ["E001"]

            # Long debounce: the pull below arrives before the push task ran.
            await _handler(server, lsp.TEXT_DOCUMENT_DID_CHANGE)(
                lsp.DidChangeTextDocumentParams(
                    text_document=lsp.VersionedTextDocumentIdentifier(uri=uri, version=2),
                    content_changes=[lsp.TextDocumentContentChangeWholeDocument(text=fixed)],
                )
            )
            after = await _handler(server, lsp.TEXT_DOCUMENT_DIAGNOSTIC)(
                lsp.DocumentDiagnosticParams(text_document=lsp.TextDocumentIdentifier(uri=uri))
            )
            assert after.items == []
            assert after.result_id == f"{uri}-2"

        asyncio.run(_run())

    def test_workspace_diagnostics(self, server: PynescriptLanguageServer) -> None:
        async def _run() -> None:
            empty = await _handler(server, lsp.WORKSPACE_DIAGNOSTIC)(
                lsp.WorkspaceDiagnosticParams(previous_result_ids=[])
            )
            assert empty.items == []

            _open(server)
            _open(server, uri="file:///other.pine", text='indicator("no version")\n')
            report = await _handler(server, lsp.WORKSPACE_DIAGNOSTIC)(
                lsp.WorkspaceDiagnosticParams(previous_result_ids=[])
            )
            uris = {item.uri for item in report.items}
            assert URI in uris
            assert "file:///other.pine" in uris

            server.settings["diagnosticsEnabled"] = False
            disabled = await _handler(server, lsp.WORKSPACE_DIAGNOSTIC)(
                lsp.WorkspaceDiagnosticParams(previous_result_ids=[])
            )
            assert disabled.items == []
            server.settings["diagnosticsEnabled"] = True

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# New language features (declaration, typeDefinition, call hierarchy, lens, inline)
# ---------------------------------------------------------------------------


class TestNewLanguageFeatures:
    def test_capabilities_advertise_new_providers(self, server: PynescriptLanguageServer) -> None:
        params = lsp.InitializeParams(
            process_id=None,
            capabilities=lsp.ClientCapabilities(),
            client_info=lsp.ClientInfo(name="features", version="0"),
        )
        builtin = server.protocol.fm.builtin_features[lsp.INITIALIZE]
        result = _drive_generator(builtin(params))
        caps = result.capabilities
        assert caps.declaration_provider is True
        assert caps.type_definition_provider is True
        assert caps.call_hierarchy_provider is not None
        assert caps.code_lens_provider is not None
        assert caps.inline_completion_provider is not None
        for method in (
            lsp.TEXT_DOCUMENT_DECLARATION,
            lsp.TEXT_DOCUMENT_TYPE_DEFINITION,
            lsp.TEXT_DOCUMENT_PREPARE_CALL_HIERARCHY,
            lsp.CALL_HIERARCHY_INCOMING_CALLS,
            lsp.CALL_HIERARCHY_OUTGOING_CALLS,
            lsp.TEXT_DOCUMENT_CODE_LENS,
            lsp.TEXT_DOCUMENT_INLINE_COMPLETION,
        ):
            assert method in server.protocol.fm.features

    def test_type_definition_and_call_hierarchy_handlers(self, server: PynescriptLanguageServer) -> None:
        source = '//@version=6\nindicator("T")\ntype Point\n    float x\np = Point.new(1.0)\nplot(p)\n'
        _open(server, text=source)
        type_def = _handler(server, lsp.TEXT_DOCUMENT_TYPE_DEFINITION)(
            lsp.TypeDefinitionParams(
                text_document=lsp.TextDocumentIdentifier(uri=URI),
                position=lsp.Position(line=4, character=0),
            )
        )
        assert type_def is not None
        assert type_def[0].range.start.line == 2

        prepared = _handler(server, lsp.TEXT_DOCUMENT_PREPARE_CALL_HIERARCHY)(
            lsp.CallHierarchyPrepareParams(
                text_document=lsp.TextDocumentIdentifier(uri=URI),
                position=lsp.Position(line=2, character=5),
            )
        )
        assert prepared is None  # cursor on `Point` is a type, not a function

    def test_code_lens_respects_setting(self, server: PynescriptLanguageServer) -> None:
        _open(server, text='//@version=5\nstrategy("S")\nplot(close)\n')
        params = lsp.CodeLensParams(text_document=lsp.TextDocumentIdentifier(uri=URI))
        server.settings["codeLensEnabled"] = False
        assert _handler(server, lsp.TEXT_DOCUMENT_CODE_LENS)(params) == []
        server.settings["codeLensEnabled"] = True
        lenses = _handler(server, lsp.TEXT_DOCUMENT_CODE_LENS)(params)
        assert [lens.command.title for lens in lenses] == ["Convert to v6"]

    def test_inline_completion_respects_setting(self, server: PynescriptLanguageServer) -> None:
        _open(server, text='//@version=6\nindicator("T")\nta.sma(\n')
        params = lsp.InlineCompletionParams(
            text_document=lsp.TextDocumentIdentifier(uri=URI),
            position=lsp.Position(line=2, character=7),
            context=lsp.InlineCompletionContext(trigger_kind=lsp.InlineCompletionTriggerKind.Invoked),
        )
        server.settings["inlineCompletionEnabled"] = False
        assert _handler(server, lsp.TEXT_DOCUMENT_INLINE_COMPLETION)(params) is None
        server.settings["inlineCompletionEnabled"] = True
        result = _handler(server, lsp.TEXT_DOCUMENT_INLINE_COMPLETION)(params)
        assert result is not None
        assert result.items[0].insert_text == "close, 14)"

    def test_settings_change_refreshes_code_lenses(
        self, server: PynescriptLanguageServer, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[Any] = []
        monkeypatch.setattr(server, "workspace_code_lens_refresh", calls.append)
        server.protocol.client_capabilities = lsp.ClientCapabilities(
            workspace=lsp.WorkspaceClientCapabilities(
                code_lens=lsp.CodeLensWorkspaceClientCapabilities(refresh_support=True),
            )
        )
        _handler(server, lsp.WORKSPACE_DID_CHANGE_CONFIGURATION)(
            lsp.DidChangeConfigurationParams(settings={"codeLensEnabled": False})
        )
        assert calls == [None]


class TestEnsureDiagnosticsCurrent:
    def test_retries_when_edit_lands_during_parse(
        self, server: PynescriptLanguageServer, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _run() -> None:
            _open(server)
            doc = server.pine_workspace.get_document(URI)
            assert doc is not None
            doc.source = '//@version=5\nindicator("U")\n'
            doc.version = 2
            calls: list[int] = []

            def _parse(target: Any) -> None:
                calls.append(target.version)
                if len(calls) == 1:
                    target.source = '//@version=5\nindicator("V")\n'
                    target.version = 3
                    return
                target.ast_version = target.version

            monkeypatch.setattr(server.pine_workspace, "_parse_and_lint", _parse)
            await server._ensure_diagnostics_current(doc)
            assert calls == [2, 3]
            assert doc.ast_version == 3

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# Diagnostic refresh (pull-model clients)
# ---------------------------------------------------------------------------


class TestDiagnosticRefresh:
    def _client_with_refresh(self) -> lsp.ClientCapabilities:
        return lsp.ClientCapabilities(
            workspace=lsp.WorkspaceClientCapabilities(
                diagnostics=lsp.DiagnosticWorkspaceClientCapabilities(refresh_support=True),
            )
        )

    def test_refresh_requested_after_open_when_supported(
        self, server: PynescriptLanguageServer, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[Any] = []
        monkeypatch.setattr(server, "workspace_diagnostic_refresh", calls.append)
        server.protocol.client_capabilities = self._client_with_refresh()

        _open(server)

        assert calls == [None]

    def test_refresh_skipped_when_client_does_not_advertise_it(
        self, server: PynescriptLanguageServer, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[Any] = []
        monkeypatch.setattr(server, "workspace_diagnostic_refresh", calls.append)
        server.protocol.client_capabilities = lsp.ClientCapabilities()

        _open(server)

        assert calls == []

    def test_refresh_requested_after_debounced_publish(
        self, server: PynescriptLanguageServer, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _run() -> None:
            calls: list[Any] = []
            monkeypatch.setattr(server, "workspace_diagnostic_refresh", calls.append)

            _open(server)
            # Only the debounced publish should refresh, not the open above.
            server.protocol.client_capabilities = self._client_with_refresh()
            await _handler(server, lsp.TEXT_DOCUMENT_DID_CHANGE)(
                lsp.DidChangeTextDocumentParams(
                    text_document=lsp.VersionedTextDocumentIdentifier(uri=URI, version=2),
                    content_changes=[lsp.TextDocumentContentChangeWholeDocument(text=SRC)],
                )
            )
            await _drain_diags(server)

            assert calls == [None]

        asyncio.run(_run())


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

    def test_publish_after_exception_swallowed(
        self, server: PynescriptLanguageServer, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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

        hover = _handler(server, lsp.TEXT_DOCUMENT_HOVER)(self._pos_params(lsp.HoverParams, line=3, character=5))
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

        _handler(server, lsp.TEXT_DOCUMENT_DEFINITION)(self._pos_params(lsp.DefinitionParams, line=2, character=1))
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
            lsp.DocumentSymbolParams(text_document=lsp.TextDocumentIdentifier(uri="file:///missing.pine"))
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
        assert lsp.INLAY_HINT_RESOLVE not in server.protocol.fm.features
        if ih:
            assert all(hint.text_edits is None for hint in ih)
            assert all(hint.data is None for hint in ih)

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
            lsp.FoldingRangeParams(text_document=lsp.TextDocumentIdentifier(uri="file:///missing.pine"))
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
            lsp.DocumentColorParams(text_document=lsp.TextDocumentIdentifier(uri="file:///missing.pine"))
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
            lsp.DocumentLinkParams(text_document=lsp.TextDocumentIdentifier(uri="file:///missing.pine"))
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
            lsp.SemanticTokensParams(text_document=lsp.TextDocumentIdentifier(uri="file:///missing.pine"))
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
