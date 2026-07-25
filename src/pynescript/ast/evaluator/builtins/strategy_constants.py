# Copyright (C) 2025 jango-blockchained
#
# This file is part of pynescript.
#
# SPDX-License-Identifier: LGPL-3.0-or-later
"""``strategy.*`` constant sentinels.

Direction, OCA, and commission-type constants used by strategy.entry/order
and ``strategy()`` declaration kwargs.
"""

from __future__ import annotations

from typing import Any

from .base import BuiltinDispatchMixin
from .base import BuiltinHandler


class StrategyConstantsMixin(BuiltinDispatchMixin):
    """Zero-arg ``strategy.*`` constants and OCA/commission enums."""

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
