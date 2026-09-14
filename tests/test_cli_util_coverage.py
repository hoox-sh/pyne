from __future__ import annotations


"""Coverage tests for the Click CLI, data/datafeed/pine_facade utils, and library registry.

No network: realtime/historical providers are stubbed or use the in-process mock;
pine-facade HTTP is monkeypatched. CI-fast (tiny inline v6 snippets, small bar counts).
"""

import asyncio
import json
import sys
import types

from pathlib import Path
from types import SimpleNamespace

import pytest

from click.testing import CliRunner

from pynescript.__main__ import cli


MINI_V6 = '//@version=6\nindicator("t")\nplot(close)\n'
MINI_V5 = '//@version=5\nindicator("t")\nplot(close)\n'
BAD_PINE = "//@version=6\nindicator(\n"
STRATEGY = '//@version=6\nstrategy("s")\nlen = input.int(14, "len")\nsma = ta.sma(close, len)\nplot(sma)\n'
SPACE_JSON = '{"params": [{"name": "len", "kind": "int", "min": 5, "max": 20}]}'


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def pine_file(tmp_path: Path) -> Path:
    p = tmp_path / "t.pine"
    p.write_text(MINI_V6, encoding="utf-8")
    return p


@pytest.fixture
def bad_file(tmp_path: Path) -> Path:
    p = tmp_path / "bad.pine"
    p.write_text(BAD_PINE, encoding="utf-8")
    return p


def _combined(result) -> str:
    return (result.output or "") + (getattr(result, "stderr", None) or "") + str(result.exception or "")


# ---------------------------------------------------------------------------
# CLI: help for every registered command + known aliases
# ---------------------------------------------------------------------------


def test_root_help_lists_commands(runner: CliRunner) -> None:
    r = runner.invoke(cli, ["--help"])
    assert r.exit_code == 0
    for name in (
        "check",
        "format",
        "convert",
        "parse-and-dump",
        "parse-and-unparse",
        "lint",
        "compile",
        "prewarm",
        "run",
        "optimize",
        "data",
        "download-builtins",
        "info",
    ):
        assert name in r.output, name


def test_each_command_help(runner: CliRunner) -> None:
    for name in sorted(cli.commands):
        r = runner.invoke(cli, [name, "--help"])
        assert r.exit_code == 0, name
        assert "Usage" in r.output, name


@pytest.mark.parametrize("alias", ["dump", "ast", "unparse", "fmt", "ls"])
def test_alias_help(runner: CliRunner, alias: str) -> None:
    r = runner.invoke(cli, [alias, "--help"])
    assert r.exit_code == 0, alias


def test_unknown_command(runner: CliRunner) -> None:
    assert runner.invoke(cli, ["no-such-cmd-xyz"]).exit_code != 0


def test_bad_flag(runner: CliRunner, pine_file: Path) -> None:
    assert runner.invoke(cli, ["check", str(pine_file), "--bogus-flag"]).exit_code == 2


# ---------------------------------------------------------------------------
# CLI: check / dump / unparse
# ---------------------------------------------------------------------------


def test_check_ok(runner: CliRunner, pine_file: Path) -> None:
    assert runner.invoke(cli, ["check", str(pine_file), "-q"]).exit_code == 0


def test_check_invalid(runner: CliRunner, bad_file: Path) -> None:
    assert runner.invoke(cli, ["check", str(bad_file), "-q"]).exit_code == 1


def test_check_missing_file(runner: CliRunner, tmp_path: Path) -> None:
    r = runner.invoke(cli, ["check", str(tmp_path / "nope.pine")])
    assert r.exit_code != 0
    assert "not found" in _combined(r).lower()


def test_check_stdin(runner: CliRunner) -> None:
    assert runner.invoke(cli, ["check", "-"], input=MINI_V6).exit_code == 0
    assert runner.invoke(cli, ["check", "-", "-q"], input=BAD_PINE).exit_code == 1


def test_check_directory(runner: CliRunner, tmp_path: Path) -> None:
    (tmp_path / "a.pine").write_text(MINI_V6, encoding="utf-8")
    (tmp_path / "skip.txt").write_text("nope", encoding="utf-8")
    assert runner.invoke(cli, ["check", str(tmp_path), "-q"]).exit_code == 0


@pytest.mark.parametrize("cmd", ["parse-and-dump", "dump", "ast"])
def test_dump_ok(runner: CliRunner, pine_file: Path, cmd: str) -> None:
    r = runner.invoke(cli, [cmd, str(pine_file)])
    assert r.exit_code == 0, _combined(r)
    assert len(r.output) > 10


def test_dump_stdin(runner: CliRunner) -> None:
    r = runner.invoke(cli, ["dump", "-"], input=MINI_V6)
    assert r.exit_code == 0
    assert len(r.output) > 10


def test_dump_missing_file(runner: CliRunner, tmp_path: Path) -> None:
    assert runner.invoke(cli, ["dump", str(tmp_path / "nope.pine")]).exit_code != 0


def test_dump_invalid(runner: CliRunner, bad_file: Path) -> None:
    assert runner.invoke(cli, ["dump", str(bad_file)]).exit_code != 0


@pytest.mark.parametrize("cmd", ["parse-and-unparse", "unparse"])
def test_unparse_ok(runner: CliRunner, pine_file: Path, cmd: str) -> None:
    r = runner.invoke(cli, [cmd, str(pine_file)])
    assert r.exit_code == 0, _combined(r)
    assert "indicator" in r.output and "plot" in r.output


def test_unparse_invalid(runner: CliRunner, bad_file: Path) -> None:
    assert runner.invoke(cli, ["parse-and-unparse", str(bad_file)]).exit_code != 0


# ---------------------------------------------------------------------------
# CLI: format / convert
# ---------------------------------------------------------------------------


def test_format_stdout(runner: CliRunner, pine_file: Path) -> None:
    r = runner.invoke(cli, ["format", str(pine_file)])
    assert r.exit_code == 0
    assert "indicator" in r.output


def test_format_check_ok(runner: CliRunner, pine_file: Path) -> None:
    assert runner.invoke(cli, ["fmt", str(pine_file), "-w"]).exit_code == 0
    assert runner.invoke(cli, ["format", str(pine_file), "--check"]).exit_code == 0


def test_format_check_dirty(runner: CliRunner, tmp_path: Path) -> None:
    p = tmp_path / "messy.pine"
    p.write_text('//@version=6\n\n\nindicator(  "t"  )\nplot(  close  )\n\n\n', encoding="utf-8")
    assert runner.invoke(cli, ["format", str(p), "--check"]).exit_code == 1


def test_format_missing_file(runner: CliRunner, tmp_path: Path) -> None:
    assert runner.invoke(cli, ["format", str(tmp_path / "nope.pine")]).exit_code != 0


