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

from __future__ import annotations

from typing import Any

from pynescript.ast.evaluator import NodeLiteralEvaluator


def _serialize_color(c: Any) -> str | None:
    """JSON-safe color string for plot_meta / bgcolor series values."""
    if c is None:
        return None
    to_rgba = getattr(c, "to_rgba", None)
    if callable(to_rgba):
        try:
            return str(to_rgba())
        except Exception:
            pass
    to_hex = getattr(c, "to_hex", None)
    if callable(to_hex):
        try:
            return str(to_hex())
        except Exception:
            pass
    if isinstance(c, str):
        return c if c else None
    if isinstance(c, int):
        return f"#{c & 0xFFFFFF:06X}"
    s = str(c)
    return s if s else None


def _unwrap_scalar(value: Any) -> Any:
    """Bar-mode: PineSeries / list → current scalar for plot capture."""
    if hasattr(value, "current") and not isinstance(value, (list, tuple, str, bytes)):
        current = getattr(value, "current", None)
        if current is not None or hasattr(value, "history"):
            value = current
    if isinstance(value, list):
        value = value[-1] if value else None
    return value


class CustomEvaluator(NodeLiteralEvaluator):
    """
    Evaluator that captures plot commands.
    Supports optional data_feed / data_provider for request.* integration.
    """

    def __init__(self, context=None, data_feed=None, data_provider=None):
        super().__init__(context, data_feed=data_feed, data_provider=data_provider)
        self.plot_outputs = []
        # Bar-by-bar mode: TA helpers return current scalar instead of full series
        self._pine_bar_mode = True
        # O(1)/O(period) call-site TA for sma/ema/rma/rsi (disable via PYNE_TA_INCREMENTAL=0)
        self._pine_ta_incremental = True
        # OHLCV history lists for ta helpers that read high/low/close by name
        self.current_series: dict[str, list] = {}
        if not hasattr(self, "_var_declarations"):
            self._var_declarations = set()

    def _builtin_plot(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> None:
        """Capture plot value + title/color for multi-series AXIS response."""
        kwargs = kwargs or {}
        if not args and "series" not in kwargs:
            return None

        value = _unwrap_scalar(kwargs.get("series", args[0] if args else None))
        title = kwargs.get("title", args[1] if len(args) > 1 else "")
        color = kwargs.get("color", args[2] if len(args) > 2 else None)
        linewidth = kwargs.get("linewidth", args[5] if len(args) > 5 else 1)
        color_s = _serialize_color(color) if color is not None else None

        self.plot_outputs.append(
            {
                "type": "plot",
                "kind": "plot",
                "value": value,
                "title": str(title or "") or None,
                "color": color_s,
                "linewidth": int(linewidth or 1),
            }
        )
        # Still register on PlotRegistry for parity/backends that inspect it
        try:
            return super()._builtin_plot(args, kwargs)
        except Exception:
            return None

    def _builtin_hline(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Any:
        """Capture hline as a constant-price series for AXIS (kind=hline)."""
        kwargs = kwargs or {}
        if not args and "price" not in kwargs:
            return None

        price = _unwrap_scalar(kwargs.get("price", args[0] if args else None))
        title = kwargs.get("title", args[1] if len(args) > 1 else "hline")
        color = kwargs.get("color", args[2] if len(args) > 2 else None)
        linestyle = kwargs.get("linestyle", args[3] if len(args) > 3 else "linestyle_solid")
        linewidth = kwargs.get("linewidth", args[4] if len(args) > 4 else 1)
        color_s = _serialize_color(color) if color is not None else None

        self.plot_outputs.append(
            {
                "type": "hline",
                "kind": "hline",
                "value": price,
                "title": str(title or "") or "hline",
                "color": color_s,
                "linewidth": int(linewidth or 1),
                "linestyle": str(linestyle or "linestyle_solid"),
                "style": "hline",
            }
        )
        try:
            return super()._builtin_hline(args, kwargs)
        except Exception:
            return None

    def _builtin_bgcolor(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> None:
        """Capture bgcolor per-bar color for AXIS background bands."""
        kwargs = kwargs or {}
        color = _unwrap_scalar(kwargs.get("color", args[0] if args else None))
        title = kwargs.get("title", args[1] if len(args) > 1 else "bgcolor")
        color_s = _serialize_color(color)
        self.plot_outputs.append(
            {
                "type": "bgcolor",
                "kind": "bgcolor",
                "value": color_s,
                "title": str(title or "") or "bgcolor",
                "color": color_s,
            }
        )
        try:
            return super()._builtin_bgcolor(args, kwargs)
        except Exception:
            return None

    def _builtin_plotshape(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> None:
        """Capture plotshape condition + style for AXIS bar markers."""
        kwargs = kwargs or {}
        if not args and "series" not in kwargs:
            return None
        value = _unwrap_scalar(kwargs.get("series", args[0] if args else None))
        title = kwargs.get("title", args[1] if len(args) > 1 else "shape")
        style = kwargs.get("style", args[2] if len(args) > 2 else "shape")
        location = kwargs.get("location", args[3] if len(args) > 3 else "")
        color = _unwrap_scalar(kwargs.get("color", args[4] if len(args) > 4 else None))
        text = kwargs.get("text", None)
        self.plot_outputs.append(
            {
                "type": "plotshape",
                "kind": "plotshape",
                "value": value,
                "title": str(title or "") or "shape",
                "color": _serialize_color(color) if color is not None else None,
                "style": str(style or "") if style is not None else "",
                "location": str(location or "") if location is not None else "",
                "text": str(text) if text is not None else "",
            }
        )
        try:
            return super()._builtin_plotshape(args, kwargs)
        except Exception:
            return None

    def _builtin_plotchar(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> None:
        """Capture plotchar condition + char for AXIS bar markers."""
        kwargs = kwargs or {}
        if not args and "series" not in kwargs:
            return None
        value = _unwrap_scalar(kwargs.get("series", args[0] if args else None))
        title = kwargs.get("title", args[1] if len(args) > 1 else "char")
        char = kwargs.get("char", args[2] if len(args) > 2 else "")
        location = kwargs.get("location", args[3] if len(args) > 3 else "")
        color = _unwrap_scalar(kwargs.get("color", args[4] if len(args) > 4 else None))
        char_s = str(char or "") if char is not None else ""
        self.plot_outputs.append(
            {
                "type": "plotchar",
                "kind": "plotchar",
                "value": value,
                "title": str(title or "") or "char",
                "color": _serialize_color(color) if color is not None else None,
                "style": "char",
                "location": str(location or "") if location is not None else "",
                "text": char_s,
                "char": char_s,
            }
        )
        try:
            return super()._builtin_plotchar(args, kwargs)
        except Exception:
            return None

    def reset_plots(self):
        # Reuse list to cut per-bar allocations (values are copied into results)
        self.plot_outputs.clear()

    def reset_var_declarations(self):
        """Reset var declarations set for per-run (from plan branch var support)."""
        self._var_declarations = set()

    def reset_events(self):
        """Reset per-bar events (from strategy events integration)."""
        # Events are typically drained from strategy state in the integrated flow
        if hasattr(self, "_strategy_state"):
            self._strategy_state._events = []  # type: ignore[attr-defined]
