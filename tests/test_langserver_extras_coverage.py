from __future__ import annotations

import ast as pyast
import base64
import importlib
import sys

from pathlib import Path
from types import ModuleType
from types import SimpleNamespace
from typing import Any
from unittest import mock

import pytest

from lsprotocol import types as lsp


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

URI = "file:///test-extra.pine"


def _ih_params(uri: str = URI) -> lsp.InlayHintParams:
    return lsp.InlayHintParams(
        text_document=lsp.TextDocumentIdentifier(uri=uri),
        range=lsp.Range(start=lsp.Position(line=0, character=0), end=lsp.Position(line=50, character=0)),
    )


def _ref_params(line: int, character: int, *, include_declaration: bool = True) -> lsp.ReferenceParams:
    return lsp.ReferenceParams(
        text_document=lsp.TextDocumentIdentifier(uri=URI),
        position=lsp.Position(line=line, character=character),
        context=lsp.ReferenceContext(include_declaration=include_declaration),
    )


# ---------------------------------------------------------------------------
# server.py — _debounce_seconds
# ---------------------------------------------------------------------------


class TestDebounceSeconds:
    def test_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from pynescript.langserver.server import _debounce_seconds

        monkeypatch.delenv("PYNESCRIPT_LSP_DEBOUNCE_MS", raising=False)
        assert _debounce_seconds() == pytest.approx(0.25)

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from pynescript.langserver.server import _debounce_seconds

        monkeypatch.setenv("PYNESCRIPT_LSP_DEBOUNCE_MS", "100")
        assert _debounce_seconds() == pytest.approx(0.10)

    def test_env_invalid_falls_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from pynescript.langserver.server import _debounce_seconds

        monkeypatch.setenv("PYNESCRIPT_LSP_DEBOUNCE_MS", "bogus")
        assert _debounce_seconds() == pytest.approx(0.25)

    def test_env_negative_clamped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from pynescript.langserver.server import _debounce_seconds

        monkeypatch.setenv("PYNESCRIPT_LSP_DEBOUNCE_MS", "-50")
        assert _debounce_seconds() == 0


# ---------------------------------------------------------------------------
# server.py — _collect_workspace_symbols + init
# ---------------------------------------------------------------------------


class TestCollectWorkspaceSymbols:
    def _doc(self, source: str) -> Any:
        from pynescript.ast.helper import parse

        return SimpleNamespace(ast=parse(source))

    def test_function_and_variable(self) -> None:
        from pynescript.langserver.server import _collect_workspace_symbols

        doc = self._doc('//@version=5\nindicator("T")\nlength = 14\nmyFunction() =>\n    1\n')
        syms = _collect_workspace_symbols(doc, URI)
        by_name = {s.name: s.kind for s in syms}
        assert by_name["length"] == lsp.SymbolKind.Variable
        assert by_name["myFunction"] == lsp.SymbolKind.Function
        assert all(s.location.uri == URI for s in syms)

    def test_type_and_enum(self) -> None:
        from pynescript.langserver.server import _collect_workspace_symbols

        doc = self._doc('//@version=5\nindicator("T")\ntype MySettings\n    int size = 10\nenum Side\n    buy\n')
        syms = _collect_workspace_symbols(doc, URI)
        by_name = {s.name: s.kind for s in syms}
        assert by_name["MySettings"] == lsp.SymbolKind.Class
        assert by_name["Side"] == lsp.SymbolKind.Enum

    def test_no_ast(self) -> None:
        from pynescript.langserver.server import _collect_workspace_symbols

        assert _collect_workspace_symbols(SimpleNamespace(ast=None), URI) == []


class TestServerInit:
    def test_init_state(self) -> None:
        from pynescript.langserver.server import PynescriptLanguageServer
        from pynescript.langserver.workspace import Workspace

        server = PynescriptLanguageServer()
        try:
            assert isinstance(server.pine_workspace, Workspace)
            assert server._pending_diag_tasks == {}
            assert server._diag_executor._max_workers == 1
        finally:
            server._diag_executor.shutdown(wait=False, cancel_futures=True)

    def test_cancel_unknown_uri_noop(self) -> None:
        from pynescript.langserver.server import PynescriptLanguageServer

        server = PynescriptLanguageServer()
        try:
            assert server._cancel_pending_diagnostics("file:///never-opened.pine") is None
        finally:
            server._diag_executor.shutdown(wait=False, cancel_futures=True)


