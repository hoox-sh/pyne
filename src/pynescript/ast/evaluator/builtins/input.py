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

"""Pine Script ``input.*`` builtins.

Pine Script semantics: every ``input.*`` call evaluates to the (default or
user-overridden) parameter value at runtime. Metadata (title, minval, group,
``active``, …) is retained on the evaluator as a side channel for UI/LSP
backends via ``_input_declarations``.
"""

from __future__ import annotations

from typing import Any

from .base import BuiltinDispatchMixin
from .base import BuiltinHandler


def _infer_type(defval: Any) -> str:
    if isinstance(defval, bool):
        return "bool"
    if isinstance(defval, int):
        return "int"
    if isinstance(defval, float):
        return "float"
    if isinstance(defval, str):
        return "string"
    return "float"


# Standard ``input.source`` dropdown (reference Pine parity).
DEFAULT_SOURCE_OPTIONS: tuple[str, ...] = (
    "open",
    "high",
    "low",
    "close",
    "hl2",
    "hlc3",
    "ohlc4",
)

# Names resolvable from chart context / current_series (includes volume/tr).
_BUILTIN_SOURCE_NAMES: frozenset[str] = frozenset((*DEFAULT_SOURCE_OPTIONS, "volume", "tr"))


class InputBuiltinsMixin(BuiltinDispatchMixin):
    """``input`` / ``input.*`` parameter builtins with metadata side channel.

    Each call returns the resolved default (or host override) and records
    declaration metadata on ``_input_declarations`` for UI/LSP hosts, unless
    ``_pine_defs_locked`` or light-plot mode suppresses recording.
    """

    def _input_builtin_map(self) -> dict[str, BuiltinHandler]:
        return {
            "input": self._handle_input,
            "input.bool": self._handle_input_bool,
            "input.int": self._handle_input_int,
            "input.float": self._handle_input_float,
            "input.price": self._handle_input_price,
            "input.string": self._handle_input_string,
            "input.symbol": self._handle_input_symbol,
            "input.session": self._handle_input_session,
            "input.source": self._handle_input_source,
            "input.time": self._handle_input_time,
            "input.timeframe": self._handle_input_timeframe,
            "input.color": self._handle_input_color,
            "input.enum": self._handle_input_enum,
            "input.text_area": self._handle_input_text_area,
        }

    def _record_input(self, meta: dict[str, Any]) -> None:
        """Append input metadata for hosts (UI, LSP, settings panels).

        After the first bar (``_pine_defs_locked``), skip re-recording so
        multi-thousand-bar runs do not grow an O(bars x inputs) list.

        ``_pine_light_plots`` (``PYNE_LIGHT_PLOTS=1``) skips meta entirely —
        corpus / success-only hosts do not need AXIS input panels.
        """
        if getattr(self, "_pine_defs_locked", False):
            return
        if getattr(self, "_pine_light_plots", False):
            return
        decls = getattr(self, "_input_declarations", None)
        if decls is None:
            decls = []
            try:
                self._input_declarations = decls  # type: ignore[attr-defined]
            except Exception:
                return
        decls.append(meta)

    def _resolve_override(self, title: str | None, defval: Any) -> Any:
        """Apply host-provided input overrides keyed by title when present.

        Scalar inputs (int/float/bool/string) must not receive a full series list
        from AXIS plot-source expansion or last-run snapshots — peel to the
        current sample so ``plot(..., linewidth=input.int(...))`` does not
        crash with ``int(list)``.
        """
        overrides = getattr(self, "_input_overrides", None)
        if not overrides or not title:
            return defval
        if title not in overrides:
            return defval
        raw = overrides[title]
        # input.source: host may pass a full series list; keep it so
        # ``_coerce_source_value`` can sample by ``bar_index``.
        # Scalar inputs (int/float/bool/string) peel list snapshots to last bar
        # so AXIS plot-source expansions do not crash ``int(list)``.
        if isinstance(raw, list):
            if not raw:
                return defval
            if isinstance(defval, str) and defval in _BUILTIN_SOURCE_NAMES:
                return raw
            last = raw[-1]
            if isinstance(defval, (int, float, bool, str)) or defval is None:
                if isinstance(last, list) and last:
                    last = last[-1]
                if isinstance(last, (int, float, bool, str)) or last is None:
                    return last if last is not None else defval
            # Complex default (series object, etc.) — keep the list
            return raw
        return raw

    def _handle_input(self, args: list[Any]) -> Any:
        """input(defval, title, tooltip, inline, group, confirm, active) → value."""
        defval = args[0] if len(args) > 0 else None
        title = args[1] if len(args) > 1 else ""
        tooltip = args[2] if len(args) > 2 else ""
        inline = args[3] if len(args) > 3 else None
        group = args[4] if len(args) > 4 else None
        confirm = args[5] if len(args) > 5 else False
        active = args[6] if len(args) > 6 else True
        value = self._resolve_override(title or None, defval)
        self._record_input(
            {
                "type": _infer_type(defval),
                "default": defval,
                "value": value,
                "title": title,
                "tooltip": tooltip,
                "inline": inline,
                "group": group,
                "confirm": confirm,
                "active": active,
            }
        )
        return value

    def _handle_input_bool(self, args: list[Any]) -> bool:
        """input.bool(defval, title, ...) → bool value."""
        defval = args[0] if len(args) > 0 else False
        title = args[1] if len(args) > 1 else ""
        tooltip = args[2] if len(args) > 2 else ""
        inline = args[3] if len(args) > 3 else None
        group = args[4] if len(args) > 4 else None
        confirm = args[5] if len(args) > 5 else False
        active = args[6] if len(args) > 6 else True
        value = bool(self._resolve_override(title or None, defval))
        self._record_input(
            {
                "type": "bool",
                "default": defval,
                "value": value,
                "title": title,
                "tooltip": tooltip,
                "inline": inline,
                "group": group,
                "confirm": confirm,
                "active": active,
            }
        )
        return value

    def _handle_input_int(self, args: list[Any]) -> int:
        """input.int(defval, title, minval, maxval, step, ...) → int value."""
        defval = args[0] if len(args) > 0 else 0
        title = args[1] if len(args) > 1 else ""
        minval = args[2] if len(args) > 2 else None
        maxval = args[3] if len(args) > 3 else None
        step = args[4] if len(args) > 4 else 1
        tooltip = args[5] if len(args) > 5 else ""
        inline = args[6] if len(args) > 6 else None
        group = args[7] if len(args) > 7 else None
        confirm = args[8] if len(args) > 8 else False
        active = args[9] if len(args) > 9 else True
        raw = self._resolve_override(title or None, defval)
        if isinstance(raw, float) and raw == int(raw):
            value = int(raw)
        else:
            value = raw
        self._record_input(
            {
                "type": "int",
                "default": defval,
                "value": value,
                "title": title,
                "min": minval,
                "max": maxval,
                "step": step,
                "tooltip": tooltip,
                "inline": inline,
                "group": group,
                "confirm": confirm,
                "active": active,
            }
        )
        return value

    def _handle_input_float(self, args: list[Any]) -> float:
        """input.float(defval, title, minval, maxval, step, ...) → float value."""
        defval = args[0] if len(args) > 0 else 0.0
        title = args[1] if len(args) > 1 else ""
        minval = args[2] if len(args) > 2 else None
        maxval = args[3] if len(args) > 3 else None
        step = args[4] if len(args) > 4 else None
        tooltip = args[5] if len(args) > 5 else ""
        inline = args[6] if len(args) > 6 else None
        group = args[7] if len(args) > 7 else None
        confirm = args[8] if len(args) > 8 else False
        active = args[9] if len(args) > 9 else True
        value = float(self._resolve_override(title or None, defval))
        self._record_input(
            {
                "type": "float",
                "default": defval,
                "value": value,
                "title": title,
                "min": minval,
                "max": maxval,
                "step": step,
                "tooltip": tooltip,
                "inline": inline,
                "group": group,
                "confirm": confirm,
                "active": active,
            }
        )
        return value

    def _handle_input_price(self, args: list[Any]) -> float:
        """input.price(...) → float value (price-optimized float input)."""
        defval = args[0] if len(args) > 0 else 0.0
        title = args[1] if len(args) > 1 else ""
        minval = args[2] if len(args) > 2 else None
        maxval = args[3] if len(args) > 3 else None
        step = args[4] if len(args) > 4 else None
        tooltip = args[5] if len(args) > 5 else ""
        inline = args[6] if len(args) > 6 else None
        group = args[7] if len(args) > 7 else None
        confirm = args[8] if len(args) > 8 else False
        active = args[9] if len(args) > 9 else True
        value = float(self._resolve_override(title or None, defval))
        self._record_input(
            {
                "type": "price",
                "default": defval,
                "value": value,
                "title": title,
                "min": minval,
                "max": maxval,
                "step": step,
                "tooltip": tooltip,
                "inline": inline,
                "group": group,
                "confirm": confirm,
                "active": active,
            }
        )
        return value

    def _handle_input_string(self, args: list[Any]) -> str:
        """input.string(...) → str value."""
        defval = args[0] if len(args) > 0 else ""
        title = args[1] if len(args) > 1 else ""
        tooltip = args[2] if len(args) > 2 else ""
        inline = args[3] if len(args) > 3 else None
        group = args[4] if len(args) > 4 else None
        confirm = args[5] if len(args) > 5 else False
        active = args[6] if len(args) > 6 else True
        value = str(self._resolve_override(title or None, defval))
        self._record_input(
            {
                "type": "string",
                "default": defval,
                "value": value,
                "title": title,
                "tooltip": tooltip,
                "inline": inline,
                "group": group,
                "confirm": confirm,
                "active": active,
            }
        )
        return value

    def _handle_input_symbol(self, args: list[Any]) -> str:
        """input.symbol(...) → str symbol."""
        defval = args[0] if len(args) > 0 else ""
        title = args[1] if len(args) > 1 else ""
        tooltip = args[2] if len(args) > 2 else ""
        inline = args[3] if len(args) > 3 else None
        group = args[4] if len(args) > 4 else None
        confirm = args[5] if len(args) > 5 else False
        active = args[6] if len(args) > 6 else True
        value = str(self._resolve_override(title or None, defval))
        self._record_input(
            {
                "type": "symbol",
                "default": defval,
                "value": value,
                "title": title,
                "tooltip": tooltip,
                "inline": inline,
                "group": group,
                "confirm": confirm,
                "active": active,
            }
        )
        return value

    def _handle_input_session(self, args: list[Any]) -> str:
        """input.session(...) → session string."""
        defval = args[0] if len(args) > 0 else ""
        title = args[1] if len(args) > 1 else ""
        tooltip = args[2] if len(args) > 2 else ""
        inline = args[3] if len(args) > 3 else None
        group = args[4] if len(args) > 4 else None
        confirm = args[5] if len(args) > 5 else False
        active = args[6] if len(args) > 6 else True
        value = str(self._resolve_override(title or None, defval))
        self._record_input(
            {
                "type": "session",
                "default": defval,
                "value": value,
                "title": title,
                "tooltip": tooltip,
                "inline": inline,
                "group": group,
                "confirm": confirm,
                "active": active,
            }
        )
        return value

    def _coerce_source_value(self, value: Any) -> Any:
        """Resolve host overrides into a bar-time series sample.

        Supports:
        - Built-in names (``close``, ``hlc3``, …) → context PineSeries / current_series
        - Full series lists from hosts (other-indicator plots) → value at ``bar_index``
        - Existing series objects / scalars → returned as-is
        """
        if isinstance(value, (list, tuple)):
            ctx = getattr(self, "context", None) or {}
            try:
                bi = int(ctx.get("bar_index", 0) or 0)
            except (TypeError, ValueError):
                bi = 0
            if 0 <= bi < len(value):
                return value[bi]
            if len(value):
                return value[-1]
            return None

        if isinstance(value, str):
            name = value.strip()
            if name in _BUILTIN_SOURCE_NAMES:
                ctx = getattr(self, "context", None) or {}
                series = ctx.get(name)
                if series is not None:
                    return series
                hist = (getattr(self, "current_series", None) or {}).get(name)
                if isinstance(hist, list) and hist:
                    return hist[-1]
            return value

        return value

    def _source_ui_label(self, value: Any, fallback: str = "close") -> str:
        """Stable string label for Inputs UI (never a raw series list)."""
        if isinstance(value, str) and value:
            return value
        if isinstance(value, (list, tuple)):
            return fallback
        name = getattr(value, "name", None)
        if isinstance(name, str) and name:
            return name
        return fallback

    def _handle_input_source(self, args: list[Any]) -> Any:
        """input.source(...) → series source (string name or series value).

        Hosts (AXIS settings, etc.) need the standard OHLC enum list when no
        custom options are provided — mirror reference Pine source dropdown:
        open, high, low, close, hl2, hlc3, ohlc4.

        Hosts may also pass a full series list (other indicator plot) as the
        override; it is sampled per ``bar_index``.
        """
        defval = args[0] if len(args) > 0 else "close"
        title = args[1] if len(args) > 1 else ""
        tooltip = args[2] if len(args) > 2 else ""
        inline = args[3] if len(args) > 3 else None
        group = args[4] if len(args) > 4 else None
        confirm = args[5] if len(args) > 5 else False
        active = args[6] if len(args) > 6 else True
        raw = self._resolve_override(title or None, defval)
        value = self._coerce_source_value(raw)
        default_label = self._source_ui_label(defval, "close")
        value_label = self._source_ui_label(raw, default_label)
        self._record_input(
            {
                "type": "source",
                "default": default_label,
                "value": value_label,
                "title": title,
                "tooltip": tooltip,
                "inline": inline,
                "group": group,
                "confirm": confirm,
                "active": active,
                "options": list(DEFAULT_SOURCE_OPTIONS),
            }
        )
        return value

    def _handle_input_time(self, args: list[Any]) -> int:
        """input.time(...) → Unix timestamp int."""
        defval = args[0] if len(args) > 0 else 0
        title = args[1] if len(args) > 1 else ""
        tooltip = args[2] if len(args) > 2 else ""
        inline = args[3] if len(args) > 3 else None
        group = args[4] if len(args) > 4 else None
        confirm = args[5] if len(args) > 5 else False
        active = args[6] if len(args) > 6 else True
        raw = self._resolve_override(title or None, defval)
        if isinstance(raw, float) and raw == int(raw):
            value = int(raw)
        else:
            value = raw
        self._record_input(
            {
                "type": "time",
                "default": defval,
                "value": value,
                "title": title,
                "tooltip": tooltip,
                "inline": inline,
                "group": group,
                "confirm": confirm,
                "active": active,
            }
        )
        return value

    def _handle_input_timeframe(self, args: list[Any]) -> str:
        """input.timeframe(...) → timeframe string."""
        defval = args[0] if len(args) > 0 else ""
        title = args[1] if len(args) > 1 else ""
        tooltip = args[2] if len(args) > 2 else ""
        inline = args[3] if len(args) > 3 else None
        group = args[4] if len(args) > 4 else None
        confirm = args[5] if len(args) > 5 else False
        active = args[6] if len(args) > 6 else True
        value = str(self._resolve_override(title or None, defval))
        self._record_input(
            {
                "type": "timeframe",
                "default": defval,
                "value": value,
                "title": title,
                "tooltip": tooltip,
                "inline": inline,
                "group": group,
                "confirm": confirm,
                "active": active,
            }
        )
        return value

    def _handle_input_color(self, args: list[Any]) -> Any:
        """input.color(...) → color value."""
        defval = args[0] if len(args) > 0 else "#000000"
        title = args[1] if len(args) > 1 else ""
        tooltip = args[2] if len(args) > 2 else ""
        inline = args[3] if len(args) > 3 else None
        group = args[4] if len(args) > 4 else None
        confirm = args[5] if len(args) > 5 else False
        active = args[6] if len(args) > 6 else True
        value = self._resolve_override(title or None, defval)
        self._record_input(
            {
                "type": "color",
                "default": defval,
                "value": value,
                "title": title,
                "tooltip": tooltip,
                "inline": inline,
                "group": group,
                "confirm": confirm,
                "active": active,
            }
        )
        return value

    def _handle_input_enum(self, args: list[Any]) -> Any:
        """input.enum(defval, title, options?, ...) → selected enum value.

        Pine signature (v5/v6)::

            input.enum(defval, title, options, tooltip, inline, group, confirm, display, active)

        ``options`` is optional. When omitted, reference Pine populates the dropdown
        from the enum type of ``defval``. Keyword-only calls like
        ``input.enum(Easing.linear, title="…", group="…")`` leave a sparse
        kwargs merge hole at the ``options`` slot (``None``), which must not be
        treated as an iterable.
        """
        defval = args[0] if len(args) > 0 else ""
        title = args[1] if len(args) > 1 else ""
        # Sparse kwargs merge pads missing slots with None — treat as omitted.
        options = args[2] if len(args) > 2 else None
        tooltip = args[3] if len(args) > 3 and args[3] is not None else ""
        inline = args[4] if len(args) > 4 else None
        group = args[5] if len(args) > 5 else None
        confirm = args[6] if len(args) > 6 and args[6] is not None else False
        active = args[7] if len(args) > 7 and args[7] is not None else True
        value = self._resolve_override(title or None, defval)
        opt_list = self._coerce_input_enum_options(options, defval)
        self._record_input(
            {
                "type": "enum",
                "default": defval,
                "value": value,
                "title": title,
                "options": opt_list,
                "tooltip": tooltip,
                "inline": inline,
                "group": group,
                "confirm": confirm,
                "active": active,
            }
        )
        return value

    def _coerce_input_enum_options(self, options: Any, defval: Any) -> list[Any]:
        """Normalize ``input.enum`` options; infer members from ``defval`` when omitted.

        Args:
            options: Explicit options list/tuple, or ``None`` when not provided.
            defval: Default enum member (often ``"EnumName.member"`` string).

        Returns:
            A list of option values suitable for the Inputs UI / overrides.
        """
        if options is None:
            # Infer full enum member list from defval when possible.
            enum_name: str | None = None
            if isinstance(defval, str) and "." in defval:
                enum_name = defval.split(".", 1)[0]
            ctx = getattr(self, "context", None)
            if enum_name and isinstance(ctx, dict):
                enum_def = ctx.get(enum_name)
                if isinstance(enum_def, dict):
                    return list(enum_def.values())
            return []
        if isinstance(options, list):
            return options
        if isinstance(options, tuple):
            return list(options)
        # array.* wrappers / generic sequences
        try:
            return list(options)
        except TypeError:
            return []

    def _handle_input_text_area(self, args: list[Any]) -> str:
        """input.text_area(defval, title, ...) → multiline string value."""
        defval = args[0] if len(args) > 0 else ""
        title = args[1] if len(args) > 1 else ""
        tooltip = args[2] if len(args) > 2 else ""
        inline = args[3] if len(args) > 3 else None
        group = args[4] if len(args) > 4 else None
        confirm = args[5] if len(args) > 5 else False
        active = args[6] if len(args) > 6 else True
        value = str(self._resolve_override(title or None, defval))
        self._record_input(
            {
                "type": "text_area",
                "default": defval,
                "value": value,
                "title": title,
                "tooltip": tooltip,
                "inline": inline,
                "group": group,
                "confirm": confirm,
                "active": active,
            }
        )
        return value


