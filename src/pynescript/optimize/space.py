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

"""Search-space construction and value clamping."""

from __future__ import annotations

from typing import Any

from pynescript.optimize.types import ParamKind
from pynescript.optimize.types import ParamSpec
from pynescript.optimize.types import ParamValue
from pynescript.optimize.types import SearchSpace

SEARCHABLE_KINDS = frozenset({"int", "float", "price", "bool", "enum"})
SKIP_TYPES = frozenset(
    {"source", "timeframe", "symbol", "session", "color", "text", "unknown"}
)


def _as_float(v: Any) -> float | None:
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def _as_choices(raw: Any) -> tuple[ParamValue, ...] | None:
    if not isinstance(raw, (list, tuple)) or not raw:
        return None
    out: list[ParamValue] = []
    for item in raw:
        if isinstance(item, (int, float, bool, str)) and not (
            isinstance(item, float) and item != item
        ):
            out.append(item)
        else:
            out.append(str(item))
    return tuple(out) if out else None


def param_from_mapping(raw: dict[str, Any]) -> ParamSpec:
    """Build a :class:`ParamSpec` from a JSON / input-def mapping."""
    name = str(raw.get("name") or raw.get("title") or raw.get("id") or "").strip()
    if not name:
        raise ValueError("parameter is missing name/title")
    kind_raw = str(raw.get("kind") or raw.get("type") or "float").strip().lower()
    if kind_raw == "price":
        kind: ParamKind = "float"
    elif kind_raw in ("int", "float", "bool"):
        kind = kind_raw  # type: ignore[assignment]
    elif kind_raw in ("enum", "categorical", "select", "string"):
        kind = "categorical"
    else:
        raise ValueError(f"unsupported parameter kind: {kind_raw!r}")

    choices = _as_choices(raw.get("choices") or raw.get("options"))
    if kind == "bool":
        return ParamSpec(name=name, kind="bool", choices=(False, True))
    if kind == "categorical":
        if not choices:
            raise ValueError(f"{name!r}: categorical parameter needs choices/options")
        return ParamSpec(name=name, kind="categorical", choices=choices)

    lo = _as_float(raw.get("min") if raw.get("min") is not None else raw.get("minval"))
    hi = _as_float(raw.get("max") if raw.get("max") is not None else raw.get("maxval"))
    step = _as_float(raw.get("step"))
    if lo is None or hi is None:
        raise ValueError(f"{name!r}: numeric parameter needs min and max")
    if hi < lo:
        lo, hi = hi, lo
    if lo == hi:
        raise ValueError(f"{name!r}: min and max must differ")
    return ParamSpec(name=name, kind=kind, min=lo, max=hi, step=step)


def space_from_payload(raw: Any) -> SearchSpace:
    """Parse a ``space`` object from ``POST /optimize`` or a params list."""
    if isinstance(raw, SearchSpace):
        return raw
    items: list[Any]
    if isinstance(raw, dict):
        items = list(raw.get("params") or raw.get("parameters") or [])
    elif isinstance(raw, list):
        items = raw
    else:
        raise ValueError("space must be an object with params[] or a list")
    if not items:
        raise ValueError("space has no parameters")
    params: list[ParamSpec] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("each space param must be an object")
        spec = param_from_mapping(item)
        if spec.name in seen:
            raise ValueError(f"duplicate parameter {spec.name!r}")
        seen.add(spec.name)
        params.append(spec)
    return SearchSpace(params=params)


def space_from_input_defs(
    defs: list[dict[str, Any]],
    *,
    include: set[str] | None = None,
    overrides: dict[str, dict[str, Any]] | None = None,
) -> SearchSpace:
    """Build a space from Runtime-exported ``input.*`` declarations.

    Skips source/color/text/session fields. Numeric fields without min/max
    are omitted unless ``overrides`` supplies bounds.
    """
    params: list[ParamSpec] = []
    for d in defs:
        if not isinstance(d, dict):
            continue
        name = str(d.get("title") or d.get("id") or "").strip()
        if not name:
            continue
        if include is not None and name not in include:
            continue
        typ = str(d.get("type") or "").strip().lower()
        if typ in SKIP_TYPES:
            continue
        merged = dict(d)
        if overrides and name in overrides:
            merged.update(overrides[name])
        try:
            if typ in SEARCHABLE_KINDS or typ in ("int", "float", "bool", "enum", "price"):
                params.append(param_from_mapping({**merged, "name": name, "kind": typ or "float"}))
        except ValueError:
            continue
    if not params:
        raise ValueError("no searchable inputs (need int/float/bool/enum with bounds)")
    return SearchSpace(params=params)


def clamp_value(spec: ParamSpec, value: Any) -> ParamValue:
    """Project ``value`` onto ``spec`` (step, bounds, choices)."""
    if spec.kind == "bool":
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)
    if spec.kind == "categorical":
        choices = spec.choices or ()
        if value in choices:
            return value  # type: ignore[return-value]
        return choices[0] if choices else str(value)
    num = _as_float(value)
    if num is None:
        num = spec.min if spec.min is not None else 0.0
    lo = spec.min if spec.min is not None else num
    hi = spec.max if spec.max is not None else num
    num = min(hi, max(lo, num))
    if spec.step and spec.step > 0:
        steps = round((num - lo) / spec.step)
        num = lo + steps * spec.step
        if num > hi:
            num = lo + ((hi - lo) // spec.step) * spec.step
    if spec.kind == "int":
        return int(round(num))
    return float(num)


def clamp_params(space: SearchSpace, params: dict[str, Any]) -> dict[str, ParamValue]:
    """Clamp a full assignment onto ``space``."""
    out: dict[str, ParamValue] = {}
    for spec in space.params:
        raw = params.get(spec.name)
        out[spec.name] = clamp_value(spec, raw)
    return out


def grid_size(space: SearchSpace, *, max_points: int = 32) -> int:
    """Cartesian size, treating continuous axes as up to ``max_points`` steps."""
    n = 1
    for spec in space.params:
        n *= _axis_cardinality(spec, max_points=max_points)
        if n > 10_000_000:
            return n
    return n


def _axis_cardinality(spec: ParamSpec, *, max_points: int) -> int:
    if spec.kind == "bool":
        return 2
    if spec.kind == "categorical":
        return max(1, len(spec.choices or ()))
    lo = spec.min if spec.min is not None else 0.0
    hi = spec.max if spec.max is not None else lo
    if spec.step and spec.step > 0:
        n = max(1, int(round((hi - lo) / spec.step)) + 1)
        return max(1, min(n, max_points))
    if spec.kind == "int":
        n = max(1, int(round(hi)) - int(round(lo)) + 1)
        return max(1, min(n, max_points))
    return max(2, min(max_points, 8))
