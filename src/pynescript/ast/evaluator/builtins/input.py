# Copyright 2024-2025 jango_blockchained
#
# Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.gnu.org/licenses/lgpl-3.0.en.html
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: LGPL-3.0-or-later

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

    def _handle_input(self, args: list[Any]) -> dict[str, Any]:
        """
        input(defval, title, tooltip, inline, group, confirm)

        Generic input function that returns parameter metadata.
        Default type is inferred from defval.

        Returns dict with parameter metadata.
        """
        defval = args[0] if len(args) > 0 else None
        title = args[1] if len(args) > 1 else ""
        tooltip = args[2] if len(args) > 2 else ""
        inline = args[3] if len(args) > 3 else None
        group = args[4] if len(args) > 4 else None
        confirm = args[5] if len(args) > 5 else False

        # Infer type from default value
        inferred_type = "float"
        if isinstance(defval, bool):
            inferred_type = "bool"
        elif isinstance(defval, int):
            inferred_type = "int"
        elif isinstance(defval, str):
            inferred_type = "string"

        return {
            "type": inferred_type,
            "default": defval,
            "title": title,
            "tooltip": tooltip,
            "inline": inline,
            "group": group,
            "confirm": confirm,
        }

    def _handle_input_bool(self, args: list[Any]) -> dict[str, Any]:
        """
        input.bool(defval, title, tooltip, inline, group, confirm)

        Create a boolean input parameter.

        Parameters:
            defval: Default value (bool)
            title: Parameter title (str)
            tooltip: Tooltip text (str)
            inline: Inline group name (str or None)
            group: Parameter group name (str or None)
            confirm: Require user confirmation (bool)

        Returns dict with parameter metadata.
        """
        defval = args[0] if len(args) > 0 else False
        title = args[1] if len(args) > 1 else ""
        tooltip = args[2] if len(args) > 2 else ""
        inline = args[3] if len(args) > 3 else None
        group = args[4] if len(args) > 4 else None
        confirm = args[5] if len(args) > 5 else False

        return {
            "type": "bool",
            "default": defval,
            "title": title,
            "tooltip": tooltip,
            "inline": inline,
            "group": group,
            "confirm": confirm,
        }

    def _handle_input_int(self, args: list[Any]) -> dict[str, Any]:
        """
        input.int(defval, title, minval, maxval, step, tooltip, inline,
                  group, confirm)

        Create an integer input parameter.

        Parameters:
            defval: Default value (int)
            title: Parameter title (str)
            minval: Minimum allowed value (int or None)
            maxval: Maximum allowed value (int or None)
            step: Step size for increment (int or None)
            tooltip: Tooltip text (str)
            inline: Inline group name (str or None)
            group: Parameter group name (str or None)
            confirm: Require user confirmation (bool)

        Returns dict with parameter metadata.
        """
        defval = args[0] if len(args) > 0 else 0
        title = args[1] if len(args) > 1 else ""
        minval = args[2] if len(args) > 2 else None
        maxval = args[3] if len(args) > 3 else None
        step = args[4] if len(args) > 4 else 1
        tooltip = args[5] if len(args) > 5 else ""
        inline = args[6] if len(args) > 6 else None
        group = args[7] if len(args) > 7 else None
        confirm = args[8] if len(args) > 8 else False

        return {
            "type": "int",
            "default": defval,
            "title": title,
            "min": minval,
            "max": maxval,
            "step": step,
            "tooltip": tooltip,
            "inline": inline,
            "group": group,
            "confirm": confirm,
        }

    def _handle_input_float(self, args: list[Any]) -> dict[str, Any]:
        """
        input.float(defval, title, minval, maxval, step, tooltip, inline, group, confirm)

        Create a float input parameter.

        Parameters:
            defval: Default value (float)
            title: Parameter title (str)
            minval: Minimum allowed value (float or None)
            maxval: Maximum allowed value (float or None)
            step: Step size for increment (float or None)
            tooltip: Tooltip text (str)
            inline: Inline group name (str or None)
            group: Parameter group name (str or None)
            confirm: Require user confirmation (bool)

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

        return {
            "type": "float",
            "default": defval,
            "title": title,
            "min": minval,
            "max": maxval,
            "step": step,
            "tooltip": tooltip,
            "inline": inline,
            "group": group,
            "confirm": confirm,
        }

    def _handle_input_price(self, args: list[Any]) -> dict[str, Any]:
        """
        input.price(defval, title, minval, maxval, step, tooltip, inline, group, confirm)

        Create a price input parameter.
        Price inputs are essentially float inputs optimized for price values.

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
        }

    def _handle_input_string(self, args: list[Any]) -> dict[str, Any]:
        """
        input.string(defval, title, tooltip, inline, group, confirm)

        Create a string input parameter.

        Parameters:
            defval: Default value (str)
            title: Parameter title (str)
            tooltip: Tooltip text (str)
            inline: Inline group name (str or None)
            group: Parameter group name (str or None)
            confirm: Require user confirmation (bool)

        Returns dict with parameter metadata.
        """
        defval = args[0] if len(args) > 0 else ""
        title = args[1] if len(args) > 1 else ""
        tooltip = args[2] if len(args) > 2 else ""
        inline = args[3] if len(args) > 3 else None
        group = args[4] if len(args) > 4 else None
        confirm = args[5] if len(args) > 5 else False

        return {
            "type": "string",
            "default": defval,
            "title": title,
            "tooltip": tooltip,
            "inline": inline,
            "group": group,
            "confirm": confirm,
        }

    def _handle_input_symbol(self, args: list[Any]) -> dict[str, Any]:
        """
        input.symbol(defval, title, tooltip, inline, group, confirm)

        Create a symbol/ticker input parameter.
        Symbol inputs are specialized string inputs for security symbols.

        Parameters:
            defval: Default symbol (str)
            title: Parameter title (str)
            tooltip: Tooltip text (str)
            inline: Inline group name (str or None)
            group: Parameter group name (str or None)
            confirm: Require user confirmation (bool)

        Returns dict with parameter metadata.
        """
        defval = args[0] if len(args) > 0 else ""
        title = args[1] if len(args) > 1 else ""
        tooltip = args[2] if len(args) > 2 else ""
        inline = args[3] if len(args) > 3 else None
        group = args[4] if len(args) > 4 else None
        confirm = args[5] if len(args) > 5 else False

        return {
            "type": "symbol",
            "default": defval,
            "title": title,
            "tooltip": tooltip,
            "inline": inline,
            "group": group,
            "confirm": confirm,
        }

    def _handle_input_session(self, args: list[Any]) -> dict[str, Any]:
        """
        input.session(defval, title, tooltip, inline, group, confirm)

        Create a session input parameter.
        Session inputs define trading session times (e.g., "0930-1600").

        Parameters:
            defval: Default session string (str)
            title: Parameter title (str)
            tooltip: Tooltip text (str)
            inline: Inline group name (str or None)
            group: Parameter group name (str or None)
            confirm: Require user confirmation (bool)

        Returns dict with parameter metadata.
        """
        defval = args[0] if len(args) > 0 else ""
        title = args[1] if len(args) > 1 else ""
        tooltip = args[2] if len(args) > 2 else ""
        inline = args[3] if len(args) > 3 else None
        group = args[4] if len(args) > 4 else None
        confirm = args[5] if len(args) > 5 else False

        return {
            "type": "session",
            "default": defval,
            "title": title,
            "tooltip": tooltip,
            "inline": inline,
            "group": group,
            "confirm": confirm,
        }

    def _handle_input_source(self, args: list[Any]) -> dict[str, Any]:
        """
        input.source(defval, title, tooltip, inline, group, confirm)

        Create a source input parameter.
        Source inputs select OHLCV data sources (close, open, high, low, hl2, hlc3, ohlc4, etc.).

        Parameters:
            defval: Default source (str, e.g., "close")
            title: Parameter title (str)
            tooltip: Tooltip text (str)
            inline: Inline group name (str or None)
            group: Parameter group name (str or None)
            confirm: Require user confirmation (bool)

        Returns dict with parameter metadata.
        """
        defval = args[0] if len(args) > 0 else "close"
        title = args[1] if len(args) > 1 else ""
        tooltip = args[2] if len(args) > 2 else ""
        inline = args[3] if len(args) > 3 else None
        group = args[4] if len(args) > 4 else None
        confirm = args[5] if len(args) > 5 else False

        return {
            "type": "source",
            "default": defval,
            "title": title,
            "tooltip": tooltip,
            "inline": inline,
            "group": group,
            "confirm": confirm,
        }

    def _handle_input_time(self, args: list[Any]) -> dict[str, Any]:
        """
        input.time(defval, title, tooltip, inline, group, confirm)

        Create a time input parameter.
        Time inputs select a specific date and time as Unix timestamp.

        Parameters:
            defval: Default time (int, Unix timestamp)
            title: Parameter title (str)
            tooltip: Tooltip text (str)
            inline: Inline group name (str or None)
            group: Parameter group name (str or None)
            confirm: Require user confirmation (bool)

        Returns dict with parameter metadata.
        """
        defval = args[0] if len(args) > 0 else 0
        title = args[1] if len(args) > 1 else ""
        tooltip = args[2] if len(args) > 2 else ""
        inline = args[3] if len(args) > 3 else None
        group = args[4] if len(args) > 4 else None
        confirm = args[5] if len(args) > 5 else False

        return {
            "type": "time",
            "default": defval,
            "title": title,
            "tooltip": tooltip,
            "inline": inline,
            "group": group,
            "confirm": confirm,
        }

    def _handle_input_timeframe(self, args: list[Any]) -> dict[str, Any]:
        """
        input.timeframe(defval, title, tooltip, inline, group, confirm)

        Create a timeframe input parameter.
        Timeframe inputs select chart timeframes (e.g., "1", "5", "1H", "D").

        Parameters:
            defval: Default timeframe (str)
            title: Parameter title (str)
            tooltip: Tooltip text (str)
            inline: Inline group name (str or None)
            group: Parameter group name (str or None)
            confirm: Require user confirmation (bool)

        Returns dict with parameter metadata.
        """
        defval = args[0] if len(args) > 0 else ""
        title = args[1] if len(args) > 1 else ""
        tooltip = args[2] if len(args) > 2 else ""
        inline = args[3] if len(args) > 3 else None
        group = args[4] if len(args) > 4 else None
        confirm = args[5] if len(args) > 5 else False

        return {
            "type": "timeframe",
            "default": defval,
            "title": title,
            "tooltip": tooltip,
            "inline": inline,
            "group": group,
            "confirm": confirm,
        }

    def _handle_input_color(self, args: list[Any]) -> dict[str, Any]:
        """
        input.color(defval, title, tooltip, inline, group, confirm)

        Create a color input parameter.
        Color inputs select RGBA color values.

        Parameters:
            defval: Default color (str, e.g., "#FF0000" or color constant)
            title: Parameter title (str)
            tooltip: Tooltip text (str)
            inline: Inline group name (str or None)
            group: Parameter group name (str or None)
            confirm: Require user confirmation (bool)

        Returns dict with parameter metadata.
        """
        defval = args[0] if len(args) > 0 else "#000000"
        title = args[1] if len(args) > 1 else ""
        tooltip = args[2] if len(args) > 2 else ""
        inline = args[3] if len(args) > 3 else None
        group = args[4] if len(args) > 4 else None
        confirm = args[5] if len(args) > 5 else False

        return {
            "type": "color",
            "default": defval,
            "title": title,
            "tooltip": tooltip,
            "inline": inline,
            "group": group,
            "confirm": confirm,
        }

    def _handle_input_enum(self, args: list[Any]) -> dict[str, Any]:
        """
        input.enum(defval, title, options, tooltip, inline, group, confirm)

        Create an enumeration input parameter.
        Enum inputs provide a dropdown list of predefined options.

        Parameters:
            defval: Default option (str)
            title: Parameter title (str)
            options: Possible values (list or tuple of str)
            tooltip: Tooltip text (str)
            inline: Inline group name (str or None)
            group: Parameter group name (str or None)
            confirm: Require user confirmation (bool)

        Returns dict with parameter metadata.
        """
        defval = args[0] if len(args) > 0 else ""
        title = args[1] if len(args) > 1 else ""
        options = args[2] if len(args) > 2 else []
        tooltip = args[3] if len(args) > 3 else ""
        inline = args[4] if len(args) > 4 else None
        group = args[5] if len(args) > 5 else None
        confirm = args[6] if len(args) > 6 else False

        return {
            "type": "enum",
            "default": defval,
            "title": title,
            "options": list(options) if not isinstance(options, list) else options,
            "tooltip": tooltip,
            "inline": inline,
            "group": group,
            "confirm": confirm,
        }