# KWARG_ORDER so _merge_kwargs_into_args maps keyword args to positionals.
InputBuiltinsMixin._handle_input._KWARG_ORDER = [
    "defval",
    "title",
    "tooltip",
    "inline",
    "group",
    "confirm",
    "active",
]
InputBuiltinsMixin._handle_input_bool._KWARG_ORDER = [
    "defval",
    "title",
    "tooltip",
    "inline",
    "group",
    "confirm",
    "active",
]
InputBuiltinsMixin._handle_input_int._KWARG_ORDER = [
    "defval",
    "title",
    "minval",
    "maxval",
    "step",
    "tooltip",
    "inline",
    "group",
    "confirm",
    "active",
]
InputBuiltinsMixin._handle_input_float._KWARG_ORDER = [
    "defval",
    "title",
    "minval",
    "maxval",
    "step",
    "tooltip",
    "inline",
    "group",
    "confirm",
    "active",
]
InputBuiltinsMixin._handle_input_price._KWARG_ORDER = [
    "defval",
    "title",
    "minval",
    "maxval",
    "step",
    "tooltip",
    "inline",
    "group",
    "confirm",
    "active",
]
InputBuiltinsMixin._handle_input_string._KWARG_ORDER = [
    "defval",
    "title",
    "tooltip",
    "inline",
    "group",
    "confirm",
    "active",
]
InputBuiltinsMixin._handle_input_symbol._KWARG_ORDER = [
    "defval",
    "title",
    "tooltip",
    "inline",
    "group",
    "confirm",
    "active",
]
InputBuiltinsMixin._handle_input_session._KWARG_ORDER = [
    "defval",
    "title",
    "tooltip",
    "inline",
    "group",
    "confirm",
    "active",
]
InputBuiltinsMixin._handle_input_source._KWARG_ORDER = [
    "defval",
    "title",
    "tooltip",
    "inline",
    "group",
    "confirm",
    "active",
]
InputBuiltinsMixin._handle_input_time._KWARG_ORDER = [
    "defval",
    "title",
    "tooltip",
    "inline",
    "group",
    "confirm",
    "active",
]
InputBuiltinsMixin._handle_input_timeframe._KWARG_ORDER = [
    "defval",
    "title",
    "tooltip",
    "inline",
    "group",
    "confirm",
    "active",
]
InputBuiltinsMixin._handle_input_color._KWARG_ORDER = [
    "defval",
    "title",
    "tooltip",
    "inline",
    "group",
    "confirm",
    "active",
]
InputBuiltinsMixin._handle_input_enum._KWARG_ORDER = [
    "defval",
    "title",
    "options",
    "tooltip",
    "inline",
    "group",
    "confirm",
    "active",
]
InputBuiltinsMixin._handle_input_text_area._KWARG_ORDER = [
    "defval",
    "title",
    "tooltip",
    "inline",
    "group",
    "confirm",
    "active",
]


