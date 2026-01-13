# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any

from .base import BuiltinDispatchMixin
from .base import BuiltinHandler


# Strategy state management
class StrategyState:
    """Global strategy execution state."""

    position_direction: str = "flat"  # "long", "short", "flat"
    entry_price: float = 0.0
    entry_bar: int = 0
    entry_time: int = 0
    position_size: float = 0.0
    commission: float = 0.0
    closed_trades: list[Trade] = field(default_factory=list)
    open_trades: list[Trade] = field(default_factory=list)
    pending_orders: dict[str, Order] = field(default_factory=dict)
    max_intraday_loss: float = float("inf")
    max_drawdown: float = float("inf")
    risk_free_capital: float = 100000.0  # Starting capital

    @classmethod
    def reset(cls) -> None:
        """Reset strategy state for testing."""
        cls.position_direction = "flat"
        cls.entry_price = 0.0
        cls.entry_bar = 0
        cls.entry_time = 0
        cls.position_size = 0.0
        cls.commission = 0.0
        cls.closed_trades = []
        cls.open_trades = []
        cls.pending_orders = {}
        cls.max_intraday_loss = float("inf")
        cls.max_drawdown = float("inf")
        cls.risk_free_capital = 100000.0


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

    def _handle_strategy_entry(self, args: list[Any]) -> None:
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
        """
        direction = args[1] if len(args) > 1 else "long"
        qty = args[2] if len(args) > 2 else 1.0
        limit_price = args[3] if len(args) > 3 else None

        # Close existing position if opposite direction
        if (direction == "long" and StrategyState.position_direction == "short") or (
            direction == "short" and StrategyState.position_direction == "long"
        ):
            self._close_position(100.0, 0, 0)  # Exit at market

        # Open new position
        StrategyState.position_direction = direction
        StrategyState.entry_price = limit_price if limit_price else 100.0
        StrategyState.entry_bar = 0
        StrategyState.entry_time = 0
        StrategyState.position_size = qty
        StrategyState.commission = 0.0

    def _handle_strategy_exit(self, args: list[Any]) -> None:
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
        qty = args[2] if len(args) > 2 else StrategyState.position_size
        exit_price = args[3] if len(args) > 3 else 101.0

        if StrategyState.position_direction != "flat":
            self._close_position(exit_price, qty, 0)

    def _handle_strategy_close(self, args: list[Any]) -> None:
        """
        strategy.close(id, qty, comment, alert, ...)

        Close current position or reduce it.

        Parameters:
            id: Order identifier (str)
            qty: Quantity to close (float or None for all)
            comment: Order comment (str)

        Returns None.
        """
        qty = args[1] if len(args) > 1 else StrategyState.position_size

        if StrategyState.position_direction != "flat":
            self._close_position(101.0, qty, 0)

    def _handle_strategy_close_all(self, _args: list[Any]) -> None:
        """
        strategy.close_all(comment, alert, ...)

        Close entire position at market.

        Parameters:
            comment: Order comment (str)

        Returns None.
        """
        if StrategyState.position_direction != "flat":
            self._close_position(101.0, StrategyState.position_size, 0)

    def _handle_strategy_cancel(self, args: list[Any]) -> None:
        """
        strategy.cancel(id, alert)

        Cancel a specific pending order.

        Parameters:
            id: Order identifier (str)
            alert: Alert on cancellation (bool or None)

        Returns None.
        """
        order_id = args[0] if len(args) > 0 else "order_1"

        if order_id in StrategyState.pending_orders:
            del StrategyState.pending_orders[order_id]

    def _handle_strategy_cancel_all(self, _args: list[Any]) -> None:
        """
        strategy.cancel_all(alert)

        Cancel all pending orders.

        Parameters:
            alert: Alert on cancellation (bool or None)

        Returns None.
        """
        StrategyState.pending_orders.clear()

    def _handle_strategy_order(self, args: list[Any]) -> None:
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
        order_id = args[0] if len(args) > 0 else "order_1"
        action = args[1] if len(args) > 1 else "buy"
        qty = args[2] if len(args) > 2 else 1.0
        limit_price = args[3] if len(args) > 3 else None
        stop_price = args[4] if len(args) > 4 else None
        comment = args[5] if len(args) > 5 else ""

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
        StrategyState.pending_orders[order_id] = order

    def _close_position(self, exit_price: float, qty: float, exit_time: int) -> None:
        """Helper to close a position and record it."""
        if StrategyState.position_direction == "flat":
            return

        # Calculate profit
        if StrategyState.position_direction == "long":
            profit = (exit_price - StrategyState.entry_price) * qty - StrategyState.commission
        else:  # short
            profit = (StrategyState.entry_price - exit_price) * qty - StrategyState.commission

        # Record trade
        trade = Trade(
            StrategyState.entry_bar,
            StrategyState.entry_time,
            StrategyState.entry_price,
            0,
            exit_time,
            exit_price,
            StrategyState.position_direction,
            qty,
            profit,
            StrategyState.commission,
        )
        StrategyState.closed_trades.append(trade)

        # Update position
        StrategyState.position_size -= qty
        if StrategyState.position_size <= 0:
            StrategyState.position_direction = "flat"
            StrategyState.position_size = 0.0

    # RISK MANAGEMENT

    def _handle_strategy_risk_max_position_size(self, args: list[Any]) -> None:
        """
        strategy.risk.max_position_size(percent)

        Set maximum position size as percentage of account equity.

        Parameters:
            percent: Maximum position size in % (float)

        Returns None.
        """
        # Mock implementation - would limit position size

    def _handle_strategy_risk_max_intraday_loss(self, args: list[Any]) -> None:
        """
        strategy.risk.max_intraday_loss(percent)

        Set maximum intraday loss to stop trading.

        Parameters:
            percent: Maximum loss in % (float)

        Returns None.
        """
        percent = args[0] if len(args) > 0 else 100.0
        StrategyState.max_intraday_loss = percent

    # UNIT CONVERSION

    def _handle_strategy_convert_to_account(self, args: list[Any]) -> float:
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

    def _handle_strategy_convert_to_symbol(self, args: list[Any]) -> float:
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

    def _handle_strategy_default_entry_qty(self, args: list[Any]) -> float:
        """
        strategy.default_entry_qty(percent_equity)

        Calculate default entry quantity based on equity percentage.

        Parameters:
            percent_equity: Percentage of equity to use (float)

        Returns default quantity.
        """
        percent_equity = args[0] if len(args) > 0 else 100.0

        # Mock: calculate qty based on account size and percentage
        allocation = StrategyState.risk_free_capital * (percent_equity / 100.0)
        return allocation / 100.0  # Assume price around 100

    # CLOSED TRADES QUERIES

    def _handle_closedtrades_entry_bar_index(self, args: list[Any]) -> int:
        """strategy.closedtrades.entry_bar_index(trade_index)"""
        trade_index = args[0] if len(args) > 0 else 0
        if 0 <= trade_index < len(StrategyState.closed_trades):
            return StrategyState.closed_trades[trade_index].entry_bar
        return 0

    def _handle_closedtrades_entry_time(self, args: list[Any]) -> int:
        """strategy.closedtrades.entry_time(trade_index)"""
        trade_index = args[0] if len(args) > 0 else 0
        if 0 <= trade_index < len(StrategyState.closed_trades):
            return StrategyState.closed_trades[trade_index].entry_time
        return 0

    def _handle_closedtrades_entry_price(self, args: list[Any]) -> float:
        """strategy.closedtrades.entry_price(trade_index)"""
        trade_index = args[0] if len(args) > 0 else 0
        if 0 <= trade_index < len(StrategyState.closed_trades):
            return StrategyState.closed_trades[trade_index].entry_price
        return 0.0

    def _handle_closedtrades_exit_bar_index(self, args: list[Any]) -> int:
        """strategy.closedtrades.exit_bar_index(trade_index)"""
        trade_index = args[0] if len(args) > 0 else 0
        if 0 <= trade_index < len(StrategyState.closed_trades):
            return StrategyState.closed_trades[trade_index].exit_bar
        return 0

    def _handle_closedtrades_exit_time(self, args: list[Any]) -> int:
        """strategy.closedtrades.exit_time(trade_index)"""
        trade_index = args[0] if len(args) > 0 else 0
        if 0 <= trade_index < len(StrategyState.closed_trades):
            return StrategyState.closed_trades[trade_index].exit_time
        return 0

    def _handle_closedtrades_exit_price(self, args: list[Any]) -> float:
        """strategy.closedtrades.exit_price(trade_index)"""
        trade_index = args[0] if len(args) > 0 else 0
        if 0 <= trade_index < len(StrategyState.closed_trades):
            return StrategyState.closed_trades[trade_index].exit_price
        return 0.0

    def _handle_closedtrades_profit(self, args: list[Any]) -> float:
        """strategy.closedtrades.profit(trade_index)"""
        trade_index = args[0] if len(args) > 0 else 0
        if 0 <= trade_index < len(StrategyState.closed_trades):
            return StrategyState.closed_trades[trade_index].profit
        return 0.0

    def _handle_closedtrades_size(self, args: list[Any]) -> float:
        """strategy.closedtrades.size(trade_index)"""
        trade_index = args[0] if len(args) > 0 else 0
        if 0 <= trade_index < len(StrategyState.closed_trades):
            return StrategyState.closed_trades[trade_index].size
        return 0.0

    def _handle_closedtrades_commission(self, args: list[Any]) -> float:
        """strategy.closedtrades.commission(trade_index)"""
        trade_index = args[0] if len(args) > 0 else 0
        if 0 <= trade_index < len(StrategyState.closed_trades):
            return StrategyState.closed_trades[trade_index].commission
        return 0.0

    # OPEN TRADES QUERIES

    def _handle_opentrades_entry_bar_index(self, args: list[Any]) -> int:
        """strategy.opentrades.entry_bar_index(trade_index)"""
        trade_index = args[0] if len(args) > 0 else 0
        if 0 <= trade_index < len(StrategyState.open_trades):
            return StrategyState.open_trades[trade_index].entry_bar
        return 0

    def _handle_opentrades_entry_time(self, args: list[Any]) -> int:
        """strategy.opentrades.entry_time(trade_index)"""
        trade_index = args[0] if len(args) > 0 else 0
        if 0 <= trade_index < len(StrategyState.open_trades):
            return StrategyState.open_trades[trade_index].entry_time
        return 0

    def _handle_opentrades_entry_price(self, args: list[Any]) -> float:
        """strategy.opentrades.entry_price(trade_index)"""
        trade_index = args[0] if len(args) > 0 else 0
        if 0 <= trade_index < len(StrategyState.open_trades):
            return StrategyState.open_trades[trade_index].entry_price
        return 0.0

    def _handle_opentrades_size(self, args: list[Any]) -> float:
        """strategy.opentrades.size(trade_index)"""
        trade_index = args[0] if len(args) > 0 else 0
        if 0 <= trade_index < len(StrategyState.open_trades):
            return StrategyState.open_trades[trade_index].size
        return 0.0

    def _handle_opentrades_profit(self, args: list[Any]) -> float:
        """strategy.opentrades.profit(trade_index)"""
        trade_index = args[0] if len(args) > 0 else 0
        if 0 <= trade_index < len(StrategyState.open_trades):
            return StrategyState.open_trades[trade_index].profit
        return 0.0

    def _handle_opentrades_commission(self, args: list[Any]) -> float:
        """strategy.opentrades.commission(trade_index)"""
        trade_index = args[0] if len(args) > 0 else 0
        if 0 <= trade_index < len(StrategyState.open_trades):
            return StrategyState.open_trades[trade_index].commission
        return 0.0
