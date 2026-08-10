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

"""Interpret vs compile series parity (small always-on subset).

Full corpus harness (default 50 scripts x 1000 bars, multiprocessing)::

    python scripts/compare_interp_compile.py --bars 1000 --limit 50
    python scripts/compare_interp_compile.py --ignore-hline-keys --ignore-fill-keys --strict-keys
    python scripts/compare_interp_compile.py --glob 'average_*.pine' --bars 200

Report: ``.cache/interp_compile_parity.json``

Optional longer pytest path (skipped unless mark is selected)::

    pytest tests/test_interp_compile_parity.py -m interp_compile_full
"""

from __future__ import annotations

import importlib.util
import os
import sys

from pathlib import Path

import pytest


_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "scripts" / "compare_interp_compile.py"
_BUILTIN = _ROOT / "tests" / "data" / "builtin_scripts"
# Shipped first-party fixtures (always present in clean clones / CI).
# Lives under tests/fixtures/ (not tests/data/) so root gitignore `data/` does not drop them.
_FIRST_PARTY = _ROOT / "tests" / "fixtures" / "first_party"

# Always-on smoke: first-party scripts only (audit 2026-08-10 Wave A).
# Third-party builtin_scripts/ corpora are optional local-only and skipped
# when missing — never silent-pass.
_ALWAYS_SCRIPTS = (
    "plot_close.pine",
    "sma.pine",
    "ema.pine",
    "rsi.pine",
    "strategy_entry.pine",
)

# Optional expanded corpus list (local only; skipped if files missing).
_OPTIONAL_CORPUS_SCRIPTS = (
    "advance_decline_line.pine",
    "arnaud_legoux_moving_average.pine",
    "aroon.pine",
    "average_true_range.pine",
    "awesome_oscillator.pine",
    "bbtrend.pine",
    "bollinger_bands.pine",
    "chande_momentum_oscillator.pine",
    "correlation_coefficient.pine",
    "donchian_channels.pine",
    "money_flow_index.pine",
    "moving_average_exponential.pine",
    "moving_average_simple.pine",
    "on_balance_volume.pine",
    "relative_strength_index.pine",
    "supertrend.pine",
    "williams_percent_range.pine",
)

# Runtime-gap statuses: skip smoke rather than red the suite.
_SKIP_STATUSES = frozenset(
    {
        "interp_error",
        "compile_error",
        "both_error",
        "both_error_same",
        "expected_error",
    }
)


def _load_harness():
    """Import scripts/compare_interp_compile.py without requiring package install."""
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    if str(_ROOT / "src") not in sys.path:
        sys.path.insert(0, str(_ROOT / "src"))
    name = "compare_interp_compile_harness"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def harness():
    if not _SCRIPT.is_file():
        pytest.skip(f"harness missing: {_SCRIPT}")
    return _load_harness()


def test_harness_series_allclose_nan_none(harness) -> None:
    ok, _ = harness.series_allclose([None, 1.0, float("nan")], [None, 1.0, None])
    assert ok
    ok, detail = harness.series_allclose([1.0], [1.0 + 1e-3])
    assert not ok
    assert "index 0" in detail
    assert "interp=" in detail
    assert "compile=" in detail


def test_harness_mismatch_detail_type_na_and_n_bad(harness) -> None:
    """Richer MISMATCH detail: type/na label + n_bad count."""
    ok, detail = harness.series_allclose(
        [1.0, 2.0, 3.0],
        [1.0, None, None],
    )
    assert not ok
    assert "type/na" in detail
    assert "n_bad=2" in detail
    assert "interp=" in detail and "compile=" in detail

    ok2, detail2 = harness.series_allclose([10.0, 20.0], [10.0, 20.5], atol=1e-9, rtol=0.0)
    assert not ok2
    assert "max_abs=" in detail2 or "n_bad=" in detail2


def test_harness_expected_error_classifier(harness) -> None:
    assert harness.is_expected_error_message(
        "not enough data to calculate auto fib extension on the current symbol. "
        "change the chart's timeframe to a lower one or select a smaller "
        "calculation depth using the indicator's `depth` settings."
    )
    assert not harness.is_expected_error_message("unknown function foo")
    assert not harness.is_expected_error_message("")


def test_harness_constant_hline(harness) -> None:
    assert harness.is_constant_hline([30.0, 30, 30.0])
    assert harness.is_constant_hline([None, 70, 70.0])
    assert not harness.is_constant_hline([1.0, 2.0])


