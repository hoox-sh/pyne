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

"""Classification helpers for intentional corpus Runtime residuals."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "scripts" / "corpus_run_runtime.py"


def _load_corpus_run_runtime():
    """Load scripts/corpus_run_runtime.py without requiring package install."""
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    if str(_ROOT / "src") not in sys.path:
        sys.path.insert(0, str(_ROOT / "src"))
    name = "corpus_run_runtime_under_test"
    spec = importlib.util.spec_from_file_location(name, _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_mod = _load_corpus_run_runtime()
EXPECTED_FAIL_RELS = _mod.EXPECTED_FAIL_RELS
is_expected_fail = _mod.is_expected_fail
corpus_rel_path = _mod.corpus_rel_path


# Docs demos added for honest residual classification (not soft-OK).
_DOCS_DEMO_RELS = (
    "set03/strategies/0256_str_exit_persist_demo.pine",
    "set03/strategies/0257_str_exit_persist_demo_2.pine",
    "set04/indicators/0776_ind_repainting_vs_non_repainting_request_security_demo.pine",
    "set04/indicators/0768_ind_invalid_line_wrap_demo.pine",
    "set04/indicators/0822_ind_searching_in_arrays.pine",
    "set04/indicators/0823_ind_session_bar_checker.pine",
    "set04/indicators/0898_ind_loop_is_too_long.pine",
)


def test_expected_fail_rels_includes_docs_demos() -> None:
    for rel in _DOCS_DEMO_RELS:
        assert rel in EXPECTED_FAIL_RELS, f"missing from EXPECTED_FAIL_RELS: {rel}"


def test_is_expected_fail_path_and_error_required() -> None:
    rel = "set04/indicators/0898_ind_loop_is_too_long.pine"
    assert is_expected_fail(rel, "exceeded 20s")
    assert is_expected_fail(rel, "Parse Error: unexpected INDENT")
    assert is_expected_fail(rel, "Runtime Error: loop is too long")
    # Empty error must not promote (bare OK / soft library timeout stays OK).
    assert not is_expected_fail(rel, "")
    assert not is_expected_fail(rel, "   ")


def test_is_expected_fail_does_not_promote_unknown_paths() -> None:
    assert not is_expected_fail(
        "set04/indicators/0000_not_a_listed_demo.pine",
        "Runtime Error: boom",
    )
    assert not is_expected_fail(
        "set01/indicators/some_real_script.pine",
        "Parse Error: unexpected token",
    )


def test_is_expected_fail_accepts_absolute_and_basename() -> None:
    abs_path = str(_ROOT / "tests" / "data" / "set04" / "indicators" / "0768_ind_invalid_line_wrap_demo.pine")
    assert is_expected_fail(abs_path, "Parse Error: invalid indent wrap")
    assert is_expected_fail("0768_ind_invalid_line_wrap_demo.pine", "Syntax Error")


def test_corpus_rel_path_normalizes_under_tests_data() -> None:
    abs_path = _ROOT / "tests" / "data" / "set03" / "strategies" / "0256_str_exit_persist_demo.pine"
    assert corpus_rel_path(str(abs_path)) == "set03/strategies/0256_str_exit_persist_demo.pine"
    assert corpus_rel_path("tests/data/set03/strategies/0256_str_exit_persist_demo.pine").endswith(
        "set03/strategies/0256_str_exit_persist_demo.pine"
    )


def test_parse_and_timeout_routes_would_classify_listed_only() -> None:
    """Mirrors _run_one classification gates for PARSE/TIMEOUT listed paths."""

    def classify_parse(path: str, err: str) -> str:
        if err.startswith("Syntax Error") or err.startswith("Parse Error"):
            if is_expected_fail(path, err):
                return "EXPECTED_FAIL"
            return "PARSE_FAIL"
        return "OTHER"

    def classify_timeout(path: str, err: str, *, library: bool = False) -> str:
        if is_expected_fail(path, err):
            return "EXPECTED_FAIL"
        if library:
            return "OK"
        return "TIMEOUT"

    assert (
        classify_parse(
            "set04/indicators/0768_ind_invalid_line_wrap_demo.pine",
            "Parse Error: bad wrap",
        )
        == "EXPECTED_FAIL"
    )
    assert (
        classify_parse(
            "set04/indicators/0822_ind_searching_in_arrays.pine",
            "Syntax Error: mid-expr",
        )
        == "EXPECTED_FAIL"
    )
    assert (
        classify_parse("set04/indicators/unlisted_scrape.pine", "Parse Error: trash")
        == "PARSE_FAIL"
    )
    assert (
        classify_timeout(
            "set04/indicators/0898_ind_loop_is_too_long.pine",
            "exceeded 20s",
        )
        == "EXPECTED_FAIL"
    )
    assert classify_timeout("set04/indicators/other_heavy.pine", "exceeded 20s") == "TIMEOUT"
    assert (
        classify_timeout(
            "set02/libraries/some_heavy_lib.pine",
            "exceeded 20s",
            library=True,
        )
        == "OK"
    )
    # Listed library runtime.error demos stay EXPECTED_FAIL even under library soft path.
    assert (
        classify_timeout(
            "set02/libraries/019_lib_functionnnetwork.pine",
            "Runtime Error: intentional",
            library=True,
        )
        == "EXPECTED_FAIL"
    )