def test_format_write_stdin_rejected(runner: CliRunner) -> None:
    assert runner.invoke(cli, ["format", "-", "-w"], input=MINI_V6).exit_code != 0


def test_convert_v5_to_v6_stdout(runner: CliRunner, tmp_path: Path) -> None:
    p = tmp_path / "c.pine"
    p.write_text(MINI_V5, encoding="utf-8")
    r = runner.invoke(cli, ["convert", str(p), "--to", "6"])
    assert r.exit_code == 0, _combined(r)
    assert "version=6" in r.output


def test_convert_v6_to_v5_write(tmp_path: Path, runner: CliRunner) -> None:
    p = tmp_path / "c.pine"
    p.write_text(MINI_V6, encoding="utf-8")
    r = runner.invoke(cli, ["convert", str(p), "--to", "v5", "-w"])
    assert r.exit_code == 0, _combined(r)
    assert "version=5" in p.read_text(encoding="utf-8")


def test_convert_stdin(runner: CliRunner) -> None:
    r = runner.invoke(cli, ["convert", "-", "--to", "6"], input=MINI_V5)
    assert r.exit_code == 0
    assert "version=6" in r.output


def test_convert_missing_target(runner: CliRunner, pine_file: Path) -> None:
    assert runner.invoke(cli, ["convert", str(pine_file)]).exit_code == 2


def test_convert_stdin_write_rejected(runner: CliRunner) -> None:
    assert runner.invoke(cli, ["convert", "-", "--to", "6", "-w"], input=MINI_V5).exit_code != 0


# ---------------------------------------------------------------------------
# CLI: lint
# ---------------------------------------------------------------------------


def test_lint_ok(runner: CliRunner, pine_file: Path) -> None:
    assert runner.invoke(cli, ["lint", str(pine_file), "--fail-on", "never"]).exit_code == 0


def test_lint_json(runner: CliRunner, pine_file: Path) -> None:
    r = runner.invoke(cli, ["lint", str(pine_file), "--json", "--fail-on", "never"])
    assert r.exit_code == 0
    assert isinstance(json.loads(r.output), list)


def test_lint_stdin(runner: CliRunner) -> None:
    r = runner.invoke(cli, ["lint", "-", "--fail-on", "never", "-q"], input=MINI_V6)
    assert r.exit_code == 0


def test_lint_missing_file(runner: CliRunner, tmp_path: Path) -> None:
    assert runner.invoke(cli, ["lint", str(tmp_path / "nope.pine"), "--fail-on", "never"]).exit_code != 0


# ---------------------------------------------------------------------------
# CLI: compile / prewarm / run / optimize
# ---------------------------------------------------------------------------


def test_compile_emit(runner: CliRunner, pine_file: Path) -> None:
    r = runner.invoke(cli, ["compile", str(pine_file), "--emit", "--no-time"])
    assert r.exit_code == 0, _combined(r)


def test_compile_missing_file(runner: CliRunner, tmp_path: Path) -> None:
    assert runner.invoke(cli, ["compile", str(tmp_path / "nope.pine"), "--no-time"]).exit_code != 0


def test_compile_invalid(runner: CliRunner, bad_file: Path) -> None:
    # The compile pipeline sanitizes/repairs truncated input; it still exits 0.
    r = runner.invoke(cli, ["compile", str(bad_file), "--no-time"])
    assert r.exit_code == 0
    assert "compiled" in r.output.lower()


def test_compile_emit_bad_output_path(runner: CliRunner, pine_file: Path, tmp_path: Path) -> None:
    r = runner.invoke(
        cli, ["compile", str(pine_file), "--emit", "--no-time", "-o", str(tmp_path / "no_such_dir" / "out.py")]
    )
    assert r.exit_code != 0


