# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

from __future__ import annotations

from typing import Any

from .base import BuiltinDispatchMixin
from .base import BuiltinHandler


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
        }

    def _handle_input(self, args: list[Any]) -> Any:
        """
        input(defval, title, tooltip, inline, group, confirm, active)

        Generic input — returns the default value directly.
        """
        defval = args[0] if len(args) > 0 else None
        return defval

    def _handle_input_bool(self, args: list[Any]) -> bool:
        """
        input.bool(defval, title, ...) → returns the boolean value directly.
        """
        defval = args[0] if len(args) > 0 else False
        return bool(defval)

    def _handle_input_int(self, args: list[Any]) -> int:
        """
        input.int(defval, title, minval, maxval, step, tooltip, inline,
                  group, confirm, active)

        Returns the default integer value.
        """
        defval = args[0] if len(args) > 0 else 0
        if isinstance(defval, float) and defval == int(defval):
            return int(defval)
        return defval

    def _handle_input_float(self, args: list[Any]) -> float:
        """
        input.float(defval, title, minval, maxval, step, tooltip, inline, group, confirm, active)

        Returns the default float value.
        """
        defval = args[0] if len(args) > 0 else 0.0
        return float(defval)

    def _handle_input_price(self, args: list[Any]) -> dict[str, Any]:
        """
        input.price(defval, title, minval, maxval, step, tooltip, inline, group, confirm, active)

        Create a price input parameter.
        Price inputs are essentially float inputs optimized for price values.

        Added July 2025: active parameter for conditional input enabling.

        Parameters:
            defval: Default price value (float)
            title: Parameter title (str)
            minval: Minimum allowed price (float or None)
            maxval: Maximum allowed price (float or None)
            step: Step size for increment (float or None)
            tooltip: Tooltip text (str)
            inline: Inline group name (str or None)
            group: Parameter group name (str or None)
            confirm: Require user confirmation (bool)
            active: Whether input is editable (bool, default true)

        Returns dict with parameter metadata.
        """
        defval = args[0] if len(args) > 0 else 0.0
        title = args[1] if len(args) > 1 else ""
        minval = args[2] if len(args) > 2 else None
        maxval = args[3] if len(args) > 3 else None
        step = args[4] if len(args) > 4 else None
        tooltip = args[5] if len(args) > 5 else ""
        inline = args[6] if len(args) > 6 else None
        group = args[7] if len(args) > 7 else None
        confirm = args[8] if len(args) > 8 else False
        active = args[9] if len(args) > 9 else True  # July 2025

        return {
            "type": "price",
            "default": defval,
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

    def _handle_input_string(self, args: list[Any]) -> dict[str, Any]:
        """
        input.string(defval, title, tooltip, inline, group, confirm, active)

        Create a string input parameter.

        Added July 2025: active parameter for conditional input enabling.

        Parameters:
            defval: Default value (str)
            title: Parameter title (str)
            tooltip: Tooltip text (str)
            inline: Inline group name (str or None)
            group: Parameter group name (str or None)
            confirm: Require user confirmation (bool)
            active: Whether input is editable (bool, default true)

        Returns dict with parameter metadata.
        """
        defval = args[0] if len(args) > 0 else ""
        title = args[1] if len(args) > 1 else ""
        tooltip = args[2] if len(args) > 2 else ""
        inline = args[3] if len(args) > 3 else None
        group = args[4] if len(args) > 4 else None
        confirm = args[5] if len(args) > 5 else False
        active = args[6] if len(args) > 6 else True  # July 2025

        return {
            "type": "string",
            "default": defval,
            "title": title,
            "tooltip": tooltip,
            "inline": inline,
            "group": group,
            "confirm": confirm,
            "active": active,
        }

    def _handle_input_symbol(self, args: list[Any]) -> dict[str, Any]:
        """
        input.symbol(defval, title, tooltip, inline, group, confirm, active)

        Create a symbol/ticker input parameter.
        Symbol inputs are specialized string inputs for security symbols.

        Added July 2025: active parameter for conditional input enabling.

        Parameters:
            defval: Default symbol (str)
            title: Parameter title (str)
            tooltip: Tooltip text (str)
            inline: Inline group name (str or None)
            group: Parameter group name (str or None)
            confirm: Require user confirmation (bool)
            active: Whether input is editable (bool, default true)

        Returns dict with parameter metadata.
        """
        defval = args[0] if len(args) > 0 else ""
        title = args[1] if len(args) > 1 else ""
        tooltip = args[2] if len(args) > 2 else ""
        inline = args[3] if len(args) > 3 else None
        group = args[4] if len(args) > 4 else None
        confirm = args[5] if len(args) > 5 else False
        active = args[6] if len(args) > 6 else True  # July 2025

        return {
            "type": "symbol",
            "default": defval,
            "title": title,
            "tooltip": tooltip,
            "inline": inline,
            "group": group,
            "confirm": confirm,
            "active": active,
        }

    def _handle_input_session(self, args: list[Any]) -> dict[str, Any]:
        """
        input.session(defval, title, tooltip, inline, group, confirm, active)

        Create a session input parameter.
        Session inputs define trading session times (e.g., "0930-1600").

        Added July 2025: active parameter for conditional input enabling.

        Parameters:
            defval: Default session string (str)
            title: Parameter title (str)
            tooltip: Tooltip text (str)
            inline: Inline group name (str or None)
            group: Parameter group name (str or None)
            confirm: Require user confirmation (bool)
            active: Whether input is editable (bool, default true)

        Returns dict with parameter metadata.
        """
        defval = args[0] if len(args) > 0 else ""
        title = args[1] if len(args) > 1 else ""
        tooltip = args[2] if len(args) > 2 else ""
        inline = args[3] if len(args) > 3 else None
        group = args[4] if len(args) > 4 else None
        confirm = args[5] if len(args) > 5 else False
        active = args[6] if len(args) > 6 else True  # July 2025

        return {
            "type": "session",
            "default": defval,
            "title": title,
            "tooltip": tooltip,
            "inline": inline,
            "group": group,
            "confirm": confirm,
            "active": active,
        }

    def _handle_input_source(self, args: list[Any]) -> dict[str, Any]:
        """
        input.source(defval, title, tooltip, inline, group, confirm, active)

        Create a source input parameter.
        Source inputs select OHLCV data sources (close, open, high, low, hl2, hlc3, ohlc4, etc.).

        Added July 2025: active parameter for conditional input enabling.

        Parameters:
            defval: Default source (str, e.g., "close")
            title: Parameter title (str)
            tooltip: Tooltip text (str)
            inline: Inline group name (str or None)
            group: Parameter group name (str or None)
            confirm: Require user confirmation (bool)
            active: Whether input is editable (bool, default true)

        Returns dict with parameter metadata.
        """
        defval = args[0] if len(args) > 0 else "close"
        title = args[1] if len(args) > 1 else ""
        tooltip = args[2] if len(args) > 2 else ""
        inline = args[3] if len(args) > 3 else None
        group = args[4] if len(args) > 4 else None
        confirm = args[5] if len(args) > 5 else False
        active = args[6] if len(args) > 6 else True  # July 2025

        return {
            "type": "source",
            "default": defval,
            "title": title,
            "tooltip": tooltip,
            "inline": inline,
            "group": group,
            "confirm": confirm,
            "active": active,
        }

    def _handle_input_time(self, args: list[Any]) -> dict[str, Any]:
        """
        input.time(defval, title, tooltip, inline, group, confirm, active)

        Create a time input parameter.
        Time inputs select a specific date and time as Unix timestamp.

        Added July 2025: active parameter for conditional input enabling.

        Parameters:
            defval: Default time (int, Unix timestamp)
            title: Parameter title (str)
            tooltip: Tooltip text (str)
            inline: Inline group name (str or None)
            group: Parameter group name (str or None)
            confirm: Require user confirmation (bool)
            active: Whether input is editable (bool, default true)

        Returns dict with parameter metadata.
        """
        defval = args[0] if len(args) > 0 else 0
        title = args[1] if len(args) > 1 else ""
        tooltip = args[2] if len(args) > 2 else ""
        inline = args[3] if len(args) > 3 else None
        group = args[4] if len(args) > 4 else None
        confirm = args[5] if len(args) > 5 else False
        active = args[6] if len(args) > 6 else True  # July 2025

        return {
            "type": "time",
            "default": defval,
            "title": title,
            "tooltip": tooltip,
            "inline": inline,
            "group": group,
            "confirm": confirm,
            "active": active,
        }

    def _handle_input_timeframe(self, args: list[Any]) -> dict[str, Any]:
        """
        input.timeframe(defval, title, tooltip, inline, group, confirm, active)

        Create a timeframe input parameter.
        Timeframe inputs select chart timeframes (e.g., "1", "5", "1H", "D").

        Added July 2025: active parameter for conditional input enabling.

        Parameters:
            defval: Default timeframe (str)
            title: Parameter title (str)
            tooltip: Tooltip text (str)
            inline: Inline group name (str or None)
            group: Parameter group name (str or None)
            confirm: Require user confirmation (bool)
            active: Whether input is editable (bool, default true)

        Returns dict with parameter metadata.
        """
        defval = args[0] if len(args) > 0 else ""
        title = args[1] if len(args) > 1 else ""
        tooltip = args[2] if len(args) > 2 else ""
        inline = args[3] if len(args) > 3 else None
        group = args[4] if len(args) > 4 else None
        confirm = args[5] if len(args) > 5 else False
        active = args[6] if len(args) > 6 else True  # July 2025

        return {
            "type": "timeframe",
            "default": defval,
            "title": title,
            "tooltip": tooltip,
            "inline": inline,
            "group": group,
            "confirm": confirm,
            "active": active,
        }

    def _handle_input_color(self, args: list[Any]) -> dict[str, Any]:
        """
        input.color(defval, title, tooltip, inline, group, confirm, active)

        Create a color input parameter.
        Color inputs select RGBA color values.

        Added July 2025: active parameter for conditional input enabling.

        Parameters:
            defval: Default color (str, e.g., "#FF0000" or color constant)
            title: Parameter title (str)
            tooltip: Tooltip text (str)
            inline: Inline group name (str or None)
            group: Parameter group name (str or None)
            confirm: Require user confirmation (bool)
            active: Whether input is editable (bool, default true)

        Returns dict with parameter metadata.
        """
        defval = args[0] if len(args) > 0 else "#000000"
        title = args[1] if len(args) > 1 else ""
        tooltip = args[2] if len(args) > 2 else ""
        inline = args[3] if len(args) > 3 else None
        group = args[4] if len(args) > 4 else None
        confirm = args[5] if len(args) > 5 else False
        active = args[6] if len(args) > 6 else True  # July 2025

        return {
            "type": "color",
            "default": defval,
            "title": title,
            "tooltip": tooltip,
            "inline": inline,
            "group": group,
            "confirm": confirm,
            "active": active,
        }

    def _handle_input_enum(self, args: list[Any]) -> dict[str, Any]:
        """
        input.enum(defval, title, options, tooltip, inline, group, confirm, active)

        Create an enumeration input parameter.
        Enum inputs provide a dropdown list of predefined options.

        Added July 2025: active parameter for conditional input enabling.

        Parameters:
            defval: Default option (str)
            title: Parameter title (str)
            options: Possible values (list or tuple of str)
            tooltip: Tooltip text (str)
            inline: Inline group name (str or None)
            group: Parameter group name (str or None)
            confirm: Require user confirmation (bool)
            active: Whether input is editable (bool, default true)

        Returns dict with parameter metadata.
        """
        defval = args[0] if len(args) > 0 else ""
        title = args[1] if len(args) > 1 else ""
        options = args[2] if len(args) > 2 else []
        tooltip = args[3] if len(args) > 3 else ""
        inline = args[4] if len(args) > 4 else None
        group = args[5] if len(args) > 5 else None
        confirm = args[6] if len(args) > 6 else False
        active = args[7] if len(args) > 7 else True  # July 2025

        return {
            "type": "enum",
            "default": defval,
            "title": title,
            "options": list(options) if not isinstance(options, list) else options,
            "tooltip": tooltip,
            "inline": inline,
            "group": group,
            "confirm": confirm,
            "active": active,
        }


# KWARG_ORDER for input.* handlers so that _merge_kwargs_into_args can correctly
# map kwargs like input(title="X", defval=10) to positional args even when the
# handler has a generic (self, args) signature.
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