_INPUT_ORDERS: dict[str, tuple[str, list[str]]] = {
    "input": ("", list(InputBuiltinsMixin._handle_input._KWARG_ORDER)),
    "input.bool": ("bool", list(InputBuiltinsMixin._handle_input_bool._KWARG_ORDER)),
    "input.int": ("int", list(InputBuiltinsMixin._handle_input_int._KWARG_ORDER)),
    "input.float": ("float", list(InputBuiltinsMixin._handle_input_float._KWARG_ORDER)),
    "input.price": ("price", list(InputBuiltinsMixin._handle_input_price._KWARG_ORDER)),
    "input.string": ("string", list(InputBuiltinsMixin._handle_input_string._KWARG_ORDER)),
    "input.symbol": ("symbol", list(InputBuiltinsMixin._handle_input_symbol._KWARG_ORDER)),
    "input.session": ("session", list(InputBuiltinsMixin._handle_input_session._KWARG_ORDER)),
    "input.source": ("source", list(InputBuiltinsMixin._handle_input_source._KWARG_ORDER)),
    "input.time": ("time", list(InputBuiltinsMixin._handle_input_time._KWARG_ORDER)),
    "input.timeframe": ("timeframe", list(InputBuiltinsMixin._handle_input_timeframe._KWARG_ORDER)),
    "input.color": ("color", list(InputBuiltinsMixin._handle_input_color._KWARG_ORDER)),
    "input.enum": ("enum", list(InputBuiltinsMixin._handle_input_enum._KWARG_ORDER)),
    "input.text_area": ("text_area", list(InputBuiltinsMixin._handle_input_text_area._KWARG_ORDER)),
}

