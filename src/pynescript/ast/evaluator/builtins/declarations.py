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

"""Script declaration functions for PineScript v6 evaluator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ScriptDeclaration:
    """Metadata for a PineScript script (indicator, strategy, or library)."""

    script_type: str  # "indicator", "strategy", or "library"
    title: str = ""
    description: str = ""
    # Pine defaults: indicator overlay=false, strategy overlay=true
    overlay: bool = False
    # v6 additions
    behind_chart: bool = False
    force_overlay: bool = False
    dynamic_requests: bool = True  # v6 default true
    max_bars_back: int | None = None
    max_lines_count: int | None = None
    max_labels_count: int | None = None
    max_boxes_count: int | None = None
    max_polylines_count: int | None = None
    # Full kwargs for strategy broker settings (commission, slippage, …)
    kwargs: dict[str, Any] | None = None


def _overlay_default(script_type: str, kwargs: dict[str, Any]) -> bool:
    """Resolve ``overlay`` flag with Pine-compatible defaults."""
    if "overlay" in kwargs:
        return bool(kwargs["overlay"])
    # force_overlay implies drawing on main chart
    if kwargs.get("force_overlay"):
        return True
    return script_type == "strategy"


def _split_declaration_args(
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    script_type: str,
) -> tuple[str, str, dict[str, Any]]:
    """Normalize Pine positional forms.

    Supported shapes (TV-compatible)::

        indicator("Title")
        indicator("Title", "Short")
        indicator("Title", "Short", true)           # 3rd pos = overlay
        indicator("Title", "Short", true, format=…) # extra positionals ignored
        strategy("Title", "Short", overlay=true, pyramiding=0, …)
    """
    title = ""
    description = ""
    merged = dict(kwargs)
    if len(args) >= 1 and args[0] is not None:
        title = str(args[0])
    if len(args) >= 2 and args[1] is not None:
        # shorttitle is often passed as 2nd positional; store as description too
        description = str(args[1])
        merged.setdefault("shorttitle", args[1])
    if len(args) >= 3 and "overlay" not in merged:
        # 3rd positional is historically overlay (bool)
        merged["overlay"] = bool(args[2])
    # Further positionals (format, precision, …) are rare; map common 4th=precision
    if len(args) >= 4 and "precision" not in merged and isinstance(args[3], (int, float)):
        merged["precision"] = int(args[3])
    return title, description, merged


def indicator(*args: Any, **kwargs: Any) -> ScriptDeclaration:
    """Declare an indicator script (accepts multi-positional TV form)."""
    title, description, kw = _split_declaration_args(args, kwargs, "indicator")
    return ScriptDeclaration(
        script_type="indicator",
        title=title,
        description=description,
        overlay=_overlay_default("indicator", kw),
        behind_chart=bool(kw.get("behind_chart", False)),
        force_overlay=bool(kw.get("force_overlay", False)),
        dynamic_requests=kw.get("dynamic_requests", True),
        max_bars_back=kw.get("max_bars_back"),
        max_lines_count=kw.get("max_lines_count"),
        max_labels_count=kw.get("max_labels_count"),
        max_boxes_count=kw.get("max_boxes_count"),
        max_polylines_count=kw.get("max_polylines_count"),
        kwargs=dict(kw),
    )


def strategy(*args: Any, **kwargs: Any) -> ScriptDeclaration:
    """Declare a strategy script (accepts multi-positional TV form)."""
    title, description, kw = _split_declaration_args(args, kwargs, "strategy")
    return ScriptDeclaration(
        script_type="strategy",
        title=title,
        description=description,
        overlay=_overlay_default("strategy", kw),
        behind_chart=bool(kw.get("behind_chart", False)),
        force_overlay=bool(kw.get("force_overlay", False)),
        dynamic_requests=kw.get("dynamic_requests", True),
        max_bars_back=kw.get("max_bars_back"),
        max_lines_count=kw.get("max_lines_count"),
        max_labels_count=kw.get("max_labels_count"),
        max_boxes_count=kw.get("max_boxes_count"),
        max_polylines_count=kw.get("max_polylines_count"),
        kwargs=dict(kw),
    )


def library(*args: Any, **kwargs: Any) -> ScriptDeclaration:
    """Declare a library script."""
    title, description, kw = _split_declaration_args(args, kwargs, "library")
    return ScriptDeclaration(
        script_type="library",
        title=title,
        description=description,
        overlay=_overlay_default("library", kw),
        behind_chart=bool(kw.get("behind_chart", False)),
        force_overlay=bool(kw.get("force_overlay", False)),
        dynamic_requests=kw.get("dynamic_requests", True),
        max_bars_back=kw.get("max_bars_back"),
        max_lines_count=kw.get("max_lines_count"),
        max_labels_count=kw.get("max_labels_count"),
        max_boxes_count=kw.get("max_boxes_count"),
        max_polylines_count=kw.get("max_polylines_count"),
        kwargs=dict(kw),
    )


def _as_builtin_handler(fn: Any) -> Any:
    """Adapt a normal Python function to the BuiltinHandler ``(args, kwargs?)`` shape."""

    def handler(args: list[Any], kwargs: dict[str, Any] | None = None) -> Any:
        return fn(*(args or []), **(kwargs or {}))

    handler.__name__ = getattr(fn, "__name__", "handler")
    handler.__doc__ = fn.__doc__
    return handler


def register_script_declaration_functions(namespace: dict) -> None:
    """Register script declaration functions in the given namespace.

    Args:
        namespace: Dictionary to register functions in (typically evaluator's builtins)
    """
    namespace["indicator"] = _as_builtin_handler(indicator)
    # v4 alias — study() is the pre-v5 name for indicator()
    namespace["study"] = _as_builtin_handler(indicator)
    # Strategy declaration may also configure broker settings on the evaluator
    namespace["strategy"] = _as_builtin_handler(strategy)
    namespace["library"] = _as_builtin_handler(library)
