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
from typing import Any

import pytest

from pynescript.ast.evaluator.builtins.map import Map
from pynescript.ast.evaluator.builtins.map import RealtimeSnapshotError
from pynescript.ast.evaluator.builtins.matrix import Matrix
from pynescript.ast.type_system import BuiltinType
from pynescript.ast.type_system import BuiltinTypeKind
from pynescript.ast.type_system import Field
from pynescript.ast.type_system import ObjectInstance
from pynescript.ast.type_system import UserDefinedType
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


_VAR_ARRAY_SRC = """//@version=6
indicator("rt arr")
var a = array.new_float()
if barstate.isrealtime
    array.push(a, close)
plot(array.size(a), "sz")
"""


def test_var_array_push_rolls_back_unconfirmed_ticks() -> None:
    """``var`` array.push on the last bar commits once, not once per tick."""
    out = Runtime(symbol="RT").run(_VAR_ARRAY_SRC, _bars(), mode="interpret", realtime_ticks=3)
    assert "error" not in out, out.get("error")
    sz = [float(v) for v in out["series"]["sz"]]
    # Historical bars never push; last bar's 3 ticks each start empty and
    # only the confirmed tick keeps the one push (not 3).
    assert sz == [0.0, 0.0, 0.0, 0.0, 1.0], sz


_VAR_NESTED_ARRAY_SRC = """//@version=6
indicator("rt nested")
var a = array.new<array<float>>()
if array.size(a) == 0
    array.push(a, array.new_float())
if barstate.isrealtime
    array.push(array.get(a, 0), close)
plot(array.size(array.get(a, 0)), "sz")
"""


def test_var_nested_array_push_rolls_back_unconfirmed_ticks() -> None:
    """Inner ``array.push`` on a ``var`` list-of-lists commits once, not N ticks."""
    out = Runtime(symbol="RT").run(_VAR_NESTED_ARRAY_SRC, _bars(), mode="interpret", realtime_ticks=3)
    assert "error" not in out, out.get("error")
    sz = [float(v) for v in out["series"]["sz"]]
    # Historical bars seed an empty inner array; last bar's 3 ticks each
    # start from that empty inner and only the confirmed tick keeps one push.
    assert sz == [0.0, 0.0, 0.0, 0.0, 1.0], sz


def test_varip_array_pushes_persist_across_ticks() -> None:
    """``varip`` array mutations are not rolled back (same object).

    Script-level ``varip a = array.new_float()`` re-evaluates the RHS on
    each realtime tick (new empty handle). Persist is the restore skip:
    pushes on a kept varip list survive.
    """
    items: list[float] = []
    ev = SimpleNamespace(
        context={"a": items},
        _var_declarations={"a"},
        _varip_declarations={"a"},
    )
    snap = _snapshot_realtime_scope(ev)
    assert snap is not None
    items.append(10.0)
    items.append(20.0)
    items.append(30.0)
    _restore_realtime_scope(ev, snap)
    assert ev.context["a"] is items
    assert items == [10.0, 20.0, 30.0]


def test_var_matrix_set_rolls_back_unconfirmed_ticks() -> None:
    """``matrix.set`` on a ``var`` matrix commits the confirmed tick only."""
    src = """//@version=6
indicator("rt mat")
var m = matrix.new<float>(1, 1, 0.0)
if barstate.isrealtime
    matrix.set(m, 0, 0, matrix.get(m, 0, 0) + 1.0)
plot(matrix.get(m, 0, 0), "v")
"""
    out = Runtime(symbol="RT").run(src, _bars(), mode="interpret", realtime_ticks=3)
    assert "error" not in out, out.get("error")
    v = [float(x) for x in out["series"]["v"]]
    assert v == [0.0, 0.0, 0.0, 0.0, 1.0], v


def test_var_map_put_rolls_back_unconfirmed_ticks() -> None:
    """``map.put`` of distinct keys on a ``var`` map commits one entry."""
    src = """//@version=6
indicator("rt map")
var m = map.new<string, float>()
if barstate.isrealtime
    map.put(m, str.tostring(map.size(m)), close)
plot(map.size(m), "sz")
"""
    out = Runtime(symbol="RT").run(src, _bars(), mode="interpret", realtime_ticks=3)
    assert "error" not in out, out.get("error")
    sz = [float(v) for v in out["series"]["sz"]]
    assert sz == [0.0, 0.0, 0.0, 0.0, 1.0], sz


_NESTED_MAP_SRC = """//@version=6
indicator("rt nested map")
var m = map.new<string, map>()
if barstate.isfirst
    map.put(m, "k", map.new<string, float>())
if barstate.isrealtime
    map.put(map.get(m, "k"), "n", nz(map.get(map.get(m, "k"), "n")) + 1.0)
plot(map.get(map.get(m, "k"), "n"), "v")
"""