_STRING_INPUTS = frozenset({"string", "symbol", "session", "timeframe", "color", "text_area"})
_UNFOLDABLE = object()


def _input_callee(func: Any) -> str | None:
    from pynescript.ast import node as ast

    if isinstance(func, ast.Name):
        return str(func.id or "")
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return f"{func.value.id}.{func.attr}"
    return None


def _fold_input_expr(node: Any) -> Any:
    """Fold a literal input argument. ``_UNFOLDABLE`` when it is not a constant."""
    from pynescript.ast import node as ast

    if node is None:
        return None
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id in ("true", "True"):
            return True
        if node.id in ("false", "False"):
            return False
        if node.id == "na":
            return None
        if node.id in _BUILTIN_SOURCE_NAMES:
            return node.id
    if isinstance(node, ast.Tuple):
        folded = []
        for elt in node.elts or []:
            value = _fold_input_expr(elt)
            if value is _UNFOLDABLE:
                return _UNFOLDABLE
            folded.append(value)
        return folded
    return _UNFOLDABLE


def _input_slots(call: Any, order: list[str]) -> dict[str, Any] | None:
    """Merge positional and named args. None when a provided arg is not a literal."""
    positionals: list[Any] = []
    named: dict[str, Any] = {}
    for arg in call.args or []:
        value = getattr(arg, "value", arg)
        name = getattr(arg, "name", None)
        folded = _fold_input_expr(value)
        if folded is _UNFOLDABLE:
            return None
        if name:
            named[str(name)] = folded
        else:
            positionals.append(folded)
    merged: list[Any] = list(positionals)
    provided = set(range(len(positionals)))
    for key, val in named.items():
        if key not in order:
            continue
        idx = order.index(key)
        while len(merged) <= idx:
            merged.append(None)
        if idx in provided:
            continue
        merged[idx] = val
        provided.add(idx)
    return {name: (merged[i] if i < len(merged) and i in provided else None) for i, name in enumerate(order)}