# ---------------------------------------------------------------------------
# features/inlay_hints.py
# ---------------------------------------------------------------------------


class TestInlayHints:
    def test_empty_source(self) -> None:
        from pynescript.langserver.features.inlay_hints import handle_inlay_hints

        assert handle_inlay_hints(_ih_params(), "") == []
        assert handle_inlay_hints(_ih_params(), None) == []

    def test_none_tree(self) -> None:
        from pynescript.langserver.features.inlay_hints import handle_inlay_hints

        assert handle_inlay_hints(_ih_params(), "x = 1", tree=None) is None

    def test_parse_failure_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import pynescript.langserver.features.inlay_hints as ih

        def _boom(*args: Any, **kwargs: Any) -> Any:
            msg = "parse boom"
            raise RuntimeError(msg)

        monkeypatch.setattr(ih, "parse", _boom)
        assert ih.handle_inlay_hints(_ih_params(), "x = 1") is None

    def test_const_int_hint(self) -> None:
        from pynescript.langserver.features.inlay_hints import handle_inlay_hints

        hints = handle_inlay_hints(_ih_params(), '//@version=5\nindicator("T")\nlength = 14\n')
        assert hints is not None and len(hints) == 1
        hint = hints[0]
        assert hint.label == ": const int"
        assert hint.kind == lsp.InlayHintKind.Type
        assert hint.position.line == 2
        assert hint.position.character == len("length")

    def test_explicit_type_skipped(self) -> None:
        from pynescript.langserver.features.inlay_hints import handle_inlay_hints

        hints = handle_inlay_hints(_ih_params(), '//@version=6\nindicator("T")\nint length = 14\n')
        assert hints == []

    def test_builtin_var_and_input(self) -> None:
        from pynescript.langserver.features.inlay_hints import handle_inlay_hints

        hints = handle_inlay_hints(_ih_params(), '//@version=6\nindicator("T")\nc = close\nn = input.int(5, "n")\n')
        assert hints is not None
        assert {h.label for h in hints} == {": series float", ": input int"}

    def test_unknown_rhs_no_hint(self) -> None:
        from pynescript.langserver.features.inlay_hints import handle_inlay_hints

        hints = handle_inlay_hints(_ih_params(), '//@version=5\nindicator("T")\nx = a + b\n')
        assert hints == []

    def test_constant_types(self) -> None:
        from pynescript.langserver.features.inlay_hints import _constant_type

        true_value = True
        assert _constant_type(true_value) == "const bool"
        assert _constant_type(3) == "const int"
        assert _constant_type(3.5) == "const float"
        assert _constant_type("s") == "const string"
        assert _constant_type(None) is None
        assert _constant_type((1, 2)) is None

    def test_call_type_unknown_module(self) -> None:
        from pynescript.ast import node as ast
        from pynescript.langserver.features.inlay_hints import _call_type

        call = ast.Call(func=ast.Attribute(value=ast.Name(id="foo"), attr="bar"), args=[])
        assert _call_type(call) is None
        plain = ast.Call(func=ast.Name(id="plot"), args=[])
        assert _call_type(plain) is None

    def test_infer_name_unknown(self) -> None:
        from pynescript.ast import node as ast
        from pynescript.langserver.features.inlay_hints import _infer_type

        assert _infer_type(ast.Name(id="something_unknown")) is None


# ---------------------------------------------------------------------------
# features/references.py extras
# ---------------------------------------------------------------------------