_NESTED_LIST_SRC = """//@version=6
indicator("rt nested list")
var m = map.new<string, list>()
if barstate.isfirst
    map.put(m, "k", array.from(0.0))
if barstate.isrealtime
    array.push(map.get(m, "k"), 1.0)
plot(array.size(map.get(m, "k")), "n")
"""


def test_var_map_nested_map_value_rolls_back_unconfirmed_ticks() -> None:
    """A nested map value must roll back with its owning ``var`` map."""
    out = Runtime(symbol="RT").run(_NESTED_MAP_SRC, _bars(), mode="interpret", realtime_ticks=3)
    assert "error" not in out, out.get("error")
    assert out["series"]["v"][-1] == 1.0
    compiled = Runtime(symbol="RT").run(_NESTED_MAP_SRC, _bars(), mode="compile", realtime_ticks=3)
    assert "error" not in compiled, compiled.get("error")
    assert compiled["series"]["v"][-1] == 1.0


_NESTED_MATRIX_SRC = """//@version=6
indicator("rt nested matrix")
var m = map.new<string, matrix>()
if barstate.isfirst
    map.put(m, "k", matrix.new<float>(1, 1, 0.0))
if barstate.isrealtime
    mat = map.get(m, "k")
    matrix.set(mat, 0, 0, matrix.get(mat, 0, 0) + 1.0)
plot(matrix.get(map.get(m, "k"), 0, 0), "v")
"""


def test_var_map_nested_matrix_value_rolls_back_unconfirmed_ticks() -> None:
    """A nested Matrix value rolls back with its owning ``var`` map (interpret)."""
    out = Runtime(symbol="RT").run(_NESTED_MATRIX_SRC, _bars(), mode="interpret", realtime_ticks=3)
    assert "error" not in out, out.get("error")
    assert out["series"]["v"][-1] == 1.0


def test_var_map_nested_list_value_rolls_back_unconfirmed_ticks() -> None:
    """A nested list value must roll back with its owning ``var`` map."""
    out = Runtime(symbol="RT").run(_NESTED_LIST_SRC, _bars(), mode="interpret", realtime_ticks=3)
    assert "error" not in out, out.get("error")
    assert [float(v) for v in out["series"]["n"]] == [1.0, 1.0, 1.0, 1.0, 2.0]
    compiled = Runtime(symbol="RT").run(_NESTED_LIST_SRC, _bars(), mode="compile", realtime_ticks=3)
    assert "error" not in compiled, compiled.get("error")
    assert [float(v) for v in compiled["series"]["n"]] == [1.0, 1.0, 1.0, 1.0, 2.0]


# Two handles, one list. Unconfirmed ticks drop the list from its parent and
# mutate the caller's handle. Rollback must put that same object back; the
# confirmed tick's push is then visible through the parent. A fresh list in
# the parent would stay at size 1.
_ALIAS_LIST_SRC = """//@version=6
indicator("rt list alias")
var held = array.from(0.0)
var outer = array.new<array<float>>()
if barstate.isfirst
    array.push(outer, held)
if barstate.isrealtime and not barstate.isconfirmed
    array.pop(outer)
    array.push(held, 1.0)
if barstate.isrealtime and barstate.isconfirmed
    array.push(held, 2.0)
plot(array.size(array.get(outer, 0)), "n")
"""

_ALIAS_MAP_LIST_SRC = """//@version=6
indicator("rt map list alias")
var held = array.from(0.0)
var m = map.new<string, array<float>>()
if barstate.isfirst
    map.put(m, "k", held)
if barstate.isrealtime and not barstate.isconfirmed
    map.remove(m, "k")
    array.push(held, 1.0)
if barstate.isrealtime and barstate.isconfirmed
    array.push(held, 2.0)
plot(array.size(map.get(m, "k")), "n")
"""


def test_nested_list_identity_survives_unconfirmed_tick_rollback() -> None:
    """A held nested list stays the object its parent had before the tick.

    Map, Matrix, and UDT values already restore into the same object. A list
    restored as a copy leaves the caller's handle stale: the confirmed push
    lands on ``held`` and the parent still shows the pre-tick size.
    """
    expected = [1.0, 1.0, 1.0, 1.0, 2.0]
    for src in (_ALIAS_LIST_SRC, _ALIAS_MAP_LIST_SRC):
        out = Runtime(symbol="RT").run(src, _bars(), mode="interpret", realtime_ticks=3)
        assert "error" not in out, out.get("error")
        assert [float(v) for v in out["series"]["n"]] == expected


