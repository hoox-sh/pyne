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

"""1-arg ``ta.max`` bar-mode incremental state matches the full recompute."""

from __future__ import annotations

from typing import Any

import pytest

from pynescript.ast.evaluator import NodeLiteralEvaluator


def _same(got: Any, exp: Any, where: str) -> None:
    if exp is None or got is None:
        assert got is exp, where
        return
    if isinstance(exp, float) and exp != exp:
        assert isinstance(got, float) and got != got, where
        return
    assert type(got) is type(exp), f"{where}: {got!r} vs {exp!r}"
    assert got == exp, where


class _BarTA(NodeLiteralEvaluator):
    def __init__(self) -> None:
        super().__init__()
        self._pine_bar_mode = True
        self._pine_ta_incremental = True
        self._ta_call_i = 0


def _walk(src: list[Any], *, incremental: bool, monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    if incremental:
        monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    else:
        monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    ev = _BarTA()
    out: list[Any] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._builtin_ta_max([src[: i + 1]]))
    return out


def test_unary_max_incremental_matches_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bar walk with the flag on equals ``PYNE_TA_INCREMENTAL=0`` (na, NaN, junk)."""
    src: list[Any] = [None, True, 0, None, 2, float("nan"), 2, "x", -1, None, 3.0, False]
    on = _walk(src, incremental=True, monkeypatch=monkeypatch)
    off = _walk(src, incremental=False, monkeypatch=monkeypatch)
    assert len(on) == len(off) == len(src)
    for i, (got, exp) in enumerate(zip(on, off, strict=True)):
        _same(got, exp, f"bar {i}")


def test_unary_max_respects_series_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    """Past ``_SERIES_MAX`` the oldest sample drops, including an early extreme."""
    cap = 4
    src: list[Any] = [100.0, None, 1.0, 2.0, None, 3.0, 0.5]
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    ev_on = _BarTA()
    ev_on._SERIES_MAX = cap
    on: list[Any] = []
    for i in range(len(src)):
        ev_on._ta_call_i = 0
        on.append(ev_on._builtin_ta_max([src[: i + 1]]))
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    ev_off = _BarTA()
    ev_off._SERIES_MAX = cap
    off: list[Any] = []
    for i in range(len(src)):
        ev_off._ta_call_i = 0
        off.append(ev_off._builtin_ta_max([src[: i + 1]]))
    for i, (got, exp) in enumerate(zip(on, off, strict=True)):
        _same(got, exp, f"cap bar {i}")
    # Last window is [2.0, None, 3.0, 0.5], not the leading 100.
    assert on[-1] == 3.0
    assert on[-1] != 100.0


def test_unary_max_second_call_does_not_rescan() -> None:
    """A later call appends one sample. The kept window object is not rebuilt."""
    src: list[Any] = [None, 1.0, None, 4.0, 2.0, None, 3.5, "nope", 0.25]
    ev = _BarTA()
    for i in range(len(src)):
        ev._ta_call_i = 0
        ev._builtin_ta_max([src[: i + 1]])
    assert len(ev._ta_inc_state) == 1
    st = next(iter(ev._ta_inc_state.values()))
    assert st["n"] == len(src)
    assert len(st["valid"]) < len(src)  # None / non-numeric are not stored
    window = st["valid"]
    ev._ta_call_i = 0
    ev._builtin_ta_max([src])
    assert st["valid"] is window
    assert st["n"] == len(src) + 1
    assert ev._ta_call_i == 0


def test_unary_max_call_sites_are_independent() -> None:
    ev = _BarTA()
    left = [1.0, 5.0, 2.0]
    right = [9.0, 0.5, 0.25]
    got_l: list[Any] = []
    got_r: list[Any] = []
    for i in range(len(left)):
        ev._pine_current_call_site = 1
        got_l.append(ev._builtin_ta_max([left[: i + 1]]))
        ev._pine_current_call_site = 2
        got_r.append(ev._builtin_ta_max([right[: i + 1]]))
    assert got_l == [1.0, 5.0, 5.0]
    assert got_r == [9.0, 9.0, 9.0]
    assert len(ev._ta_inc_state) == 2


def test_unary_max_same_bar_replaces_live_sample() -> None:
    """Same ``bar_index`` overwrites the live sample (8 must not stick)."""
    ev = _BarTA()
    ev.context["bar_index"] = 0
    assert ev._builtin_ta_max([[1.0]]) == 1.0
    ev.context["bar_index"] = 1
    assert ev._builtin_ta_max([[1.0, 8.0]]) == 8.0
    ev.context["bar_index"] = 1
    got = ev._builtin_ta_max([[1.0, None]])
    assert got == 1.0
    st = next(iter(ev._ta_inc_state.values()))
    assert st["n"] == 2
    assert st["seq"] == 2
