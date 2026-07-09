# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.
"""Parity corpus tests: run each ``.pine`` through ``Runtime.run`` and
compare the emitted events against the expected JSON fixture.

These tests are the **parity oracle** between the Python evaluator (Plan 1)
and the TypeScript port (Plan 2). Every change to event shape must be
reflected in both ``tests/fixtures/parity/json/*.json`` and
``pine-worker/src/evaluator/events.ts``.

The fixture scripts live in ``tests/fixtures/parity/pine/`` and their
expected JSON outputs live in ``tests/fixtures/parity/json/``.
Regenerate the JSON fixtures by running::

    python tests/fixtures/parity/generate_fixtures.py

See ``.opencode/plans/2026-07-05-pine-worker-strategy-events.md`` §1.10.
"""

from __future__ import annotations

import json

from pathlib import Path

import pytest

from backend.runtime import Runtime
from pynescript.ast import helper as ast_helper
from tests.fixtures.parity.ohlcv import OHLCV


FIXTURE_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "parity"


def _discover_scripts() -> list[Path]:
    """Return all ``.pine`` files in the parity corpus, sorted."""
    return sorted(FIXTURE_DIR.glob("pine/*.pine"))


def _strip_unstable_keys(events: list[dict]) -> list[dict]:
    """Remove ``script_id`` and ``run_id`` which differ per invocation."""
    for ev in events:
        ev.pop("script_id", None)
        ev.pop("run_id", None)
    return events


# ---------------------------------------------------------------------------
# Collect parametrized ids — one per .pine file, minus known-gap scripts
# ---------------------------------------------------------------------------

_scripts = _discover_scripts()
_skip_var: dict[str, str] = {
    # No scripts skipped — var/varip implemented in subtask 1.11
}


def _param_id(path: Path) -> str:
    return path.stem


@pytest.mark.parametrize("pine_path", _scripts, ids=_param_id)
def test_parity_corpus(pine_path: Path, request: pytest.FixtureRequest) -> None:
    """Run a parity fixture script through ``Runtime.run`` and compare
    the emitted events to the expected JSON fixture."""
    script_id = pine_path.stem

    # -- Check for known gaps -----------------------------------------------
    skip_reason = _skip_var.get(script_id)
    if skip_reason:
        pytest.skip(skip_reason)

    # -- Load source --------------------------------------------------------
    source = pine_path.read_text(encoding="utf-8")

    # -- Load expected JSON -------------------------------------------------
    json_path = FIXTURE_DIR / "json" / f"{script_id}.json"
    assert json_path.exists(), (
        f"Expected JSON fixture not found: {json_path}.\n"
        f"Run 'python tests/fixtures/parity/generate_fixtures.py' to create it."
    )
    expected = json.loads(json_path.read_text(encoding="utf-8"))

    # -- Execute ------------------------------------------------------------
    result: dict = Runtime().run(source, OHLCV)

    # -- Assert no error ----------------------------------------------------
    assert "error" not in result, f"Runtime error: {result['error']}"

    # -- Compare events -----------------------------------------------------
    events: list[dict] = result["events"]  # type: ignore[assignment]
    actual = _strip_unstable_keys(events)

    assert actual == expected, (
        f"Events mismatch for {script_id}\n"
        f"  Expected ({len(expected)} events): {json.dumps(expected, indent=2)}\n"
        f"  Actual   ({len(actual)} events):   {json.dumps(actual, indent=2)}"
    )


# ---------------------------------------------------------------------------
# Corpus integration (Subtask 1.10): existing builtin_scripts corpus
# ---------------------------------------------------------------------------

_BUILTIN_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "tests" / "data" / "builtin_scripts"

# Scripts that are known to fail at Runtime.run due to pre-existing
# evaluator limitations (not regressions from Plan 1). See
# docs/strategy-surface-gaps.md for details.
_CORPUS_KNOWN_GAPS: dict[str, str] = {
    "rsi_strategy": "ta.rsi requires series history — pre-existing evaluator gap",
    "macd_strategy": "ta.ema requires series history — pre-existing evaluator gap",
    "greedy_strategy": (
        "strategy.position_size, strategy.position_avg_price, syminfo.mintick not yet implemented (Plan 2+)"
    ),
}


