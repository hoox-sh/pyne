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

"""Pine Script AST evaluator package.

Bar-by-bar interpreter for Pine Script ASTs. Hosts (backend Runtime,
pyne-worker, tests) typically:

1. Build one :class:`NodeLiteralEvaluator` (or a thin subclass) with a shared
   ``context`` dict.
2. Inject OHLCV / ``bar_index`` / ``time`` into that dict each bar.
3. Call ``evaluator.visit(script_ast)`` once per bar.

There is **no** separate ``NodeEvaluator`` class. The public composed type is
:class:`NodeLiteralEvaluator` (also used by :func:`pynescript.ast.helper.literal_eval`
and full-script execution). Hosts may subclass it (e.g.
:class:`~pynescript.runtime.evaluator.CustomEvaluator`) for plot capture or
series injection.

Mixin composition (MRO left-to-right; first matching ``visit_*`` wins)::

    NodeLiteralEvaluator
      → BaseEvaluator        # context, type/library registries, generic_visit
      → LiteralEvaluator     # Constant, Tuple
      → ExpressionEvaluator  # BinOp, Call, Compare, Conditional, If/Switch expr
      → BuiltinEvaluator     # ta.*, strategy.*, plot, request.*, …
      → StatementEvaluator   # Script, Assign, FunctionDef, Import, loops
      → NameEvaluator        # Name, Attribute, Subscript

Cross-cutting semantics:

- **``na``** is Python ``None`` (not a special object).
- **Series history** for plain list series is chronological (oldest first);
  ``series[0]`` is the current bar (``list[-1]``). Series wrappers may store
  ``history`` most-recent-first — see :mod:`.names`.
- **``var`` / ``varip``** initialize on first *execution* of the declaration
  (tracked in ``_var_declarations``), not strictly on ``bar_index == 0``.
- **UDF / method params** rebind keys on the live ``context`` dict and restore
  on return so hosts can keep mutating ``bar_index`` / OHLCV in place.
- **Strategy events** are captured on ``_strategy_state`` (:class:`~.events.StrategyEvent`).
"""

from __future__ import annotations

from typing import Any

from pynescript.ast.evaluator.builtins.strategy import StrategyState
from pynescript.ast.evaluator.libraries import LibraryModule
from pynescript.ast.helper import parse

from .base import BaseEvaluator
from .builtins import BuiltinEvaluator
from .expressions import ExpressionEvaluator
from .literals import LiteralEvaluator
from .names import NameEvaluator
from .statements import StatementEvaluator


class NodeLiteralEvaluator(
    BaseEvaluator,
    LiteralEvaluator,
    ExpressionEvaluator,
    BuiltinEvaluator,
    StatementEvaluator,
    NameEvaluator,
):
    """Full Pine Script evaluator (literals, expressions, statements, builtins).

    Despite the historical name, this is the **complete** interpreter used for
    scripts and for literal-only evaluation. Mixins supply ``visit_*`` methods;
    :class:`~pynescript.ast.visitor.NodeVisitor.visit` dispatches by node type.

    State owned here (beyond :class:`~.base.BaseEvaluator`):

    - ``_strategy_state`` — position + :class:`~.events.StrategyEvent` buffer
    - ``_var_declarations`` — names already initialized by ``var`` / ``varip``

    Hosts often set ``_pine_defs_locked = True`` after the first bar so
    :meth:`~.statements.StatementEvaluator.visit_FunctionDef` does not rebuild
    multi-dispatch tables every bar.

    Args:
        context: Shared variable/function map. Hosts update the *same* dict
            each bar (do not replace it under the evaluator mid-run).
        data_feed: Optional realtime feed for ``request.*`` builtins.
        data_provider: Optional historical provider for ``request.*``.
    """

    def __init__(self, context=None, data_feed=None, data_provider=None):
        """Initialize mixins, strategy event buffer, and ``var`` tracking.

        See the class docstring for *context*, *data_feed*, and *data_provider*.
        """
        super().__init__(context=context, data_feed=data_feed, data_provider=data_provider)
        # Support for strategy events (from plan branch integration)
        if not hasattr(self, "_strategy_state"):
            self._strategy_state = StrategyState()

        if not hasattr(self, "_var_declarations"):
            self._var_declarations = set()

        # Wire realtime/historical data for request.* builtins (v6 live data)
        # (base already injects; these ensure presence even if context pre-populated)
        if data_feed is not None:
            self.context["data_feed"] = data_feed
        if data_provider is not None:
            self.context["data_provider"] = data_provider

    def reset_events(self):
        """Clear captured strategy events (per-bar drain / test isolation)."""
        if hasattr(self, "_strategy_state"):
            self._strategy_state._events = []  # type: ignore[attr-defined]

    def evaluate_script(self, source: str) -> Any:
        """Parse Pine source and evaluate the resulting ``Script`` AST once.

        Single-shot convenience for tests and library registration. Multi-bar
        hosts should parse once and call ``visit(tree)`` each bar instead.

        Args:
            source: Pine Script source code

        Returns:
            Value of the last statement in the script body (or ``None``)
        """
        tree = parse(source, mode="exec")
        return self.visit(tree)

    def register_library_source(self, namespace: str, name: str, version: int, source: str) -> None:
        """Register Pine source for lazy ``import namespace/name/version`` resolution."""
        self._library_registry.register_source(namespace, name, version, source)

    def lookup_library(
        self,
        *,
        namespace: str | None = None,
        name: str,
        version: int | None = None,
    ) -> LibraryModule | None:
        """Look up a previously evaluated or registered library module."""
        return self._library_registry.lookup(namespace=namespace, name=name, version=version)
