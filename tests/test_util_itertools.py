# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Coverage for ``pynescript.util.itertools.grouper``."""

from __future__ import annotations

import pytest

from pynescript.util.itertools import grouper


def test_grouper_fill_pads_remainder() -> None:
    assert list(grouper(range(5), 2, incomplete="fill", fillvalue=-1)) == [
        (0, 1),
        (2, 3),
        (4, -1),
    ]


def test_grouper_fill_default_none() -> None:
    assert list(grouper("ABC", 2)) == [("A", "B"), ("C", None)]


def test_grouper_ignore_drops_remainder() -> None:
    assert list(grouper(range(5), 2, incomplete="ignore")) == [(0, 1), (2, 3)]


def test_grouper_strict_even() -> None:
    assert list(grouper([1, 2, 3, 4], 2, incomplete="strict")) == [(1, 2), (3, 4)]


def test_grouper_strict_raises_on_uneven() -> None:
    it = grouper([1, 2, 3], 2, incomplete="strict")
    next(it)
    with pytest.raises(ValueError):
        next(it)


def test_grouper_invalid_mode() -> None:
    with pytest.raises(ValueError, match="Expected fill"):
        list(grouper([1], 1, incomplete="drop"))


def test_grouper_empty() -> None:
    assert list(grouper([], 3)) == []
