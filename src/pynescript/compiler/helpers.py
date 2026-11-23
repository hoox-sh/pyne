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
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Pure helper functions extracted from :mod:`pynescript.compiler.compiler`.

Kept in a separate module so the monolithic ``CompilerVisitor`` can be split
incrementally without changing behavior. These helpers have no dependency on
visitor state (no ``self``), so they are safe to import anywhere.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from pynescript.ast import node as ast


def _fold_int_attr(value: Any, default: int) -> int:
    """Best-effort ``int()`` of a folded literal; *default* when unconvertible."""
    try:
        return int(value)  # float("inf") → OverflowError, nan → ValueError
    except (TypeError, ValueError, OverflowError):
        return default


def _is_chart_point_namespace(recv: object) -> bool:
    """Whether ``recv`` is the ``chart.point`` namespace (not a value).

    ``chart.point.from_index`` / ``.copy`` / ``.now`` are namespace constructors.
    Lowering them as collection methods silently drops the point argument.
    """
    return (
        isinstance(recv, ast.Attribute)
        and recv.attr == "point"
        and isinstance(recv.value, ast.Name)
        and recv.value.id == "chart"
    )


def _iter_child_values(node: Any) -> Iterator[Any]:
    """Yield child field values of an AST node (slots-compatible traversal).

    ``node.__dict__.values()`` was used before AST nodes became slotted
    dataclasses — slotted nodes have no ``__dict__``, so traversal must go
    through the declared ``_fields``. Mirrors the old semantics: lists are
    yielded whole (callers recurse per item); unset fields are skipped.
    """
    for name in node._fields:
        try:
            yield getattr(node, name)
        except AttributeError:
            continue