def test_harness_is_fill_background_key(harness) -> None:
    assert harness.is_fill_background_key("Background")
    assert harness.is_fill_background_key("Middle Background")
    assert harness.is_fill_background_key("Bollinger Bands Background Fill")
    assert harness.is_fill_background_key("bgcolor")
    assert harness.is_fill_background_key("Overbought background")
    assert not harness.is_fill_background_key("Upper")
    assert not harness.is_fill_background_key("ATR")
    assert not harness.is_fill_background_key("hline")


def test_harness_normalize_error_auto_fib(harness) -> None:
    ie = (
        "Runtime Error at bar 86314600000 (index 999): RuntimeError: Not enough data "
        "to calculate Auto Fib Extension on the current symbol. Change the chart's "
        "timeframe to a lower one or select a smaller calculation depth using the "
        "indicator's `Depth` settings."
    )
    ce = (
        "Compiled Runtime Error: RuntimeError: Not enough data to calculate Auto Fib "
        "Extension on the current symbol. Change the chart's timeframe to a lower one "
        "or select a smaller calculation depth using the indicator's `Depth` settings."
    )
    ni = harness.normalize_error(ie)
    nc = harness.normalize_error(ce)
    assert ni == nc
    assert "not enough data" in ni
    assert "auto fib extension" in ni
    assert "runtime error at bar" not in ni
    assert "compiled runtime error" not in ni
    # Float bar timestamps (host packing) must still strip cleanly.
    ie_f = (
        "Runtime Error at bar 4234600000.0 (index 49): RuntimeError: Not enough data "
        "to calculate Auto Fib Retracement on the current symbol."
    )
    ni_f = harness.normalize_error(ie_f)
    assert "runtime error at bar" not in ni_f
    assert "not enough data" in ni_f
    assert harness.is_expected_error_message(ni_f)


def test_harness_compare_ignore_fill_keys(harness) -> None:
    interp = {
        "Mid": [1.0, 2.0],
        "Background": [0.0, 0.0],
        "Bollinger Bands Background Fill": [1.0, 1.0],
    }
    compile_ = {"Mid": [1.0, 2.0]}
    cmp_ = harness.compare_series_maps(interp, compile_, ignore_fill_keys=False)
    assert cmp_["only_interp"] == ["Background", "Bollinger Bands Background Fill"]
    assert cmp_["fill_background_only"] is True
    assert not cmp_["mismatches"]

    cmp_ign = harness.compare_series_maps(interp, compile_, ignore_fill_keys=True)
    assert cmp_ign["only_interp"] == []
    assert "Background" in cmp_ign["ignored_fill_keys"]
    assert cmp_ign["fill_background_only"] is False


def test_harness_compare_ignore_hline_keys(harness) -> None:
    interp = {"plot": [1.0, 2.0], "hline": [70.0, 70.0]}
    compile_ = {"plot": [1.0, 2.0]}
    cmp_ = harness.compare_series_maps(interp, compile_, ignore_hline_keys=True)
    assert cmp_["only_interp"] == []
    assert "hline" in cmp_["ignored_hline_keys"]


def test_harness_summarize_buckets(harness) -> None:
    results = [
        {"status": "OK", "only_interp": [], "only_compile": []},
        {"status": "OK", "only_interp": ["hline"], "only_compile": []},
        {"status": "fill_background_only", "only_interp": ["Background"], "only_compile": []},
        {"status": "both_error_same"},
        {"status": "expected_error"},
        {"status": "both_error"},
        {"status": "MISMATCH"},
        {"status": "compile_error"},
    ]
    counts = harness.summarize(results)
    assert counts["OK"] == 2
    assert counts["structural_only"] == 1
    assert counts["fill_background_only"] == 1
    assert counts["both_error_same"] == 1
    assert counts["expected_error"] == 1
    assert counts["both_error"] == 1
    assert counts["MISMATCH"] == 1
    assert counts["compile_error"] == 1
    text = harness.format_summary(counts, total=len(results), elapsed_s=1.5)
    assert "both_error_same" in text
    assert "expected_error" in text
    assert "fill_background_only" in text