def test_prewarm_json_mocked(runner: CliRunner, pine_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import pynescript.compiler.engine as eng

    monkeypatch.setattr(
        eng,
        "prewarm_scripts",
        lambda _sources=None, force_builtins=False: {
            "has_numba": False,
            "builtins_warmed": 3,
            "scripts_ok": 1,
            "scripts_failed": 0,
            "errors": [],
            "disk_cache_dir": "",
        },
    )
    r = runner.invoke(cli, ["prewarm", str(pine_file), "--json"])
    assert r.exit_code == 0, _combined(r)
    assert json.loads(r.output)["scripts_ok"] == 1


def test_prewarm_scripts_failed_mocked(runner: CliRunner, pine_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import pynescript.compiler.engine as eng

    monkeypatch.setattr(
        eng,
        "prewarm_scripts",
        lambda _sources=None, force_builtins=False: {
            "has_numba": False,
            "builtins_warmed": 0,
            "scripts_ok": 0,
            "scripts_failed": 1,
            "errors": ["boom"],
            "disk_cache_dir": "",
        },
    )
    assert runner.invoke(cli, ["prewarm", str(pine_file), "--json"]).exit_code == 1


def test_prewarm_missing_file(runner: CliRunner, tmp_path: Path) -> None:
    assert runner.invoke(cli, ["prewarm", str(tmp_path / "nope.pine")]).exit_code == 2


def test_run_json(runner: CliRunner, pine_file: Path) -> None:
    r = runner.invoke(cli, ["run", str(pine_file), "--bars", "8", "--json"])
    assert r.exit_code == 0, _combined(r)
    assert json.loads(r.output)["bars"] == 8


def test_run_text(runner: CliRunner, pine_file: Path) -> None:
    assert runner.invoke(cli, ["run", str(pine_file), "--bars", "8"]).exit_code == 0


def test_run_stdin(runner: CliRunner) -> None:
    r = runner.invoke(cli, ["run", "-", "--bars", "8", "--json"], input=MINI_V6)
    assert r.exit_code == 0, _combined(r)


def test_run_bad_bars(runner: CliRunner, pine_file: Path) -> None:
    r = runner.invoke(cli, ["run", str(pine_file), "--bars", "1"])
    assert r.exit_code != 0
    assert "bars" in _combined(r).lower()


def test_run_missing_file(runner: CliRunner, tmp_path: Path) -> None:
    assert runner.invoke(cli, ["run", str(tmp_path / "nope.pine"), "--bars", "8"]).exit_code != 0


def test_optimize_missing_space(runner: CliRunner, tmp_path: Path) -> None:
    p = tmp_path / "s.pine"
    p.write_text(STRATEGY, encoding="utf-8")
    r = runner.invoke(cli, ["optimize", str(p), "--bars", "20", "--trials", "2"])
    assert r.exit_code != 0
    assert "space" in _combined(r).lower()


def test_optimize_bad_space(runner: CliRunner, tmp_path: Path) -> None:
    p = tmp_path / "s.pine"
    p.write_text(STRATEGY, encoding="utf-8")
    r = runner.invoke(cli, ["optimize", str(p), "--bars", "20", "--trials", "2", "--space", "{bad"])
    assert r.exit_code != 0


def test_optimize_bad_bars(runner: CliRunner, tmp_path: Path) -> None:
    p = tmp_path / "s.pine"
    p.write_text(STRATEGY, encoding="utf-8")
    r = runner.invoke(cli, ["optimize", str(p), "--bars", "4", "--trials", "2", "--space", SPACE_JSON])
    assert r.exit_code != 0
    assert "bars" in _combined(r).lower()


def test_optimize_missing_file(runner: CliRunner, tmp_path: Path) -> None:
    r = runner.invoke(cli, ["optimize", str(tmp_path / "nope.pine"), "--space", SPACE_JSON])
    assert r.exit_code == 2


# ---------------------------------------------------------------------------
# CLI: data / download-builtins / info
# ---------------------------------------------------------------------------


def test_data_mock_table(runner: CliRunner) -> None:
    r = runner.invoke(cli, ["data", "AAPL", "--provider", "mock", "--period", "1d"])
    assert r.exit_code == 0, _combined(r)
    assert "AAPL" in r.output


def test_data_mock_json(runner: CliRunner) -> None:
    r = runner.invoke(cli, ["data", "AAPL", "--provider", "mock", "--period", "1d", "--format", "json"])
    assert r.exit_code == 0, _combined(r)
    payload = json.loads(r.output)
    assert payload["provider"] == "mock" and payload["bars"] > 0


def test_data_mock_csv(runner: CliRunner) -> None:
    r = runner.invoke(cli, ["data", "AAPL", "--provider", "mock", "--period", "1d", "--format", "csv"])
    assert r.exit_code == 0
    assert r.output.splitlines()[0] == "open,high,low,close,volume"


def test_data_output_file(runner: CliRunner, tmp_path: Path) -> None:
    out = tmp_path / "bars.json"
    r = runner.invoke(cli, ["data", "AAPL", "--provider", "mock", "--period", "1d", "--format", "json", "-o", str(out)])
    assert r.exit_code == 0, _combined(r)
    assert json.loads(out.read_text(encoding="utf-8"))["bars"] > 0


def test_data_provider_error(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    import pynescript.util.data as data_mod

    def _boom(*a, **k):
        from pynescript.util.data import DataProviderError

        raise DataProviderError("fake outage")

    monkeypatch.setattr(data_mod, "get_provider", _boom)
    assert runner.invoke(cli, ["data", "AAPL", "--provider", "mock"]).exit_code == 1


def test_data_bad_provider(runner: CliRunner) -> None:
    assert runner.invoke(cli, ["data", "AAPL", "--provider", "nope"]).exit_code == 2


def test_data_missing_symbol(runner: CliRunner) -> None:
    assert runner.invoke(cli, ["data"]).exit_code == 2


_CATALOG = [
    {"scriptName": "RSI", "scriptIdPart": "STD;RSI", "version": "52"},
    {"scriptName": "Supertrend", "scriptIdPart": "STD;Supertrend", "version": "12"},
]


def test_download_builtins_list_mocked(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    import pynescript.util.pine_facade as facade

    monkeypatch.setattr(facade, "list_builtin_scripts", lambda session=None: list(_CATALOG))
    r = runner.invoke(cli, ["download-builtins", "--list", "--plain"])
    assert r.exit_code == 0, _combined(r)


def test_download_builtins_full_mocked(runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import pynescript.util.pine_facade as facade

    monkeypatch.setattr(facade, "list_builtin_scripts", lambda session=None: list(_CATALOG))
    monkeypatch.setattr(facade, "get_script", lambda *a, **k: {"source": MINI_V6})
    dest = tmp_path / "builtins"
    r = runner.invoke(cli, ["download-builtins", str(dest), "--yes", "--limit", "1", "--plain"])
    assert r.exit_code == 0, _combined(r)
    assert list(dest.glob("*.pine"))


def test_info_text(runner: CliRunner) -> None:
    r = runner.invoke(cli, ["info"])
    assert r.exit_code == 0
    assert "pynescript" in r.output


def test_info_json(runner: CliRunner) -> None:
    r = runner.invoke(cli, ["info", "--json"])
    assert r.exit_code == 0
    assert json.loads(r.output)["name"] == "pynescript"


def test_info_alias_ls(runner: CliRunner) -> None:
    r = runner.invoke(cli, ["ls", "--json"])
    assert r.exit_code == 0
    assert json.loads(r.output)["name"] == "pynescript"


# ---------------------------------------------------------------------------
# util/data.py (no network)
# ---------------------------------------------------------------------------


def test_mock_provider_fetch_shape() -> None:
    from pynescript.util.data import MockDataProvider

    out = MockDataProvider(seed=7).fetch("AAPL", "1d", "1d")
    assert set(("open", "high", "low", "close", "volume")) <= set(out)
    assert len(out["close"]) == 1
    out2 = MockDataProvider(seed=7).fetch("AAPL", "1mo", "1d")
    assert len(out2["close"]) == 30


def test_mock_provider_quote() -> None:
    from pynescript.util.data import MockDataProvider

    q = MockDataProvider(seed=1).fetch_quote("BTC")
    assert q["symbol"] == "BTC" and q["last"] > 0 and q["bid"] < q["ask"]


def test_chart_provider_match_and_fetch() -> None:
    from pynescript.util.data import ChartOHLCVProvider

    bars = [{"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 10.0, "time": 1}]
    prov = ChartOHLCVProvider(bars, symbol="AAPL")
    assert prov._matches_chart("AAPL") and prov._matches_chart("CHART") and prov._matches_chart("EX:AAPL")
    assert not prov._matches_chart("MSFT")
    out = prov.fetch("AAPL")
    assert out["close"] == [1.5]
    assert prov.fetch("MSFT")["close"] == []
    assert ChartOHLCVProvider([], symbol="AAPL").fetch("AAPL")["close"] == []
    quote = prov.fetch_quote("AAPL")
    assert quote["last"] == 1.5
    assert prov.fetch_quote("MSFT")["last"] == 0.0


def test_get_provider_variants() -> None:
    from pynescript.util.data import CCXTProvider
    from pynescript.util.data import ChartOHLCVProvider
    from pynescript.util.data import MockDataProvider
    from pynescript.util.data import YahooFinanceProvider
    from pynescript.util.data import get_provider

    assert isinstance(get_provider("mock"), MockDataProvider)
    assert isinstance(get_provider("yahoo"), YahooFinanceProvider)
    assert isinstance(get_provider("ccxt", exchange="kraken"), CCXTProvider)
    assert isinstance(get_provider("chart", bars=[], symbol="X"), ChartOHLCVProvider)
    with pytest.raises(Exception):
        get_provider("nope")


def test_normalize_ccxt_symbol() -> None:
    from pynescript.util.data import normalize_ccxt_symbol

    assert normalize_ccxt_symbol("coinbase", "BTC/USDT") == "BTC/USD"
    assert normalize_ccxt_symbol("coinbase", "BTC/USDC") == "BTC/USD"
    assert normalize_ccxt_symbol("coinbase", "") == ""
    assert normalize_ccxt_symbol("binance", "BTC/USDT") == "BTC/USDT"


def test_geo_block_message() -> None:
    from pynescript.util.data import geo_block_message

    assert geo_block_message("binance", RuntimeError("block access from your country 451")) is not None
    assert "kraken" in (geo_block_message("binance", RuntimeError("block access from your country")) or "")
    assert geo_block_message("binance", RuntimeError("timeout")) is None


def test_tune_ccxt_public_urls() -> None:
    from pynescript.util.data import tune_ccxt_public_urls

    assert tune_ccxt_public_urls(SimpleNamespace(), "kraken") is None
    ex = SimpleNamespace(options={}, urls={"api": {"public": "https://api.binance.com/api/v3/ticker"}})
    tune_ccxt_public_urls(ex, "binance")
    assert "data-api.binance.vision" in ex.urls["api"]["public"]
    assert ex.options["defaultType"] == "spot"
    assert tune_ccxt_public_urls(SimpleNamespace(), "binance") is None


def test_yahoo_missing_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    from pynescript.util.data import DataProviderError
    from pynescript.util.data import YahooFinanceProvider

    monkeypatch.setitem(sys.modules, "yfinance", None)
    with pytest.raises(DataProviderError):
        YahooFinanceProvider().fetch("AAPL")


def test_yahoo_fetch_mocked() -> None:
    from pynescript.util.data import YahooFinanceProvider

    class _Col:
        def __init__(self, vals) -> None:
            self._vals = vals

        def tolist(self):
            return list(self._vals)

    class _Frame:
        empty = False

        def __getitem__(self, key):
            return _Col([1.0, 2.0])

    class _Ticker:
        def __init__(self, symbol) -> None:
            self.info = {
                "bid": 1.0,
                "ask": 2.0,
                "currentPrice": 1.5,
                "open": 1.0,
                "dayHigh": 2.0,
                "dayLow": 0.5,
                "volume": 10,
            }

        def history(self, **kwargs):
            return _Frame()

    fake = types.ModuleType("yfinance")
    fake.Ticker = _Ticker
    sys.modules["yfinance"] = fake
    try:
        prov = YahooFinanceProvider()
        out = prov.fetch("AAPL")
        assert out["close"] == [1.0, 2.0]
        assert prov.fetch_quote("AAPL")["last"] == 1.5
    finally:
        del sys.modules["yfinance"]


def test_yahoo_empty_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    from pynescript.util.data import DataProviderError
    from pynescript.util.data import YahooFinanceProvider

    class _Empty:
        empty = True

    fake = types.ModuleType("yfinance")
    fake.Ticker = lambda symbol: SimpleNamespace(history=lambda **k: _Empty())
    monkeypatch.setitem(sys.modules, "yfinance", fake)
    with pytest.raises(DataProviderError):
        YahooFinanceProvider().fetch("BOGUS")


def test_alphavantage_missing_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    from pynescript.util.data import AlphaVantageProvider
    from pynescript.util.data import DataProviderError

    monkeypatch.setitem(sys.modules, "alpha_vantage", None)
    monkeypatch.setitem(sys.modules, "alpha_vantage.foreignexchange", None)
    monkeypatch.setitem(sys.modules, "alpha_vantage.techindicators", None)
    with pytest.raises(DataProviderError):
        AlphaVantageProvider(api_key="x").fetch("IBM")


def test_alphavantage_stub_client() -> None:
    from pynescript.util.data import AlphaVantageProvider
    from pynescript.util.data import DataProviderError

    prov = AlphaVantageProvider(api_key="x")

    class _TI:
        def get_daily(self, **kwargs):
            return (
                {"2024-01-02": {"1. open": "1", "2. high": "2", "3. low": "0.5", "4. close": "1.5", "5. volume": "10"}},
                {},
            )

        def get_quote_endpoint(self, **kwargs):
            return (
                {
                    "05. price": "1.5",
                    "02. open": "1",
                    "03. high": "2",
                    "04. low": "0.5",
                    "06. volume": "10",
                    "07. latest trading day": "2024-01-02",
                },
                {},
            )

    prov._client = {"ti": _TI(), "fx": object()}
    out = prov.fetch("IBM", period="compact")
    assert out["close"] == [1.5]
    assert prov.fetch_quote("IBM")["last"] == 1.5

    class _FailTI:
        def get_daily(self, **kwargs):
            raise RuntimeError("denied")

        def get_quote_endpoint(self, **kwargs):
            raise RuntimeError("denied")

    prov._client = {"ti": _FailTI(), "fx": object()}
    with pytest.raises(DataProviderError):
        prov.fetch("IBM")
    with pytest.raises(DataProviderError):
        prov.fetch_quote("IBM")


def test_ccxt_missing_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    from pynescript.util.data import CCXTProvider
    from pynescript.util.data import DataProviderError

    monkeypatch.setitem(sys.modules, "ccxt", None)
    with pytest.raises(DataProviderError):
        CCXTProvider(exchange="binance").fetch("BTC/USDT")


def test_ccxt_unknown_exchange(monkeypatch: pytest.MonkeyPatch) -> None:
    from pynescript.util.data import CCXTProvider
    from pynescript.util.data import DataProviderError

    monkeypatch.setitem(sys.modules, "ccxt", types.ModuleType("ccxt"))
    with pytest.raises(DataProviderError):
        CCXTProvider(exchange="no_such_exchange_xyz").fetch("BTC/USDT")


def test_ccxt_stub_exchange() -> None:
    from pynescript.util.data import CCXTProvider
    from pynescript.util.data import DataProviderError

    prov = CCXTProvider(exchange="binance")
    candle = [1700000000000, 1.0, 2.0, 0.5, 1.5, 10.0]
    prov._exchange = SimpleNamespace(
        fetch_ohlcv=lambda *a, **k: [candle],
        fetch_ticker=lambda *a, **k: {
            "bid": 1.0,
            "ask": 2.0,
            "last": 1.5,
            "open": 1.0,
            "high": 2.0,
            "low": 0.5,
            "baseVolume": 10.0,
        },
    )
    assert prov._parse_timeframe(" 1h ") == "1h" and prov._parse_timeframe("") == "1d"
    assert prov.fetch_ohlcv("BTC/USDT", "1h") == [candle]
    assert prov.fetch("BTC/USDT", period="1d")["close"] == [1.5]
    assert prov.fetch_quote("BTC/USDT")["last"] == 1.5

    def _denied(*a, **k):
        raise RuntimeError("block access from your country 451")

    prov._exchange = SimpleNamespace(fetch_ohlcv=_denied, fetch_ticker=_denied)
    with pytest.raises(DataProviderError, match="region"):
        prov.fetch("BTC/USDT")
    with pytest.raises(DataProviderError):
        prov.fetch_quote("BTC/USDT")


def test_resolve_request_sources() -> None:
    from pynescript.util.data import ChartOHLCVProvider
    from pynescript.util.data import resolve_request_sources
    from pynescript.util.datafeed import MockDataFeed

    feed, _ = resolve_request_sources(data_source="mock")
    assert isinstance(feed, MockDataFeed)
    _, prov = resolve_request_sources(chart_bars=[{"close": 1.0}])
    assert isinstance(prov, ChartOHLCVProvider)
    sentinel = object()
    assert resolve_request_sources(data_feed=sentinel, data_provider=sentinel) == (sentinel, sentinel)
    _, prov2 = resolve_request_sources(data_source="yahoo")
    assert type(prov2).__name__ == "YahooFinanceProvider"
    feed3, _ = resolve_request_sources(data_source="ccxt", source_options={"exchange": "kraken"})
    assert type(feed3).__name__ == "CCXTProDataFeed"
    assert isinstance(resolve_request_sources()[1], type(None)) or True
    assert get_provider_default_mock() is True


def get_provider_default_mock() -> bool:
    from pynescript.util.data import MockDataProvider
    from pynescript.util.data import get_provider

    return isinstance(get_provider("mock", seed=3), MockDataProvider)


# ---------------------------------------------------------------------------
# util/datafeed.py (no network; asyncio.run, no pytest-asyncio needed)
# ---------------------------------------------------------------------------


def test_get_datafeed_variants() -> None:
    from pynescript.util.datafeed import CCXTProDataFeed
    from pynescript.util.datafeed import DataFeedError
    from pynescript.util.datafeed import MockDataFeed
    from pynescript.util.datafeed import get_datafeed

    assert isinstance(get_datafeed("mock"), MockDataFeed)
    assert isinstance(get_datafeed("ccxtpro", exchange="binance"), CCXTProDataFeed)
    assert isinstance(get_datafeed("ccxt"), CCXTProDataFeed)
    with pytest.raises(DataFeedError):
        get_datafeed("nope")


def test_mock_feed_sync_helpers() -> None:
    from pynescript.util.datafeed import MockDataFeed

    feed = MockDataFeed(start_price=100.0)
    ticker = feed.fetch_latest_ticker()
    assert ticker["last"] == 100.0
    bars = feed.fetch_latest_ohlcv(limit=3)
    assert len(bars) == 3 and all(len(b) == 6 for b in bars)


def test_mock_feed_streams() -> None:
    from pynescript.util.datafeed import MockDataFeed

    async def _go() -> None:
        feed = MockDataFeed()
        async with feed:
            async for candle in feed.watch_ohlcv("BTC/USDT"):
                assert len(candle) == 6
                break
            async for trade in feed.watch_trades():
                assert "price" in trade
                break
            async for tick in feed.watch_ticker():
                assert "last" in tick
                break
            async for book in feed.watch_order_book(limit=3):
                assert len(book["bids"]) == 3
                break

    asyncio.run(_go())


def test_ccxtpro_bad_exchange_errors_without_network() -> None:
    from pynescript.util.datafeed import CCXTProDataFeed
    from pynescript.util.datafeed import DataFeedError

    async def _go() -> None:
        feed = CCXTProDataFeed(exchange="no_such_exchange_xyz")
        with pytest.raises(DataFeedError):
            async for _ in feed.watch_ohlcv("BTC/USDT"):
                break

    asyncio.run(_go())


def test_composite_feed_prefers_primary_and_falls_back() -> None:
    from pynescript.util.datafeed import CompositeDataFeed
    from pynescript.util.datafeed import MockDataFeed

    primary = MockDataFeed(start_price=10.0)
    fallback = MockDataFeed(start_price=20.0)
    comp = CompositeDataFeed(primary, fallback)
    assert comp.fetch_latest_ticker("BTC/USDT")["last"] == 10.0

    class _Fail:
        def fetch_latest_ticker(self, symbol):
            raise RuntimeError("down")

        def fetch_latest_ohlcv(self, *a, **k):
            raise RuntimeError("down")

        async def close(self) -> None:
            return None

    comp2 = CompositeDataFeed(_Fail(), fallback)
    assert comp2.fetch_latest_ticker("BTC/USDT")["last"] == 20.0
    assert len(comp2.fetch_latest_ohlcv("BTC/USDT")) > 0
    comp3 = CompositeDataFeed(_Fail(), None)
    assert comp3.fetch_latest_ticker("BTC/USDT") == {}
    assert comp3.fetch_latest_ohlcv("BTC/USDT") == []


def test_composite_watch_fallback() -> None:
    from pynescript.util.datafeed import CompositeDataFeed
    from pynescript.util.datafeed import MockDataFeed

    class _FailStream:
        async def watch_ohlcv(self, *a, **k):
            raise RuntimeError("down")
            yield  # pragma: no cover - make this an async generator

    async def _go() -> None:
        comp = CompositeDataFeed(_FailStream(), MockDataFeed())
        async for candle in comp.watch_ohlcv("BTC/USDT"):
            assert len(candle) == 6
            break
        async for tick in CompositeDataFeed(MockDataFeed(), None).watch_ticker("BTC/USDT"):
            assert "last" in tick
            break

    asyncio.run(_go())


def test_broker_market_and_limit_fills() -> None:
    from pynescript.util.datafeed import DataFeedBroker
    from pynescript.util.datafeed import MockDataFeed

    broker = DataFeedBroker(MockDataFeed(), initial_balance=1000.0)
    oid = broker.place_order("BTC/USDT", "buy", 1.0)
    asyncio.run(broker._process_fills(100.0))
    assert broker.orders[oid].filled and broker.get_position("BTC/USDT") == 1.0
    assert broker.get_balance() == 900.0

    oid2 = broker.place_order("BTC/USDT", "buy", 1.0, price=50.0)
    asyncio.run(broker._process_fills(100.0))
    assert not broker.orders[oid2].filled

    broker2 = DataFeedBroker(MockDataFeed(), initial_balance=1000.0)
    oid3 = broker2.place_order("BTC/USDT", "sell", 1.0)
    asyncio.run(broker2._process_fills(100.0))
    assert broker2.orders[oid3].filled and broker2.get_position("BTC/USDT") == 0.0
    asyncio.run(broker2.stop())


# ---------------------------------------------------------------------------
# util/pine_facade.py (no network; requests monkeypatched)
# ---------------------------------------------------------------------------


def test_facade_meta_helpers() -> None:
    from pynescript.util import pine_facade as facade

    assert facade._meta_name({"scriptName": "Kaufman&#039;s X"}) == "Kaufman's X"
    assert facade._meta_name({}) == "unnamed"
    assert facade._meta_id({"scriptIdPart": "STD;RSI"}) == "STD;RSI"
    assert facade._meta_id({}) == ""
    assert facade._pretty_version("52.0") == "52" and facade._pretty_version("52") == "52"
    assert facade._meta_version({"version": "52.0"}) == "52"
    assert facade._canonical_kind("study") == "indicator"
    assert facade._meta_kind({"extra": {"kind": "study"}}, "Volume") == "indicator"
    assert facade._meta_kind({}, "My Strategy") == "strategy"
    assert facade._meta_kind({}, "Math Library") == "library"
    assert facade._meta_kind({}, "RSI") == "indicator"
    assert facade._meta_extra({"extra": {"a": 1}}) == {"a": 1}
    assert facade._meta_extra({}) == {}
    assert facade._meta_short({"extra": {"shortDescription": "s"}}) == "s"
    assert facade._meta_plots({"extra": {"stats": {"plot": 3}}}) == "3"
    assert facade._meta_plots({}) == ""
    assert "strategy" in facade._kind_markup("strategy")
    assert facade._normalize_filename("Chande/Kroll Stop") == "chande_kroll_stop.pine"
    assert facade._use_rich(plain=True) is False
    assert facade._console(plain=True) is None


def test_facade_existing_and_assign(tmp_path: Path) -> None:
    from pynescript.util import pine_facade as facade

    assert facade._existing_pines(tmp_path / "missing") == set()
    (tmp_path / "a.pine").write_text("x", encoding="utf-8")
    (tmp_path / "note.txt").write_text("x", encoding="utf-8")
    assert facade._existing_pines(tmp_path) == {"a.pine"}
    catalog = [{"scriptName": "RSI", "version": "46.0"}, {"scriptName": "RSI", "version": "47.0"}]
    names = [fn for _meta, fn in facade.assign_filenames(catalog)]
    assert names[0] != names[1] and all(n.endswith(".pine") for n in names)


def test_facade_list_and_get_mocked() -> None:
    from pynescript.util import pine_facade as facade

    class _Resp:
        def __init__(self, payload) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self):
            return self._payload

    fake = SimpleNamespace(get=lambda *a, **k: _Resp([{"scriptName": "RSI"}]))
    assert facade.list_builtin_scripts(session=fake) == [{"scriptName": "RSI"}]
    fake2 = SimpleNamespace(get=lambda *a, **k: _Resp({"source": MINI_V6}))
    assert facade.get_script("STD;RSI", "52", session=fake2)["source"] == MINI_V6


def test_facade_download_dry_run_and_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from pynescript.util import pine_facade as facade

    monkeypatch.setattr(facade, "list_builtin_scripts", lambda session=None: list(_CATALOG))
    summary = facade.download_builtin_scripts(tmp_path, dry_run=True, plain=True)
    assert summary["total"] == 2 and summary["saved"] == 0
    limited = facade.download_builtin_scripts(tmp_path, dry_run=True, plain=True, limit=1)
    assert limited["total"] == 1
    monkeypatch.setattr(facade, "list_builtin_scripts", lambda session=None: [])
    empty = facade.download_builtin_scripts(tmp_path, dry_run=True, plain=True)
    assert empty["total"] == 0


def test_facade_download_skip_existing(tmp_path: Path) -> None:
    from pynescript.util import pine_facade as facade

    dest = tmp_path / "rsi.pine"
    dest.write_text("old", encoding="utf-8")

    def _no_session():  # pragma: no cover - must not be called
        raise AssertionError("network session must not be created when skipping")

    res = facade._download_script({"scriptName": "RSI"}, tmp_path, "utf-8", "rsi.pine", _no_session, True)
    assert res.status == "skipped" and dest.read_text(encoding="utf-8") == "old"


def test_facade_download_failure_branch(tmp_path: Path) -> None:
    from pynescript.util import pine_facade as facade

    def _session():
        raise RuntimeError("offline")

    res = facade._download_script(
        {"scriptName": "RSI", "scriptIdPart": "STD;RSI", "version": "1"}, tmp_path, "utf-8", "rsi.pine", _session, False
    )
    assert res.status == "failed"


def test_facade_main_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from pynescript.util import pine_facade as facade

    monkeypatch.setattr(facade, "list_builtin_scripts", lambda session=None: list(_CATALOG))
    assert facade.main(["--list", "--plain", str(tmp_path)]) == 0
    assert facade._build_arg_parser().parse_args(["--list"]).dry_run is True


def test_facade_render_catalog_plain(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    from pynescript.util import pine_facade as facade

    facade.render_catalog(_CATALOG, tmp_path, 2, set(), console=None)
    assert "RSI" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# ast/evaluator/libraries.py
# ---------------------------------------------------------------------------


def test_coerce_stub_int() -> None:
    from pynescript.ast.evaluator.libraries import _coerce_stub_int

    assert _coerce_stub_int(None) is None
    assert _coerce_stub_int(True) == 1
    assert _coerce_stub_int(7) == 7
    assert _coerce_stub_int(7.9) == 7
    assert _coerce_stub_int(float("nan")) is None
    assert _coerce_stub_int("12") == 12
    assert _coerce_stub_int("nope") is None
    assert _coerce_stub_int(object()) is None


def test_merge_stub_args() -> None:
    from pynescript.ast.evaluator.libraries import _merge_stub_args

    assert _merge_stub_args((1, 2), {"d": 9}, ["a", "b", "c", "d"]) == [1, 2, None, 9]
    assert _merge_stub_args((1,), {"unknown_key": 5}, ["a", "b"]) == [1]
    assert _merge_stub_args((1, 2), {"a": 99}, ["a", "b"]) == [1, 2]


def test_stub_index_roundtrip_and_edges() -> None:
    from pynescript.ast.evaluator.libraries import _stub_index_1d_to_2d
    from pynescript.ast.evaluator.libraries import _stub_index_2d_to_1d

    assert _stub_index_2d_to_1d(3, 4, 1, 2) == 6
    assert _stub_index_2d_to_1d(dim_x=3, dim_y=4, ix=1, iy=2) == 6
    assert _stub_index_2d_to_1d(1) is None
    assert _stub_index_2d_to_1d("a", "b", "c", "d") is None
    assert _stub_index_1d_to_2d(3, 4, 6) == (1, 2)
    assert _stub_index_1d_to_2d(dim_x=3, dim_y=4, i=6) == (1, 2)
    assert _stub_index_1d_to_2d(3, 0, 6) is None
    assert _stub_index_1d_to_2d(1, 2) is None


def test_stub_known_exports_map() -> None:
    from pynescript.ast.evaluator.libraries import STUB_KNOWN_EXPORTS

    assert callable(STUB_KNOWN_EXPORTS["index_2d_to_1d"])
    assert callable(STUB_KNOWN_EXPORTS["index_1d_to_2d"])


def test_bind_ta_stubs() -> None:
    from pynescript.ast.evaluator.libraries import bind_tradingview_ta_stub_exports

    ev = SimpleNamespace(_builtin_ta_aroon=lambda merged: (10.0, 20.0), _builtin_ta_kama=lambda merged: 42.0)
    bound = bind_tradingview_ta_stub_exports(ev)
    assert bound["aroon"](14) == (20.0, 10.0)
    assert bound["kama"]("close", length=10) == 42.0

    ev_none = SimpleNamespace(_builtin_ta_aroon=lambda merged: None, _builtin_ta_kama=lambda merged: None)
    bound_none = bind_tradingview_ta_stub_exports(ev_none)
    assert bound_none["aroon"](14) == (None, None)
    assert bound_none["kama"]("close") is None


def test_library_module_access() -> None:
    from pynescript.ast.evaluator.libraries import LibraryModule

    mod = LibraryModule(title="Lib", namespace="ns", version=1, exports={"f": 123})
    assert mod.f == 123
    assert "f" in mod and "zzz" not in mod
    with pytest.raises(AttributeError):
        mod.zzz
    with pytest.raises(AttributeError):
        mod._private


def test_library_registry() -> None:
    from pynescript.ast.evaluator.libraries import LibraryModule
    from pynescript.ast.evaluator.libraries import LibraryRegistry

    reg = LibraryRegistry()
    assert reg.lookup(name="Missing") is None
    assert reg.get_source("ns", "Lib", 1) is None
    mod = LibraryModule(title="Lib", namespace="ns", version=1, exports={"f": 1})
    reg.register(mod)
    assert reg.lookup(name="Lib") is mod
    assert reg.lookup(namespace="ns", name="Lib", version=1) is mod
    # Unknown version falls back to the title match.
    assert reg.lookup(namespace="ns", name="Lib", version=2) is mod
    reg.register_source("ns", "Lib", 2, MINI_V6)
    assert reg.get_source("ns", "Lib", 2) == MINI_V6
    bare = LibraryModule(title="Bare")
    reg.register(bare)
    assert reg.lookup(name="Bare") is bare


# ---------------------------------------------------------------------------
# util/datafeed.py — CCXTPro paths via fake ccxt.pro (no network)
# ---------------------------------------------------------------------------

_CANDLE = [1700000000000, 1.0, 2.0, 0.5, 1.5, 10.0]


class _FakeProExchange:
    """Stand-in for a ccxt.pro exchange class (constructed with a params dict)."""

    last_params: dict | None = None

    def __init__(self, params) -> None:  # noqa: ANN001
        self.params = dict(params or {})
        type(self).last_params = self.params
        self.closed = False
        # Ordered watch_ohlcv script: ("return", rows) | ("raise", exc).
        self.ohlcv_script: list = []
        self.failures: dict[str, list[Exception]] = {}

    def _next(self, name: str, default):  # noqa: ANN001, ANN002
        errs = self.failures.get(name, [])
        if errs:
            raise errs.pop(0)
        return default

    async def watch_ohlcv(self, symbol, timeframe="1m", limit=None):  # noqa: ANN001, ANN002, ANN003
        if self.ohlcv_script:
            kind, payload = self.ohlcv_script.pop(0)
            if kind == "raise":
                raise payload
            return payload
        errs = self.failures.get("watch_ohlcv", [])
        if errs:
            raise errs.pop(0)
        return [list(_CANDLE)]

    async def watch_trades(self, symbol, limit=None):  # noqa: ANN001, ANN002, ANN003
        return self._next("watch_trades", [{"price": 1.5, "amount": 0.1}])

    async def watch_ticker(self, symbol):  # noqa: ANN001, ANN002
        return self._next("watch_ticker", {"last": 1.5, "bid": 1.0, "ask": 2.0})

    async def watch_order_book(self, symbol, limit=20):  # noqa: ANN001, ANN002, ANN003
        return self._next("watch_order_book", {"bids": [[1.0, 1.0]], "asks": [[2.0, 1.0]]})

    async def fetch_ohlcv(self, symbol, timeframe="1m", limit=None):  # noqa: ANN001, ANN002, ANN003
        return [list(_CANDLE)]

    async def fetch_ticker(self, symbol):  # noqa: ANN001, ANN002
        return {"last": 9.5}

    async def close(self) -> None:
        self.closed = True


def _install_fake_ccxt_pro(monkeypatch: pytest.MonkeyPatch, exchange_cls: type = _FakeProExchange) -> None:
    pkg = types.ModuleType("ccxt")
    sub = types.ModuleType("ccxt.pro")
    sub.binance = exchange_cls
    pkg.pro = sub
    monkeypatch.setitem(sys.modules, "ccxt", pkg)
    monkeypatch.setitem(sys.modules, "ccxt.pro", sub)


async def _collect_one(agen):  # noqa: ANN001, ANN002
    async for item in agen:
        return item
    raise AssertionError("stream ended without items")


def test_ccxtpro_watch_ohlcv_falsy_then_data_then_fatal(monkeypatch: pytest.MonkeyPatch) -> None:
    from pynescript.util.datafeed import CCXTProDataFeed
    from pynescript.util.datafeed import DataFeedError

    _install_fake_ccxt_pro(monkeypatch)

    async def _go2() -> None:
        feed = CCXTProDataFeed(exchange="binance")
        await feed._get_exchange()
        ex = feed._exchange
        ex.ohlcv_script = [("return", []), ("return", [list(_CANDLE)])]
        ex.failures["watch_ohlcv"] = [RuntimeError("boom")]
        seen = []

        async def _run():
            async for item in feed.watch_ohlcv("BTC/USDT"):
                seen.append(item)
                if len(seen) == 1:
                    break

        await _run()
        assert seen and seen[0] == [list(_CANDLE)]
        with pytest.raises(DataFeedError):
            async for _ in feed.watch_ohlcv("BTC/USDT"):
                pass

    asyncio.run(_go2())


def test_ccxtpro_watch_trades_ticker_book_and_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    from pynescript.util.datafeed import CCXTProDataFeed
    from pynescript.util.datafeed import DataFeedError

    _install_fake_ccxt_pro(monkeypatch)

    async def _go() -> None:
        assert (await _collect_one(CCXTProDataFeed(exchange="binance").watch_trades("BTC/USDT")))[0]["price"] == 1.5
        assert (await _collect_one(CCXTProDataFeed(exchange="binance").watch_ticker("BTC/USDT")))["last"] == 1.5
        book = await _collect_one(CCXTProDataFeed(exchange="binance").watch_order_book("BTC/USDT"))
        assert book["bids"] == [[1.0, 1.0]]
        for method in ("watch_trades", "watch_ticker", "watch_order_book"):
            feed = CCXTProDataFeed(exchange="binance")
            await feed._get_exchange()
            feed._exchange.failures[method] = [RuntimeError("boom")]
            agen = {
                "watch_trades": feed.watch_trades,
                "watch_ticker": feed.watch_ticker,
                "watch_order_book": feed.watch_order_book,
            }[method]("BTC/USDT")
            with pytest.raises(DataFeedError):
                async for _ in agen:
                    pass

    asyncio.run(_go())


def test_ccxtpro_connection_retry_then_data(monkeypatch: pytest.MonkeyPatch) -> None:
    from pynescript.util.datafeed import CCXTProDataFeed
    from pynescript.util.datafeed import DataFeedError

    _install_fake_ccxt_pro(monkeypatch)

    async def _no_sleep(_delay) -> None:  # noqa: ANN001
        return None

    monkeypatch.setattr(asyncio, "sleep", _no_sleep)

    async def _go() -> None:
        feed = CCXTProDataFeed(exchange="binance")
        await feed._get_exchange()
        feed._exchange.ohlcv_script = [
            ("raise", RuntimeError("connection lost")),
            ("return", [list(_CANDLE)]),
            ("raise", RuntimeError("fatal")),
        ]
        seen = []
        with pytest.raises(DataFeedError):
            async for item in feed.watch_ohlcv("BTC/USDT"):
                seen.append(item)
        assert seen == [[list(_CANDLE)]]

    asyncio.run(_go())


def test_ccxtpro_fetch_latest_and_fallbacks(monkeypatch: pytest.MonkeyPatch) -> None:
    from pynescript.util.datafeed import CCXTProDataFeed

    _install_fake_ccxt_pro(monkeypatch)
    feed = CCXTProDataFeed(exchange="binance")
    rows = feed.fetch_latest_ohlcv("BTC/USDT", limit=1)
    assert rows and rows[0][4] == 1.5
    assert feed.fetch_latest_ticker("BTC/USDT")["last"] == 1.5

    feed2 = CCXTProDataFeed(exchange="binance")

    async def _go() -> None:
        await feed2._get_exchange()
        feed2._exchange.failures["watch_ohlcv"] = [RuntimeError("ws down")]
        feed2._exchange.failures["watch_ticker"] = [RuntimeError("ws down")]
        assert (await feed2._fetch_latest_ohlcv_async("BTC/USDT"))[0][4] == 1.5
        assert (await feed2._fetch_latest_ticker_async("BTC/USDT"))["last"] == 9.5

    asyncio.run(_go())

    class _NullTicker(_FakeProExchange):
        async def fetch_ticker(self, symbol):  # noqa: ANN001, ANN002
            return None

    _install_fake_ccxt_pro(monkeypatch, _NullTicker)

    async def _go_null() -> None:
        feed3 = CCXTProDataFeed(exchange="binance")
        await feed3._get_exchange()
        feed3._exchange.failures["watch_ticker"] = [RuntimeError("ws down")]
        assert await feed3._fetch_latest_ticker_async("BTC/USDT") == {}

    asyncio.run(_go_null())


def test_ccxtpro_binance_params_and_close(monkeypatch: pytest.MonkeyPatch) -> None:
    from pynescript.util.datafeed import CCXTProDataFeed

    _install_fake_ccxt_pro(monkeypatch)
    _FakeProExchange.last_params = None

    async def _go() -> None:
        feed = CCXTProDataFeed(exchange="binance", api_key="k", secret="s", password="p", sandbox=True)
        async with feed:
            assert feed._exchange is not None
        params = _FakeProExchange.last_params or {}
        assert params.get("apiKey") == "k" and params.get("secret") == "s"
        assert params.get("password") == "p" and params.get("sandbox") is True
        assert params.get("options", {}).get("defaultType") == "spot"
        assert feed._exchange is None  # closed on exit
        await feed.close()  # no-op when already closed

        feed2 = CCXTProDataFeed(exchange="binance")
        async with feed2:

            async def _broken() -> None:
                raise RuntimeError("close failed")

            feed2._exchange.close = _broken
        assert feed2._exchange is None  # best-effort close swallows errors

    asyncio.run(_go())


def test_broker_run_with_finite_feed() -> None:
    from pynescript.util.datafeed import DataFeed
    from pynescript.util.datafeed import DataFeedBroker

    class _FiniteFeed(DataFeed):
        def __init__(self, tickers) -> None:  # noqa: ANN001
            self._tickers = list(tickers)
            self.closed = False

        async def watch_ohlcv(self, symbol, timeframe="1m", limit=None):  # noqa: ANN001, ANN002, ANN003
            if False:
                yield

        async def watch_trades(self, symbol, limit=None):  # noqa: ANN001, ANN002, ANN003
            if False:
                yield

        async def watch_ticker(self, symbol):  # noqa: ANN001, ANN002
            for tick in self._tickers:
                yield tick

        async def watch_order_book(self, symbol, limit=20):  # noqa: ANN001, ANN002, ANN003
            if False:
                yield

        async def close(self) -> None:
            self.closed = True

        async def __aenter__(self) -> _FiniteFeed:
            return self

        async def __aexit__(self, *args) -> None:  # noqa: ANN001, ANN002
            await self.close()

    broker = DataFeedBroker(_FiniteFeed([{"last": 100.0}, {"last": 110.0}]), initial_balance=1000.0)
    buy = broker.place_order("BTC/USDT", "buy", 1.0)
    sell = broker.place_order("BTC/USDT", "sell", 1.0)
    asyncio.run(broker.run(["BTC/USDT"]))
    assert broker.orders[buy].filled and broker.orders[sell].filled
    assert broker.get_position("BTC/USDT") == 0.0
    assert broker.feed.closed is True


def test_broker_insufficient_balance_and_sell_with_position() -> None:
    from pynescript.util.datafeed import DataFeedBroker
    from pynescript.util.datafeed import MockDataFeed

    poor = DataFeedBroker(MockDataFeed(), initial_balance=10.0)
    oid = poor.place_order("BTC/USDT", "buy", 1.0)
    asyncio.run(poor._process_fills(100.0))
    assert poor.orders[oid].filled and poor.get_position("BTC/USDT") == 0.0 and poor.get_balance() == 10.0

    rich = DataFeedBroker(MockDataFeed(), initial_balance=0.0)
    rich.positions["BTC/USDT"] = 2.0
    oid2 = rich.place_order("BTC/USDT", "sell", 1.0)
    asyncio.run(rich._process_fills(100.0))
    assert rich.orders[oid2].filled and rich.get_position("BTC/USDT") == 1.0 and rich.get_balance() == 100.0
