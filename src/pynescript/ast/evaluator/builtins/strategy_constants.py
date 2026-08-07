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

"""``strategy.*`` constant sentinels.

Direction, OCA, and commission-type constants used by strategy.entry/order
and ``strategy()`` declaration kwargs.
"""

from __future__ import annotations

from typing import Any

from .base import BuiltinDispatchMixin
from .base import BuiltinHandler


class StrategyConstantsMixin(BuiltinDispatchMixin):
    """Zero-arg ``strategy.*`` direction, OCA, commission, and qty-type sentinels.

    Contributes ``_strategy_constants_builtin_map`` into
    :class:`~pynescript.ast.evaluator.builtins.BuiltinEvaluator`. Note
    ``strategy.cash`` is intentionally not registered here (collides with the
    free-cash series on :class:`~.strategy.StrategyBuiltinsMixin`).
    """

    def _strategy_constants_builtin_map(self) -> dict[str, BuiltinHandler]:
        return {
            "strategy.long": self._handle_strategy_long,
            "strategy.short": self._handle_strategy_short,
            # OCA group types
            "strategy.oca.none": self._handle_oca_none,
            "strategy.oca.cancel": self._handle_oca_cancel,
            "strategy.oca.reduce": self._handle_oca_reduce,
            # Commission types (for strategy(..., commission_type=...))
            "strategy.commission.percent": self._handle_commission_percent,
            "strategy.commission.cash_per_order": self._handle_commission_cash_per_order,
            "strategy.commission.cash_per_contract": self._handle_commission_cash_per_contract,
            # Direction / qty helpers used as constants in some scripts
            "strategy.direction.long": self._handle_strategy_long,
            "strategy.direction.short": self._handle_strategy_short,
            "strategy.direction.all": self._handle_direction_all,
            # default_qty_type sentinels (strategy(..., default_qty_type=...))
            # NOTE: strategy.cash is *not* registered here — it collides with the
            # free-cash series (StrategyBuiltinsMixin._handle_strategy_cash). That
            # handler returns a dual float tagged with ``_pine_qty_type = "cash"``
            # so ``default_qty_type=strategy.cash`` still resolves correctly.
            "strategy.fixed": self._handle_qty_fixed,
            "strategy.percent_of_equity": self._handle_qty_percent_of_equity,
        }

    def _handle_strategy_long(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> str:
        return "long"

    def _handle_strategy_short(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> str:
        return "short"

    def _handle_oca_none(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> str:
        return "none"

    def _handle_oca_cancel(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> str:
        return "cancel"

    def _handle_oca_reduce(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> str:
        return "reduce"

    def _handle_commission_percent(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> str:
        return "percent"

    def _handle_commission_cash_per_order(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> str:
        return "cash_per_order"

    def _handle_commission_cash_per_contract(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> str:
        return "cash_per_contract"

    def _handle_direction_all(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> str:
        return "all"

    def _handle_qty_fixed(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> str:
        return "fixed"

    def _handle_qty_percent_of_equity(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> str:
        return "percent_of_equity"

    def _handle_qty_cash(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> str:
        return "cash"
