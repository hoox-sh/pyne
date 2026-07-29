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

from dataclasses import dataclass
from typing import Any

from pynescript.ast.evaluator.events import StrategyEvent

from .base import BuiltinDispatchMixin
from .base import BuiltinHandler


@dataclass
class Order:
    """Pending order (may fill over multiple bars / partially)."""

    order_id: str
    order_type: str  # "market", "limit", "stop", "stop-limit"
    direction: str  # "buy", "sell"
    quantity: float
    limit_price: float | None = None
    stop_price: float | None = None
    comment: str = ""
    filled_qty: float = 0.0
    # Cap fill size per bar when > 0 (partial fill model); 0 = fill remaining
    max_fill_per_bar: float = 0.0
    oca_name: str | None = None
    oca_type: str = "none"  # none | cancel | reduce

    @property
    def remaining_qty(self) -> float:
        return max(0.0, float(self.quantity) - float(self.filled_qty))


@dataclass
class OpenTrade:
    """Open (unrealized) trade record."""

    entry_id: str
    entry_bar: int
    entry_time: int
    entry_price: float
    direction: str  # "long" or "short"
    size: float
    commission: float = 0.0


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
    entry_id: str = ""


# Strategy state management
class StrategyState:
    """Per-run strategy execution state.

    Each evaluator instance owns its own ``StrategyState`` (isolated multi-run
    and strategy-events capture). Tests and callers must read/write through
    ``evaluator._strategy_state``, not class-level attributes.

    ``position_size`` is stored as a non-negative quantity; direction is in
    ``position_direction``. The Pine series ``strategy.position_size`` is signed
    (+long / -short) and computed by the builtin accessor.
    """

    def __init__(self) -> None:
        self.position_direction: str = "flat"
        self.entry_price: float = 0.0
        self.entry_bar: int = 0
        self.entry_time: int = 0
        self.position_size: float = 0.0
        self.commission: float = 0.0  # last trade commission cache
        self.position_entry_name: str = ""
        self.closed_trades: list[Trade] = []
        self.open_trades: list[OpenTrade] = []
        self.pending_orders: dict[str, Order] = {}
        self.max_intraday_loss: float = float("inf")
        self.initial_capital: float = 100_000.0
        self.risk_free_capital: float = 100_000.0
        self.account_currency: str = "USD"
        # Broker settings from strategy() declaration
        self.commission_type: str = "percent"  # percent | cash_per_order | cash_per_contract
        self.commission_value: float = 0.0
        self.slippage_ticks: int = 0
        self.pyramiding: int = 0  # 0 = one entry; >0 max additional entries
        self.mintick: float = 0.01
        self.closedtrades_first_index: int = 0
        self.max_contracts_held_all: float = 0.0
        self.max_contracts_held_long: float = 0.0
        self.max_contracts_held_short: float = 0.0
        # Risk: max position size as % of equity (None = unlimited)
        self.max_position_size_percent: float | None = None
        self.max_drawdown_risk: float | None = None  # absolute equity drawdown cap
        self.max_drawdown_risk_percent: float | None = None  # optional % of peak
        self.max_cons_loss_days: int | None = None
        self.allow_entry_in: str = "all"  # all | long | short
        self.entries_blocked: bool = False  # risk halt (drawdown / cons loss days)
        self.consecutive_loss_days: int = 0
        self._last_trade_day: int | None = None  # exit_time // day_ms bucket
        self._day_pnl: float = 0.0
        # Default partial-fill cap per bar for pending orders (0 = full remaining)
        self.default_max_fill_per_bar: float = 0.0
        # Equity curve tracking for max drawdown / runup
        self._equity_peak: float = 100_000.0
        self._equity_trough: float = 100_000.0
        self._max_drawdown: float = 0.0
        self._max_runup: float = 0.0
        self._max_drawdown_percent: float = 0.0
        self._max_runup_percent: float = 0.0
        self._events: list[StrategyEvent] = []
        # Running aggregates — O(1) netprofit/wintrades (avoid re-summing closed_trades)
        self._netprofit: float = 0.0
        self._grossprofit: float = 0.0
        self._grossloss: float = 0.0
        self._wintrades: int = 0
        self._losstrades: int = 0
        self._eventrades: int = 0

    def drain_events(self) -> list[StrategyEvent]:
        """Return all captured events and clear the internal buffer."""
        events = list(self._events)
        self._events.clear()
        return events

    def note_closed_trade_day(self, exit_time: int, profit: float) -> None:
        """Track consecutive calendar-day losses for risk.max_cons_loss_days.

        Day bucket = floor(exit_time / 86_400_000) when time looks like ms,
        else floor(exit_time / 86_400) for seconds, else bar-time as-is.
        """
        t = int(exit_time)
        if t > 10_000_000_000:  # ms epoch
            day = t // 86_400_000
        elif t > 10_000_000:  # seconds epoch
            day = t // 86_400
        else:
            day = t
        if self._last_trade_day is None or day != self._last_trade_day:
            # Finalize previous day
            if self._last_trade_day is not None:
                if self._day_pnl < 0:
                    self.consecutive_loss_days += 1
                elif self._day_pnl > 0:
                    self.consecutive_loss_days = 0
            self._last_trade_day = day
            self._day_pnl = 0.0
        self._day_pnl += float(profit)
        if self.max_cons_loss_days is not None and self.consecutive_loss_days >= int(self.max_cons_loss_days):
            self.entries_blocked = True

    def reset(self) -> None:
        """Reset this instance to flat/empty defaults (for reuse in tests)."""
        self.__init__()

    def signed_position_size(self) -> float:
        """Pine ``strategy.position_size``: +qty long, -qty short, 0 flat."""
        if self.position_direction == "long":
            return float(self.position_size)
        if self.position_direction == "short":
            return -float(self.position_size)
        return 0.0

    def note_closed_profit(self, profit: float) -> None:
        """Update O(1) aggregates when a closed trade is recorded."""
        p = float(profit)
        self._netprofit += p
        if p > 0:
            self._grossprofit += p
            self._wintrades += 1
        elif p < 0:
            self._grossloss += -p
            self._losstrades += 1
        else:
            self._eventrades += 1

    def netprofit(self) -> float:
        return self._netprofit

    def openprofit(self, mark_price: float) -> float:
        trades = self.open_trades
        if not trades:
            return 0.0
        # Fast path: single open trade (common)
        if len(trades) == 1:
            t = trades[0]
            if t.direction == "long":
                return (mark_price - t.entry_price) * t.size - t.commission
            return (t.entry_price - mark_price) * t.size - t.commission
        total = 0.0
        for t in trades:
            if t.direction == "long":
                total += (mark_price - t.entry_price) * t.size - t.commission
            else:
                total += (t.entry_price - mark_price) * t.size - t.commission
        return total

    def equity(self, mark_price: float) -> float:
        eq = self.initial_capital + self._netprofit + self.openprofit(mark_price)
        self._track_equity_curve(eq)
        return eq

    def _track_equity_curve(self, equity: float) -> None:
        """Update peak/trough and max drawdown / runup from an equity sample."""
        if equity > self._equity_peak:
            self._equity_peak = equity
        if equity < self._equity_trough:
            self._equity_trough = equity
        # Drawdown: drop from peak
        dd = self._equity_peak - equity
        if dd > self._max_drawdown:
            self._max_drawdown = dd
            if self._equity_peak > 0:
                self._max_drawdown_percent = 100.0 * dd / self._equity_peak
        # Runup: rise from trough
        ru = equity - self._equity_trough
        if ru > self._max_runup:
            self._max_runup = ru
            if self._equity_trough > 0:
                self._max_runup_percent = 100.0 * ru / self._equity_trough

    def grossprofit(self) -> float:
        return self._grossprofit

    def grossloss(self) -> float:
        # Pine reports gross loss as a positive number
        return self._grossloss

    def wintrades(self) -> int:
        return self._wintrades

    def losstrades(self) -> int:
        return self._losstrades

    def eventrades(self) -> int:
        return self._eventrades

    def _pct_of_initial(self, amount: float) -> float:
        if self.initial_capital == 0:
            return 0.0
        return 100.0 * float(amount) / float(self.initial_capital)

    def avg_trade(self) -> float:
        n = len(self.closed_trades)
        return self.netprofit() / n if n else 0.0

    def avg_winning_trade(self) -> float:
        n = self.wintrades()
        return self.grossprofit() / n if n else 0.0

    def avg_losing_trade(self) -> float:
        n = self.losstrades()
        return self.grossloss() / n if n else 0.0

    def capital_held(self) -> float:
        return float(sum(abs(t.entry_price * t.size) for t in self.open_trades))

    def cash(self, mark_price: float) -> float:
        """Approximate free cash: equity minus capital locked in open positions."""
        return float(self.equity(mark_price) - self.capital_held())

    def note_position_size(self) -> None:
        """Update max contracts held after a fill."""
        size = float(self.position_size)
        if size > self.max_contracts_held_all:
            self.max_contracts_held_all = size
        if self.position_direction == "long" and size > self.max_contracts_held_long:
            self.max_contracts_held_long = size
        if self.position_direction == "short" and size > self.max_contracts_held_short:
            self.max_contracts_held_short = size