class TestReferencesExtras:
    SRC = '//@version=5\nindicator("Test")\nlength = 14\nplot(ta.sma(close, length))\n'

    def test_none_source(self) -> None:
        from pynescript.langserver.features.references import handle_references

        assert handle_references(_ref_params(3, 25), None, URI) == []

    def test_no_word_at_cursor(self) -> None:
        from pynescript.langserver.features.references import handle_references

        assert handle_references(_ref_params(0, 0), "//@version=5\n", URI) == []

    def test_none_tree(self) -> None:
        from pynescript.langserver.features.references import handle_references

        assert handle_references(_ref_params(3, 25), self.SRC, URI, tree=None) == []

    def test_dedup_same_line(self) -> None:
        from pynescript.langserver.features.references import ReferencesFinder

        finder = ReferencesFinder("x", URI, include_declaration=True)
        finder._add_location("x", 2)
        finder._add_location("x", 2)
        assert len(finder.locations) == 1

    def test_store_excluded_when_flag_false(self) -> None:
        from pynescript.ast import node as ast
        from pynescript.langserver.features.references import ReferencesFinder

        finder = ReferencesFinder("length", URI, include_declaration=False)
        finder.visit_Name(ast.Name(id="length", ctx=ast.Store()))
        assert finder.locations == [] and finder.declaration_found is False

    def test_function_def_excluded_when_flag_false(self) -> None:
        from pynescript.ast import node as ast
        from pynescript.langserver.features.references import ReferencesFinder

        finder = ReferencesFinder("f", URI, include_declaration=False)
        finder.visit_FunctionDef(ast.FunctionDef(name="f", body=[]))
        assert finder.locations == []

    def test_attribute_and_call_visitors(self) -> None:
        from pynescript.ast import node as ast
        from pynescript.langserver.features.references import ReferencesFinder

        finder = ReferencesFinder("Side.buy", URI, include_declaration=True)
        finder.visit_Attribute(ast.Attribute(value=ast.Name(id="Side"), attr="buy"))
        assert len(finder.locations) == 1
        finder2 = ReferencesFinder("foo", URI, include_declaration=True)
        finder2.visit_Call(ast.Call(func=ast.Name(id="foo"), args=[ast.Name(id="foo")]))
        assert len(finder2.locations) == 1  # call site deduped by line

    def test_typedef_and_enumdef(self) -> None:
        from pynescript.ast import node as ast
        from pynescript.langserver.features.references import ReferencesFinder

        finder = ReferencesFinder("MyType", URI, include_declaration=True)
        finder.visit_TypeDef(ast.TypeDef(name="MyType", body=[]))
        assert finder.declaration_found is True
        finder2 = ReferencesFinder("Side", URI, include_declaration=True)
        finder2.visit_EnumDef(ast.EnumDef(name="Side", body=[]))
        assert finder2.declaration_found is True


# ---------------------------------------------------------------------------
# ext/jupyter.py
# ---------------------------------------------------------------------------