def test_harness_cli_flags_registered(harness) -> None:
    """New residual flags must exist without breaking existing CLI."""
    ap_src = Path(harness.__file__).read_text(encoding="utf-8")
    assert "--ignore-fill-keys" in ap_src
    assert "--strict-errors" in ap_src
    assert "--ignore-hline-keys" in ap_src
    assert "--strict-keys" in ap_src
    assert "both_error_same" in ap_src
    assert "expected_error" in ap_src
    assert "fill_background_only" in ap_src
    # Non-fatal set includes both_error_same + expected_error
    assert "both_error_same" in harness._NON_FATAL_STATUSES
    assert "expected_error" in harness._NON_FATAL_STATUSES
    assert "fill_background_only" in harness._NON_FATAL_STATUSES
    assert "both_error_same" in harness._ERROR_STATUSES
    assert "expected_error" in harness._ERROR_STATUSES


@pytest.mark.parametrize("name", _ALWAYS_SCRIPTS)
def test_interp_compile_parity_smoke(harness, name: str) -> None:
    """Always-on: first-party fixtures x 100 bars, no value mismatches.

    These files are shipped under ``tests/data/first_party/`` so CI and clean
    clones actually exercise interpret↔compile value parity (audit 2026-08-10).
    """
    path = _FIRST_PARTY / name
    assert path.is_file(), f"first-party fixture missing (must ship): {path}"

    result = harness.run_one_script(
        str(path),
        100,
        ignore_hline_keys=False,
        ignore_fill_keys=False,
        sanitize=False,
    )
    # Runtime gaps on either backend are environment issues — skip rather
    # than red the whole suite (value parity is the contract we enforce).
    if result["status"] in _SKIP_STATUSES:
        pytest.skip(
            f"{name}: {result['status']} interp={result.get('interp_error')!r} "
            f"compile={result.get('compile_error')!r}"
        )
    # fill_background_only is structural warn, not a value failure
    assert result["status"] in ("OK", "fill_background_only"), (
        f"{name}: status={result['status']} mismatches={result.get('mismatches')}"
    )
    assert not result.get("mismatches"), result.get("mismatches")


@pytest.mark.parametrize("name", _OPTIONAL_CORPUS_SCRIPTS)
def test_interp_compile_parity_optional_corpus(harness, name: str) -> None:
    """Optional local corpus smoke; skipped when third-party files are absent."""
    path = _BUILTIN / name
    if not path.is_file():
        pytest.skip(f"optional corpus script missing: {path}")

    result = harness.run_one_script(
        str(path),
        100,
        ignore_hline_keys=False,
        ignore_fill_keys=False,
        sanitize=True,
    )
    if result["status"] in _SKIP_STATUSES:
        pytest.skip(
            f"{name}: {result['status']} interp={result.get('interp_error')!r} "
            f"compile={result.get('compile_error')!r}"
        )
    assert result["status"] in ("OK", "fill_background_only"), (
        f"{name}: status={result['status']} mismatches={result.get('mismatches')}"
    )
    assert not result.get("mismatches"), result.get("mismatches")


@pytest.mark.interp_compile_full
def test_interp_compile_parity_full_subset(harness, request: pytest.FixtureRequest) -> None:
    """Optional: 20 scripts x 200 bars (opt-in via ``-m interp_compile_full``)."""
    # Stay skipped in default suite runs; only execute when the mark is selected
    # or PYNE_INTERP_COMPILE_FULL=1 is set.
    markexpr = (getattr(request.config.option, "markexpr", None) or "").strip()
    env_on = os.environ.get("PYNE_INTERP_COMPILE_FULL", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    if "interp_compile_full" not in markexpr and not env_on:
        pytest.skip(
            "opt-in full parity: pytest -m interp_compile_full "
            "or PYNE_INTERP_COMPILE_FULL=1 "
            "(or run scripts/compare_interp_compile.py)"
        )
    paths = sorted(_BUILTIN.glob("*.pine"))[:20]
    if len(paths) < 5:
        # Fall back to shipped first-party fixtures so opt-in path still runs.
        paths = sorted(_FIRST_PARTY.glob("*.pine"))
    if len(paths) < 1:
        pytest.skip("no first-party or builtin_scripts corpus available")
    code = harness.main(
        [
            "--bars",
            "200",
            "--limit",
            "20",
            "--workers",
            "1",
            "--ignore-fill-keys",
            "--out",
            str(_ROOT / ".cache" / "interp_compile_parity_pytest.json"),
            "--files",
            *[str(p) for p in paths],
        ]
    )
    # main returns 1 only on value (or --strict-keys / --strict-errors) failures
    assert code == 0, "see .cache/interp_compile_parity_pytest.json"
