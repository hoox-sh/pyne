# Copyright (C) 2025 jango-blockchained
#
# This file is part of pynescript.
#
# pynescript is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pynescript is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: LGPL-3.0-or-later

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
    # v6 additions
    behind_chart: bool = False
    force_overlay: bool = False
    dynamic_requests: bool = True  # v6 default true
    max_bars_back: int | None = None
    max_lines_count: int | None = None
    max_labels_count: int | None = None
    max_boxes_count: int | None = None


def indicator(title: str = "", description: str = "", **kwargs: Any) -> ScriptDeclaration:
    """Declare an indicator script.

    Args:
        title: Full title of the indicator
        description: Description of the indicator
        **kwargs: Additional parameters accepted by PineScript (v6: behind_chart, force_overlay, etc.)

    Returns:
        ScriptDeclaration object with script metadata
    """
    return ScriptDeclaration(
        script_type="indicator",
        title=str(title),
        description=str(description),
        behind_chart=bool(kwargs.get("behind_chart", False)),
        force_overlay=bool(kwargs.get("force_overlay", False)),
        dynamic_requests=kwargs.get("dynamic_requests", True),
        max_bars_back=kwargs.get("max_bars_back"),
        max_lines_count=kwargs.get("max_lines_count"),
        max_labels_count=kwargs.get("max_labels_count"),
        max_boxes_count=kwargs.get("max_boxes_count"),
    )


def strategy(title: str = "", description: str = "", **kwargs: Any) -> ScriptDeclaration:
    """Declare a strategy script.

    Args:
        title: Full title of the strategy
        description: Description of the strategy
        **kwargs: Additional strategy parameters (pyramiding, default_qty_type, etc.; v6: behind_chart, force_overlay)

    Returns:
        ScriptDeclaration object with script metadata
    """
    return ScriptDeclaration(
        script_type="strategy",
        title=str(title),
        description=str(description),
        behind_chart=bool(kwargs.get("behind_chart", False)),
        force_overlay=bool(kwargs.get("force_overlay", False)),
        dynamic_requests=kwargs.get("dynamic_requests", True),
        max_bars_back=kwargs.get("max_bars_back"),
        max_lines_count=kwargs.get("max_lines_count"),
        max_labels_count=kwargs.get("max_labels_count"),
        max_boxes_count=kwargs.get("max_boxes_count"),
    )


def library(title: str = "", description: str = "", **kwargs: Any) -> ScriptDeclaration:
    """Declare a library script.

    Args:
        title: Full title of the library
        description: Description of the library
        **kwargs: Additional parameters accepted by PineScript (v6: behind_chart etc.)

    Returns:
        ScriptDeclaration object with script metadata
    """
    return ScriptDeclaration(
        script_type="library",
        title=str(title),
        description=str(description),
        behind_chart=bool(kwargs.get("behind_chart", False)),
        force_overlay=bool(kwargs.get("force_overlay", False)),
        dynamic_requests=kwargs.get("dynamic_requests", True),
        max_bars_back=kwargs.get("max_bars_back"),
        max_lines_count=kwargs.get("max_lines_count"),
        max_labels_count=kwargs.get("max_labels_count"),
        max_boxes_count=kwargs.get("max_boxes_count"),
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
    namespace["strategy"] = _as_builtin_handler(strategy)
    namespace["library"] = _as_builtin_handler(library)