class StrategyBuiltinsMixin(BuiltinDispatchMixin):
    """Strategy execution functions for entry, exit, and trade management."""

    def _record_strategy_event(self, event: StrategyEvent) -> None:
        """Append a captured event to the current run's event buffer.

        If ``ohlc`` was left as zeros (legacy call sites), fill from the
        current bar so AXIS markers / equity can resolve a fill price without
        a host-side bar join.

        Avoids ``dataclasses.replace`` (field reflection) — rebuild only when
        needed with a single OHLC cache per bar.
        """
        ohlc = event.ohlc
        if ohlc[0] == 0.0 and ohlc[1] == 0.0 and ohlc[2] == 0.0 and ohlc[3] == 0.0:
            event = StrategyEvent(
                kind=event.kind,
                id=event.id,
                direction=event.direction,
                qty=event.qty,
                order_type=event.order_type,
                limit=event.limit,
                stop=event.stop,
                oca_name=event.oca_name,
                comment=event.comment,
                bar_index=event.bar_index,
                bar_time=event.bar_time,
                ohlc=self._bar_ohlc(),
                script_id=event.script_id,
                run_id=event.run_id,
            )
        self._strategy_state._events.append(event)

    def _bar_ohlc(self) -> tuple[float, float, float, float]:
        """OHLC of the bar currently being evaluated (for StrategyEvent.ohlc).

        Caches per bar_index so multiple events on the same bar share one
        coerce pass (entry+close, OCA cancels, …).
        """
        ctx = getattr(self, "context", {}) or {}
        bi = ctx.get("bar_index", 0)
        if getattr(self, "_ohlc_cache_bar", None) == bi:
            cached = getattr(self, "_ohlc_cache", None)
            if cached is not None:
                return cached  # type: ignore[return-value]
        o = self._coerce_number(ctx.get("open"), default=0.0)
        h = self._coerce_number(ctx.get("high"), default=0.0)
        lo = self._coerce_number(ctx.get("low"), default=0.0)
        c = self._coerce_number(ctx.get("close"), default=self._mark_price())
        tup = (float(o), float(h), float(lo), float(c))
        self._ohlc_cache_bar = bi  # type: ignore[attr-defined]
        self._ohlc_cache = tup  # type: ignore[attr-defined]
        return tup

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
            # Series / stats variables (zero-arg builtins)
            "strategy.position_size": self._handle_strategy_position_size,
            "strategy.position_avg_price": self._handle_strategy_position_avg_price,
            "strategy.position_entry_name": self._handle_strategy_position_entry_name,
            "strategy.opentrades": self._handle_strategy_opentrades_count,
            "strategy.closedtrades": self._handle_strategy_closedtrades_count,
            "strategy.closedtrades.first_index": self._handle_strategy_closedtrades_first_index,
            "strategy.netprofit": self._handle_strategy_netprofit,
            "strategy.netprofit_percent": self._handle_strategy_netprofit_percent,
            "strategy.openprofit": self._handle_strategy_openprofit,
            "strategy.openprofit_percent": self._handle_strategy_openprofit_percent,
            "strategy.equity": self._handle_strategy_equity,
            "strategy.initial_capital": self._handle_strategy_initial_capital,
            "strategy.cash": self._handle_strategy_cash,
            "strategy.account_currency": self._handle_strategy_account_currency,
            "strategy.grossprofit": self._handle_strategy_grossprofit,
            "strategy.grossprofit_percent": self._handle_strategy_grossprofit_percent,
            "strategy.grossloss": self._handle_strategy_grossloss,
            "strategy.grossloss_percent": self._handle_strategy_grossloss_percent,
            "strategy.wintrades": self._handle_strategy_wintrades,
            "strategy.losstrades": self._handle_strategy_losstrades,
            "strategy.eventrades": self._handle_strategy_eventrades,
            "strategy.avg_trade": self._handle_strategy_avg_trade,
            "strategy.avg_trade_percent": self._handle_strategy_avg_trade_percent,
            "strategy.avg_winning_trade": self._handle_strategy_avg_winning_trade,
            "strategy.avg_winning_trade_percent": self._handle_strategy_avg_winning_trade_percent,
            "strategy.avg_losing_trade": self._handle_strategy_avg_losing_trade,
            "strategy.avg_losing_trade_percent": self._handle_strategy_avg_losing_trade_percent,
            "strategy.max_drawdown": self._handle_strategy_max_drawdown,
            "strategy.max_drawdown_percent": self._handle_strategy_max_drawdown_percent,
            "strategy.max_runup": self._handle_strategy_max_runup,
            "strategy.max_runup_percent": self._handle_strategy_max_runup_percent,
            "strategy.max_contracts_held_all": self._handle_strategy_max_contracts_held_all,
            "strategy.max_contracts_held_long": self._handle_strategy_max_contracts_held_long,
            "strategy.max_contracts_held_short": self._handle_strategy_max_contracts_held_short,
            "strategy.opentrades.capital_held": self._handle_strategy_opentrades_capital_held,
            "strategy.margin_liquidation_price": self._handle_strategy_margin_liquidation_price,
            # Risk management
            "strategy.risk.max_position_size": (self._handle_strategy_risk_max_position_size),
            "strategy.risk.max_intraday_loss": (self._handle_strategy_risk_max_intraday_loss),
            "strategy.risk.max_intraday_filled_orders": (self._handle_strategy_risk_max_intraday_filled_orders),
            "strategy.risk.max_drawdown": self._handle_strategy_risk_max_drawdown,
            "strategy.risk.max_cons_loss_days": self._handle_strategy_risk_max_cons_loss_days,
            "strategy.risk.allow_entry_in": self._handle_strategy_risk_allow_entry_in,
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

    @staticmethod
    def _coerce_number(value: Any, default: float = 0.0) -> float:
        """Extract a numeric scalar from context values (including PineSeries)."""
        if value is None:
            return float(default)
        # backend.series.PineSeries exposes .current
        current = getattr(value, "current", None)
        if current is not None and not isinstance(value, (int, float, str)):
            value = current
        if isinstance(value, str) and value.lower() in {"", "na", "nan", "none"}:
            return float(default)
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    @classmethod
    def _coerce_optional_price(cls, value: Any) -> float | None:
        """Parse optional limit/stop; Pine ``na`` / None → None."""
        if value is None:
            return None
        if isinstance(value, str) and value.lower() in {"", "na", "nan", "none"}:
            return None
        current = getattr(value, "current", None)
        if current is not None and not isinstance(value, (int, float, str)):
            value = current
            if value is None:
                return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _mark_price(self) -> float:
        """Current mark price for MTM / market fills (prefer close)."""
        ctx = getattr(self, "context", {}) or {}
        price = ctx.get("close", None)
        if price is None:
            price = self._strategy_state.entry_price or 100.0
            return float(price)
        return self._coerce_number(price, default=100.0)

    def _mintick(self) -> float:
        ctx = getattr(self, "context", {}) or {}
        sym = ctx.get("syminfo")
        if sym is not None:
            mt = getattr(sym, "mintick", None)
            if mt is not None:
                try:
                    return float(mt)
                except (TypeError, ValueError):
                    pass
            if isinstance(sym, dict) and "mintick" in sym:
                try:
                    return float(sym["mintick"])
                except (TypeError, ValueError):
                    pass
        return float(self._strategy_state.mintick or 0.01)

    def _apply_slippage(self, price: float, action: str) -> float:
        """Shift fill price by strategy slippage (ticks × mintick)."""
        ticks = int(self._strategy_state.slippage_ticks or 0)
        if ticks <= 0:
            return float(price)
        slip = ticks * self._mintick()
        if action in {"buy", "long"}:
            return float(price) + slip
        return float(price) - slip

    def _calc_commission(self, qty: float, price: float) -> float:
        """Commission for a fill of ``qty`` at ``price``."""
        st = self._strategy_state
        val = float(st.commission_value or 0.0)
        if val == 0:
            return 0.0
        ctype = (st.commission_type or "percent").lower()
        q = abs(float(qty))
        p = abs(float(price))
        if ctype in {"percent", "strategy.commission.percent"}:
            return q * p * (val / 100.0)
        if ctype in {"cash_per_order", "strategy.commission.cash_per_order"}:
            return val
        if ctype in {"cash_per_contract", "strategy.commission.cash_per_contract"}:
            return val * q
        return 0.0

    def _apply_strategy_declaration(self, decl: Any) -> None:
        """Apply strategy() kwargs stored on ScriptDeclaration / kwargs dict."""
        if not hasattr(self, "_strategy_state"):
            self._strategy_state = StrategyState()
        st = self._strategy_state
        # Support ScriptDeclaration with extra attrs or raw kwargs map
        src = decl
        kwargs = getattr(decl, "kwargs", None)
        if isinstance(kwargs, dict):
            src = kwargs
        elif not isinstance(decl, dict):
            # Pull known fields if present as attributes
            mapping = {}
            for key in (
                "commission_type",
                "commission_value",
                "slippage",
                "pyramiding",
                "initial_capital",
                "currency",
                "default_qty_value",
            ):
                if hasattr(decl, key):
                    mapping[key] = getattr(decl, key)
            src = mapping
        if not isinstance(src, dict):
            return
        if "initial_capital" in src and src["initial_capital"] is not None:
            st.initial_capital = float(src["initial_capital"])
            st.risk_free_capital = float(src["initial_capital"])
            st._equity_peak = float(src["initial_capital"])
            st._equity_trough = float(src["initial_capital"])
        if "commission_type" in src and src["commission_type"] is not None:
            st.commission_type = str(src["commission_type"])
        if "commission_value" in src and src["commission_value"] is not None:
            st.commission_value = float(src["commission_value"])
        if "slippage" in src and src["slippage"] is not None:
            st.slippage_ticks = int(src["slippage"])
        if "pyramiding" in src and src["pyramiding"] is not None:
            st.pyramiding = int(src["pyramiding"])
        if "currency" in src and src["currency"] is not None:
            st.account_currency = str(src["currency"])

    def _bar_index(self) -> int:
        ctx = getattr(self, "context", {}) or {}
        return int(self._coerce_number(ctx.get("bar_index", 0), default=0))

    def _bar_time(self) -> int:
        ctx = getattr(self, "context", {}) or {}
        return int(self._coerce_number(ctx.get("time", 0), default=0))

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
        entry_id = str(kw.get("id", args[0] if args else "entry"))
        direction = str(kw.get("direction", args[1] if len(args) > 1 else "long")).lower()
        # Normalize strategy.long / strategy.short constants
        if direction in {"strategy.long", "1", "long"}:
            direction = "long"
        elif direction in {"strategy.short", "-1", "short"}:
            direction = "short"
        qty = self._coerce_number(kw.get("qty", args[2] if len(args) > 2 else 1.0), default=1.0)
        # Positional limit is rare; prefer kwargs. stop= for stop-entry is common.
        limit_price = self._coerce_optional_price(kw.get("limit", args[3] if len(args) > 3 else None))
        stop_price = self._coerce_optional_price(kw.get("stop", args[4] if len(args) > 4 else None))

        fill_price = float(limit_price) if limit_price is not None else self._mark_price()
        bar_index = self._bar_index()
        bar_time = self._bar_time()

        # --- Risk gates (allow_entry_in / entries_blocked / drawdown) ---
        if not self._risk_allows_entry(direction, fill_price):
            # Stay within StrategyEventKind union; hosts filter on comment.
            self._record_strategy_event(
                StrategyEvent(
                    kind="order",
                    id=entry_id,
                    direction=direction,
                    qty=0.0,
                    order_type="market",
                    limit=limit_price,
                    stop=stop_price,
                    oca_name=None,
                    comment="risk_blocked",
                    bar_index=bar_index,
                    bar_time=bar_time,
                    ohlc=(0.0, 0.0, 0.0, 0.0),
                    script_id="",
                    run_id="",
                )
            )
            return

        # Apply risk max position size (% of equity at fill price)
        pct = self._strategy_state.max_position_size_percent
        if pct is not None and pct > 0 and fill_price > 0:
            equity = self._strategy_state.equity(fill_price)
            max_qty = (equity * (pct / 100.0)) / fill_price
            if qty > max_qty:
                qty = float(max_qty)
        if qty <= 0:
            return

        # Stop/limit entries become pending orders (filled by process_pending_orders)
        if limit_price is not None or stop_price is not None:
            action = "buy" if direction == "long" else "sell"
            if stop_price is not None and limit_price is not None:
                order_type = "stop-limit"
            elif stop_price is not None:
                order_type = "stop"
            else:
                order_type = "limit"
            order = Order(
                entry_id,
                order_type,
                action,
                qty,
                limit_price,
                stop_price,
                str(kw.get("comment", "") or ""),
            )
            self._strategy_state.pending_orders[entry_id] = order
            self._record_strategy_event(
                StrategyEvent(
                    kind="order",
                    id=entry_id,
                    direction=direction,
                    qty=qty,
                    order_type="limit" if order_type == "limit" else "stop",
                    limit=limit_price,
                    stop=stop_price,
                    oca_name=None,
                    comment=kw.get("comment", None),
                    bar_index=bar_index,
                    bar_time=bar_time,
                    ohlc=(0.0, 0.0, 0.0, 0.0),
                    script_id="",
                    run_id="",
                )
            )
            return

        fill_price = self._apply_slippage(fill_price, "buy" if direction == "long" else "sell")
        commission = self._calc_commission(qty, fill_price)
        self._strategy_state.commission = commission

        # Close existing position if opposite direction
        if (direction == "long" and self._strategy_state.position_direction == "short") or (
            direction == "short" and self._strategy_state.position_direction == "long"
        ):
            self._close_position(self._mark_price(), self._strategy_state.position_size, bar_time)

        # Open new position (absolute size + direction)
        self._strategy_state.position_direction = direction
        self._strategy_state.entry_price = fill_price
        self._strategy_state.entry_bar = bar_index
        self._strategy_state.entry_time = bar_time
        self._strategy_state.position_size = qty
        self._strategy_state.position_entry_name = entry_id
        self._strategy_state.open_trades = [
            OpenTrade(
                entry_id=entry_id,
                entry_bar=bar_index,
                entry_time=bar_time,
                entry_price=fill_price,
                direction=direction,
                size=qty,
                commission=commission,
            )
        ]
        self._strategy_state.note_position_size()
        self._strategy_state.equity(fill_price)  # sample equity curve

        self._record_strategy_event(
            StrategyEvent(
                kind="entry",
                id=entry_id,
                direction=direction,
                qty=qty,
                order_type=None,
                limit=limit_price,
                stop=stop_price,
                oca_name=None,
                comment=kw.get("comment", None),
                bar_index=bar_index,
                bar_time=bar_time,
                ohlc=(0.0, 0.0, 0.0, 0.0),
                script_id="",
                run_id="",
            )
        )

    def _risk_allows_entry(self, direction: str, mark_price: float) -> bool:
        """Apply strategy.risk.* gates before opening an entry."""
        st = self._strategy_state
        allow = (st.allow_entry_in or "all").lower()
        if allow in {"long", "strategy.long"} and direction != "long":
            return False
        if allow in {"short", "strategy.short"} and direction != "short":
            return False
        if st.entries_blocked:
            return False
        # Update equity curve and check drawdown cap
        equity = st.equity(mark_price)
        if st.max_drawdown_risk is not None and st._max_drawdown >= float(st.max_drawdown_risk):
            st.entries_blocked = True
            return False
        if st.max_drawdown_risk_percent is not None and st._max_drawdown_percent >= float(
            st.max_drawdown_risk_percent
        ):
            st.entries_blocked = True
            return False
        # Consecutive loss-day halt
        if st.max_cons_loss_days is not None and st.consecutive_loss_days >= int(st.max_cons_loss_days):
            st.entries_blocked = True
            return False
        _ = equity
        return True

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
        qty = float(kw.get("qty", args[2] if len(args) > 2 else self._strategy_state.position_size))

        # v6: evaluate both (limit/profit) and (stop/loss) pairs; choose the one market price would activate first
        limit_p = kw.get("limit") or kw.get("profit")
        stop_p = kw.get("stop") or kw.get("loss")
        current_p = self._mark_price()
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
            exit_price = float(limit_p or stop_p or current_p)

        if self._strategy_state.position_direction != "flat":
            self._close_position(exit_price, qty, self._bar_time())

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
        qty = float(kw.get("qty", args[1] if len(args) > 1 else self._strategy_state.position_size))

        if self._strategy_state.position_direction != "flat":
            self._close_position(self._mark_price(), qty, self._bar_time())

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
                bar_index=self._bar_index(),
                bar_time=self._bar_time(),
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
            self._close_position(self._mark_price(), self._strategy_state.position_size, self._bar_time())

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
                bar_index=self._bar_index(),
                bar_time=self._bar_time(),
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
        strategy.order(id, direction, qty, limit, stop, oca_name, oca_type, comment, ...)

        Official positional order (TV reference). Pending orders fill via
        :meth:`process_pending_orders`. Supports OCA groups and partial fills
        (``max_fill_per_bar`` kwarg).
        """
        if not hasattr(self, "_strategy_state"):
            self._strategy_state = StrategyState()
        kw = kwargs or {}
        order_id = str(kw.get("id", args[0] if len(args) > 0 else "order_1"))
        raw_action = kw.get("direction", kw.get("action", args[1] if len(args) > 1 else "buy"))
        action = str(raw_action).lower()
        if action in {"strategy.long", "long", "1"}:
            action = "buy"
        elif action in {"strategy.short", "short", "-1"}:
            action = "sell"
        qty = self._coerce_number(kw.get("qty", args[2] if len(args) > 2 else 1.0), default=1.0)
        limit_price = self._coerce_optional_price(kw.get("limit", args[3] if len(args) > 3 else None))
        stop_price = self._coerce_optional_price(kw.get("stop", args[4] if len(args) > 4 else None))
        # TV: oca_name, oca_type, comment — also tolerate comment before oca
        oca_name = kw.get("oca_name", args[5] if len(args) > 5 else None)
        oca_type_raw = kw.get("oca_type", args[6] if len(args) > 6 else "none")
        comment = kw.get("comment", args[7] if len(args) > 7 else "")
        # Heuristic: if args[5] looks like oca type constant, shift
        if isinstance(oca_name, str) and oca_name.lower() in {"none", "cancel", "reduce"}:
            oca_type_raw = oca_name
            oca_name = kw.get("oca_name")
            comment = kw.get("comment", args[6] if len(args) > 6 else comment)
        # If args[5] is comment-like and args[6] is oca type (greedy script:
        # comment="TPSL", oca.reduce, oca_name="TPSL" is NOT that order —
        # greedy is: ..., "TPSL", oca.reduce, "TPSL" = oca_name, oca_type, comment)
        oca_type = str(oca_type_raw or "none").lower()
        if oca_type in {"strategy.oca.none", "oca.none"}:
            oca_type = "none"
        elif oca_type in {"strategy.oca.cancel", "oca.cancel"}:
            oca_type = "cancel"
        elif oca_type in {"strategy.oca.reduce", "oca.reduce"}:
            oca_type = "reduce"
        oca_name_str = None if oca_name is None else str(oca_name)
        if oca_name_str is not None and oca_name_str.lower() in {"none", "cancel", "reduce"}:
            oca_name_str = None
        max_fill = self._coerce_number(
            kw.get("max_fill_per_bar", self._strategy_state.default_max_fill_per_bar),
            default=0.0,
        )

        if stop_price is not None and limit_price is not None:
            order_type = "stop-limit"
        elif stop_price is not None:
            order_type = "stop"
        elif limit_price is not None:
            order_type = "limit"
        else:
            order_type = "market"

        order = Order(
            order_id,
            order_type,
            action,
            qty,
            limit_price,
            stop_price,
            str(comment) if comment is not None else "",
            max_fill_per_bar=max_fill,
            oca_name=oca_name_str,
            oca_type=oca_type,
        )
        self._strategy_state.pending_orders[order_id] = order

        self._record_strategy_event(
            StrategyEvent(
                kind="order",
                id=order_id,
                direction="long" if action in {"buy", "long"} else "short",
                qty=qty,
                order_type="market" if order_type == "market" else "limit" if order_type == "limit" else "stop",
                limit=limit_price,
                stop=stop_price,
                oca_name=oca_name_str,
                comment=str(comment) if comment is not None else "",
                bar_index=self._bar_index(),
                bar_time=self._bar_time(),
                ohlc=(0.0, 0.0, 0.0, 0.0),
                script_id="",
                run_id="",
            )
        )

    def process_pending_orders(
        self,
        *,
        open_: float | None = None,
        high: float | None = None,
        low: float | None = None,
        close: float | None = None,
    ) -> list[str]:
        """Evaluate pending limit/stop orders against the current bar OHLC.

        Returns list of order ids that fully filled this call.
        Called by Runtime each bar (before script visit) when bar mode.
        """
        if not hasattr(self, "_strategy_state"):
            return []
        pending = self._strategy_state.pending_orders
        if not pending:
            return []
        ctx = getattr(self, "context", {}) or {}
        o = self._coerce_number(open_ if open_ is not None else ctx.get("open"), default=self._mark_price())
        h = self._coerce_number(high if high is not None else ctx.get("high"), default=o)
        l = self._coerce_number(low if low is not None else ctx.get("low"), default=o)
        c = self._coerce_number(close if close is not None else ctx.get("close"), default=o)

        fully_filled: list[str] = []
        # Snapshot ids — OCA may delete siblings mid-loop
        for order_id in list(pending.keys()):
            order = self._strategy_state.pending_orders.get(order_id)
            if order is None:
                continue
            if order.remaining_qty <= 0:
                self._strategy_state.pending_orders.pop(order_id, None)
                fully_filled.append(order_id)
                continue
            fill_price = self._order_fill_price(order, o, h, l, c)
            if fill_price is None:
                continue
            fill_qty = order.remaining_qty
            if order.max_fill_per_bar and order.max_fill_per_bar > 0:
                fill_qty = min(fill_qty, float(order.max_fill_per_bar))
            if fill_qty <= 0:
                continue
            self._fill_order(order, fill_price, fill_qty)
            if order.remaining_qty <= 1e-12:
                fully_filled.append(order_id)
        return fully_filled

    def _order_fill_price(
        self,
        order: Order,
        open_: float,
        high: float,
        low: float,
        close: float,
    ) -> float | None:
        """Return fill price if order triggers this bar, else None."""
        ot = order.order_type
        action = order.direction  # buy/sell
        if ot == "market":
            return close
        if ot == "limit":
            lim = order.limit_price
            if lim is None:
                return None
            if action in {"buy", "long"} and low <= lim:
                # Buy limit: fill at limit (or better open if gapped)
                return min(lim, open_) if open_ < lim else lim
            if action in {"sell", "short"} and high >= lim:
                return max(lim, open_) if open_ > lim else lim
            return None
        if ot == "stop":
            stop = order.stop_price
            if stop is None:
                return None
            if action in {"buy", "long"} and high >= stop:
                return max(stop, open_) if open_ > stop else stop
            if action in {"sell", "short"} and low <= stop:
                return min(stop, open_) if open_ < stop else stop
            return None
        if ot == "stop-limit":
            stop = order.stop_price
            lim = order.limit_price
            if stop is None or lim is None:
                return None
            # Activate when stop touched, fill only if limit still available
            if action in {"buy", "long"} and high >= stop and low <= lim:
                return lim
            if action in {"sell", "short"} and low <= stop and high >= lim:
                return lim
            return None
        return None

    def _fill_order(self, order: Order, fill_price: float, fill_qty: float) -> None:
        """Apply a fill to an order (entry/close) and shrink remaining qty."""
        fill_qty = float(min(fill_qty, order.remaining_qty))
        if fill_qty <= 0:
            return
        action = order.direction
        fill_price = self._apply_slippage(float(fill_price), action)
        order.filled_qty += fill_qty
        bar_time = self._bar_time()
        bar_index = self._bar_index()
        commission = self._calc_commission(fill_qty, fill_price)
        self._strategy_state.commission = commission

        if action in {"buy", "long"}:
            if self._strategy_state.position_direction == "short":
                cover = min(fill_qty, self._strategy_state.position_size)
                self._close_position(fill_price, cover, bar_time)
                leftover = fill_qty - cover
                if leftover > 1e-12 and self._risk_allows_entry("long", fill_price):
                    self._open_position_qty(
                        "long", leftover, fill_price, order.order_id, bar_index, bar_time, commission
                    )
            else:
                if self._risk_allows_entry("long", fill_price):
                    self._open_position_qty(
                        "long", fill_qty, fill_price, order.order_id, bar_index, bar_time, commission
                    )
        else:  # sell / short
            if self._strategy_state.position_direction == "long":
                cover = min(fill_qty, self._strategy_state.position_size)
                self._close_position(fill_price, cover, bar_time)
                leftover = fill_qty - cover
                if leftover > 1e-12 and self._risk_allows_entry("short", fill_price):
                    self._open_position_qty(
                        "short", leftover, fill_price, order.order_id, bar_index, bar_time, commission
                    )
            else:
                if self._risk_allows_entry("short", fill_price):
                    self._open_position_qty(
                        "short", fill_qty, fill_price, order.order_id, bar_index, bar_time, commission
                    )

        self._record_strategy_event(
            StrategyEvent(
                kind="order",
                id=order.order_id,
                direction="long" if action in {"buy", "long"} else "short",
                qty=fill_qty,
                order_type="market",
                limit=order.limit_price,
                stop=order.stop_price,
                oca_name=order.oca_name,
                comment=f"fill:{order.comment}" if order.comment else "fill",
                bar_index=bar_index,
                bar_time=bar_time,
                ohlc=(0.0, 0.0, 0.0, 0.0),
                script_id="",
                run_id="",
            )
        )
        # OCA: cancel or reduce siblings after this fill
        self._apply_oca_after_fill(order, fill_qty)
        if order.remaining_qty <= 1e-12:
            self._strategy_state.pending_orders.pop(order.order_id, None)

    def _apply_oca_after_fill(self, filled: Order, fill_qty: float) -> None:
        """Cancel or reduce other orders in the same OCA group."""
        if not filled.oca_name or filled.oca_type in {"none", ""}:
            return
        name = filled.oca_name
        otype = (filled.oca_type or "none").lower()
        for oid, other in list(self._strategy_state.pending_orders.items()):
            if oid == filled.order_id or other.oca_name != name:
                continue
            if otype == "cancel":
                del self._strategy_state.pending_orders[oid]
                self._record_strategy_event(
                    StrategyEvent(
                        kind="cancel",
                        id=oid,
                        direction=None,
                        qty=None,
                        order_type=None,
                        limit=None,
                        stop=None,
                        oca_name=name,
                        comment="oca_cancel",
                        bar_index=self._bar_index(),
                        bar_time=self._bar_time(),
                        ohlc=(0.0, 0.0, 0.0, 0.0),
                        script_id="",
                        run_id="",
                    )
                )
            elif otype == "reduce":
                other.quantity = max(0.0, float(other.quantity) - float(fill_qty))
                if other.remaining_qty <= 1e-12:
                    del self._strategy_state.pending_orders[oid]
                    self._record_strategy_event(
                        StrategyEvent(
                            kind="cancel",
                            id=oid,
                            direction=None,
                            qty=None,
                            order_type=None,
                            limit=None,
                            stop=None,
                            oca_name=name,
                            comment="oca_reduce",
                            bar_index=self._bar_index(),
                            bar_time=self._bar_time(),
                            ohlc=(0.0, 0.0, 0.0, 0.0),
                            script_id="",
                            run_id="",
                        )
                    )

    def _open_position_qty(
        self,
        direction: str,
        qty: float,
        fill_price: float,
        entry_id: str,
        bar_index: int,
        bar_time: int,
        commission: float = 0.0,
    ) -> None:
        """Open or add to a position (absolute qty, same direction)."""
        st = self._strategy_state
        # Pyramiding: 0 = replace/add only if flat; n = max open entries
        if st.position_direction == direction and st.position_size > 0:
            if st.pyramiding <= 0 and len(st.open_trades) >= 1:
                # Default: allow add for order fills (averaging) but cap by pyramiding=0 as single entry size update
                pass
            elif st.pyramiding > 0 and len(st.open_trades) >= st.pyramiding + 1:
                return
            total = st.position_size + qty
            st.entry_price = (st.entry_price * st.position_size + fill_price * qty) / total
            st.position_size = total
            st.open_trades.append(
                OpenTrade(
                    entry_id=entry_id,
                    entry_bar=bar_index,
                    entry_time=bar_time,
                    entry_price=fill_price,
                    direction=direction,
                    size=qty,
                    commission=float(commission),
                )
            )
        else:
            st.position_direction = direction
            st.entry_price = fill_price
            st.entry_bar = bar_index
            st.entry_time = bar_time
            st.position_size = qty
            st.position_entry_name = entry_id
            st.open_trades = [
                OpenTrade(
                    entry_id=entry_id,
                    entry_bar=bar_index,
                    entry_time=bar_time,
                    entry_price=fill_price,
                    direction=direction,
                    size=qty,
                    commission=float(commission),
                )
            ]
        st.note_position_size()
        st.equity(fill_price)
        self._record_strategy_event(
            StrategyEvent(
                kind="entry",
                id=entry_id,
                direction=direction,
                qty=qty,
                order_type=None,
                limit=None,
                stop=None,
                oca_name=None,
                comment="order_fill",
                bar_index=bar_index,
                bar_time=bar_time,
                ohlc=(0.0, 0.0, 0.0, 0.0),
                script_id="",
                run_id="",
            )
        )

    def _close_position(self, exit_price: float, qty: float, exit_time: int) -> None:
        """Helper to close (or partially close) the open position and record trades."""
        if self._strategy_state.position_direction == "flat" or qty <= 0:
            return

        # Tests / callers may seed position_* without open_trades; synthesize one.
        if not self._strategy_state.open_trades and self._strategy_state.position_size > 0:
            self._strategy_state.open_trades = [
                OpenTrade(
                    entry_id="",
                    entry_bar=self._strategy_state.entry_bar,
                    entry_time=self._strategy_state.entry_time,
                    entry_price=self._strategy_state.entry_price,
                    direction=self._strategy_state.position_direction,
                    size=float(self._strategy_state.position_size),
                    commission=float(self._strategy_state.commission),
                )
            ]

        remaining = float(qty)
        exit_bar = self._bar_index()
        exit_price = float(exit_price)
        exit_time = int(exit_time)

        new_open: list[OpenTrade] = []
        for ot in self._strategy_state.open_trades:
            if remaining <= 0:
                new_open.append(ot)
                continue
            close_qty = min(ot.size, remaining)
            if ot.direction == "long":
                profit = (exit_price - ot.entry_price) * close_qty - ot.commission * (close_qty / ot.size)
            else:
                profit = (ot.entry_price - exit_price) * close_qty - ot.commission * (close_qty / ot.size)

            commission = ot.commission * (close_qty / ot.size) if ot.size else 0.0
            self._strategy_state.closed_trades.append(
                Trade(
                    entry_bar=ot.entry_bar,
                    entry_time=ot.entry_time,
                    entry_price=ot.entry_price,
                    exit_bar=exit_bar,
                    exit_time=exit_time,
                    exit_price=exit_price,
                    direction=ot.direction,
                    size=close_qty,
                    profit=profit,
                    commission=commission,
                    entry_id=ot.entry_id,
                )
            )
            self._strategy_state.note_closed_profit(profit)
            self._strategy_state.note_closed_trade_day(exit_time, profit)
            leftover = ot.size - close_qty
            if leftover > 1e-12:
                new_open.append(
                    OpenTrade(
                        entry_id=ot.entry_id,
                        entry_bar=ot.entry_bar,
                        entry_time=ot.entry_time,
                        entry_price=ot.entry_price,
                        direction=ot.direction,
                        size=leftover,
                        commission=ot.commission - commission,
                    )
                )
            remaining -= close_qty

        self._strategy_state.open_trades = new_open
        self._strategy_state.position_size = float(sum(t.size for t in new_open))
        if self._strategy_state.position_size <= 1e-12:
            self._strategy_state.position_direction = "flat"
            self._strategy_state.position_size = 0.0
            self._strategy_state.entry_price = 0.0
            self._strategy_state.position_entry_name = ""
        else:
            # Weighted average entry of remaining opens
            total = sum(t.size for t in new_open)
            self._strategy_state.entry_price = sum(t.entry_price * t.size for t in new_open) / total
            self._strategy_state.position_direction = new_open[0].direction
            self._strategy_state.entry_bar = new_open[0].entry_bar
            self._strategy_state.entry_time = new_open[0].entry_time
            self._strategy_state.position_entry_name = new_open[0].entry_id
        self._strategy_state.equity(exit_price)  # sample equity curve after close

    # SERIES / STATS VARIABLES

    def _handle_strategy_position_size(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        return self._strategy_state.signed_position_size()

    def _handle_strategy_position_avg_price(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        if self._strategy_state.position_direction == "flat":
            return float("nan")
        return float(self._strategy_state.entry_price)

    def _handle_strategy_position_entry_name(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> str:
        return str(self._strategy_state.position_entry_name or "")

    def _handle_strategy_opentrades_count(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> int:
        return len(self._strategy_state.open_trades)

    def _handle_strategy_closedtrades_count(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> int:
        return len(self._strategy_state.closed_trades)

    def _handle_strategy_closedtrades_first_index(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> int:
        return int(self._strategy_state.closedtrades_first_index)

    def _handle_strategy_netprofit(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        return self._strategy_state.netprofit()

    def _handle_strategy_netprofit_percent(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        return self._strategy_state._pct_of_initial(self._strategy_state.netprofit())

    def _handle_strategy_openprofit(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        return self._strategy_state.openprofit(self._mark_price())

    def _handle_strategy_openprofit_percent(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        return self._strategy_state._pct_of_initial(self._strategy_state.openprofit(self._mark_price()))

    def _handle_strategy_equity(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        return self._strategy_state.equity(self._mark_price())

    def _handle_strategy_initial_capital(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        return float(self._strategy_state.initial_capital)

    def _handle_strategy_cash(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        return self._strategy_state.cash(self._mark_price())

    def _handle_strategy_account_currency(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> str:
        return str(self._strategy_state.account_currency)

    def _handle_strategy_grossprofit(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        return self._strategy_state.grossprofit()

    def _handle_strategy_grossprofit_percent(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        return self._strategy_state._pct_of_initial(self._strategy_state.grossprofit())

    def _handle_strategy_grossloss(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        return self._strategy_state.grossloss()

    def _handle_strategy_grossloss_percent(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        return self._strategy_state._pct_of_initial(self._strategy_state.grossloss())

    def _handle_strategy_wintrades(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> int:
        return int(self._strategy_state.wintrades())

    def _handle_strategy_losstrades(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> int:
        return int(self._strategy_state.losstrades())

    def _handle_strategy_eventrades(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> int:
        return int(self._strategy_state.eventrades())

    def _handle_strategy_avg_trade(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        return self._strategy_state.avg_trade()

    def _handle_strategy_avg_trade_percent(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        return self._strategy_state._pct_of_initial(self._strategy_state.avg_trade())

    def _handle_strategy_avg_winning_trade(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        return self._strategy_state.avg_winning_trade()

    def _handle_strategy_avg_winning_trade_percent(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        return self._strategy_state._pct_of_initial(self._strategy_state.avg_winning_trade())

    def _handle_strategy_avg_losing_trade(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        return self._strategy_state.avg_losing_trade()

    def _handle_strategy_avg_losing_trade_percent(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        return self._strategy_state._pct_of_initial(self._strategy_state.avg_losing_trade())

    def _handle_strategy_max_drawdown(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        self._strategy_state.equity(self._mark_price())
        return float(self._strategy_state._max_drawdown)

    def _handle_strategy_max_drawdown_percent(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        self._strategy_state.equity(self._mark_price())
        return float(self._strategy_state._max_drawdown_percent)

    def _handle_strategy_max_runup(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        self._strategy_state.equity(self._mark_price())
        return float(self._strategy_state._max_runup)

    def _handle_strategy_max_runup_percent(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        self._strategy_state.equity(self._mark_price())
        return float(self._strategy_state._max_runup_percent)

    def _handle_strategy_max_contracts_held_all(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        return float(self._strategy_state.max_contracts_held_all)

    def _handle_strategy_max_contracts_held_long(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        return float(self._strategy_state.max_contracts_held_long)

    def _handle_strategy_max_contracts_held_short(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        return float(self._strategy_state.max_contracts_held_short)

    def _handle_strategy_opentrades_capital_held(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        return self._strategy_state.capital_held()

    def _handle_strategy_margin_liquidation_price(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> None:
        # Not modeled without margin sim; Pine returns na when unknown.
        return None

    # RISK MANAGEMENT

    def _handle_strategy_risk_max_position_size(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> None:
        """
        strategy.risk.max_position_size(percent)

        Set maximum position size as percentage of account equity.
        Subsequent entries cap qty so (qty * price) <= equity * percent/100.
        """
        kw = kwargs or {}
        percent = kw.get("percent", args[0] if len(args) > 0 else None)
        if percent is None:
            return
        self._strategy_state.max_position_size_percent = float(percent)

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

    def _handle_strategy_risk_max_drawdown(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> None:
        """strategy.risk.max_drawdown(value, type) — cap overall drawdown risk.

        When ``type`` is percent (or value looks like a small percentage flag
        via kwargs), store as percent-of-peak; otherwise absolute currency.
        """
        kw = kwargs or {}
        value = kw.get("value", args[0] if len(args) > 0 else None)
        if value is None:
            return
        risk_type = str(kw.get("type", args[1] if len(args) > 1 else "absolute")).lower()
        if risk_type in {"percent", "percentage", "strategy.percent_of_equity", "%"}:
            self._strategy_state.max_drawdown_risk_percent = float(value)
        else:
            self._strategy_state.max_drawdown_risk = float(value)

    def _handle_strategy_risk_max_cons_loss_days(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> None:
        """strategy.risk.max_cons_loss_days(days) — stop after N consecutive loss days."""
        kw = kwargs or {}
        days = kw.get("days", args[0] if len(args) > 0 else None)
        if days is None:
            return
        self._strategy_state.max_cons_loss_days = int(days)

    def _handle_strategy_risk_allow_entry_in(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> None:
        """strategy.risk.allow_entry_in(value) — 'all' | 'long' | 'short'."""
        kw = kwargs or {}
        value = kw.get("value", args[0] if len(args) > 0 else "all")
        self._strategy_state.allow_entry_in = str(value)

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
        """strategy.opentrades.profit(trade_index) — mark-to-market vs close."""
        trade_index = args[0] if len(args) > 0 else 0
        if 0 <= trade_index < len(self._strategy_state.open_trades):
            ot = self._strategy_state.open_trades[trade_index]
            mark = self._mark_price()
            if ot.direction == "long":
                return (mark - ot.entry_price) * ot.size - ot.commission
            return (ot.entry_price - mark) * ot.size - ot.commission
        return 0.0

    def _handle_opentrades_commission(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> float:
        """strategy.opentrades.commission(trade_index)"""
        trade_index = args[0] if len(args) > 0 else 0
        if 0 <= trade_index < len(self._strategy_state.open_trades):
            return self._strategy_state.open_trades[trade_index].commission
        return 0.0
