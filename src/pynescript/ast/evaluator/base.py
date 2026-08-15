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

"""Shared evaluator infrastructure: context, constants, type and library registries.

:class:`BaseEvaluator` is the first mixin in :class:`~pynescript.ast.evaluator.NodeLiteralEvaluator`'s
MRO. It owns the mutable execution environment that hosts update bar-by-bar
(``close``, ``bar_index``, ``time``, …) and the registries for UDTs and
``import`` libraries. Mixins that implement ``visit_*`` methods assume this
base is present.
"""

from __future__ import annotations

import math

from itertools import count
from typing import Any

from pynescript.ast import node as ast
from pynescript.ast.evaluator.libraries import LibraryModule
from pynescript.ast.evaluator.libraries import LibraryRegistry
from pynescript.ast.type_system import TypeRegistry
from pynescript.ast.visitor import NodeVisitor


# Optimize: Pre-compute math constants at module level
_MATH_CONSTANTS = {
    "math.pi": math.pi,
    "math.e": math.e,
    "math.phi": (1 + math.sqrt(5)) / 2,
    "math.rphi": 2 / (1 + math.sqrt(5)),
    # v6 (Feb 2025): bid/ask on 1T. Omitted quotes are na — never invent mocks.
    "bid": None,
    "ask": None,
    # Additional v6 syminfo / timeframe constants (simple defaults)
    "syminfo.isin": "",
    "syminfo.current_contract": None,
    "syminfo.main_tickerid": "UNKNOWN",
    # Chart timeframe defaults (daily). Hosts override via Timeframe object
    # and/or flat keys; flat keys win when a local var shadows ``timeframe``.
    "timeframe.period": "D",
    "timeframe.main_period": "D",
    "timeframe.multiplier": 1,
    "timeframe.isintraday": False,
    "timeframe.isdaily": True,
    "timeframe.isweekly": False,
    "timeframe.ismonthly": False,
    "timeframe.isseconds": False,
    "timeframe.isinseconds": False,
    "timeframe.isminutes": False,
    "timeframe.ishours": False,
    "timeframe.isdwm": True,
    # format.* constants used by str.tostring / indicator(format=...)
    "format.mintick": "mintick",
    "format.percent": "percent",
    "format.volume": "volume",
    "format.price": "price",
    # v6 text formatting constants
    "text.formatting.none": "",
    "text.formatting.bold": "bold",
    "text.formatting.italic": "italic",
    "text.formatting.bold_italic": "bold italic",
    # v6 text size constants (can be used as int or str; int for points in v6)
    "size.auto": "auto",
    "size.tiny": 8,
    "size.small": 10,
    "size.normal": 12,
    "size.large": 16,
    "size.huge": 20,
    # array/matrix sort order (Reference Pine: ascending=1, descending=-1)
    "order.ascending": 1,
    "order.descending": -1,
    # barmerge.* for request.security gaps/lookahead (compile emits True/False;
    # interpret accepts the constants but does not implement gap-fill/lookahead).
    "barmerge.gaps_on": True,
    "barmerge.gaps_off": False,
    "barmerge.lookahead_on": True,
    "barmerge.lookahead_off": False,
    # plotshape / plotchar style & location (compiler emits attr name; interpret needs context)
    "shape.arrowup": "arrowup",
    "shape.arrowdown": "arrowdown",
    "shape.circle": "circle",
    "shape.cross": "cross",
    "shape.diamond": "diamond",
    "shape.flag": "flag",
    "shape.labelup": "labelup",
    "shape.labeldown": "labeldown",
    "shape.square": "square",
    "shape.triangledown": "triangledown",
    "shape.triangleup": "triangleup",
    "shape.xcross": "xcross",
    "location.abovebar": "abovebar",
    "location.belowbar": "belowbar",
    "location.top": "top",
    "location.bottom": "bottom",
    "location.absolute": "absolute",
    # drawing / table placement
    "xloc.bar_index": "bar_index",
    "xloc.bar_time": "bar_time",
    "yloc.price": "price",
    "yloc.abovebar": "abovebar",
    "yloc.belowbar": "belowbar",
    "extend.none": "none",
    "extend.left": "left",
    "extend.right": "right",
    "extend.both": "both",
    "display.none": "none",
    "display.all": "all",
    "display.data_window": "data_window",
    "display.price_scale": "price_scale",
    "display.status_line": "status_line",
    "position.top_left": "top_left",
    "position.top_center": "top_center",
    "position.top_right": "top_right",
    "position.middle_left": "middle_left",
    "position.middle_center": "middle_center",
    "position.middle_right": "middle_right",
    "position.bottom_left": "bottom_left",
    "position.bottom_center": "bottom_center",
    "position.bottom_right": "bottom_right",
    "hline.style_solid": "solid",
    "hline.style_dashed": "dashed",
    "hline.style_dotted": "dotted",
    # dayofweek.* — Reference Pine: Sunday=1 … Saturday=7 (set05 timestamp residual)
    "dayofweek.sunday": 1,
    "dayofweek.monday": 2,
    "dayofweek.tuesday": 3,
    "dayofweek.wednesday": 4,
    "dayofweek.thursday": 5,
    "dayofweek.friday": 6,
    "dayofweek.saturday": 7,
    # month.* — reference calendar month constants 1..12
    "month.january": 1,
    "month.february": 2,
    "month.march": 3,
    "month.april": 4,
    "month.may": 5,
    "month.june": 6,
    "month.july": 7,
    "month.august": 8,
    "month.september": 9,
    "month.october": 10,
    "month.november": 11,
    "month.december": 12,
    # v6 updated color constants (from design spec)
    "color.red": "#F23645",
    "color.green": "#22AB94",
    "color.blue": "#2962FF",
    "color.yellow": "#FDD835",
    "color.orange": "#FF6D00",
    "color.purple": "#7B1FA2",
    "color.teal": "#089981",
    "color.white": "#FFFFFF",
    "color.black": "#000000",
    "color.gray": "#787B86",
}

