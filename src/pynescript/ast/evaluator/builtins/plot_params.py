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

"""Canonical Pine v6 plot-family signatures shared by every pyne surface.

Single source of truth for positional argument order so runtime capture,
interpret evaluation, host packing, and compile-mode collection never drift.
Wire tables list params exported to AXIS ``plot_meta`` (serialize-only
contract: omitted key == Pine default).
"""

from __future__ import annotations

import math

from typing import Any


# kind -> ((param, position), ...) in Pine v6 canonical order.
PLOT_PARAM_SPECS: dict[str, tuple[tuple[str, int], ...]] = {
    "plot": (
        ("series", 0),
        ("title", 1),
        ("color", 2),
        ("linewidth", 3),
        ("style", 4),
        ("trackprice", 5),
        ("histbase", 6),
        ("offset", 7),
        ("join", 8),
        ("editable", 9),
        ("show_last", 10),
        ("display", 11),
    ),
    "hline": (
        ("price", 0),
        ("title", 1),
        ("color", 2),
        ("linestyle", 3),
        ("linewidth", 4),
        ("editable", 5),
        ("display", 6),
    ),
    "bgcolor": (("color", 0), ("offset", 1), ("editable", 2), ("show_last", 3)),
    "barcolor": (("color", 0), ("offset", 1), ("editable", 2), ("show_last", 3)),
    "plotshape": (
        ("series", 0),
        ("title", 1),
        ("style", 2),
        ("location", 3),
        ("color", 4),
        ("offset", 5),
        ("text", 6),
        ("text_size", 7),
        ("editable", 8),
        ("show_last", 9),
    ),
    "plotchar": (
        ("series", 0),
        ("title", 1),
        ("char", 2),
        ("location", 3),
        ("color", 4),
        ("offset", 5),
        ("text", 6),
        ("text_size", 7),
        ("editable", 8),
        ("show_last", 9),
    ),
}

# Params exported to AXIS plot_meta, per kind (subset of the spec above).
WIRE_PARAMS: dict[str, tuple[str, ...]] = {
    "plot": ("trackprice", "histbase", "offset", "join", "editable", "show_last"),
    "hline": ("editable",),
    "bgcolor": ("offset", "editable", "show_last"),
    "barcolor": ("offset", "editable", "show_last"),
    "plotshape": ("offset", "editable", "show_last"),
    "plotchar": ("offset", "editable", "show_last"),
    "plotcandle": ("wickcolor", "bordercolor"),
    "plotbar": ("bordercolor",),
}

WIRE_INT_PARAMS = frozenset({"offset", "show_last"})
WIRE_FLOAT_PARAMS = frozenset({"histbase"})
WIRE_BOOL_PARAMS = frozenset({"trackprice", "join", "editable"})
WIRE_COLOR_PARAMS = frozenset({"wickcolor", "bordercolor"})

# Pine defaults; equal values are omitted from the wire payload.
WIRE_DEFAULTS: dict[str, Any] = {"offset": 0, "histbase": 0.0}


def param_index(kind: str, param: str) -> int:
    """Positional index of *param* for builtin *kind* (-1 when unknown)."""
    spec = PLOT_PARAM_SPECS.get(kind)
    if spec is None:
        return -1
    for name, pos in spec:
        if name == param:
            return pos
    return -1


def resolve_arg(
    kind: str,
    param: str,
    args: list[Any],
    kwargs: dict[str, Any] | None,
    default: Any = None,
) -> Any:
    """Kwarg-first resolution of *param* from raw call args."""
    if kwargs and param in kwargs:
        return kwargs[param]
    idx = param_index(kind, param)
    if idx >= 0 and len(args) > idx:
        return args[idx]
    return default


def _wire_color(value: Any) -> str | None:
    """Best-effort JSON-safe color string (hex int, str, to_rgba()/to_hex())."""
    if isinstance(value, str):
        return value or None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return f"#{value & 0xFFFFFF:06X}"
    for meth in ("to_rgba", "to_hex"):
        fn = getattr(value, meth, None)
        if callable(fn):
            try:
                return str(fn())
            except Exception:
                return None
    return None


def _coerce_wire_value(param: str, value: Any) -> Any:
    """Coerce *value* to its wire type; None when unserializable or default."""
    if param in WIRE_INT_PARAMS:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        iv = int(value)
        return None if iv == WIRE_DEFAULTS.get(param) else iv
    if param in WIRE_FLOAT_PARAMS:
        try:
            fv = float(value)
        except (TypeError, ValueError):
            return None
        return None if math.isnan(fv) or fv == WIRE_DEFAULTS.get(param) else fv
    if param in WIRE_BOOL_PARAMS and isinstance(value, (bool, int, float)):
        return bool(value)
    return _wire_color(value) if param in WIRE_COLOR_PARAMS else None


def extract_wire_meta(
    kind: str,
    args: list[Any],
    kwargs: dict[str, Any] | None,
    unwrap: Any = None,
) -> dict[str, Any]:
    """Serialize-only plot_meta extras from one first-sighting call.

    Defaults omitted; unresolvable dynamic-typed values skipped (callers may
    retry via lazy pending). *unwrap* optionally normalizes series/list to a
    scalar (hosts pass their unwrapper); kept as a parameter to avoid an
    import cycle with pynescript.runtime.
    """
    out: dict[str, Any] = {}
    for param in WIRE_PARAMS.get(kind, ()):
        raw = resolve_arg(kind, param, args or [], kwargs)
        if raw is None:
            continue
        value = unwrap(raw) if unwrap is not None else raw
        if value is None:
            continue
        coerced = _coerce_wire_value(param, value)
        if coerced is not None:
            out[param] = coerced
    return out
