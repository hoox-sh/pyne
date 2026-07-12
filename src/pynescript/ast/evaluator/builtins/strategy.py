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

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pynescript.ast.evaluator.events import StrategyEvent

from .base import BuiltinDispatchMixin
from .base import BuiltinHandler


# Strategy state management
class StrategyState:
    """Per-run strategy execution state.

    Each evaluator instance owns its own StrategyState. Class-level
    defaults remain for backward compatibility with test code that
    references ``StrategyState.position_direction`` directly, but
    handlers read/write through the instance held on the evaluator.
    """

    def __init__(self) -> None:
        self.position_direction: str = "flat"
        self.entry_price: float = 0.0
        self.entry_bar: int = 0
        self.entry_time: int = 0
        self.position_size: float = 0.0
        self.commission: float = 0.0
        self.closed_trades: list[Trade] = []
        self.open_trades: list[Trade] = []
        self.pending_orders: dict[str, Order] = {}
        self.max_intraday_loss: float = float("inf")
        self.max_drawdown: float = float("inf")
        self.risk_free_capital: float = 100000.0
        self._events: list[StrategyEvent] = []

    def drain_events(self) -> list[StrategyEvent]:
        """Return all captured events and clear the internal buffer."""
        events = list(self._events)
        self._events.clear()
        return events

    @classmethod
    def reset(cls) -> None:
        """Reset class-level defaults (legacy, prefer instance creation)."""
        cls.position_direction = "flat"  # type: ignore[misc]
        cls.entry_price = 0.0  # type: ignore[misc]
        cls.entry_bar = 0  # type: ignore[misc]
        cls.entry_time = 0  # type: ignore[misc]
        cls.position_size = 0.0  # type: ignore[misc]
        cls.commission = 0.0  # type: ignore[misc]
        cls.closed_trades = []  # type: ignore[misc]
        cls.open_trades = []  # type: ignore[misc]
        cls.pending_orders = {}  # type: ignore[misc]
        cls.max_intraday_loss = float("inf")  # type: ignore[misc]
        cls.max_drawdown = float("inf")  # type: ignore[misc]
        cls.risk_free_capital = 100000.0  # type: ignore[misc]


@dataclass
class Order:
    """Pending order."""

    order_id: str
    order_type: str  # "market", "limit", "stop", "stop-limit"
    direction: str  # "buy", "sell"
    quantity: float
    limit_price: float | None = None
    stop_price: float | None = None
    comment: str = ""


@dataclass
class Trade:
    """Closed trade record."""

    entry_bar: int
    entry_time: int
    entry_price: float
    exit_bar: int
    exit_time: int
    exit_price: float
    direction: str  # "long" or "short"
    size: float
    profit: float
    commission: float