def test_var_udt_field_rolls_back_unconfirmed_ticks() -> None:
    """UDT field writes on a ``var`` instance roll back with the object."""
    src = """//@version=6
indicator("rt udt")
type S
    float x = 0.0
var S s = S.new()
if barstate.isrealtime
    s.x := s.x + 1.0
plot(s.x, "x")
"""
    out = Runtime(symbol="RT").run(src, _bars(), mode="interpret", realtime_ticks=3)
    assert "error" not in out, out.get("error")
    x = [float(v) for v in out["series"]["x"]]
    assert x == [0.0, 0.0, 0.0, 0.0, 1.0], x


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

    def test_list_contents_restored_same_identity(self) -> None:
        items = [1.0]
        alias = items
        ev = SimpleNamespace(
            context={"a": items, "alias": alias, "host": "keep"},
            _var_declarations={"a", "alias"},
            _varip_declarations=set(),
        )
        snap = _snapshot_realtime_scope(ev)
        assert snap is not None
        items.append(2.0)
        _restore_realtime_scope(ev, snap)
        assert ev.context["a"] is items
        assert ev.context["alias"] is items
        assert items == [1.0]

    def test_nested_list_inner_append_rolls_back(self) -> None:
        """One extra list level: inner appends do not leak across restores."""
        inner: list[float] = []
        outer = [inner]
        ev = SimpleNamespace(
            context={"a": outer},
            _var_declarations={"a"},
            _varip_declarations=set(),
        )
        snap = _snapshot_realtime_scope(ev)
        assert snap is not None
        inner.append(1.0)
        inner.append(2.0)
        _restore_realtime_scope(ev, snap)
        assert ev.context["a"] is outer
        assert outer[0] is inner
        assert inner == []

    def test_nested_list_restore_keeps_snapshot_pristine(self) -> None:
        """Bar-open snapshots are reused (update_last_bar); inner copies stay frozen."""
        inner: list[float] = []
        outer = [inner]
        ev = SimpleNamespace(
            context={"a": outer},
            _var_declarations={"a"},
            _varip_declarations=set(),
        )
        snap = _snapshot_realtime_scope(ev)
        assert snap is not None
        outer[0].append(1.0)
        _restore_realtime_scope(ev, snap)
        outer[0].append(2.0)
        _restore_realtime_scope(ev, snap)
        assert ev.context["a"] is outer
        assert outer[0] == []

    def test_dict_of_lists_inner_append_rolls_back(self) -> None:
        """One extra dict level: list values roll back into the same list object."""
        inner: list[float] = []
        data = {"k": inner}
        ev = SimpleNamespace(
            context={"m": data},
            _var_declarations={"m"},
            _varip_declarations=set(),
        )
        snap = _snapshot_realtime_scope(ev)
        assert snap is not None
        inner.append(9.0)
        data["n"] = [1.0]
        _restore_realtime_scope(ev, snap)
        assert ev.context["m"] is data
        assert data["k"] is inner
        assert data == {"k": []}
        assert inner == []

    def test_removed_nested_list_keeps_identity(self) -> None:
        """Clearing a var array on a tick must not replace the nested list."""
        inner = [0.0]
        outer = [inner]
        ev = SimpleNamespace(
            context={"a": outer, "held": inner},
            _var_declarations={"a", "held"},
            _varip_declarations=set(),
        )
        snap = _snapshot_realtime_scope(ev)
        assert snap is not None
        outer.clear()
        inner.append(1.0)
        _restore_realtime_scope(ev, snap)
        assert outer[0] is inner
        assert ev.context["held"] is inner
        assert inner == [0.0]
        outer.clear()
        inner.append(2.0)
        _restore_realtime_scope(ev, snap)
        assert outer[0] is inner
        assert inner == [0.0]

    def test_varip_list_contents_persist(self) -> None:
        items = [1.0]
        ev = SimpleNamespace(
            context={"a": items},
            _var_declarations={"a"},
            _varip_declarations={"a"},
        )
        snap = _snapshot_realtime_scope(ev)
        assert snap is not None
        items.append(2.0)
        _restore_realtime_scope(ev, snap)
        assert ev.context["a"] is items
        assert items == [1.0, 2.0]

    def test_dict_contents_restored_same_identity(self) -> None:
        data = {"k": 1.0}
        ev = SimpleNamespace(
            context={"m": data},
            _var_declarations={"m"},
            _varip_declarations=set(),
        )
        snap = _snapshot_realtime_scope(ev)
        assert snap is not None
        data["k"] = 99.0
        data["n"] = 2.0
        _restore_realtime_scope(ev, snap)
        assert ev.context["m"] is data
        assert data == {"k": 1.0}

    def test_matrix_contents_restored_same_identity(self) -> None:
        mat = Matrix(1, 1, 0.0)
        ev = SimpleNamespace(
            context={"m": mat},
            _var_declarations={"m"},
            _varip_declarations=set(),
        )
        snap = _snapshot_realtime_scope(ev)
        assert snap is not None
        mat.set(0, 0, 7.0)
        mat.add_row([8.0])
        _restore_realtime_scope(ev, snap)
        assert ev.context["m"] is mat
        assert mat.rows() == 1
        assert mat.columns() == 1
        assert mat.get(0, 0) == 0.0

    def test_map_contents_restored_same_identity(self) -> None:
        mp = Map()
        mp.put("k", 1.0)
        ev = SimpleNamespace(
            context={"m": mp},
            _var_declarations={"m"},
            _varip_declarations=set(),
        )
        snap = _snapshot_realtime_scope(ev)
        assert snap is not None
        mp.put("k", 9.0)
        mp.put("n", 2.0)
        _restore_realtime_scope(ev, snap)
        assert ev.context["m"] is mp
        assert mp.size() == 1
        assert mp.get("k") == 1.0

    def test_udt_fields_restored_same_identity(self) -> None:
        udt = UserDefinedType("S")
        udt.add_field(Field("x", BuiltinType(BuiltinTypeKind.FLOAT), 0.0))
        inst = ObjectInstance(udt)
        ev = SimpleNamespace(
            context={"s": inst},
            _var_declarations={"s"},
            _varip_declarations=set(),
        )
        snap = _snapshot_realtime_scope(ev)
        assert snap is not None
        inst.set_field("x", 5.0)
        _restore_realtime_scope(ev, snap)
        assert ev.context["s"] is inst
        assert inst.get_field("x") == 0.0


