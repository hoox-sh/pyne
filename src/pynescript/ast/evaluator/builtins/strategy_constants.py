# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.
"""``strategy.*`` constant sentinels.

These are the canonical values passed as the ``direction`` argument to
``strategy.entry`` and ``strategy.order``. They MUST be registered
builtins — falling through to name lookup (which yields the literal
string ``"strategy.long"``) is the bug Plan 1 of
``.opencode/plans/2026-07-05-pine-worker-strategy-events.md`` is
fixing.

Lives in its own module so the constants are easy to find, easy to
test, and trivially mirrored by the TypeScript port in
``pine-worker`` (subtask 2.4.10).
"""

from __future__ import annotations

from typing import Any

from .base import BuiltinDispatchMixin
from .base import BuiltinHandler


class StrategyConstantsMixin(BuiltinDispatchMixin):
    """``strategy.long`` and ``strategy.short`` — zero-arg builtin constants."""

    def _strategy_constants_builtin_map(self) -> dict[str, BuiltinHandler]:
        return {
            "strategy.long": self._handle_strategy_long,
            "strategy.short": self._handle_strategy_short,
        }

    def _handle_strategy_long(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Any:
        return "long"

    def _handle_strategy_short(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Any:
        return "short"