class StrategyBuiltinsMixin(BuiltinDispatchMixin):
    """Strategy execution functions for entry, exit, and trade management."""

    def _record_strategy_event(self, event: StrategyEvent) -> None:
        """Append a captured event to the current run's event buffer."""
        self._strategy_state._events.append(event)

    def _strategy_builtin_map(self) -> dict[str, BuiltinHandler]:
        return {
            # Entry/Exit functions
            "strategy.entry": self._handle_strategy_entry,
            "strategy.exit": self._handle_strategy_exit,
            "strategy.close": self._handle_strategy_close,
            "strategy.close_all": self._handle_strategy_close_all,
            "strategy.cancel": self._handle_strategy_cancel,
            "strategy.cancel_all": self._handle_strategy_cancel_all,
            "strategy.order": self._handle_strategy_order,
            # Risk management
            "strategy.risk.max_position_size": (self._handle_strategy_risk_max_position_size),
            "strategy.risk.max_intraday_loss": (self._handle_strategy_risk_max_intraday_loss),
            "strategy.risk.max_intraday_filled_orders": (self._handle_strategy_risk_max_intraday_filled_orders),
            # Unit conversion
            "strategy.convert_to_account": (self._handle_strategy_convert_to_account),
            "strategy.convert_to_symbol": (self._handle_strategy_convert_to_symbol),
            # Quantity calculation
            "strategy.default_entry_qty": (self._handle_strategy_default_entry_qty),
            # Trade history queries
            "strategy.closedtrades.entry_bar_index": (self._handle_closedtrades_entry_bar_index),
            "strategy.closedtrades.entry_time": (self._handle_closedtrades_entry_time),
            "strategy.closedtrades.entry_price": (self._handle_closedtrades_entry_price),
            "strategy.closedtrades.exit_bar_index": (self._handle_closedtrades_exit_bar_index),
            "strategy.closedtrades.exit_time": (self._handle_closedtrades_exit_time),
            "strategy.closedtrades.exit_price": (self._handle_closedtrades_exit_price),
            "strategy.closedtrades.profit": (self._handle_closedtrades_profit),
            "strategy.closedtrades.size": self._handle_closedtrades_size,
            "strategy.closedtrades.commission": (self._handle_closedtrades_commission),
            # Open position queries
            "strategy.opentrades.entry_bar_index": (self._handle_opentrades_entry_bar_index),
            "strategy.opentrades.entry_time": (self._handle_opentrades_entry_time),
            "strategy.opentrades.entry_price": (self._handle_opentrades_entry_price),
            "strategy.opentrades.size": self._handle_opentrades_size,
            "strategy.opentrades.profit": self._handle_opentrades_profit,
            "strategy.opentrades.commission": (self._handle_opentrades_commission),
        }

    # ENTRY/EXIT FUNCTIONS

    def _handle_strategy_entry(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> None:
        """
        strategy.entry(id, direction, qty, limit, stop, comment, alert, ...)

        Create entry order for strategy.

        Parameters:
            id: Order identifier (str)
            direction: "long" or "short" (str)
            qty: Order quantity (float)
            limit: Limit price (float or None)
            stop: Stop price (float or None)
            comment: Order comment (str)

        Returns None. Records trade in strategy state.

        Args are read positionally; kwargs take precedence and are the
        canonical Pine form (``strategy.entry(id=\"L\",
        direction=\"long\", qty=10)``). See subtask 1.3 of the
        pine-worker-strategy-events plan.
        """
        if not hasattr(self, "_strategy_state"):
            self._strategy_state = StrategyState()
        kw = kwargs or {}
        direction = kw.get("direction", args[1] if len(args) > 1 else "long")
        qty = kw.get("qty", args[2] if len(args) > 2 else 1.0)
        limit_price = kw.get("limit", args[3] if len(args) > 3 else None)

        # Close existing position if opposite direction
        if (direction == "long" and self._strategy_state.position_direction == "short") or (
            direction == "short" and self._strategy_state.position_direction == "long"
        ):
            self._close_position(100.0, 0, 0)  # Exit at market

        # Open new position
        self._strategy_state.position_direction = direction
        self._strategy_state.entry_price = limit_price if limit_price else 100.0
        self._strategy_state.entry_bar = 0
        self._strategy_state.entry_time = 0
        self._strategy_state.position_size = qty
        self._strategy_state.commission = 0.0

        self._record_strategy_event(
            StrategyEvent(
                kind="entry",
                id=kw.get("id", args[0] if args else None),
                direction=direction,
                qty=qty,
                order_type=None,
                limit=limit_price,
                stop=None,
                oca_name=None,
                comment=kw.get("comment", None),
                bar_index=self.context.get("bar_index", 0),
                bar_time=self.context.get("time", 0),
                ohlc=(0.0, 0.0, 0.0, 0.0),
                script_id="",
                run_id="",
            )
        )

    def _handle_strategy_exit(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> None:
        """
        strategy.exit(id, from_entry, qty, limit, stop, comment, alert, ...)

        Create exit order closing a specific entry.

        Parameters:
            id: Order identifier (str)
            from_entry: Entry order to close (str)
            qty: Quantity to close (float or None for all)
            limit: Limit price (float or None)
            stop: Stop price (float or None)
            comment: Order comment (str)

        Returns None. Closes position or partial position.
        """
        kw = kwargs or {}
        qty = kw.get("qty", args[2] if len(args) > 2 else self._strategy_state.position_size)

        # v6: evaluate both (limit/profit) and (stop/loss) pairs; choose the one market price would activate first
        limit_p = kw.get("limit") or kw.get("profit")
        stop_p = kw.get("stop") or kw.get("loss")
        current_p = self.context.get("close", self._strategy_state.entry_price or 100.0)
        is_long = self._strategy_state.position_direction == "long"

        if limit_p is not None and stop_p is not None:
            # Choose the trigger that would hit first based on current price direction
            if is_long:
                # Closing long: stop (lower) or limit (higher)
                if current_p <= stop_p:
                    exit_price = stop_p
                elif current_p >= limit_p:
                    exit_price = limit_p
                else:
                    exit_price = min(limit_p, stop_p) if limit_p < stop_p else limit_p
            else:
                # Closing short: stop (higher) or limit (lower)
                if current_p >= stop_p:
                    exit_price = stop_p
                elif current_p <= limit_p:
                    exit_price = limit_p
                else:
                    exit_price = max(limit_p, stop_p) if limit_p > stop_p else limit_p
        else:
            exit_price = limit_p or stop_p or 101.0

        if self._strategy_state.position_direction != "flat":
            self._close_position(exit_price, qty, 0)

        self._record_strategy_event(
            StrategyEvent(
                kind="exit",
                id=kw.get("id", args[0] if args else None),
                direction=None,
                qty=qty,
                order_type=None,
                limit=limit_p,
                stop=stop_p,
                oca_name=None,
                comment=kw.get("comment", None),
                bar_index=self.context.get("bar_index", 0),
                bar_time=self.context.get("time", 0),
                ohlc=(0.0, 0.0, 0.0, 0.0),
                script_id="",
                run_id="",
            )
        )

    def _handle_strategy_close(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> None:
        """
        strategy.close(id, qty, comment, alert, ...)

        Close current position or reduce it.

        Parameters:
            id: Order identifier (str)
            qty: Quantity to close (float or None for all)
            comment: Order comment (str)

        Returns None.
        """
        kw = kwargs or {}
        qty = kw.get("qty", args[1] if len(args) > 1 else self._strategy_state.position_size)

        if self._strategy_state.position_direction != "flat":
            self._close_position(101.0, qty, 0)

        self._record_strategy_event(
            StrategyEvent(
                kind="close",
                id=kw.get("id", args[0] if args else None),
                direction=None,
                qty=qty,
                order_type=None,
                limit=None,
                stop=None,
                oca_name=None,
                comment=kw.get("comment", None),
                bar_index=self.context.get("bar_index", 0),
                bar_time=self.context.get("time", 0),
                ohlc=(0.0, 0.0, 0.0, 0.0),
                script_id="",
                run_id="",
            )
        )

    def _handle_strategy_close_all(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> None:
        """
        strategy.close_all(comment, alert, ...)

        Close entire position at market.

        Parameters:
            comment: Order comment (str)

        Returns None.
        """
        kw = kwargs or {}
        if self._strategy_state.position_direction != "flat":
            self._close_position(101.0, self._strategy_state.position_size, 0)

        self._record_strategy_event(
            StrategyEvent(
                kind="close_all",
                id=None,
                direction=None,
                qty=None,
                order_type=None,
                limit=None,
                stop=None,
                oca_name=None,
                comment=kw.get("comment", None),
                bar_index=self.context.get("bar_index", 0),
                bar_time=self.context.get("time", 0),
                ohlc=(0.0, 0.0, 0.0, 0.0),
                script_id="",
                run_id="",
            )
        )

    def _handle_strategy_cancel(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> None:
        """
        strategy.cancel(id, alert)

        Cancel a specific pending order.

        Parameters:
            id: Order identifier (str)
            alert: Alert on cancellation (bool or None)

        Returns None.
        """
        kw = kwargs or {}
        order_id = kw.get("id", args[0] if len(args) > 0 else "order_1")

        if order_id in self._strategy_state.pending_orders:
            del self._strategy_state.pending_orders[order_id]

        self._record_strategy_event(
            StrategyEvent(
                kind="cancel",
                id=order_id,
                direction=None,
                qty=None,
                order_type=None,
                limit=None,
                stop=None,
                oca_name=None,
                comment=None,
                bar_index=self.context.get("bar_index", 0),
                bar_time=self.context.get("time", 0),
                ohlc=(0.0, 0.0, 0.0, 0.0),
                script_id="",
                run_id="",
            )
        )

    def _handle_strategy_cancel_all(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> None:
        """
        strategy.cancel_all(alert)

        Cancel all pending orders.

        Parameters:
            alert: Alert on cancellation (bool or None)

        Returns None.
        """
        self._strategy_state.pending_orders.clear()

        self._record_strategy_event(
            StrategyEvent(
                kind="cancel_all",
                id=None,
                direction=None,
                qty=None,
                order_type=None,
                limit=None,
                stop=None,
                oca_name=None,
                comment=None,
                bar_index=self.context.get("bar_index", 0),
                bar_time=self.context.get("time", 0),
                ohlc=(0.0, 0.0, 0.0, 0.0),
                script_id="",
                run_id="",
            )
        )

    def _handle_strategy_order(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> None:
        """
        strategy.order(id, action, qty, limit, stop, comment, alert, ...)

        Place a custom order (market, limit, stop, stop-limit).

        Parameters:
            id: Order identifier (str)
            action: "buy" or "sell" (str)
            qty: Quantity (float)
            limit: Limit price for limit/stop-limit (float or None)
            stop: Stop price for stop/stop-limit (float or None)
            comment: Order comment (str)

        Returns None.
        """
        kw = kwargs or {}
        order_id = kw.get("id", args[0] if len(args) > 0 else "order_1")
        action = kw.get("action", args[1] if len(args) > 1 else "buy")
        qty = kw.get("qty", args[2] if len(args) > 2 else 1.0)
        limit_price = kw.get("limit", args[3] if len(args) > 3 else None)
        stop_price = kw.get("stop", args[4] if len(args) > 4 else None)
        comment = kw.get("comment", args[5] if len(args) > 5 else "")

        # Determine order type
        if stop_price and limit_price:
            order_type = "stop-limit"
        elif stop_price:
            order_type = "stop"
        elif limit_price:
            order_type = "limit"
        else:
            order_type = "market"

        order = Order(order_id, order_type, action, qty, limit_price, stop_price, comment)
        self._strategy_state.pending_orders[order_id] = order

        self._record_strategy_event(
            StrategyEvent(
                kind="order",
                id=order_id,
                direction=action,
                qty=qty,
                order_type=order_type,
                limit=limit_price,
                stop=stop_price,
                oca_name=None,
                comment=comment,
                bar_index=self.context.get("bar_index", 0),
                bar_time=self.context.get("time", 0),
                ohlc=(0.0, 0.0, 0.0, 0.0),
                script_id="",
                run_id="",
            )
        )

    def _close_position(self, exit_price: float, qty: float, exit_time: int) -> None:
        """Helper to close a position and record it."""
        if self._strategy_state.position_direction == "flat":
            return

        # Calculate profit
        if self._strategy_state.position_direction == "long":
            profit = (exit_price - self._strategy_state.entry_price) * qty - self._strategy_state.commission
        else:  # short
            profit = (self._strategy_state.entry_price - exit_price) * qty - self._strategy_state.commission

        # Record trade
        trade = Trade(
            self._strategy_state.entry_bar,
            self._strategy_state.entry_time,
            self._strategy_state.entry_price,
            0,
            exit_time,
            exit_price,
            self._strategy_state.position_direction,
            qty,
            profit,
            self._strategy_state.commission,
        )
        self._strategy_state.closed_trades.append(trade)

        # Update position
        self._strategy_state.position_size -= qty
        if self._strategy_state.position_size <= 0:
            self._strategy_state.position_direction = "flat"
            self._strategy_state.position_size = 0.0

    # RISK MANAGEMENT

    def _handle_strategy_risk_max_position_size(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> None:
        """
        strategy.risk.max_position_size(percent)

        Set maximum position size as percentage of account equity.

        Parameters:
            percent: Maximum position size in % (float)

        Returns None.
        """
        # Mock implementation - would limit position size

    def _handle_strategy_risk_max_intraday_filled_orders(
        self, args: list[Any], kwargs: dict[str, Any] | None = None
    ) -> None:
        """
        strategy.risk.max_intraday_filled_orders(max_orders)

        Set maximum number of intraday filled orders to limit trading.

        Parameters:
            max_orders: Maximum number of filled orders per day (int)

        Returns None.
        """

    def _handle_strategy_risk_max_intraday_loss(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> None:
        """
        strategy.risk.max_intraday_loss(percent)

        Set maximum intraday loss to stop trading.

        Parameters:
            percent: Maximum loss in % (float)

        Returns None.
        """
        percent = args[0] if len(args) > 0 else 100.0
        self._strategy_state.max_intraday_loss = percent

    # UNIT CONVERSION

    def _handle_strategy_convert_to_account(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        """
        strategy.convert_to_account(value, symbol, timeframe)

        Convert quantity/price from symbol to account currency/units.

        Parameters:
            value: Value to convert (float)
            symbol: Source symbol (str)
            timeframe: Timeframe (str)

        Returns converted value.
        """
        value = args[0] if len(args) > 0 else 1.0

        # Mock: simple passthrough conversion
        return value * 1.0

    def _handle_strategy_convert_to_symbol(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        """
        strategy.convert_to_symbol(value, symbol, timeframe)

        Convert quantity/price from account to symbol units.

        Parameters:
            value: Value to convert (float)
            symbol: Target symbol (str)
            timeframe: Timeframe (str)

        Returns converted value.
        """
        value = args[0] if len(args) > 0 else 1.0

        # Mock: simple passthrough conversion
        return value * 1.0

    def _handle_strategy_default_entry_qty(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        """
        strategy.default_entry_qty(percent_equity)

        Calculate default entry quantity based on equity percentage.

        Parameters:
            percent_equity: Percentage of equity to use (float)

        Returns default quantity.
        """
        percent_equity = args[0] if len(args) > 0 else 100.0

        # Mock: calculate qty based on account size and percentage
        allocation = self._strategy_state.risk_free_capital * (percent_equity / 100.0)
        return allocation / 100.0  # Assume price around 100

    # CLOSED TRADES QUERIES

    def _handle_closedtrades_entry_bar_index(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> int:
        """strategy.closedtrades.entry_bar_index(trade_index)"""
        trade_index = args[0] if len(args) > 0 else 0
        if 0 <= trade_index < len(self._strategy_state.closed_trades):
            return self._strategy_state.closed_trades[trade_index].entry_bar
        return 0

    def _handle_closedtrades_entry_time(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> int:
        """strategy.closedtrades.entry_time(trade_index)"""
        trade_index = args[0] if len(args) > 0 else 0
        if 0 <= trade_index < len(self._strategy_state.closed_trades):
            return self._strategy_state.closed_trades[trade_index].entry_time
        return 0

    def _handle_closedtrades_entry_price(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        """strategy.closedtrades.entry_price(trade_index)"""
        trade_index = args[0] if len(args) > 0 else 0
        if 0 <= trade_index < len(self._strategy_state.closed_trades):
            return self._strategy_state.closed_trades[trade_index].entry_price
        return 0.0

    def _handle_closedtrades_exit_bar_index(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> int:
        """strategy.closedtrades.exit_bar_index(trade_index)"""
        trade_index = args[0] if len(args) > 0 else 0
        if 0 <= trade_index < len(self._strategy_state.closed_trades):
            return self._strategy_state.closed_trades[trade_index].exit_bar
        return 0

    def _handle_closedtrades_exit_time(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> int:
        """strategy.closedtrades.exit_time(trade_index)"""
        trade_index = args[0] if len(args) > 0 else 0
        if 0 <= trade_index < len(self._strategy_state.closed_trades):
            return self._strategy_state.closed_trades[trade_index].exit_time
        return 0

    def _handle_closedtrades_exit_price(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        """strategy.closedtrades.exit_price(trade_index)"""
        trade_index = args[0] if len(args) > 0 else 0
        if 0 <= trade_index < len(self._strategy_state.closed_trades):
            return self._strategy_state.closed_trades[trade_index].exit_price
        return 0.0

    def _handle_closedtrades_profit(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        """strategy.closedtrades.profit(trade_index)"""
        trade_index = args[0] if len(args) > 0 else 0
        if 0 <= trade_index < len(self._strategy_state.closed_trades):
            return self._strategy_state.closed_trades[trade_index].profit
        return 0.0

    def _handle_closedtrades_size(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        """strategy.closedtrades.size(trade_index)"""
        trade_index = args[0] if len(args) > 0 else 0
        if 0 <= trade_index < len(self._strategy_state.closed_trades):
            return self._strategy_state.closed_trades[trade_index].size
        return 0.0

    def _handle_closedtrades_commission(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        """strategy.closedtrades.commission(trade_index)"""
        trade_index = args[0] if len(args) > 0 else 0
        if 0 <= trade_index < len(self._strategy_state.closed_trades):
            return self._strategy_state.closed_trades[trade_index].commission
        return 0.0

    # OPEN TRADES QUERIES

    def _handle_opentrades_entry_bar_index(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> int:
        """strategy.opentrades.entry_bar_index(trade_index)"""
        trade_index = args[0] if len(args) > 0 else 0
        if 0 <= trade_index < len(self._strategy_state.open_trades):
            return self._strategy_state.open_trades[trade_index].entry_bar
        return 0

    def _handle_opentrades_entry_time(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> int:
        """strategy.opentrades.entry_time(trade_index)"""
        trade_index = args[0] if len(args) > 0 else 0
        if 0 <= trade_index < len(self._strategy_state.open_trades):
            return self._strategy_state.open_trades[trade_index].entry_time
        return 0

    def _handle_opentrades_entry_price(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        """strategy.opentrades.entry_price(trade_index)"""
        trade_index = args[0] if len(args) > 0 else 0
        if 0 <= trade_index < len(self._strategy_state.open_trades):
            return self._strategy_state.open_trades[trade_index].entry_price
        return 0.0

    def _handle_opentrades_size(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        """strategy.opentrades.size(trade_index)"""
        trade_index = args[0] if len(args) > 0 else 0
        if 0 <= trade_index < len(self._strategy_state.open_trades):
            return self._strategy_state.open_trades[trade_index].size
        return 0.0

    def _handle_opentrades_profit(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        """strategy.opentrades.profit(trade_index)"""
        trade_index = args[0] if len(args) > 0 else 0
        if 0 <= trade_index < len(self._strategy_state.open_trades):
            return self._strategy_state.open_trades[trade_index].profit
        return 0.0

    def _handle_opentrades_commission(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        """strategy.opentrades.commission(trade_index)"""
        trade_index = args[0] if len(args) > 0 else 0
        if 0 <= trade_index < len(self._strategy_state.open_trades):
            return self._strategy_state.open_trades[trade_index].commission
        return 0.0