def _input_record(kind: str, slots: dict[str, Any]) -> dict[str, Any]:
    """Same metadata shape as the interpret ``input.*`` handlers (no overrides)."""
    defval = slots.get("defval")
    if kind == "int":
        if defval is None and "defval" not in slots:
            defval = 0
        value = int(defval) if isinstance(defval, float) and defval == int(defval) else defval
        if value is None:
            value = 0
        return {
            "type": "int",
            "default": 0 if defval is None else defval,
            "value": value,
            "title": slots.get("title") or "",
            "min": slots.get("minval"),
            "max": slots.get("maxval"),
            "step": 1 if slots.get("step") is None else slots.get("step"),
            "tooltip": slots.get("tooltip") or "",
            "inline": slots.get("inline"),
            "group": slots.get("group"),
            "confirm": bool(slots.get("confirm") or False),
            "active": True if slots.get("active") is None else bool(slots.get("active")),
        }
    if kind in ("float", "price"):
        default = 0.0 if defval is None else defval
        return {
            "type": kind,
            "default": default,
            "value": float(default),
            "title": slots.get("title") or "",
            "min": slots.get("minval"),
            "max": slots.get("maxval"),
            "step": slots.get("step"),
            "tooltip": slots.get("tooltip") or "",
            "inline": slots.get("inline"),
            "group": slots.get("group"),
            "confirm": bool(slots.get("confirm") or False),
            "active": True if slots.get("active") is None else bool(slots.get("active")),
        }
    if kind == "bool":
        default = False if defval is None else defval
        return {
            "type": "bool",
            "default": default,
            "value": bool(default),
            "title": slots.get("title") or "",
            "tooltip": slots.get("tooltip") or "",
            "inline": slots.get("inline"),
            "group": slots.get("group"),
            "confirm": bool(slots.get("confirm") or False),
            "active": True if slots.get("active") is None else bool(slots.get("active")),
        }
    if kind == "source":
        label = defval if isinstance(defval, str) and defval else "close"
        return {
            "type": "source",
            "default": label,
            "value": label,
            "title": slots.get("title") or "",
            "tooltip": slots.get("tooltip") or "",
            "inline": slots.get("inline"),
            "group": slots.get("group"),
            "confirm": bool(slots.get("confirm") or False),
            "active": True if slots.get("active") is None else bool(slots.get("active")),
            "options": list(DEFAULT_SOURCE_OPTIONS),
        }
    if kind in _STRING_INPUTS or kind == "enum":
        default = "" if defval is None else defval
        meta = {
            "type": kind,
            "default": default,
            "value": "" if default is None else str(default),
            "title": slots.get("title") or "",
            "tooltip": slots.get("tooltip") or "",
            "inline": slots.get("inline"),
            "group": slots.get("group"),
            "confirm": bool(slots.get("confirm") or False),
            "active": True if slots.get("active") is None else bool(slots.get("active")),
        }
        if kind == "enum" and slots.get("options") is not None:
            meta["options"] = list(slots["options"]) if isinstance(slots["options"], list) else slots["options"]
        return meta
    if kind == "time":
        default = 0 if defval is None else defval
        return {
            "type": "time",
            "default": default,
            "value": default,
            "title": slots.get("title") or "",
            "tooltip": slots.get("tooltip") or "",
            "inline": slots.get("inline"),
            "group": slots.get("group"),
            "confirm": bool(slots.get("confirm") or False),
            "active": True if slots.get("active") is None else bool(slots.get("active")),
        }
    # bare input(): type follows the default value
    return {
        "type": _infer_type(defval),
        "default": defval,
        "value": defval,
        "title": slots.get("title") or "",
        "tooltip": slots.get("tooltip") or "",
        "inline": slots.get("inline"),
        "group": slots.get("group"),
        "confirm": bool(slots.get("confirm") or False),
        "active": True if slots.get("active") is None else bool(slots.get("active")),
    }


