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

    Plot capture (bar mode / Runtime host):
      - Values go into columnar ``_plot_value_cols`` (one list per call-site order).
      - Meta (title/color/kind/…) is recorded once in ``_plot_meta_list``.
      - ``plot_outputs`` stays as a per-bar legacy buffer (cleared each bar) for
        any mid-bar readers; Runtime prefers columns when present.
      - ``PlotRegistry`` (super()) is optional: Runtime disables it when the
        script has no ``fill()`` so plot() need not return Plot handles.
    """

    def __init__(self, context=None, data_feed=None, data_provider=None):
        super().__init__(context, data_feed=data_feed, data_provider=data_provider)
        self.plot_outputs: list[Any] = []
        # Columnar capture (preferred by Runtime post-process)
        self._plot_value_cols: list[list[Any]] = []
        self._plot_meta_list: list[dict[str, Any]] = []
        self._plot_capture_i = 0
        self._plot_bars_done = 0
        # When False, skip PlotRegistry super() path (fill() needs True).
        # Default True so non-Runtime CustomEvaluator users keep registry semantics.
        self._pine_need_plot_ids = True
        # Bar-by-bar mode: TA helpers return current scalar instead of full series
        self._pine_bar_mode = True
        # O(1)/O(period) call-site TA for sma/ema/rma/rsi (disable via PYNE_TA_INCREMENTAL=0)
        self._pine_ta_incremental = True
        # OHLCV history lists for ta helpers that read high/low/close by name
        self.current_series: dict[str, list] = {}
        if not hasattr(self, "_var_declarations"):
            self._var_declarations = set()

    def _capture_plot(
        self,
        kind: str,
        value: Any,
        title: str | None,
        color_s: str | None,
        linewidth: int = 1,
        **extra: Any,
    ) -> None:
        """Append one plot cell for this bar into columnar buffers."""
        i = self._plot_capture_i
        self._plot_capture_i = i + 1
        cols = self._plot_value_cols
        meta = self._plot_meta_list
        if i >= len(cols):
            # New call-site order index: pad prior bars with None
            cols.append([None] * self._plot_bars_done)
            entry: dict[str, Any] = {
                "type": kind,
                "kind": kind,
                "title": title,
                "color": color_s,
                "linewidth": int(linewidth or 1),
            }
            for k, v in extra.items():
                if v is not None:
                    entry[k] = v
            meta.append(entry)
        else:
            m = meta[i]
            if m.get("color") is None and color_s is not None:
                m["color"] = color_s
            for k, v in extra.items():
                if v is not None and m.get(k) is None:
                    m[k] = v
        cols[i].append(value)

    def finish_bar_plots(self) -> None:
        """Pad short columns for call sites not hit this bar; advance bar counter."""
        n = self._plot_capture_i
        cols = self._plot_value_cols
        for j in range(n, len(cols)):
            cols[j].append(None)
        self._plot_bars_done += 1
        self._plot_capture_i = 0

    def _maybe_registry(self, method_name: str, args: list[Any], kwargs: dict[str, Any] | None) -> Any:
        if not self._pine_need_plot_ids:
            return None
        try:
            return getattr(super(), method_name)(args, kwargs)
        except Exception:
            return None

    def _builtin_plot(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Any:
        """Capture plot value + title/color for multi-series AXIS response."""
        kwargs = kwargs or {}
        if not args and "series" not in kwargs:
            return None

        value = _unwrap_scalar(kwargs.get("series", args[0] if args else None))
        title = kwargs.get("title", args[1] if len(args) > 1 else "")
        color = kwargs.get("color", args[2] if len(args) > 2 else None)
        linewidth = kwargs.get("linewidth", args[5] if len(args) > 5 else 1)
        color_s = _serialize_color(color) if color is not None else None
        title_s = str(title or "") or None

        self._capture_plot("plot", value, title_s, color_s, int(linewidth or 1))
        return self._maybe_registry("_builtin_plot", args, kwargs)

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

        self._capture_plot(
            "hline",
            price,
            str(title or "") or "hline",
            color_s,
            int(linewidth or 1),
            linestyle=str(linestyle or "linestyle_solid"),
            style="hline",
        )
        return self._maybe_registry("_builtin_hline", args, kwargs)

    def _builtin_bgcolor(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Any:
        """Capture bgcolor per-bar color for AXIS background bands."""
        kwargs = kwargs or {}
        color = _unwrap_scalar(kwargs.get("color", args[0] if args else None))
        title = kwargs.get("title", args[1] if len(args) > 1 else "bgcolor")
        color_s = _serialize_color(color)
        self._capture_plot(
            "bgcolor",
            color_s,
            str(title or "") or "bgcolor",
            color_s,
        )
        return self._maybe_registry("_builtin_bgcolor", args, kwargs)

    def _builtin_plotshape(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Any:
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
        self._capture_plot(
            "plotshape",
            value,
            str(title or "") or "shape",
            _serialize_color(color) if color is not None else None,
            style=str(style or "") if style is not None else "",
            location=str(location or "") if location is not None else "",
            text=str(text) if text is not None else "",
        )
        return self._maybe_registry("_builtin_plotshape", args, kwargs)

    def _builtin_plotchar(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Any:
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
        self._capture_plot(
            "plotchar",
            value,
            str(title or "") or "char",
            _serialize_color(color) if color is not None else None,
            style="char",
            location=str(location or "") if location is not None else "",
            text=char_s,
            char=char_s,
        )
        return self._maybe_registry("_builtin_plotchar", args, kwargs)

    def reset_plots(self):
        # Per-bar index reset; columns accumulate across the run.
        # Legacy plot_outputs kept empty (Runtime uses columns).
        self.plot_outputs.clear()
        self._plot_capture_i = 0

    def reset_var_declarations(self):
        """Reset var declarations set for per-run (from plan branch var support)."""
        self._var_declarations = set()

    def reset_events(self):
        """Reset per-bar events (from strategy events integration)."""
        # Events are typically drained from strategy state in the integrated flow
        if hasattr(self, "_strategy_state"):
            self._strategy_state._events = []  # type: ignore[attr-defined]
