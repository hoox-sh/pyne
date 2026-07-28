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


class InputBuiltinsMixin(BuiltinDispatchMixin):
    """Input/parameter configuration for Pine Script indicators and strategies."""

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
        multi-thousand-bar runs do not grow an O(bars × inputs) list.
        """
        if getattr(self, "_pine_defs_locked", False):
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
        """Apply host-provided input overrides keyed by title when present."""
        overrides = getattr(self, "_input_overrides", None)
        if not overrides or not title:
            return defval
        if title in overrides:
            return overrides[title]
        return defval

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

    def _handle_input_source(self, args: list[Any]) -> Any:
        """input.source(...) → series source (string name or series value)."""
        defval = args[0] if len(args) > 0 else "close"
        title = args[1] if len(args) > 1 else ""
        tooltip = args[2] if len(args) > 2 else ""
        inline = args[3] if len(args) > 3 else None
        group = args[4] if len(args) > 4 else None
        confirm = args[5] if len(args) > 5 else False
        active = args[6] if len(args) > 6 else True
        value = self._resolve_override(title or None, defval)
        self._record_input(
            {
                "type": "source",
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
        """input.enum(defval, title, options, ...) → selected enum value."""
        defval = args[0] if len(args) > 0 else ""
        title = args[1] if len(args) > 1 else ""
        options = args[2] if len(args) > 2 else []
        tooltip = args[3] if len(args) > 3 else ""
        inline = args[4] if len(args) > 4 else None
        group = args[5] if len(args) > 5 else None
        confirm = args[6] if len(args) > 6 else False
        active = args[7] if len(args) > 7 else True
        value = self._resolve_override(title or None, defval)
        opt_list = list(options) if not isinstance(options, list) else options
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
