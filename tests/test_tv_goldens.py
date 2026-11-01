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

"""TradingView golden parity (vendored OpenPineScript exports).

The heavy lifting lives in ``scripts/compare_tv_goldens.py``.  These tests keep
the fixture set honest:

* every export has the harness that produced it;
* no column regresses outside the explicit known-divergence baseline;
* the baseline carries a real reason, not a silent TODO;
* ``str.tostring`` keeps enough precision for the exported rows;
* the CSV route works for future "Export chart data..." fixtures.
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys

from collections import deque
from pathlib import Path

import pytest


_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "scripts" / "compare_tv_goldens.py"
_FIXTURES = _ROOT / "tests" / "fixtures" / "tv_goldens"
_BASELINE = _FIXTURES / "baseline.json"


def _harness_module():
    spec = importlib.util.spec_from_file_location("compare_tv_goldens_harness", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_tv_golden_fixtures_are_paired() -> None:
    exports = sorted([*_FIXTURES.rglob("*.log"), *_FIXTURES.rglob("*.csv")])
    assert len(exports) >= 9, f"expected the vendored OpenPineScript exports, found {len(exports)}"
    for export in exports:
        harness = export.with_name(export.name.split(".")[0] + ".pine")
        assert harness.exists(), f"{export.name} has no sibling {harness.name}"
        assert harness.stat().st_size > 0
    assert (_FIXTURES / "openpinescript" / "LICENSE").exists()


def test_vendored_fixture_hashes_match_sources() -> None:
    import hashlib

    sources = json.loads((_FIXTURES / "SOURCES.json").read_text(encoding="utf-8"))
    files = sources.get("files") or {}
    assert files
    for relative, entry in files.items():
        path = _FIXTURES / "openpinescript" / relative
        assert path.exists(), f"missing vendored fixture {relative}"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == entry["sha256"], f"{relative} changed; refresh SOURCES.json deliberately"


def test_tv_golden_baseline_has_reasons() -> None:
    baseline = json.loads(_BASELINE.read_text(encoding="utf-8"))
    columns = baseline.get("columns") or {}
    missing = [key for key, entry in columns.items() if not str(entry.get("reason") or "").strip()]
    todo = [key for key, entry in columns.items() if entry.get("reason") == "TODO: triage"]
    assert not missing, f"baseline entries without a reason: {missing}"
    assert not todo, f"baseline entries still marked TODO: {todo}"


def test_tv_goldens_have_no_new_failures() -> None:
    harness = _harness_module()
    results = harness.compare_all(_FIXTURES, _BASELINE)
    errors = [(result.export.path.name, result.error) for result in results if result.error]
    assert not errors, f"harnesses crashed: {errors}"
    new = [
        (result.export.path.name, column.column, column.problems)
        for result in results
        for column in result.columns
        if column.status == "new"
    ]
    assert not new, "new TradingView parity failures:\n" + "\n".join(
        f"{export}::{column}: {problems}" for export, column, problems in new
    )
    counts = harness._summarize(results)
    assert counts["pass"] > 0
    assert counts["new"] == 0


def test_tostring_unwraps_series_and_keeps_precision() -> None:
    from pynescript.runtime.host import Runtime

    bars = [
        {"time": 1_000_000, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 10.0},
        {"time": 1_086_400_000, "open": 1.5, "high": 2.5, "low": 1.0, "close": 2.0, "volume": 11.0},
    ]
    source = """