class TestJupyter:
    def test_sample_data_shape(self) -> None:
        from pynescript.ext.jupyter import create_sample_data

        data = create_sample_data(10)
        assert set(data) == {"open", "high", "low", "close", "volume"}
        assert all(len(v) == 10 for v in data.values())
        assert all(h >= min(o, c) for o, c, h in zip(data["open"], data["close"], data["high"], strict=True))

    def test_evaluate_error_path(self) -> None:
        from pynescript.ext.jupyter import create_sample_data
        from pynescript.ext.jupyter import evaluate_indicator

        result = evaluate_indicator("this is not valid pine @#$", create_sample_data(5))
        assert "error" in result

    def test_evaluate_ok(self) -> None:
        from pynescript.ext.jupyter import create_sample_data
        from pynescript.ext.jupyter import evaluate_indicator

        result = evaluate_indicator('//@version=6\nindicator("T")\nx = 1\n', create_sample_data(5))
        assert isinstance(result, dict) and "error" not in result

    def test_display_without_pandas(self) -> None:
        import pynescript.ext.jupyter as jup

        assert sys.modules.get("pandas") is None
        assert jup.display_indicator_table({"a": [1.0, 2.0]}, rows=1) is None

    def test_display_with_fake_pandas(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import pynescript.ext.jupyter as jup

        class FakeDF:
            def __init__(self, data: Any) -> None:
                self.data = data

            def __getitem__(self, cols: Any) -> FakeDF:
                return self

            def head(self, rows: int) -> str:
                return f"head-{rows}"

        fake_pd = ModuleType("pandas")
        fake_pd.DataFrame = FakeDF  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "pandas", fake_pd)
        assert jup.display_indicator_table({"a": [1.0]}, rows=3) == "head-3"

    def test_load_extension_no_ipython(self) -> None:
        from pynescript.ext.jupyter import load_ipython_extension

        assert sys.modules.get("IPython") is None
        with pytest.raises(ImportError):
            load_ipython_extension(object())

    def test_load_extension_fake_ipython(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from pynescript.ext.jupyter import load_ipython_extension

        seen: dict[str, Any] = {}

        def fake_register_cell_magic(func: Any) -> Any:
            seen["magic"] = func.__name__
            return func

        fake_magic = ModuleType("IPython.core.magic")
        fake_magic.register_cell_magic = fake_register_cell_magic  # type: ignore[attr-defined]
        fake_core = ModuleType("IPython.core")
        fake_ipython = ModuleType("IPython")
        monkeypatch.setitem(sys.modules, "IPython", fake_ipython)
        monkeypatch.setitem(sys.modules, "IPython.core", fake_core)
        monkeypatch.setitem(sys.modules, "IPython.core.magic", fake_magic)

        ns: dict[str, Any] = {}
        load_ipython_extension(SimpleNamespace(user_ns=ns))
        assert seen["magic"] == "pinescript"
        assert {"pine_parse", "pine_unparse", "pine_lint"} <= set(ns)


# ---------------------------------------------------------------------------
# ext/pygments/lexers.py
# ---------------------------------------------------------------------------


class TestPygmentsLexer:
    def test_registry(self) -> None:
        from pynescript.ext.pygments.lexers import PinescriptLexer

        assert "pinescript" in PinescriptLexer.aliases
        assert "*.pine" in PinescriptLexer.filenames

    def test_tokens(self) -> None:
        from pygments.token import Token

        from pynescript.ext.pygments.lexers import PinescriptLexer

        toks = list(PinescriptLexer().get_tokens_unprocessed('//@version=5\nindicator("T")\nx = 14\n'))
        assert len(toks) > 5
        assert all(len(t) == 3 for t in toks)
        kinds = {t[1] for t in toks}
        assert Token.Name in kinds or Token.Keyword in kinds

    def test_indent_dedent_skipped(self) -> None:
        from pynescript.ext.pygments.lexers import PinescriptLexer

        src = '//@version=5\nindicator("T")\nif close > open\n    x = 1\n'
        toks = list(PinescriptLexer().get_tokens_unprocessed(src))
        assert all(isinstance(t[2], str) for t in toks)


# ---------------------------------------------------------------------------
# ext/nautilus_trader/strategy.py (stubbed optional dependency)
# ---------------------------------------------------------------------------


def _ensure_nautilus_stubs() -> None:
    if "pynescript.ext.nautilus_trader.strategy" in sys.modules:
        return
    for name in [
        "nautilus_trader",
        "nautilus_trader.config",
        "nautilus_trader.model",
        "nautilus_trader.model.data",
        "nautilus_trader.model.identifiers",
        "nautilus_trader.model.instruments",
        "nautilus_trader.trading",
        "nautilus_trader.trading.strategy",
    ]:
        sys.modules.setdefault(name, ModuleType(name))

    class StrategyConfig:
        def __init__(self, **kwargs: Any) -> None:
            for key, value in kwargs.items():
                setattr(self, key, value)

    class Strategy:
        def __init__(self, config: Any) -> None:
            self.config = config

    sys.modules["nautilus_trader.config"].StrategyConfig = StrategyConfig  # type: ignore[attr-defined]
    sys.modules["nautilus_trader.model.data"].Bar = type("Bar", (), {})  # type: ignore[attr-defined]
    sys.modules["nautilus_trader.model.data"].BarType = type("BarType", (), {})  # type: ignore[attr-defined]
    sys.modules["nautilus_trader.model.data"].TradeTick = type("TradeTick", (), {})  # type: ignore[attr-defined]
    sys.modules["nautilus_trader.model.identifiers"].InstrumentId = type("InstrumentId", (), {})  # type: ignore[attr-defined]
    sys.modules["nautilus_trader.model.instruments"].Instrument = type("Instrument", (), {})  # type: ignore[attr-defined]
    sys.modules["nautilus_trader.trading.strategy"].Strategy = Strategy  # type: ignore[attr-defined]


class TestNautilusStrategy:
    def _strategy_mod(self) -> Any:
        _ensure_nautilus_stubs()
        return importlib.import_module("pynescript.ext.nautilus_trader.strategy")

    def test_import_and_config(self) -> None:
        mod = self._strategy_mod()
        assert hasattr(mod, "PinescriptStrategy") and hasattr(mod, "PinescriptStrategyConfig")
        cfg = mod.PinescriptStrategyConfig(instrument_id="BTCUSDT", bar_type="1-MIN")
        assert cfg.instrument_id == "BTCUSDT"

    def test_lifecycle(self) -> None:
        mod = self._strategy_mod()
        cfg = mod.PinescriptStrategyConfig(instrument_id="X", bar_type="B")
        strat = mod.PinescriptStrategy(cfg)
        assert strat.instrument is None
        strat.cache = SimpleNamespace(instrument=lambda iid: f"inst-{iid}")
        strat.request_bars = mock.Mock()
        strat.subscribe_bars = mock.Mock()
        strat.subscribe_trade_ticks = mock.Mock()
        strat.on_start()
        assert strat.instrument == "inst-X"
        strat.request_bars.assert_called_once_with("B")
        assert strat.on_bar(object()) is None
        assert strat.on_trade_tick(object()) is None
        assert strat.on_reset() is None

    def test_on_stop(self) -> None:
        mod = self._strategy_mod()
        cfg = mod.PinescriptStrategyConfig(instrument_id="X", bar_type="B")
        strat = mod.PinescriptStrategy(cfg)
        strat.cancel_all_orders = mock.Mock()
        strat.close_all_positions = mock.Mock()
        strat.unsubscribe_bars = mock.Mock()
        strat.on_stop()
        strat.cancel_all_orders.assert_called_once_with("X")
        strat.unsubscribe_bars.assert_called_once_with("B")


# ---------------------------------------------------------------------------
# langserver/providers/metadata_decrypt.py
# ---------------------------------------------------------------------------


class _FakeFernet:
    def __init__(self, key: bytes) -> None:
        self.key = key

    def encrypt(self, data: bytes) -> bytes:
        return base64.urlsafe_b64encode(data)

    def decrypt(self, token: bytes) -> bytes:
        return base64.urlsafe_b64decode(token)


def _stub_fernet(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_leaf = ModuleType("cryptography.fernet")
    fake_leaf.Fernet = _FakeFernet  # type: ignore[attr-defined]
    fake_root = ModuleType("cryptography")
    fake_root.fernet = fake_leaf  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "cryptography", fake_root)
    monkeypatch.setitem(sys.modules, "cryptography.fernet", fake_leaf)


class TestMetadataDecrypt:
    def _mdec(self) -> Any:
        return importlib.import_module("pynescript.langserver.providers.metadata_decrypt")

    def test_no_key_raises(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        mdec = self._mdec()
        monkeypatch.setattr(mdec, "_fernet_key", None)
        monkeypatch.setattr(mdec, "_PROVIDERS_DIR", tmp_path)
        monkeypatch.delenv("PYNESCRIPT_METADATA_KEY", raising=False)
        with pytest.raises(RuntimeError):
            mdec._get_fernet_key()

    def test_env_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mdec = self._mdec()
        monkeypatch.setattr(mdec, "_fernet_key", None)
        monkeypatch.setenv("PYNESCRIPT_METADATA_KEY", "env-key-material")
        assert mdec._get_fernet_key() == b"env-key-material"

    def test_cached_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mdec = self._mdec()
        monkeypatch.setattr(mdec, "_fernet_key", b"cached")
        assert mdec._get_fernet_key() == b"cached"

    def test_round_trip(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        import hashlib
        import json

        mdec = self._mdec()
        _stub_fernet(monkeypatch)
        payload = {"ta.sma": {"label": "ta.sma"}}
        plaintext = json.dumps(payload).encode()
        enc = tmp_path / "meta.enc"
        sha = tmp_path / "meta.sha"
        enc.write_bytes(_FakeFernet(b"k").encrypt(plaintext))
        sha.write_text(hashlib.sha256(plaintext).hexdigest()[:16] + "\n")
        monkeypatch.setattr(mdec, "_METADATA_ENC", enc)
        monkeypatch.setattr(mdec, "_METADATA_SHA", sha)
        monkeypatch.setattr(mdec, "_fernet_key", b"k")
        assert mdec.load_encrypted_metadata() == payload

    def test_integrity_mismatch(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        mdec = self._mdec()
        _stub_fernet(monkeypatch)
        enc = tmp_path / "meta.enc"
        sha = tmp_path / "meta.sha"
        enc.write_bytes(_FakeFernet(b"k").encrypt(b'{"a": 1}'))
        sha.write_text("0" * 16)
        monkeypatch.setattr(mdec, "_METADATA_ENC", enc)
        monkeypatch.setattr(mdec, "_METADATA_SHA", sha)
        monkeypatch.setattr(mdec, "_fernet_key", b"k")
        with pytest.raises(ValueError):
            mdec.load_encrypted_metadata()

    def test_plaintext_preferred(self) -> None:
        mdec = self._mdec()
        data = mdec.get_metadata_cached()
        assert isinstance(data, dict) and len(data) > 400

    def test_missing_both_raises(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        mdec = self._mdec()
        monkeypatch.setattr(mdec, "_METADATA_PLAIN", tmp_path / "no.json")
        monkeypatch.setattr(mdec, "_METADATA_ENC", tmp_path / "no.enc")
        with pytest.raises(FileNotFoundError):
            mdec.get_metadata_cached()


# ---------------------------------------------------------------------------
# ast/grammar/asdl/tool/asdlgen.py
# ---------------------------------------------------------------------------


class TestAsdlgen:
    def test_internals_and_builtins(self) -> None:
        from pynescript.ast.grammar.asdl.tool.asdlgen import PythonGenerator

        gen = PythonGenerator()
        assert len(gen._generate_internals()) == 4
        assert len(gen._generate_builtin_types()) == 4
        base = gen._generate_base()
        assert base.name == "AST"
        exports = gen._generate_exports(["A", "B"])
        assert isinstance(exports, pyast.Assign)

    def test_attributes_helpers(self) -> None:
        import ast as _ast

        from pynescript.ast.grammar.asdl.tool.asdlgen import PythonGenerator

        gen = PythonGenerator()
        target = _ast.Name(id="x", ctx=_ast.Store())
        annotation = _ast.Name(id="int", ctx=_ast.Load())
        field = _ast.AnnAssign(target=target, annotation=annotation, simple=1)
        fixed = gen._fix_attributes([field])
        assert fixed[0].value is not None
        assert isinstance(gen._assign_fields([field]), _ast.AnnAssign)
        assert isinstance(gen._assign_attributes([field]), _ast.AnnAssign)

    def test_visit_field_qualifiers(self) -> None:
        import pyasdl

        from pynescript.ast.grammar.asdl.tool.asdlgen import PythonGenerator

        tree = pyasdl.parse("module T { expr = Foo(int a, int? b, int* c) }")
        fields = tree.body[0].value.types[0].fields
        gen = PythonGenerator()
        plain, opt, seq = (gen.visit_Field(f) for f in fields)
        assert plain.value is not None and seq.value is not None
        assert isinstance(opt.annotation, pyast.BinOp)
        assert isinstance(seq.annotation, pyast.Subscript)

    def test_visit_field_invalid_qualifier(self) -> None:
        from pynescript.ast.grammar.asdl.tool.asdlgen import PythonGenerator

        gen = PythonGenerator()
        with pytest.raises(ValueError):
            gen.visit_Field(SimpleNamespace(name="x", kind="int", qualifier="bogus"))

    def test_defaults_none(self) -> None:
        import pyasdl

        from pynescript.ast.grammar.asdl.tool.asdlgen import PythonGenerator

        tree = pyasdl.parse("module T { expr = Foo(int a) }")
        gen = PythonGenerator(defaults="none")
        assert gen.visit_Field(tree.body[0].value.types[0].fields[0]).value is None

    def test_generate_module(self) -> None:
        import pyasdl

        from pynescript.ast.grammar.asdl.tool.asdlgen import PythonGenerator

        tree = pyasdl.parse("module T { expr = Constant(int value) }")
        stub = PythonGenerator().generate(tree)
        assert isinstance(stub, pyast.Module)
        src = pyast.unparse(pyast.fix_missing_locations(stub))
        assert "class Constant" in src and "__all__" in src

    def test_main(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        from pynescript.ast.grammar.asdl.tool import asdlgen

        src = tmp_path / "M.asdl"
        out = tmp_path / "Out.py"
        src.write_text("module M { expr = Constant(int value) }\n", encoding="utf-8")
        monkeypatch.setattr(sys, "argv", ["asdlgen", str(src), "-o", str(out)])
        asdlgen.main()
        assert "class Constant" in out.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# grammar generate tools (mocked subprocess — no ANTLR run)
# ---------------------------------------------------------------------------


class TestGenerateTools:
    def test_asdl_generate_main(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from pynescript.ast.grammar.asdl.tool import generate as asdl_gen

        calls: list[Any] = []

        def _check_call(cmd: Any, *args: Any, **kwargs: Any) -> int:
            calls.append(cmd)
            return 0

        def _noop(*args: Any, **kwargs: Any) -> Any:
            return None

        monkeypatch.setattr(asdl_gen.subprocess, "check_call", _check_call)
        monkeypatch.setattr(asdl_gen.subprocess, "call", _noop)
        monkeypatch.setattr(asdl_gen.shutil, "which", _noop)
        monkeypatch.setattr(asdl_gen.shutil, "copy", _noop)
        asdl_gen.main()
        assert len(calls) == 1 and "-o" in calls[0]

    def test_antlr4_generate_main(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from pynescript.ast.grammar.antlr4.tool import generate as antlr_gen

        calls: list[Any] = []

        def _check_call(cmd: Any, *args: Any, **kwargs: Any) -> int:
            calls.append(cmd)
            return 0

        def _noop(*args: Any, **kwargs: Any) -> Any:
            return None

        monkeypatch.setattr(antlr_gen.subprocess, "check_call", _check_call)
        monkeypatch.setattr(antlr_gen.shutil, "copy", _noop)
        antlr_gen.main()
        assert len(calls) == 1 and "-Dlanguage=Python3" in calls[0]


# ---------------------------------------------------------------------------
# ast/__main__.py and langserver/__main__.py
# ---------------------------------------------------------------------------


class TestAstMain:
    def test_help(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from pynescript.ast import __main__ as ast_main

        monkeypatch.setattr(sys, "argv", ["pynescript.ast", "--help"])
        with pytest.raises(SystemExit) as exc:
            ast_main.main()
        assert exc.value.code == 0

    def test_main_prints_dump(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: Any) -> None:
        from pynescript.ast import __main__ as ast_main
        from pynescript.ast.helper import parse as real_parse

        pine = tmp_path / "t.pine"
        pine.write_bytes(b'//@version=5\nindicator("T")\nx = 1\n')
        monkeypatch.setattr(sys, "argv", ["pynescript.ast", str(pine)])
        monkeypatch.setattr(ast_main, "parse", lambda src, *a: real_parse(src.decode(), *a))
        ast_main.main()
        assert "Script" in capsys.readouterr().out

    def test_main_eval_mode_attrs(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: Any) -> None:
        from pynescript.ast import __main__ as ast_main
        from pynescript.ast.helper import parse as real_parse

        pine = tmp_path / "e.pine"
        pine.write_bytes(b"close > open")
        monkeypatch.setattr(sys, "argv", ["pynescript.ast", str(pine), "--mode", "eval", "--include-attributes"])
        monkeypatch.setattr(ast_main, "parse", lambda src, *a, **k: real_parse(src.decode(), *a, **k))
        ast_main.main()
        assert "Compare" in capsys.readouterr().out


class TestLangserverMain:
    def test_main_starts_io(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import pynescript.langserver.__main__ as ls_main

        started: list[bool] = []

        class FakeServer:
            def start_io(self) -> None:
                started.append(True)

        monkeypatch.setattr(ls_main, "PynescriptLanguageServer", FakeServer)
        ls_main.main()
        assert started == [True]


# ---------------------------------------------------------------------------
# protocol/constants.py + langserver/config.py
# ---------------------------------------------------------------------------


class TestProtocolConstants:
    def test_severity_map(self) -> None:
        from pynescript.langserver.protocol.constants import DIAGNOSTIC_SEVERITY_MAP

        assert DIAGNOSTIC_SEVERITY_MAP["E"] == lsp.DiagnosticSeverity.Error
        assert DIAGNOSTIC_SEVERITY_MAP["W"] == lsp.DiagnosticSeverity.Warning
        assert set(DIAGNOSTIC_SEVERITY_MAP) == {"E", "W", "C", "I"}

    def test_completion_kinds(self) -> None:
        from pynescript.langserver.protocol.constants import COMPLETION_ITEM_KINDS

        assert COMPLETION_ITEM_KINDS["function"] == lsp.CompletionItemKind.Function
        assert COMPLETION_ITEM_KINDS["keyword"] == lsp.CompletionItemKind.Keyword

    def test_symbol_kinds(self) -> None:
        from pynescript.langserver.protocol.constants import SYMBOL_KINDS

        assert SYMBOL_KINDS["function"] == lsp.SymbolKind.Function
        assert SYMBOL_KINDS["variable"] == lsp.SymbolKind.Variable


class TestConfigExtras:
    def test_capabilities_sync(self) -> None:
        from pynescript.langserver.config import get_server_capabilities

        caps = get_server_capabilities()
        assert caps.text_document_sync and caps.text_document_sync.open_close is True
        assert caps.completion_provider and caps.completion_provider.resolve_provider is True
        assert caps.inlay_hint_provider is not None

    def test_token_legends(self) -> None:
        from pynescript.langserver.config import semantic_token_modifiers
        from pynescript.langserver.config import semantic_token_types

        assert "function" in semantic_token_types()
        assert "declaration" in semantic_token_modifiers()

    def test_filter_options(self) -> None:
        from pynescript.langserver.config import get_filter_options

        patterns = [f["pattern"] for f in get_filter_options()]
        assert "**/*.pine" in patterns


# ---------------------------------------------------------------------------
# ast/transformer.py
# ---------------------------------------------------------------------------


class TestNodeTransformer:
    def test_replace(self) -> None:
        from pynescript.ast import node as ast
        from pynescript.ast.transformer import NodeTransformer

        class Replacer(NodeTransformer):
            def visit_Constant(self, node: ast.Constant) -> Any:  # noqa: N802
                if node.value == 1:
                    return ast.Constant(value=99)
                return node

        tree = Replacer().visit(ast.Script(body=[ast.Assign(target=ast.Name(id="x"), value=ast.Constant(value=1))]))
        assert isinstance(tree, ast.Script)
        assign = tree.body[0]
        assert isinstance(assign, ast.Assign) and assign.value.value == 99

    def test_delete_from_list(self) -> None:
        from pynescript.ast import node as ast
        from pynescript.ast.transformer import NodeTransformer

        class Deleter(NodeTransformer):
            def visit_Assign(self, node: ast.Assign) -> Any:  # noqa: N802
                return None

        script = ast.Script(
            body=[
                ast.Assign(target=ast.Name(id="x"), value=ast.Constant(value=1)),
                ast.Assign(target=ast.Name(id="y"), value=ast.Constant(value=2)),
            ]
        )
        out = Deleter().visit(script)
        assert isinstance(out, ast.Script) and out.body == []

    def test_splice_list(self) -> None:
        from pynescript.ast import node as ast
        from pynescript.ast.transformer import NodeTransformer

        class Splicer(NodeTransformer):
            def visit_Constant(self, node: ast.Constant) -> Any:  # noqa: N802
                if node.value == 1:
                    return [ast.Constant(value=1), ast.Constant(value=2)]
                return node

        script = ast.Script(body=[ast.Expr(value=ast.Constant(value=1))])
        out = Splicer().visit(script)
        assert isinstance(out, ast.Script)
        expr = out.body[0]
        assert isinstance(expr, ast.Expr) and isinstance(expr.value, list) and len(expr.value) == 2

    def test_scalar_replace(self) -> None:
        from pynescript.ast import node as ast
        from pynescript.ast.transformer import NodeTransformer

        class Renamer(NodeTransformer):
            def visit_Name(self, node: ast.Name) -> Any:  # noqa: N802
                if isinstance(node.id, str):
                    return ast.Name(id=node.id.upper())
                return node

        assign = ast.Assign(target=ast.Name(id="x"), value=ast.Constant(value=1))
        out = Renamer().visit(assign)
        assert isinstance(out, ast.Assign) and out.target.id == "X"
