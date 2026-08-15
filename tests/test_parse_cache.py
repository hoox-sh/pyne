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

"""Tests for process-local parse/AST cache (Phase 1.6 / PYNE_PARSE_CACHE)."""

from __future__ import annotations

import threading

import pytest

from pynescript.ast.helper import clear_parse_cache
from pynescript.ast.helper import dump
from pynescript.ast.helper import parse
from pynescript.ast.helper import parse_cache_info
from pynescript.ast.helper import unparse


SRC_MIN = """//@version=5
indicator("cache_test")
plot(close)
"""

SRC_EXPR = "close > open"


@pytest.fixture(autouse=True)
def _isolate_parse_cache(monkeypatch):
    """Enable cache with a known max; clear before/after each test."""
    monkeypatch.setenv("PYNE_PARSE_CACHE", "1")
    monkeypatch.setenv("PYNE_PARSE_CACHE_MAX", "8")
    clear_parse_cache()
    yield
    clear_parse_cache()


def test_warm_hit_same_identity():
    a = parse(SRC_MIN)
    b = parse(SRC_MIN)
    assert a is b
    info = parse_cache_info()
    assert info["enabled"] is True
    assert info["size"] >= 1
    assert info["hits"] >= 1
    assert info["misses"] >= 1


def test_unparse_matches_across_hits():
    a = parse(SRC_MIN)
    out_a = unparse(a)
    b = parse(SRC_MIN)
    out_b = unparse(b)
    assert out_a == out_b
    assert a is b
    # Structural dump stable
    assert dump(a) == dump(b)


def test_mode_is_part_of_key():
    # Different modes must not collide even if source strings differ in role.
    # SRC_EXPR is only valid as eval; full script is exec.
    tree_exec = parse(SRC_MIN, mode="exec")
    tree_eval = parse(SRC_EXPR, mode="eval")
    again_exec = parse(SRC_MIN, mode="exec")
    again_eval = parse(SRC_EXPR, mode="eval")
    assert tree_exec is again_exec
    assert tree_eval is again_eval
    assert tree_exec is not tree_eval


def test_clear_parse_cache_resets():
    a = parse(SRC_MIN)
    clear_parse_cache()
    info = parse_cache_info()
    assert info["size"] == 0
    assert info["hits"] == 0
    assert info["misses"] == 0
    b = parse(SRC_MIN)
    assert a is not b
    assert dump(a) == dump(b)
    assert unparse(a) == unparse(b)


def test_disable_via_env(monkeypatch):
    monkeypatch.setenv("PYNE_PARSE_CACHE", "0")
    clear_parse_cache()
    a = parse(SRC_MIN)
    b = parse(SRC_MIN)
    assert a is not b
    assert unparse(a) == unparse(b)
    assert parse_cache_info()["enabled"] is False
    assert parse_cache_info()["size"] == 0


def test_lru_eviction_bounded(monkeypatch):
    monkeypatch.setenv("PYNE_PARSE_CACHE_MAX", "3")
    clear_parse_cache()
    scripts = [f"//@version=5\nindicator(\"s{i}\")\nplot(close + {i})\n" for i in range(5)]
    trees = [parse(s) for s in scripts]
    info = parse_cache_info()
    assert info["size"] <= 3
    # First two should have been evicted; re-parse rebuilds
    early = parse(scripts[0])
    assert early is not trees[0]
    assert dump(early) == dump(trees[0])
    # Most recent still warm
    late = parse(scripts[-1])
    assert late is trees[-1]


def test_different_sources_different_trees():
    a = parse(SRC_MIN)
    b = parse(SRC_MIN + "\n// trailing comment variation\n")
    assert a is not b


def test_filename_not_in_key():
    a = parse(SRC_MIN, filename="a.pine")
    b = parse(SRC_MIN, filename="b.pine")
    assert a is b


def test_tls_parse_indent_then_simple_no_bleed(monkeypatch):
    """Reused lexer must drop indent stack between distinct sources."""
    monkeypatch.setenv("PYNE_PARSE_CACHE", "0")
    indented = """
//@version=5
indicator("indented")
f() =>
    x = 1
    if x > 0
        x + 1
    else
        x
plot(f())
"""
    simple = """
//@version=5
indicator("simple")
plot(close)
"""
    a = parse(indented)
    b = parse(simple)
    assert unparse(parse(unparse(a)))  # round-trip still parses
    assert "indicator" in unparse(b)
    # Second parse must not inherit INDENT/DEDENT from f()'s block.
    again = parse(simple)
    assert dump(b) == dump(again)