def collect_input_declarations(source: str) -> list[dict[str, Any]]:
    """Literal ``input.*`` metadata for the compile host.

    Interpret records this while executing. Compile never runs those handlers,
    so the declared inputs were dropped from the result. Global calls with
    literal arguments are folded here. Calls inside user functions are skipped
    (Pine rejects ``input.*`` there). A non-literal argument skips that call
    rather than publishing a guessed default.
    """
    if not source or "input" not in source:
        return []
    try:
        from pynescript.ast import node as ast
        from pynescript.ast.helper import iter_child_nodes
        from pynescript.ast.helper import parse

        tree = parse(source)
    except Exception:
        return []

    found: list[dict[str, Any]] = []
    stack = [tree]
    while stack:
        current = stack.pop()
        children = list(iter_child_nodes(current))
        for child in reversed(children):
            if isinstance(child, ast.FunctionDef):
                continue
            stack.append(child)
        if not isinstance(current, ast.Call):
            continue
        name = _input_callee(current.func)
        spec = _INPUT_ORDERS.get(name or "")
        if spec is None:
            continue
        kind, order = spec
        slots = _input_slots(current, order)
        if slots is None:
            continue
        try:
            found.append(_input_record(kind, slots))
        except (TypeError, ValueError):
            continue

    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in found:
        title = str(item.get("title") or "")
        if title and title in seen:
            continue
        if title:
            seen.add(title)
        deduped.append(item)
    return deduped