# Unique per evaluator instance (never recycled). Bound call-site tuples that
# still carry instance methods must stamp this so a shared/cached AST cannot
# invoke another evaluator's plot / incremental TA handlers.
_EVAL_GENERATION = count(1)


class BaseEvaluator(NodeVisitor):
    """Visitor base: execution context, math defaults, UDT and library registries.

    Responsibilities shared by all evaluator mixins:

    - **``context``** — flat ``dict`` of variables, callables, enums, and
      dotted builtin keys (``strategy.position_size``, ``color.red``, …).
      Hosts must mutate this dict in place between bars; UDF/method bodies
      rebind parameters on the same object so bar series stay visible.
    - **Math / chart defaults** — ``_MATH_CONSTANTS`` filled via ``setdefault``
      so host values (real ``bid``/``ask``, inferred timeframe flags) win.
      Omitted bid/ask stay ``None`` (na); hosts/data_feeds must set quotes.
    - **``type_registry``** — user-defined types (``type X``).
    - **``_library_registry``** — ``library(...)`` / ``import`` resolution.
    - **``_active_library`` / ``_pending_library_exports``** — buffer while
      evaluating a library script for registration at end of ``visit_Script``.

    Does not implement statement/expression visitors; those live on the other
    mixins. Unhandled nodes raise via :meth:`generic_visit`.
    """

    def __init__(
        self,
        context: dict[str, Any] | None = None,
        data_feed: Any | None = None,
        data_provider: Any | None = None,
    ):
        """Build context and registries; optionally wire request.* data sources.

        Args:
            context: Optional pre-seeded variables/functions (merged with
                defaults; existing keys are never overwritten by constants).
            data_feed: Optional realtime/historical feed for ``request.*``.
            data_provider: Optional historical data provider for ``request.*``.
        """
        # Initialize visitor cache for tracking visited nodes
        super().__init__()
        # Set up context: use provided or create empty dict
        self.context = context or {}
        # Merge pre-computed math/constants into context for optimization.
        # Do not overwrite host-provided keys (e.g. timeframe.isintraday from
        # Runtime bar-spacing inference, or custom bid/ask).
        for _key, _val in _MATH_CONSTANTS.items():
            self.context.setdefault(_key, _val)
        # Wire optional data sources used by request.* builtins
        if data_feed is not None:
            self.context["data_feed"] = data_feed
        if data_provider is not None:
            self.context["data_provider"] = data_provider
        # Initialize type registry for user-defined types
        self.type_registry = TypeRegistry()
        # In-process library export/import registry (v6 export const, etc.)
        self._library_registry = LibraryRegistry()
        self._active_library: LibraryModule | None = None
        self._pending_library_exports: dict[str, Any] = {}
        # Bar-loop call-site caches (pre-allocated so visit_Call avoids None checks).
        # Keyed by id(Call AST node); AST is stable for the script lifetime.
        self._call_site_cache: dict[int, tuple] = {}
        # Stamped on bound ``_pine_call_site`` tuples (see expressions.visit_Call).
        self._eval_generation: int = next(_EVAL_GENERATION)
        # name → (tag, handler) for _call_builtin after first resolve
        self._builtin_resolved: dict[str, tuple[int, Any]] = {}
        # Pine dual namespace: UDFs stay callable even when a series local
        # reuses the same name (``ma = ta.sma(...); ma(src, n) => …``).
        self._user_functions: dict[str, Any] = {}
        # Names used with history subscript (``x[1]``); assigned as PineSeries.
        self._history_names: set[str] = set()
        self._history_names_scanned: bool = False
        # bar_index last written for each history-tracked series (same-bar replace).
        self._series_assign_bar: dict[str, int] = {}

    def generic_visit(self, node: ast.AST):
        """Fail closed on AST node types with no ``visit_*`` implementation.

        Args:
            node: AST node that no mixin handled

        Raises:
            ValueError: Always, naming the unexpected Python type
        """
        msg = f"unexpected type of node: {type(node)}"
        raise ValueError(msg)

    def _error(self, msg: str):
        """Raise ``ValueError(msg)`` — shared failure path for mixins.

        Args:
            msg: Human-readable error

        Raises:
            ValueError: Always
        """
        raise ValueError(msg)