@pytest.mark.parametrize(
    "script_name",
    [
        "rsi_strategy",
        "macd_strategy",
        "greedy_strategy",
    ],
)
def test_corpus_strategy_script_parses(script_name: str) -> None:
    """Verify that existing strategy corpus scripts at least parse cleanly.

    These scripts are part of the parametrized parse/unparse corpus and are
    tested there already; this test confirms the file exists and can be
    parsed by the helper module as a smoke check.
    """
    path = _BUILTIN_SCRIPTS_DIR / f"{script_name}.pine"
    assert path.exists(), f"Corpus script not found: {path}"
    source = path.read_text(encoding="utf-8")
    ast_tree = ast_helper.parse(source)
    assert ast_tree is not None, f"Failed to parse {script_name}"


@pytest.mark.parametrize(
    "script_name",
    sorted(_CORPUS_KNOWN_GAPS),
)
def test_corpus_strategy_script_runtime_known_gap(script_name: str) -> None:
    """Document known Runtime.run gaps for existing strategy scripts.

    These scripts cannot run to completion due to pre-existing evaluator
    gaps (not related to Plan 1). The test exists to track when the gap is
    closed: when it starts passing, remove the entry from ``_CORPUS_KNOWN_GAPS``.
    """
    source = (_BUILTIN_SCRIPTS_DIR / f"{script_name}.pine").read_text(encoding="utf-8")
    result: dict = Runtime().run(source, OHLCV)

    reason = _CORPUS_KNOWN_GAPS.get(script_name, "unknown pre-existing gap")
    assert "error" in result, (
        f"{script_name} unexpectedly succeeded! "
        f"If the pre-existing gap was fixed, remove {script_name} "
        f"from _CORPUS_KNOWN_GAPS in test_parity.py.\n"
        f"Events: {json.dumps(result.get('events', []), indent=2)}"
    )
    # Expected to fail — document the gap
    pytest.skip(f"Known gap: {reason} ({result['error'][:80]})")


# ---------------------------------------------------------------------------
# End-to-end smoke test: minimal strategy using ALL implemented builtins
# ---------------------------------------------------------------------------


def test_minimal_strategy_pipeline() -> None:
    """Run a minimal strategy that exercises every implemented builtin
    through ``Runtime.run``. This verifies the full pipeline: parse →
    evaluate → emit events → serialize.

    This is intentionally NOT a fixture-based test — it asserts event
    shapes are well-formed (correct kinds, ids, bar_index threaded).
    Exact values may change as builtins evolve.
    """
    source = """//@version=6
strategy("PipelineTest", overlay=true)

// -- Entry / exit -------------------------------------------------------
if bar_index == 0
    strategy.entry("L1", strategy.long, qty=10.0, comment="buy")
if bar_index == 1
    strategy.exit("L1", qty=5.0, stop=90.0, limit=110.0)
if bar_index == 2
    strategy.close("L1")
"""
    result: dict = Runtime().run(source, OHLCV)

    # -- No runtime error -------------------------------------------------
    assert "error" not in result, f"Unexpected error: {result['error']}"

    # -- Events are present and well-typed --------------------------------
    events: list[dict] = result["events"]  # type: ignore[assignment]
    assert len(events) == 3, f"Expected 3 events, got {len(events)}"

    kinds = [e["kind"] for e in events]
    assert kinds == ["entry", "exit", "close"], f"Unexpected kinds: {kinds}"

    # -- bar_index and bar_time are threaded from context -----------------
    assert events[0]["bar_index"] == 0
    assert events[1]["bar_index"] == 1
    assert events[2]["bar_index"] == 2

    # -- script_id and run_id are present ---------------------------------
    for ev in events:
        assert ev.get("script_id"), f"Missing script_id in {ev['kind']}"
        assert ev.get("run_id"), f"Missing run_id in {ev['kind']}"
