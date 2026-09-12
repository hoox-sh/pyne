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

"""Intrabar rollback of ``var`` scope on realtime ticks (D-04 increment).

Reference Pine re-executes forming bars per tick with non-``varip`` state
rolled back to the last confirmed bar. Intermediate ticks therefore start
from confirmed state; only the final (confirmed) tick commits.
``varip`` persists across ticks by design.
"""

from __future__ import annotations

from types import SimpleNamespace

from pynescript.runtime import Runtime
from pynescript.runtime.host import _restore_realtime_scope
from pynescript.runtime.host import _snapshot_realtime_scope


def test_snapshot_restores_once_fired() -> None:
    ev = SimpleNamespace(
        context={"x": 1},
        _var_declarations=set(),
        _once_fired={42: True},
        _varip_declarations=set(),
    )
    snap = _snapshot_realtime_scope(ev)
    assert snap is not None
    assert snap["once_fired"] == {42: True}
    ev._once_fired[99] = True
    _restore_realtime_scope(ev, snap)
    assert ev._once_fired == {42: True}


def _bars(n: int = 5) -> list[dict[str, float | int]]:
    out: list[dict[str, float | int]] = []
    for i in range(n):
        c = 100.0 + i
        out.append(
            {
                "time": 1_704_067_200_000 + i * 86_400_000,
                "open": c,
                "high": c + 1.0,
                "low": c - 1.0,
                "close": c,
                "volume": 1000.0,
            }
        )
    return out


_COUNTER_SRC = """//@version=6
indicator("rt")
var int n = 0
varip int w = na(w[1]) ? 0 : w
n := n + 1
w := w + (barstate.isconfirmed ? 0 : 1)
plot(n, "n")
plot(w, "w")
"""


def test_var_rolls_back_across_intermediate_ticks() -> None:
    """``var`` counter commits once per bar, not once per tick."""
    out = Runtime(symbol="RT").run(_COUNTER_SRC, _bars(), mode="interpret", realtime_ticks=3)
    assert "error" not in out, out.get("error")
    n = [float(v) for v in out["series"]["n"]]
    # Historical bars 0-3 commit 1..4; last bar's 3 ticks each start from
    # confirmed 4 and commit 5 (not 5, 6, 7).
    assert n == [1.0, 2.0, 3.0, 4.0, 5.0], n


def test_varip_persists_across_intermediate_ticks() -> None:
    """``varip`` writes survive intermediate ticks (no rollback).

    The ``na(w[1])`` initializer is a no-op rebind on ticks (history is
    stable), so the ``:=`` accumulation is the only per-tick delta. Without
    varip tracking the restore would reset ``w`` to 0 every tick and the
    final bar would read 0.0.
    """
    out = Runtime(symbol="RT").run(_COUNTER_SRC, _bars(), mode="interpret", realtime_ticks=3)
    assert "error" not in out, out.get("error")
    w = [float(v) for v in out["series"]["w"]]
    # Historical bars are confirmed (+0); last bar ticks +1, +1, +0.
    assert w == [0.0, 0.0, 0.0, 0.0, 2.0], w


def test_single_tick_unchanged() -> None:
    """No realtime window: identical to the historical run."""
    out = Runtime(symbol="RT").run(_COUNTER_SRC, _bars(), mode="interpret")
    assert "error" not in out, out.get("error")
    assert [float(v) for v in out["series"]["n"]] == [1.0, 2.0, 3.0, 4.0, 5.0]
    assert [float(v) for v in out["series"]["w"]] == [0.0, 0.0, 0.0, 0.0, 0.0]


def test_plain_assignment_recomputes_from_confirmed() -> None:
    """Non-``var`` derived values recompute identically each tick."""
    src = """//@version=6
indicator("rt")
x = close * 2
plot(x, "x")
"""
    out = Runtime(symbol="RT").run(src, _bars(), mode="interpret", realtime_ticks=3)
    assert "error" not in out, out.get("error")
    assert [float(v) for v in out["series"]["x"]] == [200.0, 202.0, 204.0, 206.0, 208.0]


def _fake_evaluator() -> SimpleNamespace:
    """Duck-typed evaluator: one var, one varip, one series-like value."""
    series = SimpleNamespace(update=lambda v: None, current=10.0, history=[10.0, 9.0])
    return SimpleNamespace(
        context={"n": 4, "w": 7, "s": series, "host": "keep"},
        _var_declarations={"n", "w"},
        _varip_declarations={"w"},
    )


class TestScopeHelpers:
    """Unit coverage for the snapshot/restore pair (D-04 increment)."""

    def test_var_restored_varip_persists(self) -> None:
        ev = _fake_evaluator()
        snap = _snapshot_realtime_scope(ev)
        assert snap is not None
        ev.context["n"] = 99
        ev.context["w"] = 100
        _restore_realtime_scope(ev, snap)
        assert ev.context["n"] == 4
        assert ev.context["w"] == 100

    def test_new_names_removed(self) -> None:
        ev = _fake_evaluator()
        snap = _snapshot_realtime_scope(ev)
        assert snap is not None
        ev.context["tick_only"] = 1
        _restore_realtime_scope(ev, snap)
        assert "tick_only" not in ev.context
        assert ev.context["host"] == "keep"

    def test_series_current_restored(self) -> None:
        ev = _fake_evaluator()
        snap = _snapshot_realtime_scope(ev)
        assert snap is not None
        ev.context["s"].current = 99.0
        _restore_realtime_scope(ev, snap)
        assert ev.context["s"].current == 10.0

    def test_declarations_restored(self) -> None:
        ev = _fake_evaluator()
        snap = _snapshot_realtime_scope(ev)
        assert snap is not None
        ev.context["late"] = 1
        ev._var_declarations.add("late")
        _restore_realtime_scope(ev, snap)
        assert ev._var_declarations == {"n", "w"}
        assert "late" not in ev.context

    def test_helpers_never_raise_on_junk(self) -> None:
        assert _snapshot_realtime_scope(None) is None
        assert _snapshot_realtime_scope(SimpleNamespace()) is None
        _restore_realtime_scope(None, None)
        _restore_realtime_scope(SimpleNamespace(), None)
        _restore_realtime_scope(SimpleNamespace(), {})
        ev = _fake_evaluator()
        _restore_realtime_scope(ev, {"bogus": True})