//@version=5
indicator("tostring")
log.info("ROW|" + str.tostring(time, "#") + "," + str.tostring(close, "#.##########"))
"""
    result = Runtime(symbol="TEST").run(source, bars, mode="interpret")
    assert result.get("error") is None
    messages = [entry["message"] for entry in result.get("logs") or []]
    assert messages == ["ROW|1000000,1.5", "ROW|1086400000,2"]


def test_sma_same_call_site_overwrites_current_bar() -> None:
    """One ``ta.sma`` AST site reached several times per bar with different
    sources shares a window and replaces the live sample (TradingView).

    Committed history is the last source written on each prior bar. Distinct
    call sites (different periods / AST nodes) stay independent.
    """
    from pynescript.ast.evaluator import NodeLiteralEvaluator

    class _Inc(NodeLiteralEvaluator):
        def __init__(self) -> None:
            super().__init__()
            self._pine_bar_mode = True
            self._pine_ta_incremental = True
            self._ta_inc_state = {}
            self._ta_call_i = 0
            self.context = {"bar_index": 0}
            self._pine_current_call_site = 7

    closes = [float(i + 1) for i in range(12)]
    period = 3
    ev = _Inc()
    got: list[float | None] = []
    window: deque[float] = deque()
    for bar in range(len(closes)):
        ev.context["bar_index"] = bar
        ev._ta_call_i = 0
        total = 0.0
        any_na = False
        appended = False
        for offset in range(3):
            src = closes[bar - offset] if bar - offset >= 0 else math.nan
            val = ev._sma_inc_update([src], period)
            if not appended:
                window.append(src)
                appended = True
            else:
                window[-1] = src
            last = list(window)[-period:]
            if len(last) < period or any(math.isnan(x) for x in last):
                exp = None
                any_na = True
            else:
                exp = sum(last) / period
            if val is None:
                any_na = True
            else:
                total += val
            if exp is None:
                assert val is None, f"bar {bar} offset {offset}: got {val} expected na"
            else:
                assert val == pytest.approx(exp), f"bar {bar} offset {offset}: {val} != {exp}"
        got.append(None if any_na else total)
    assert got[-1] is not None


def test_loop_sma_close_i_matches_overwrite_model() -> None:
    """Runtime ``for i = 0 to 2 / ta.sma(close[i], n)`` follows the TV rule."""
    from pynescript.ast.helper import clear_parse_cache
    from pynescript.runtime.host import Runtime

    clear_parse_cache()
    closes = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0, 21.0]
    bars = [
        {
            "time": 1_577_836_800_000 + i * 86_400_000,
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "volume": 1.0,
        }
        for i, close in enumerate(closes)
    ]
    source = """
//@version=5
indicator("loop sma")
s = 0.0
for i = 0 to 2
    s := s + ta.sma(close[i], 3)
plot(s, "s")
"""
    result = Runtime(symbol="T").run(source, bars, mode="interpret")
    assert result.get("error") is None, result.get("error")
    series = result.get("series") or {}
    assert "s" in series, series.keys()
    window: deque[float] = deque()
    period = 3
    for bar in range(len(closes)):
        total = 0.0
        any_na = False
        appended = False
        for offset in range(3):
            src = closes[bar - offset] if bar - offset >= 0 else math.nan
            if not appended:
                window.append(src)
                appended = True
            else:
                window[-1] = src
            last = list(window)[-period:]
            if len(last) < period or any(math.isnan(x) for x in last):
                any_na = True
            else:
                total += sum(last) / period
        got = series["s"][bar]
        if any_na:
            assert got is None or (isinstance(got, float) and math.isnan(got)), f"bar {bar}: {got}"
        else:
            assert got == pytest.approx(total), f"bar {bar}: {got} != {total}"


def test_csv_export_route(tmp_path: Path) -> None:
    harness = _harness_module()
    pine = tmp_path / "harness_csv.pine"
    pine.write_text(
        '//@version=5\nindicator("csv")\nplot(ta.sma(close, 2), "sma_2")\n',
        encoding="utf-8",
    )
    export = tmp_path / "harness_csv.TEST.1D.csv"
    export.write_text(
        "time,open,high,low,close,volume,sma_2\n"
        "2020-01-01T00:00:00Z,1,2,0.5,1.5,10,1.5\n"
        "2020-01-02T00:00:00Z,1.5,3,1,2.5,11,2.0\n"
        "2020-01-03T00:00:00Z,2.5,4,2,3.5,12,3.0\n",
        encoding="utf-8",
    )
    loaded = harness._load_export(export)
    assert len(loaded.bars) == 3
    assert loaded.columns["sma_2"] == [1.5, 2.0, 3.0]

    ours = harness._run_harness(loaded, "interpret")
    assert math.isnan(ours["sma_2"][0])
    assert ours["sma_2"][1] == pytest.approx(2.0)
    assert ours["sma_2"][2] == pytest.approx(3.0)