def test_tls_parse_concurrent_distinct_sources(monkeypatch):
    """Each thread has its own ANTLR engine; distinct sources must not collide."""
    monkeypatch.setenv("PYNE_PARSE_CACHE", "0")
    sources = [
        f"//@version=5\nindicator(\"t{i}\")\nplot(close + {i})\n" for i in range(12)
    ]
    errors: list[BaseException] = []
    dumps: dict[int, str] = {}
    lock = threading.Lock()

    def worker(i: int, src: str) -> None:
        try:
            tree = parse(src)
            text = dump(tree)
            with lock:
                dumps[i] = text
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i, s)) for i, s in enumerate(sources)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert len(dumps) == len(sources)
    serial = {i: dump(parse(s)) for i, s in enumerate(sources)}
    assert dumps == serial


def test_concurrent_parse_same_source():
    clear_parse_cache()
    results: list[object] = []
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            results.append(parse(SRC_MIN))
        except BaseException as exc:  # noqa: BLE001 — collect for assertion
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert len(results) == 8
    # All hits share one identity after concurrent first-fill
    assert all(r is results[0] for r in results)


def test_cached_tree_two_evaluators_independent_call_sites():
    """Same parse identity, two evaluators: no bound-handler leak.

    ``parse()`` scrubs on cache hit; this holds the tree and visits it with
    two evaluators *without* a second parse, which is the residual H1 path.
    """
    from pynescript.ast.evaluator import NodeLiteralEvaluator
    from pynescript.ast.helper import walk

    src = "ta.sma(close, 3)"
    tree = parse(src, mode="eval")
    ev1 = NodeLiteralEvaluator({"close": [1, 2, 3, 4, 5]})
    r1 = ev1.visit(tree.body)
    ev2 = NodeLiteralEvaluator({"close": [10, 20, 30]})
    r2 = ev2.visit(tree.body)
    assert r1 == [None, None, 2, 3, 4]
    assert r2 == [None, None, 20]

    calls = [n for n in walk(tree) if type(n).__name__ == "Call"]
    assert calls
    site = getattr(calls[0], "_pine_call_site", None)
    assert site is not None
    assert site[-1] == ev2._eval_generation
    assert getattr(site[2], "__self__", None) is ev2

    # First evaluator still computes from its own state after rebind.
    assert ev1.visit(tree.body) == r1
    assert getattr(calls[0], "_pine_call_site")[-1] == ev1._eval_generation


def test_parse_cache_two_runtimes_call_expr_history_independent() -> None:
    """Call-expr ``ta.sma(...)[1]`` must not leak across Runtime parse-cache hits."""
    from pynescript.ast.evaluator.expressions import pine_call_site_id
    from pynescript.ast.helper import walk
    from pynescript.runtime import Runtime

    src = """
//@version=5
indicator("hist")
plot(ta.sma(close, 3)[1], "s1")
"""
    clear_parse_cache()
    tree = parse(src)
    calls = [n for n in walk(tree) if type(n).__name__ == "Call"]
    assert calls
    sid = pine_call_site_id(calls[0])
    assert sid > 0
    assert getattr(calls[0], "_pine_site_id") == sid

    def _bars(n: int, start: float) -> list[dict[str, float | int]]:
        return [
            {
                "open": start + i,
                "high": start + i + 1,
                "low": start + i - 1,
                "close": start + i,
                "volume": 1.0,
                "time": 1_700_000_000_000 + i * 60_000,
            }
            for i in range(n)
        ]

    a = Runtime(symbol="A").run(src, _bars(8, 10.0), mode="interpret")
    b = Runtime(symbol="B").run(src, _bars(8, 100.0), mode="interpret")
    assert "error" not in a, a.get("error")
    assert "error" not in b, b.get("error")
    # Second run must not inherit first run's sma history.
    assert a["series"]["s1"][-1] != b["series"]["s1"][-1]
    assert getattr(calls[0], "_pine_site_id") == sid
