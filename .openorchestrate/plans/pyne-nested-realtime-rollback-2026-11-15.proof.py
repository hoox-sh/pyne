# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Assertion proof: nested Map values roll back on unconfirmed realtime ticks."""

# ruff: noqa: S101, T201

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
from pynescript.runtime.host import _snapshot_realtime_scope


_NESTED_MAP = """//@version=6
indicator("rt nested map")
var m = map.new<string, map>()
if barstate.isfirst
    map.put(m, "k", map.new<string, float>())
if barstate.isrealtime
    map.put(map.get(m, "k"), "n", nz(map.get(map.get(m, "k"), "n")) + 1.0)
plot(map.get(map.get(m, "k"), "n"), "v")
"""

_NESTED_LIST = """//@version=6
indicator("rt nested list")
var m = map.new<string, list>()
if barstate.isfirst
    map.put(m, "k", array.from(0.0))
if barstate.isrealtime
    array.push(map.get(m, "k"), 1.0)
plot(array.size(map.get(m, "k")), "n")
"""

_NESTED_MATRIX = """//@version=6
indicator("rt nested matrix")
var m = map.new<string, matrix>()
if barstate.isfirst
    map.put(m, "k", matrix.new<float>(1, 1, 0.0))
if barstate.isrealtime
    mat = map.get(m, "k")
    matrix.set(mat, 0, 0, matrix.get(mat, 0, 0) + 1.0)
plot(matrix.get(map.get(m, "k"), 0, 0), "v")
"""

_SCALAR_MAP = """//@version=6
indicator("rt map")
var m = map.new<string, float>()
if barstate.isrealtime
    map.put(m, str.tostring(map.size(m)), close)
plot(map.size(m), "sz")
"""

_UDT_SCALAR = """//@version=6
indicator("rt udt")
type S
    float x = 0.0
var S s = S.new()
if barstate.isrealtime
    s.x := s.x + 1.0
plot(s.x, "x")
"""


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


def _run(src: str, mode: str) -> dict[str, Any]:
    return Runtime(symbol="RT").run(src, _bars(), mode=mode, realtime_ticks=3)


def main() -> None:
    # 1. Nested map value: unconfirmed mutations rolled back, confirmed commits.
    for mode in ("interpret", "compile"):
        out = _run(_NESTED_MAP, mode)
        assert "error" not in out, out.get("error")
        assert out["series"]["v"][-1] == 1.0, (mode, out["series"])

    # 2. Nested list value.
    for mode in ("interpret", "compile"):
        out = _run(_NESTED_LIST, mode)
        assert "error" not in out, out.get("error")
        assert [float(v) for v in out["series"]["n"]] == [1.0, 1.0, 1.0, 1.0, 2.0], (mode, out["series"])

    # 3. Nested Matrix value (interpret; compile nested-Matrix is a pre-existing gap).
    matrix = _run(_NESTED_MATRIX, "interpret")
    assert "error" not in matrix, matrix.get("error")
    assert matrix["series"]["v"][-1] == 1.0, matrix["series"]

    # 4. Regressions: scalar map put and UDT scalar field still roll back.
    scalar = _run(_SCALAR_MAP, "interpret")
    assert "error" not in scalar, scalar.get("error")
    assert [float(v) for v in scalar["series"]["sz"]] == [0.0, 0.0, 0.0, 0.0, 1.0], scalar["series"]
    udt = _run(_UDT_SCALAR, "interpret")
    assert "error" not in udt, udt.get("error")
    assert [float(v) for v in udt["series"]["x"]] == [0.0, 0.0, 0.0, 0.0, 1.0], udt["series"]

    # 5. Cycles fail closed (host does not silently skip the snapshot).
    cyclic = Map()
    cyclic.data["self"] = cyclic
    ev = SimpleNamespace(
        context={"m": cyclic},
        _var_declarations={"m"},
        _varip_declarations=set(),
    )
    with pytest.raises(RealtimeSnapshotError, match="cyclic container"):
        _snapshot_realtime_scope(ev)

    # 6. Removed/replaced nested containers restore with their original type.
    def _nested_map() -> tuple[Map, Any]:
        outer = Map()
        inner = Map()
        inner.data["n"] = 7.0
        outer.data["k"] = inner
        return outer, outer.copy_contents()

    outer, snap = _nested_map()
    outer.data.clear()
    outer.restore_contents(snap)
    assert isinstance(outer.data["k"], Map)
    assert outer.data["k"].data == {"n": 7.0}

    outer = Map()
    outer.data["k"] = Matrix(1, 1, 7.0)
    snap = outer.copy_contents()
    outer.data.clear()
    outer.restore_contents(snap)
    assert isinstance(outer.data["k"], Matrix)
    assert outer.data["k"].data == [[7.0]]

    udt = UserDefinedType("S")
    udt.add_field(Field("x", BuiltinType(BuiltinTypeKind.FLOAT), 7.0))
    outer = Map()
    outer.data["k"] = ObjectInstance(udt)
    snap = outer.copy_contents()
    outer.data.clear()
    outer.restore_contents(snap)
    assert isinstance(outer.data["k"], ObjectInstance)
    assert outer.data["k"].fields == {"x": 7.0}

    outer, snap = _nested_map()
    outer.data["k"] = "replacement"
    outer.restore_contents(snap)
    assert isinstance(outer.data["k"], Map)
    assert outer.data["k"].data == {"n": 7.0}

    print("NESTED_ROLLBACK_OK map=1.0 list=2.0 matrix=1.0 scalar=1.0 udt=1.0 cycle=1 removed=1 replaced=1")


if __name__ == "__main__":
    main()