def test_snapshot_realtime_scope_cyclic_map_raises() -> None:
    """A cyclic container fails closed instead of skipping the snapshot."""
    cyclic = Map()
    cyclic.data["self"] = cyclic
    ev = SimpleNamespace(
        context={"m": cyclic},
        _var_declarations={"m"},
        _varip_declarations=set(),
    )
    with pytest.raises(RealtimeSnapshotError, match="cyclic container"):
        _snapshot_realtime_scope(ev)


def _nested_map_snapshot() -> tuple[Map, Any]:
    outer = Map()
    inner = Map()
    inner.data["n"] = 7.0
    outer.data["k"] = inner
    return outer, outer.copy_contents()


def test_map_snapshot_restores_removed_nested_map() -> None:
    outer, snap = _nested_map_snapshot()
    outer.data.clear()
    outer.restore_contents(snap)
    restored = outer.data["k"]
    assert isinstance(restored, Map)
    assert restored.data == {"n": 7.0}


def test_map_snapshot_restores_removed_nested_matrix() -> None:
    outer = Map()
    outer.data["k"] = Matrix(1, 1, 7.0)
    snap = outer.copy_contents()
    outer.data.clear()
    outer.restore_contents(snap)
    restored = outer.data["k"]
    assert isinstance(restored, Matrix)
    assert restored.data == [[7.0]]


def test_map_snapshot_restores_removed_nested_udt() -> None:
    udt = UserDefinedType("S")
    udt.add_field(Field("x", BuiltinType(BuiltinTypeKind.FLOAT), 7.0))
    inst = ObjectInstance(udt)
    outer = Map()
    outer.data["k"] = inst
    snap = outer.copy_contents()
    outer.data.clear()
    outer.restore_contents(snap)
    restored = outer.data["k"]
    assert isinstance(restored, ObjectInstance)
    assert restored.fields == {"x": 7.0}


def test_map_snapshot_restores_replaced_nested_map() -> None:
    outer, snap = _nested_map_snapshot()
    outer.data["k"] = "replacement"
    outer.restore_contents(snap)
    restored = outer.data["k"]
    assert isinstance(restored, Map)
    assert restored.data == {"n": 7.0}


def test_map_snapshot_restores_removed_nested_list_identity() -> None:
    """A list removed from a map comes back as the same object, like a nested map."""
    inner = [0.0]
    outer = Map()
    outer.put("k", inner)
    snap = outer.copy_contents()
    outer.remove("k")
    inner.append(1.0)
    outer.restore_contents(snap)
    assert outer.get("k") is inner
    assert inner == [0.0]
    outer.put("k", [9.0])
    inner.append(2.0)
    outer.restore_contents(snap)
    assert outer.get("k") is inner
    assert inner == [0.0]
    outer.remove("k")
    inner.append(3.0)
    outer.restore_contents(snap)
    assert outer.get("k") is inner
    assert inner == [0.0]
