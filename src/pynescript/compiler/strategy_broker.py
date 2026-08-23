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

"""Lightweight strategy broker for the compile (object-mode) path.

Used only when :class:`~pynescript.compiler.compiler.CompilerVisitor` emits
strategy APIs. Instantiated inside generated ``execute_script_compiled`` as
``__strategy``; not used on the pure-numeric njit path.

Public types
------------
- :class:`PendingOrder` — limit/stop/stop-limit (and market-pending) state.
- :class:`CompileStrategyBroker` — position, equity, pending book, event log.

Order / event contracts
-----------------------
Supports market entry/close plus pending limit/stop/stop-limit with per-bar
OHLC fills (aligned with the interpreter's ``process_pending_orders``).

Event dict shape (``kind`` ∈ entry/close/close_all/order/cancel/cancel_all)::

    {
      "kind", "id", "direction", "qty", "order_type",
      "limit", "stop", "oca_name", "comment",
      "bar_index", "bar_time", "ohlc": [o, h, l, c],
    }

Host result extras (object-mode return dict): ``__events`` (via
:meth:`CompileStrategyBroker.to_events`), ``__position_size``, ``__netprofit``,
``__equity``.

Hot-path notes
--------------
- ``begin_bar`` folds set_bar + process_pending into one call (less float churn).
- Empty pending skips work; market entry skips classify/opt_float.
- ``_emit`` builds the event dict without intermediate ``**fields`` packing.
- Event order and dict shape are preserved (tests / Runtime consumers).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


def _is_na(value: Any) -> bool:
    if value is None:
        return True
    # Hot path: plain float/int (including numpy float64 via float subclass)
    t = type(value)
    if t is float:
        return value != value  # NaN
    if t is int:
        return False
    if isinstance(value, float):
        return value != value
    if isinstance(value, str) and value.lower() in {"", "na", "nan", "none"}:
        return True
    return False


def _opt_float(value: Any) -> float | None:
    if value is None:
        return None
    t = type(value)
    if t is float:
        return None if value != value else value
    if t is int:
        return float(value)
    if isinstance(value, str) and value.lower() in {"", "na", "nan", "none"}:
        return None
    try:
        f = float(value)
        return None if f != f else f
    except (TypeError, ValueError):
        return None


def _norm_dir(direction: Any) -> str | None:
    """Normalize to ``long``/``short``; ``None`` if unrecognised (reject, do not fill)."""
    # Compile path almost always passes "long" / "short" already.
    if direction == "long" or direction == "short":
        return direction  # type: ignore[return-value]
    if direction is None:
        return None
    d = str(direction).lower().strip()
    if d in {"strategy.long", "long", "1", "buy"}:
        return "long"
    if d in {"strategy.short", "short", "-1", "sell"}:
        return "short"
    return None


def _parse_qty(qty: Any) -> tuple[str, float]:
    """Strict qty for compile broker: ``ok`` / ``missing`` / ``invalid``."""
    if qty is None:
        return ("missing", 0.0)
    if isinstance(qty, str) and qty.lower() in {"", "na", "nan", "none"}:
        return ("missing", 0.0)
    try:
        f = float(qty)
    except (TypeError, ValueError):
        return ("invalid", 0.0)
    if not math.isfinite(f) or f < 0:
        return ("invalid", 0.0)
    return ("ok", float(f))


@dataclass
class PendingOrder:
    """One working order in the compile-path pending book.

    Attributes
    ----------
    order_type:
        ``market`` | ``limit`` | ``stop`` | ``stop-limit``.
    direction:
        ``long`` | ``short`` (normalized).
    is_entry:
        ``False`` for reduce-only / cover intent when opposite the open position.
    oca_type:
        ``none`` | ``cancel`` | ``reduce`` after normalization.
    """

    order_id: str
    order_type: str  # market | limit | stop | stop-limit
    direction: str  # long | short
    quantity: float
    limit_price: float | None = None
    stop_price: float | None = None
    comment: str | None = None
    oca_name: str | None = None
    oca_type: str = "none"
    filled_qty: float = 0.0
    max_fill_per_bar: float = 0.0
    # entry vs reduce-only close intent
    is_entry: bool = True
    # strategy.exit from_entry (compiler emits from_entry= on close; optional)
    from_entry: str | None = None
    # Trailing stop state (strategy.exit trail_*). Distances are price units.
    trail_offset: float | None = None
    trail_activation: float | None = None
    trail_active: bool = False

    @property
    def remaining(self) -> float:
        """Unfilled quantity (never negative)."""
        return max(0.0, float(self.quantity) - float(self.filled_qty))

    @property
    def is_trail(self) -> bool:
        """True when a positive trail offset is configured."""
        return self.trail_offset is not None and self.trail_offset > 0


@dataclass
class OpenLeg:
    """One open entry leg (minimal interpret ``OpenTrade`` subset).

    Used for multi-leg pyramiding and ``strategy.exit(..., from_entry=...)``
    targeting on the compile path. Also backs ``strategy.opentrades.*`` queries.

    ``max_drawdown`` / ``max_runup`` are approximate max adverse / favorable
    excursion (currency) while open, updated from bar high/low MTM.
    """

    entry_id: str
    size: float
    entry_price: float
    direction: str  # long | short
    commission: float = 0.0
    entry_bar: int = 0
    entry_time: int = 0
    entry_comment: str = ""
    max_drawdown: float = 0.0
    max_runup: float = 0.0


@dataclass
class ClosedTradeRecord:
    """Minimal closed-trade record for ``strategy.closedtrades.*`` queries.

    One record per :meth:`CompileStrategyBroker._realize_close` call (aggregated
    when multiple legs reduce in a single close). Not a full TV trade object.

    Per-trade ``max_drawdown`` / ``max_runup`` are copied from the open leg's
    MTM extremes (approximate OHLC path; not tick-accurate).
    """

    entry_id: str
    size: float
    entry_price: float
    exit_price: float
    profit: float
    commission: float
    direction: str  # long | short
    entry_bar: int = 0
    entry_time: int = 0
    exit_bar: int = 0
    exit_time: int = 0
    exit_id: str = ""
    entry_comment: str = ""
    exit_comment: str = ""
    max_drawdown: float = 0.0
    max_runup: float = 0.0


class CompileStrategyBroker:
    """Per-run strategy state for compiled object-mode scripts.

    Public methods mirror Pine ``strategy.entry`` / ``close`` / ``order`` /
    ``cancel`` surfaces enough for corpus + API consumers. Bar context is set
    via :meth:`begin_bar` (preferred) or :meth:`set_bar` +
    :meth:`process_pending_orders`.

    Properties ``equity``, ``openprofit``, ``max_drawdown`` / ``max_runup``
    (and percent variants) are mark-to-market against the current bar close.
    """

    def __init__(
        self,
        initial_capital: float = 100_000.0,
        commission_value: float = 0.0,
        commission_type: str = "percent",
        slippage_ticks: int = 0,
        mintick: float = 0.01,
        pyramiding: int = 0,
        default_qty_type: str = "fixed",
        default_qty_value: float = 1.0,
        avg_price_model: str = "stock",
        leverage: float | None = None,
        margin_long: float | None = None,
        margin_short: float | None = None,
    ) -> None:
        """Construct broker state for one compiled run.

        Parameters mirror Pine ``strategy()`` declaration kwargs when the
        visitor captures them into the generated ctor call.

        Commission model (interpret parity, closer to reference semantics): charge on **entry**
        (held as ``position_commission`` / openprofit drag) **and** on **exit**
        fills; both realize into netprofit on close.

        ``default_qty_type`` / ``default_qty_value`` mirror interpret when the
        visitor wires them into the ctor (percent_of_equity / cash / fixed).

        ``avg_price_model`` (pynescript extension): ``stock`` | ``futures`` |
        ``inverse``. Multi-leg open list supports ``from_entry`` exits.
        ``stock`` reweights remaining-leg VWAP on partial close; ``futures`` /
        ``inverse`` keep sticky net AEP until flat.

        ``leverage`` (pynescript extension): buying-power multiplier for
        percent_of_equity / cash default qty and margin locked in ``cash``.
        """
        self.initial_capital = float(initial_capital)
        self.commission_value = float(commission_value)
        self.commission_type = str(commission_type)
        self.slippage_ticks = int(slippage_ticks)
        self.mintick = float(mintick)
        # 0 = one market entry id; n = up to n additional same-direction entries
        self.pyramiding = int(pyramiding) if pyramiding is not None else 0
        dqt = str(default_qty_type or "fixed").replace("strategy.", "").lower()
        if dqt in {"percent", "percentage"}:
            dqt = "percent_of_equity"
        self.default_qty_type: str = dqt
        self.default_qty_value: float = float(default_qty_value) if default_qty_value is not None else 1.0
        # Soft-normalize avg model (keep in sync with interpret _norm_avg_price_model)
        raw_apm = str(avg_price_model or "stock").replace("strategy.", "").replace("avg_price_", "").strip().lower()
        if raw_apm in {"stock", "pine", "average", "avg", "lot", "fifo"}:
            self.avg_price_model: str = "stock"
        elif raw_apm in {"futures", "future", "perp", "perpetual", "net", "linear"}:
            self.avg_price_model = "futures"
        elif raw_apm in {"inverse", "coin", "coin_m", "harmonic"}:
            self.avg_price_model = "inverse"
        else:
            self.avg_price_model = "stock"
        self.leverage = 1.0
        if leverage is not None:
            try:
                lev = float(leverage)
            except (TypeError, ValueError):
                lev = 1.0
            if lev != lev or lev <= 0:
                lev = 1.0
            self.leverage = 1.0 if lev < 1.0 else lev
        else:
            sides: list[float] = []
            for raw in (margin_long, margin_short):
                if raw is None:
                    continue
                try:
                    m = float(raw)
                except (TypeError, ValueError):
                    continue
                if m > 0:
                    sides.append(m)
            if sides:
                self.leverage = max(1.0, 100.0 / max(sides))
        self.position_size: float = 0.0  # signed: +long / -short
        self.position_avg_price: float = float("nan")
        self.position_entry_name: str = ""
        # Open entry legs (pyramiding / from_entry). open_entry_count mirrors len.
        self.open_legs: list[OpenLeg] = []
        self.open_entry_count: int = 0
        # Remaining entry commission on the open position (openprofit drag).
        # Exit commission is charged at close time and never sits on the open.
        self.position_commission: float = 0.0
        self.netprofit: float = 0.0
        self.closed_trades: int = 0
        # Per-close records for strategy.closedtrades.*(i) queries.
        self.closed_trade_records: list[ClosedTradeRecord] = []
        self.wintrades: int = 0
        self.losstrades: int = 0
        self.eventrades: int = 0
        self.grossprofit: float = 0.0
        self.grossloss: float = 0.0
        # Pine strategy.max_contracts_held_* (unsigned qty peaks; interpret parity)
        self.max_contracts_held_all: float = 0.0
        self.max_contracts_held_long: float = 0.0
        self.max_contracts_held_short: float = 0.0
        self.account_currency: str = "USD"
        self.closedtrades_first_index: int = 0
        self.events: list[dict[str, Any]] = []
        self.pending_orders: dict[str, PendingOrder] = {}
        self._bar_index: int = 0
        self._bar_time: int = 0
        self._mark: float = 0.0
        self._open: float = 0.0
        self._high: float = 0.0
        self._low: float = 0.0
        self._close: float = 0.0
        self._equity_peak: float = float(initial_capital)
        self._equity_trough: float = float(initial_capital)
        self._max_drawdown: float = 0.0
        self._max_runup: float = 0.0
        self._max_drawdown_percent: float = 0.0
        self._max_runup_percent: float = 0.0
        # strategy.risk.* subset (not full TV risk engine; interpret-aligned halt cascade)
        self.allow_entry_in: str = "all"  # all | long | short
        self.max_position_size_percent: float | None = None
        self.max_drawdown_risk: float | None = None  # absolute equity drawdown cap
        self.max_drawdown_risk_percent: float | None = None  # % of peak equity
        self.max_cons_loss_days: int | None = None
        # Intraday loss halt as % of initial capital (interpret stores; we enforce)
        self.max_intraday_loss: float = float("inf")
        # Cap filled orders per calendar-day bucket (entries + exits)
        self.max_intraday_filled_orders: int | None = None
        self.entries_blocked: bool = False  # risk halt (drawdown / cons loss / intraday)
        self.consecutive_loss_days: int = 0
        self._last_trade_day: int | None = None  # exit_time day bucket
        self._day_pnl: float = 0.0
        self._fills_day: int | None = None  # day bucket for fill counting
        self._day_filled_orders: int = 0

    def begin_bar(
        self,
        bar_index: int,
        open_: float,
        high: float,
        low: float,
        close: float,
        bar_time: int = 0,
    ) -> None:
        """One-call bar setup + pending fill (compile hot path).

        Prefer this over separate ``set_bar`` + ``process_pending_orders`` —
        avoids re-float of OHLC and skips pending walk when empty.
        """
        o = float(open_)
        h = float(high)
        l = float(low)
        c = float(close)
        self._bar_index = int(bar_index)
        self._bar_time = int(bar_time)
        self._open = o
        self._high = h
        self._low = l
        self._close = c
        self._mark = c
        # Equity only changes mid-run when position open (mark-to-market) or
        # after closes (netprofit). Flat → constant; skip peak/trough work.
        if self.position_size != 0.0:
            self._update_equity_extremes()
            self._update_leg_extremes()
        if self.pending_orders:
            self._process_pending_ohlc(o, h, l, c)

    def set_bar(
        self,
        bar_index: int,
        bar_time: int = 0,
        mark: float = 0.0,
        open_: float | None = None,
        high: float | None = None,
        low: float | None = None,
        close: float | None = None,
    ) -> None:
        """Update bar context. Call process_pending_orders separately after OHLC set."""
        self._bar_index = int(bar_index)
        self._bar_time = int(bar_time)
        c = float(close if close is not None else mark)
        o = float(open_ if open_ is not None else c)
        h = float(high if high is not None else max(o, c))
        l = float(low if low is not None else min(o, c))
        self._open, self._high, self._low, self._close = o, h, l, c
        self._mark = c
        if self.position_size != 0.0:
            self._update_equity_extremes()
            self._update_leg_extremes()

    def process_pending_orders(
        self,
        open_: float | None = None,
        high: float | None = None,
        low: float | None = None,
        close: float | None = None,
    ) -> list[str]:
        """Fill pending orders against this bar's OHLC. Returns fully filled ids."""
        if not self.pending_orders:
            return []
        o = float(open_ if open_ is not None else self._open)
        h = float(high if high is not None else self._high)
        l = float(low if low is not None else self._low)
        c = float(close if close is not None else self._close)
        return self._process_pending_ohlc(o, h, l, c)

    def _process_pending_ohlc(
        self,
        o: float,
        h: float,
        l: float,
        c: float,
    ) -> list[str]:
        fully: list[str] = []
        # Snapshot keys — OCA may delete siblings mid-loop
        for oid in list(self.pending_orders.keys()):
            order = self.pending_orders.get(oid)
            if order is None:
                continue
            if order.remaining <= 0:
                self.pending_orders.pop(oid, None)
                fully.append(oid)
                continue
            # Trail: ratchet stop from favorable extreme, then test fill
            if order.is_trail:
                self._update_trail_stop(order, h, l)
            fill_px = self._trigger_price(order, o, h, l, c)
            if fill_px is None:
                continue
            fill_qty = order.remaining
            if order.max_fill_per_bar and order.max_fill_per_bar > 0:
                fill_qty = min(fill_qty, float(order.max_fill_per_bar))
            if fill_qty <= 0:
                continue
            self._apply_fill(order, fill_px, fill_qty)
            if order.remaining <= 1e-12:
                fully.append(oid)
        return fully

    def _update_trail_stop(self, order: PendingOrder, high: float, low: float) -> None:
        """Ratchet a trailing stop from bar extremes once armed.

        Long exit (sell stop, direction ``short``): after activation,
        ``stop = high - offset``, only rising. Short exit (buy stop, direction
        ``long``): ``stop = low + offset``, only falling. Fixed ``stop_price``
        set at placement acts as a floor/ceiling that the trail may improve
        but not worsen beyond on first arm.
        """
        if not order.is_trail:
            return
        offset = float(order.trail_offset or 0.0)
        if offset <= 0:
            return
        action = order.direction  # short closes long; long covers short
        act = order.trail_activation
        if not order.trail_active:
            if act is None:
                order.trail_active = True
            elif action == "short" and high >= float(act):
                order.trail_active = True
            elif action == "long" and low <= float(act):
                order.trail_active = True
            else:
                return
        if action == "short":
            candidate = float(high) - offset
            if order.stop_price is None or candidate > float(order.stop_price):
                order.stop_price = candidate
        elif action == "long":
            candidate = float(low) + offset
            if order.stop_price is None or candidate < float(order.stop_price):
                order.stop_price = candidate

    def _trigger_price(
        self,
        order: PendingOrder,
        open_: float,
        high: float,
        low: float,
        close: float,
    ) -> float | None:
        ot = order.order_type
        d = order.direction
        if ot == "market":
            return close
        if ot == "limit":
            lim = order.limit_price
            if lim is None:
                return None
            if d == "long" and low <= lim:
                return min(lim, open_) if open_ < lim else lim
            if d == "short" and high >= lim:
                return max(lim, open_) if open_ > lim else lim
            return None
        if ot == "stop":
            stop = order.stop_price
            if stop is None:
                return None
            if d == "long" and high >= stop:
                return max(stop, open_) if open_ > stop else stop
            if d == "short" and low <= stop:
                return min(stop, open_) if open_ < stop else stop
            return None
        if ot == "stop-limit":
            stop, lim = order.stop_price, order.limit_price
            if stop is None or lim is None:
                return None
            if d == "long" and high >= stop and low <= lim:
                return lim
            if d == "short" and low <= stop and high >= lim:
                return lim
            return None
        return None

    def _apply_fill(self, order: PendingOrder, fill_price: float, fill_qty: float) -> None:
        fill_qty = min(fill_qty, order.remaining)
        if fill_qty <= 0:
            return
        order.filled_qty += fill_qty
        d = order.direction
        px = self._slip(float(fill_price), d)
        fe = order.from_entry
        # Closing opposite / reducing — honor from_entry when set (exit brackets)
        if not order.is_entry:
            # Force close in this direction (sell covers long, buy covers short)
            if d == "short" and self.position_size > 0:
                self.close(
                    id=order.order_id,
                    qty=fill_qty,
                    price=px,
                    comment=order.comment,
                    from_entry=fe,
                )
            elif d == "long" and self.position_size < 0:
                self.close(
                    id=order.order_id,
                    qty=fill_qty,
                    price=px,
                    comment=order.comment,
                    from_entry=fe,
                )
            else:
                self._open_or_add(d, fill_qty, px, order.order_id, order.comment)
        else:
            self._open_or_add(d, fill_qty, px, order.order_id, order.comment)

        self._emit(
            "order",
            id=order.order_id,
            direction=d,
            qty=fill_qty,
            order_type="market",
            limit=order.limit_price,
            stop=order.stop_price,
            oca_name=order.oca_name,
            comment=f"fill:{order.comment}" if order.comment else "fill",
        )
        self._oca_after_fill(order, fill_qty)
        if order.remaining <= 1e-12:
            self.pending_orders.pop(order.order_id, None)

    def _oca_after_fill(self, filled: PendingOrder, fill_qty: float) -> None:
        if not filled.oca_name or filled.oca_type in {"none", ""}:
            return
        name = filled.oca_name
        otype = (filled.oca_type or "none").lower()
        for oid, other in list(self.pending_orders.items()):
            if oid == filled.order_id or other.oca_name != name:
                continue
            if otype == "cancel":
                self.pending_orders.pop(oid, None)
                self._emit("cancel", id=oid, oca_name=name, comment="oca_cancel")
            elif otype == "reduce":
                other.quantity = max(0.0, float(other.quantity) - float(fill_qty))
                if other.remaining <= 1e-12:
                    self.pending_orders.pop(oid, None)
                    self._emit("cancel", id=oid, oca_name=name, comment="oca_reduce")

    def _entry_open_size(self, from_entry: str | None) -> float:
        """Open size for ``from_entry`` legs, or whole position when unset."""
        if not from_entry:
            return abs(float(self.position_size))
        if not self.open_legs:
            # Single-lot fallback: match last entry name or accept when unnamed.
            if abs(self.position_size) <= 0:
                return 0.0
            if not self.position_entry_name or self.position_entry_name == from_entry:
                return abs(float(self.position_size))
            return 0.0
        return float(sum(leg.size for leg in self.open_legs if leg.entry_id == from_entry))

    def _new_leg(
        self,
        entry_id: str,
        size: float,
        entry_price: float,
        direction: str,
        commission: float = 0.0,
        *,
        entry_bar: int | None = None,
        entry_time: int | None = None,
        entry_comment: str = "",
        max_drawdown: float = 0.0,
        max_runup: float = 0.0,
    ) -> OpenLeg:
        """Build an :class:`OpenLeg` stamped with current bar context."""
        return OpenLeg(
            entry_id=str(entry_id),
            size=float(size),
            entry_price=float(entry_price),
            direction=direction,
            commission=float(commission),
            entry_bar=int(self._bar_index if entry_bar is None else entry_bar),
            entry_time=int(self._bar_time if entry_time is None else entry_time),
            entry_comment=str(entry_comment or ""),
            max_drawdown=float(max_drawdown),
            max_runup=float(max_runup),
        )

    @staticmethod
    def _day_bucket(ts: int) -> int:
        """Calendar-day bucket from bar/exit time (ms, s, or raw)."""
        t = int(ts)
        if t > 10_000_000_000:  # ms epoch
            return t // 86_400_000
        if t > 10_000_000:  # seconds epoch
            return t // 86_400
        return t

    def _roll_fill_day(self) -> None:
        """Reset intraday fill counter when the bar-time day bucket changes."""
        day = self._day_bucket(self._bar_time)
        if self._fills_day is None or day != self._fills_day:
            self._fills_day = day
            self._day_filled_orders = 0

    def _note_filled_order(self) -> None:
        """Count one filled order toward max_intraday_filled_orders."""
        self._roll_fill_day()
        self._day_filled_orders += 1
        self._note_position_size()

    def _note_position_size(self) -> None:
        """Update ``strategy.max_contracts_held_*`` after a fill.

        Compile ``position_size`` is signed; peaks are unsigned quantities
        (same as interpret ``StrategyState.note_position_size``).
        """
        size = abs(float(self.position_size))
        if size > self.max_contracts_held_all:
            self.max_contracts_held_all = size
        if self.position_size > 0 and size > self.max_contracts_held_long:
            self.max_contracts_held_long = size
        elif self.position_size < 0 and size > self.max_contracts_held_short:
            self.max_contracts_held_short = size

    def _ensure_legs(self) -> None:
        """Materialise a single synthetic leg when size is open but list empty."""
        if self.open_legs or abs(self.position_size) <= 0:
            return
        d = "long" if self.position_size > 0 else "short"
        self.open_legs = [
            self._new_leg(
                entry_id=str(self.position_entry_name or ""),
                size=abs(float(self.position_size)),
                entry_price=float(self.position_avg_price)
                if self.position_avg_price == self.position_avg_price
                else 0.0,
                direction=d,
                commission=float(self.position_commission or 0.0),
            )
        ]
        self.open_entry_count = 1

    def _open_or_add(
        self,
        direction: str,
        qty: float,
        px: float,
        entry_id: str,
        comment: str | None,
        *,
        respect_pyramiding: bool = False,
    ) -> bool:
        """Open / add / reverse a position.

        Returns False when the entry was blocked (pyramiding / invalid).

        Parameters
        ----------
        respect_pyramiding:
            Market ``strategy.entry`` path: extra same-direction fills only
            when ``open_entry_count < pyramiding + 1`` (same id or not).
            A filled position is never overwritten — that used to reset
            ``position_avg_price`` every bar the entry condition stayed true.
            Pending order fills keep averaging (``respect_pyramiding=False``).
            When ``pyramiding <= 0``, pending averages stay a **single** entry
            leg (``open_entry_count == 1``) with VWAP avg (F2).
            Pending same-id replacement is the ``pending_orders[id]`` upsert.
        """
        d = direction if direction == "long" or direction == "short" else _norm_dir(direction)
        if d is None:
            return False
        q = abs(float(qty))
        if q <= 0 or not math.isfinite(q):
            return False
        eid = str(entry_id)
        # Reverse if opposite — emit close only (interpret parity; no close_all).
        if (d == "long" and self.position_size < 0) or (d == "short" and self.position_size > 0):
            self.close(id=eid, qty=abs(self.position_size), comment="reverse", price=px)
        same_dir = (self.position_size > 0 and d == "long") or (self.position_size < 0 and d == "short")
        if same_dir and abs(self.position_size) > 0:
            self._ensure_legs()
            if respect_pyramiding:
                max_entries = int(self.pyramiding) + 1 if self.pyramiding is not None else 1
                if not (self.pyramiding > 0 and self.open_entry_count < max_entries):
                    return False  # pyramiding blocked
                comm = self._commission(q, px)
                signed = q if d == "long" else -q
                old = abs(self.position_size)
                self.position_avg_price = (self.position_avg_price * old + px * q) / (old + q)
                self.position_size += signed
                self.position_commission += comm
                self.position_entry_name = eid
                cmt = str(comment) if comment else ""
                self.open_legs.append(
                    self._new_leg(
                        entry_id=eid,
                        size=q,
                        entry_price=px,
                        direction=d,
                        commission=comm,
                        entry_comment=cmt,
                    )
                )
                self.open_entry_count = len(self.open_legs)
                self._note_filled_order()
                self._update_leg_extremes()
                self._emit("entry", id=eid, direction=d, qty=q, comment=comment)
                return True
            else:
                # Average-add (pending order fills).
                # F2: pyramiding<=0 → single leg + VWAP; pyramiding>0 appends a
                # leg when under cap (interpret open_trades parity).
                if self.pyramiding > 0 and len(self.open_legs) >= int(self.pyramiding) + 1:
                    return False  # at open-leg cap
                comm = self._commission(q, px)
                signed = q if d == "long" else -q
                old = abs(self.position_size)
                self.position_avg_price = (self.position_avg_price * old + px * q) / (old + q)
                self.position_size += signed
                self.position_commission += comm
                self.position_entry_name = eid
                cmt = str(comment) if comment else ""
                if self.pyramiding <= 0:
                    # Merge into one leg (VWAP), keep first entry_id when present
                    if self.open_legs:
                        first = self.open_legs[0]
                        total_comm = float(sum(leg.commission for leg in self.open_legs)) + comm
                        self.open_legs = [
                            self._new_leg(
                                entry_id=first.entry_id,
                                size=old + q,
                                entry_price=float(self.position_avg_price),
                                direction=d,
                                commission=total_comm,
                                entry_bar=first.entry_bar,
                                entry_time=first.entry_time,
                                entry_comment=first.entry_comment or cmt,
                                max_drawdown=float(first.max_drawdown),
                                max_runup=float(first.max_runup),
                            )
                        ]
                    else:
                        self.open_legs = [
                            self._new_leg(
                                entry_id=eid,
                                size=q,
                                entry_price=px,
                                direction=d,
                                commission=comm,
                                entry_comment=cmt,
                            )
                        ]
                    self.open_entry_count = 1
                else:
                    self.open_legs.append(
                        self._new_leg(
                            entry_id=eid,
                            size=q,
                            entry_price=px,
                            direction=d,
                            commission=comm,
                            entry_comment=cmt,
                        )
                    )
                    self.open_entry_count = len(self.open_legs)
                self._note_filled_order()
                self._update_leg_extremes()
                self._emit("entry", id=eid, direction=d, qty=q, comment=comment)
                return True
        # Flat open or reverse re-entry (filled same-dir is handled above)
        comm = self._commission(q, px)
        signed = q if d == "long" else -q
        self.position_size = signed
        self.position_avg_price = px
        self.position_commission = comm
        self.position_entry_name = eid
        cmt = str(comment) if comment else ""
        self.open_legs = [
            self._new_leg(
                entry_id=eid,
                size=q,
                entry_price=px,
                direction=d,
                commission=comm,
                entry_comment=cmt,
            )
        ]
        self.open_entry_count = 1
        self._note_filled_order()
        self._update_leg_extremes()
        self._emit("entry", id=eid, direction=d, qty=q, comment=comment)
        return True

    def _slip(self, price: float, direction: str) -> float:
        if self.slippage_ticks <= 0:
            return price
        slip = self.slippage_ticks * self.mintick
        if direction == "long":
            return price + slip
        if direction == "short":
            return price - slip
        d = _norm_dir(direction)
        if d is None:
            return price
        return price + slip if d == "long" else price - slip

    def _commission(self, qty: float, price: float) -> float:
        val = self.commission_value
        if val == 0:
            return 0.0
        q, p = abs(qty), abs(price)
        ct = self.commission_type
        # Avoid .lower() when already a plain token
        if ct == "percent" or ct == "strategy.commission.percent":
            return q * p * (val / 100.0)
        if ct == "cash_per_order" or ct == "strategy.commission.cash_per_order":
            return val
        if ct == "cash_per_contract" or ct == "strategy.commission.cash_per_contract":
            return val * q
        ct_l = ct.lower()
        if ct_l in {"percent", "strategy.commission.percent"}:
            return q * p * (val / 100.0)
        if ct_l in {"cash_per_order", "strategy.commission.cash_per_order"}:
            return val
        if ct_l in {"cash_per_contract", "strategy.commission.cash_per_contract"}:
            return val * q
        return 0.0

    def _resolve_default_qty(self, fill_price: float) -> float:
        """Resolve entry size from ``default_qty_type`` / ``default_qty_value``.

        Mirrors interpret ``_resolve_default_entry_qty``:
        - ``fixed``: contracts = default_qty_value (default 1); leverage ignored
        - ``percent_of_equity``: margin = equity * (pct/100); qty = margin * leverage / price
        - ``cash``: margin = cash_amount; qty = margin * leverage / price
        """
        dqt = (self.default_qty_type or "fixed").replace("strategy.", "").lower()
        val = float(self.default_qty_value or 0.0)
        price = float(fill_price) if fill_price and fill_price > 0 else float(self._mark or 1.0)
        if price <= 0 or price != price:
            price = 1.0
        lev = float(self.leverage) if self.leverage and self.leverage > 0 else 1.0
        if dqt in {"percent_of_equity", "percent", "percentage"}:
            equity = float(self.equity)
            margin = equity * (val / 100.0)
            return max(0.0, (margin * lev) / price)
        if dqt == "cash":
            return max(0.0, (val * lev) / price)
        return max(0.0, val if val > 0 else 1.0)

    def _exit_fill_price(
        self,
        *,
        limit: float | None,
        stop: float | None,
        is_long: bool,
        is_short: bool,
    ) -> float | None:
        """Exit fill price when bar OHLC touches stop/limit (pending OHLC semantics).

        Matches interpret ``_handle_strategy_exit`` + ``process_pending_orders``:
        returns a fill price only when high/low of the current bar reaches the
        level. When mark sits *between* stop and limit, returns ``None`` so the
        caller can place a pending order instead of filling immediately.
        """
        limit_p = _opt_float(limit)
        stop_p = _opt_float(stop)
        if limit_p is None and stop_p is None:
            return None
        hi = float(self._high)
        lo = float(self._low)
        op = float(self._open)
        # Prefer OHLC path (same as interpret pending fills)
        if is_long:
            # Close long: sell limit (TP) when high >= lim; sell stop when low <= stop
            hit_lim = limit_p is not None and hi >= limit_p
            hit_stop = stop_p is not None and lo <= stop_p
            if hit_lim and hit_stop:
                # Both touched: prefer stop (worse for long) — conservative
                return float(stop_p)  # type: ignore[arg-type]
            if hit_lim:
                return float(limit_p) if op > limit_p else float(limit_p)  # type: ignore[arg-type]
            if hit_stop:
                return float(stop_p) if op < stop_p else float(stop_p)  # type: ignore[arg-type]
            return None
        if is_short:
            hit_lim = limit_p is not None and lo <= limit_p
            hit_stop = stop_p is not None and hi >= stop_p
            if hit_lim and hit_stop:
                return float(stop_p)  # type: ignore[arg-type]
            if hit_lim:
                return float(limit_p)  # type: ignore[arg-type]
            if hit_stop:
                return float(stop_p)  # type: ignore[arg-type]
            return None
        return None

    def _emit(
        self,
        kind: str,
        *,
        id: Any = None,
        direction: Any = None,
        qty: Any = None,
        order_type: Any = None,
        limit: Any = None,
        stop: Any = None,
        oca_name: Any = None,
        comment: Any = None,
    ) -> None:
        # Explicit kwargs (no **fields) + single dict alloc; shape matches prior API.
        self.events.append(
            {
                "kind": kind,
                "id": id,
                "direction": direction,
                "qty": qty,
                "order_type": order_type,
                "limit": limit,
                "stop": stop,
                "oca_name": oca_name,
                "comment": comment,
                "bar_index": self._bar_index,
                "bar_time": self._bar_time,
                "ohlc": [self._open, self._high, self._low, self._close],
            }
        )

    def _classify_order_type(self, limit: Any, stop: Any) -> str:
        lim, stp = _opt_float(limit), _opt_float(stop)
        if lim is not None and stp is not None:
            return "stop-limit"
        if stp is not None:
            return "stop"
        if lim is not None:
            return "limit"
        return "market"

    def risk_allow_entry_in(self, value: Any = "all", **_kwargs: Any) -> None:
        """``strategy.risk.allow_entry_in(value)`` — ``all`` | ``long`` | ``short``."""
        raw = value if value is not None else _kwargs.get("value", "all")
        s = str(raw).replace("strategy.", "").strip().lower()
        if s in {"long", "short", "all"}:
            self.allow_entry_in = s
        else:
            self.allow_entry_in = "all"

    def risk_max_position_size(self, percent: Any = None, **_kwargs: Any) -> None:
        """``strategy.risk.max_position_size(percent)`` — cap entry notional vs equity."""
        raw = percent if percent is not None else _kwargs.get("percent", _kwargs.get("value"))
        if raw is None or _is_na(raw):
            return
        try:
            p = float(raw)
        except (TypeError, ValueError):
            return
        if not math.isfinite(p) or p <= 0:
            return
        self.max_position_size_percent = p

    def risk_max_drawdown(self, value: Any = None, type: Any = "absolute", **_kwargs: Any) -> None:
        """``strategy.risk.max_drawdown(value, type)`` — absolute or % of peak.

        When *type* is percent (``percent`` / ``percent_of_equity`` / ``%``),
        store as percent-of-peak; otherwise absolute currency units.
        """
        raw = value if value is not None else _kwargs.get("value")
        if raw is None or _is_na(raw):
            return
        try:
            v = float(raw)
        except (TypeError, ValueError):
            return
        if not math.isfinite(v) or v < 0:
            return
        risk_type = type if type is not None else _kwargs.get("type", "absolute")
        rt = str(risk_type).replace("strategy.", "").strip().lower()
        if rt in {"percent", "percentage", "percent_of_equity", "%"}:
            self.max_drawdown_risk_percent = v
        else:
            self.max_drawdown_risk = v

    def risk_max_cons_loss_days(self, days: Any = None, **_kwargs: Any) -> None:
        """``strategy.risk.max_cons_loss_days(days)`` — halt after N loss days."""
        raw = days if days is not None else _kwargs.get("days", _kwargs.get("value"))
        if raw is None or _is_na(raw):
            return
        try:
            d = int(raw)
        except (TypeError, ValueError):
            return
        if d < 0:
            return
        self.max_cons_loss_days = d

    def risk_max_intraday_loss(self, percent: Any = None, **_kwargs: Any) -> None:
        """``strategy.risk.max_intraday_loss(percent)`` — halt on day loss % of capital.

        Interpret stores the limit; compile also enforces via day PnL tracking
        shared with :meth:`note_closed_trade_day`.
        """
        raw = percent if percent is not None else _kwargs.get("percent", _kwargs.get("value"))
        if raw is None or _is_na(raw):
            return
        try:
            p = float(raw)
        except (TypeError, ValueError):
            return
        if not math.isfinite(p) or p < 0:
            return
        self.max_intraday_loss = p

    def risk_max_intraday_filled_orders(self, max_orders: Any = None, **_kwargs: Any) -> None:
        """``strategy.risk.max_intraday_filled_orders(max)`` — cap fills per day.

        Counts successful entry and exit fills in the current bar-time day
        bucket. Further entries are blocked (``risk_blocked``) once the cap is
        hit; the counter resets when the day bucket rolls.
        """
        raw = max_orders if max_orders is not None else _kwargs.get(
            "max_orders", _kwargs.get("value", _kwargs.get("max"))
        )
        if raw is None or _is_na(raw):
            return
        try:
            n = int(raw)
        except (TypeError, ValueError):
            return
        if n < 0:
            return
        self.max_intraday_filled_orders = n

    def note_closed_trade_day(self, exit_time: int, profit: float) -> None:
        """Track consecutive calendar-day losses for risk.max_cons_loss_days.

        Day bucket = floor(exit_time / 86_400_000) when time looks like ms,
        else floor(exit_time / 86_400) for seconds, else bar-time as-is.
        Mirrors interpret ``StrategyState.note_closed_trade_day``.
        """
        day = self._day_bucket(int(exit_time))
        if self._last_trade_day is None or day != self._last_trade_day:
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
        # Intraday loss: day's realized loss as % of initial capital
        if (
            math.isfinite(self.max_intraday_loss)
            and self.max_intraday_loss < float("inf")
            and self.initial_capital > 0
            and self._day_pnl < 0
        ):
            loss_pct = 100.0 * (-self._day_pnl) / float(self.initial_capital)
            if loss_pct >= float(self.max_intraday_loss):
                self.entries_blocked = True

    def _risk_allows_entry(self, direction: str) -> bool:
        """Interpret-aligned risk gates before opening an entry.

        Checks: allow_entry_in, entries_blocked, max_drawdown (abs/%),
        max_cons_loss_days, max_intraday_loss, max_intraday_filled_orders.
        Sets ``entries_blocked`` when a permanent halt limit is hit (further
        entries comment ``risk_blocked``). Filled-order cap is day-scoped.
        """
        allow = (self.allow_entry_in or "all").lower().replace("strategy.", "")
        if allow in {"long"} and direction != "long":
            return False
        if allow in {"short"} and direction != "short":
            return False
        if self.entries_blocked:
            return False
        # Drawdown caps (series extremes already updated on bars / closes)
        if self.max_drawdown_risk is not None and self._max_drawdown >= float(self.max_drawdown_risk):
            self.entries_blocked = True
            return False
        if self.max_drawdown_risk_percent is not None and self._max_drawdown_percent >= float(
            self.max_drawdown_risk_percent
        ):
            self.entries_blocked = True
            return False
        if self.max_cons_loss_days is not None and self.consecutive_loss_days >= int(self.max_cons_loss_days):
            self.entries_blocked = True
            return False
        if (
            math.isfinite(self.max_intraday_loss)
            and self.max_intraday_loss < float("inf")
            and self.initial_capital > 0
            and self._day_pnl < 0
        ):
            loss_pct = 100.0 * (-self._day_pnl) / float(self.initial_capital)
            if loss_pct >= float(self.max_intraday_loss):
                self.entries_blocked = True
                return False
        # Day-scoped fill cap (resets when bar-time day bucket rolls)
        if self.max_intraday_filled_orders is not None:
            self._roll_fill_day()
            if self._day_filled_orders >= int(self.max_intraday_filled_orders):
                return False
        return True

    def _cap_qty_by_max_position(self, qty: float, fill_price: float) -> float:
        """Apply ``max_position_size_percent`` of equity at *fill_price*."""
        pct = self.max_position_size_percent
        if pct is None or pct <= 0 or fill_price <= 0 or fill_price != fill_price:
            return qty
        equity = float(self.equity)
        max_qty = (equity * (pct / 100.0)) / float(fill_price)
        if max_qty < 0 or not math.isfinite(max_qty):
            return 0.0
        return min(float(qty), float(max_qty))

    def entry(
        self,
        id: str = "entry",
        direction: str = "long",
        qty: float | None = None,
        limit: float | None = None,
        stop: float | None = None,
        comment: str | None = None,
        price: float | None = None,
        **_kwargs: Any,
    ) -> None:
        """Pine ``strategy.entry`` — market fill now or pending limit/stop.

        ``qty=None`` (compiler omits qty) resolves via ``default_qty_type`` /
        ``default_qty_value`` — same as interpret missing-qty path.
        """
        d = _norm_dir(direction)
        if d is None:
            self._emit(
                "order",
                id=str(id),
                direction=None,
                qty=0.0,
                order_type="market",
                comment="invalid_direction",
            )
            return
        if not self._risk_allows_entry(d):
            self._emit(
                "order",
                id=str(id),
                direction=d,
                qty=0.0,
                order_type="market",
                comment="risk_blocked",
            )
            return
        status, parsed_q = _parse_qty(qty)
        if status == "invalid":
            self._emit(
                "order",
                id=str(id),
                direction=d,
                qty=0.0,
                order_type="market",
                comment="invalid_qty",
            )
            return
        # Resolve mark early for default qty (percent_of_equity needs price).
        if price is None or _is_na(price):
            px_hint = self._mark
        else:
            px_hint = float(price)
        q = self._resolve_default_qty(px_hint) if status == "missing" else abs(parsed_q)
        q = self._cap_qty_by_max_position(q, px_hint if px_hint and px_hint > 0 else 1.0)
        if q <= 0:
            self._emit(
                "order",
                id=str(id),
                direction=d,
                qty=0.0,
                order_type="market",
                comment="invalid_qty",
            )
            return
        # Market fast path: no limit/stop → skip classify + opt_float.
        if limit is None and stop is None:
            px = px_hint
            if self.slippage_ticks > 0:
                px = self._slip(px, d)
            self._open_or_add(
                d, q, px, str(id), comment, respect_pyramiding=True
            )
            return

        ot = self._classify_order_type(limit, stop)
        if ot != "market":
            # Pending stop/limit entry
            self.pending_orders[str(id)] = PendingOrder(
                order_id=str(id),
                order_type=ot,
                direction=d,
                quantity=q,
                limit_price=_opt_float(limit),
                stop_price=_opt_float(stop),
                comment=comment,
                is_entry=True,
            )
            self._emit(
                "order",
                id=str(id),
                direction=d,
                qty=q,
                order_type=ot if ot == "limit" else "stop",
                limit=_opt_float(limit),
                stop=_opt_float(stop),
                comment=comment,
            )
            return
        # Market entry — immediate (limit/stop were NA-ish)
        px = px_hint
        if self.slippage_ticks > 0:
            px = self._slip(px, d)
        else:
            px = float(px)
        self._open_or_add(
            d, q, px, str(id), comment, respect_pyramiding=True
        )

    def _resolve_trail_params(
        self,
        trail_price: float | None,
        trail_points: float | None,
        trail_offset: float | None,
    ) -> tuple[float | None, float | None]:
        """Parse trail_* kwargs → (activation_price, offset_price units).

        Distances are in **ticks** (× :attr:`mintick`) per Pine. Prefer
        ``trail_points`` when it is a positive tick distance (TV: points wins
        over offset when both are set). ``na`` / ``≤0`` is ignored — not
        coerced to 0 — so a valid ``trail_offset`` can still apply.
        Returns ``(None, None)`` when no positive trail distance is configured.
        """
        act = _opt_float(trail_price)
        points = _opt_float(trail_points)
        offset = _opt_float(trail_offset)
        if points is not None and points > 0:
            ticks = points
        elif offset is not None and offset > 0:
            ticks = offset
        else:
            return (None, None)
        offset_price = float(ticks) * float(self.mintick)
        if offset_price <= 0:
            return (None, None)
        return (act, offset_price)

    def _exit_entry_avg(self, from_entry: str | None) -> float | None:
        """Average entry price for the exit target (``from_entry`` legs or whole lot)."""
        if from_entry:
            legs = [leg for leg in self.open_legs if leg.entry_id == from_entry]
            total = sum(float(leg.size) for leg in legs)
            if total > 0:
                return sum(float(leg.entry_price) * float(leg.size) for leg in legs) / total
            if not self.open_legs and self.position_size != 0.0:
                avg = float(self.position_avg_price)
                return avg if avg == avg and math.isfinite(avg) else None
            return None
        if self.position_size == 0.0:
            return None
        avg = float(self.position_avg_price)
        return avg if avg == avg and math.isfinite(avg) else None

    def _tick_offset_price(
        self,
        ticks: float | None,
        entry_avg: float | None,
        *,
        is_long: bool,
        is_profit: bool,
    ) -> float | None:
        """Map ``profit``/``loss`` ticks to an absolute price from *entry_avg*."""
        if ticks is None or entry_avg is None:
            return None
        t = float(ticks)
        avg = float(entry_avg)
        if t <= 0 or not math.isfinite(t) or not math.isfinite(avg):
            return None
        offset = t * float(self.mintick)
        if offset <= 0 or not math.isfinite(offset):
            return None
        if is_long:
            return avg + offset if is_profit else avg - offset
        return avg - offset if is_profit else avg + offset

    def _merge_exit_bracket_prices(
        self,
        *,
        limit_p: float | None,
        stop_p: float | None,
        profit_ticks: float | None,
        loss_ticks: float | None,
        is_long: bool,
        from_entry: str | None,
    ) -> tuple[float | None, float | None]:
        """``limit``/``stop`` stay absolute; ``profit``/``loss`` fill missing legs.

        Tick offsets are ``ticks * mintick`` from the exit's entry average.
        When both a tick param and its absolute twin are set, the absolute
        price wins. First-touch of the resulting limit+stop pair is unchanged.
        """
        entry_avg = self._exit_entry_avg(from_entry)
        if limit_p is None:
            limit_p = self._tick_offset_price(
                profit_ticks, entry_avg, is_long=is_long, is_profit=True
            )
        if stop_p is None:
            stop_p = self._tick_offset_price(
                loss_ticks, entry_avg, is_long=is_long, is_profit=False
            )
        return limit_p, stop_p

    def close(
        self,
        id: str | None = None,
        qty: float | None = None,
        comment: str | None = None,
        price: float | None = None,
        limit: float | None = None,
        stop: float | None = None,
        profit: float | None = None,
        loss: float | None = None,
        qty_percent: float | None = None,
        trail_price: float | None = None,
        trail_points: float | None = None,
        trail_offset: float | None = None,
        **_kwargs: Any,
    ) -> None:
        """Close (part of) the open position at mark or *price*; update PnL.

        When ``stop`` / ``limit`` (or ``loss`` / ``profit``) are provided the
        compiler has mapped ``strategy.exit`` → ``close``. Match the interpret
        oracle: pick an exit fill price from those legs and emit ``kind=exit``.

        ``profit`` / ``loss`` are ticks from entry average
        (``ticks * mintick``); ``limit`` / ``stop`` stay absolute prices.
        ``na`` / None / ``<= 0`` profit or loss ignore that bracket leg.

        ``qty_percent`` (when set and not na) sizes as ``target * pct/100``
        capped to the open target (whole lot or ``from_entry`` size); wins over
        absolute ``qty``.

        Trail (``trail_offset`` / ``trail_points`` ticks × mintick, optional
        ``trail_price`` activation) places a pending stop that ratchets with
        bar high/low in :meth:`process_pending_orders` (interpret-aligned
        minimal trail).

        ``from_entry`` (explicit kwarg from compiler, or for stop/limit exit
        brackets ``id`` when used as the entry filter) reduces only matching
        open legs. Unknown ``from_entry`` is a soft no-op after the
        placement/close event.
        """
        # Compiler maps strategy.exit → close(..., from_entry=..., stop/limit/trail).
        # Prefer explicit from_entry; fall back to id only for exit brackets so
        # direct broker tests that pass id= keep working.
        limit_p = _opt_float(limit)
        stop_p = _opt_float(stop)
        profit_ticks = _opt_float(profit)
        loss_ticks = _opt_float(loss)
        trail_activation, trail_offset_px = self._resolve_trail_params(
            trail_price if trail_price is not None else _kwargs.get("trail_price"),
            trail_points if trail_points is not None else _kwargs.get("trail_points"),
            trail_offset if trail_offset is not None else _kwargs.get("trail_offset"),
        )
        has_trail = trail_offset_px is not None
        has_tick_bracket = (profit_ticks is not None and profit_ticks > 0) or (
            loss_ticks is not None and loss_ticks > 0
        )
        is_exit = limit_p is not None or stop_p is not None or has_trail or has_tick_bracket
        event_kind = "exit" if is_exit else "close"
        event_stop = stop_p if stop_p is not None else (trail_activation if has_trail else None)
        raw_fe = _kwargs.get("from_entry")
        from_entry: str | None = None
        if raw_fe is not None and str(raw_fe) != "":
            from_entry = str(raw_fe)
        elif is_exit and id is not None and str(id) != "":
            from_entry = str(id)

        if self.position_size == 0:
            self._emit(
                event_kind,
                id=id,
                qty=0.0,
                comment=comment,
                limit=limit_p,
                stop=event_stop,
            )
            return

        target_size = self._entry_open_size(from_entry)
        # Soft no-op when from_entry matches no open leg.
        if from_entry is not None and target_size <= 0:
            self._emit(
                event_kind,
                id=id,
                qty=0.0,
                comment=comment,
                limit=limit_p,
                stop=event_stop,
            )
            return

        d = "long" if self.position_size > 0 else "short"
        if has_tick_bracket:
            limit_p, stop_p = self._merge_exit_bracket_prices(
                limit_p=limit_p,
                stop_p=stop_p,
                profit_ticks=profit_ticks,
                loss_ticks=loss_ticks,
                is_long=(d == "long"),
                from_entry=from_entry,
            )
            event_stop = stop_p if stop_p is not None else (trail_activation if has_trail else None)
            is_exit = limit_p is not None or stop_p is not None or has_trail
            event_kind = "exit" if is_exit else "close"
        # qty_percent wins over qty when both provided (interpret parity).
        pct = _opt_float(qty_percent if qty_percent is not None else _kwargs.get("qty_percent"))
        if pct is not None:
            if pct <= 0:
                close_qty = 0.0
            else:
                close_qty = float(target_size) * (min(float(pct), 100.0) / 100.0)
        elif qty is None or _is_na(qty):
            close_qty = float(target_size)
        else:
            status, parsed = _parse_qty(qty)
            if status == "invalid":
                self._emit(
                    "order",
                    id=id,
                    direction=None,
                    qty=0.0,
                    order_type="market",
                    comment="invalid_qty",
                )
                return
            close_qty = (
                float(target_size) if status == "missing" else min(abs(float(parsed)), float(target_size))
            )
        if close_qty <= 0 or not math.isfinite(close_qty):
            return

        # Visitor maps strategy.exit id → comment=; use that as the order name
        # when id is omitted so pending keys / placement events match interpret.
        exit_oid: str | None = None
        if is_exit:
            if id is not None and str(id) != "":
                exit_oid = str(id)
            elif comment is not None and str(comment) != "":
                exit_oid = str(comment)

        if is_exit:
            # Always emit exit event (placement / intent) for host parity.
            self._emit(
                "exit",
                id=exit_oid if exit_oid is not None else id,
                qty=close_qty,
                comment=comment,
                direction=None,
                limit=limit_p,
                stop=event_stop,
            )
            pending_base = exit_oid if exit_oid is not None else "exit"
            # Trail always goes through pending + process (ratchet needs bar path).
            # Fixed stop/limit: fill same-bar when OHLC already touches, else pending.
            if has_trail:
                self._place_exit_pending(
                    base=pending_base,
                    exit_dir="short" if d == "long" else "long",
                    close_qty=close_qty,
                    limit_p=limit_p,
                    stop_p=stop_p,
                    comment=comment,
                    from_entry=from_entry,
                    trail_offset_px=trail_offset_px,
                    trail_activation=trail_activation,
                )
                self.process_pending_orders()
                return
            px = self._exit_fill_price(
                limit=limit_p,
                stop=stop_p,
                is_long=(d == "long"),
                is_short=(d == "short"),
            )
            if px is None:
                self._place_exit_pending(
                    base=pending_base,
                    exit_dir="short" if d == "long" else "long",
                    close_qty=close_qty,
                    limit_p=limit_p,
                    stop_p=stop_p,
                    comment=comment,
                    from_entry=from_entry,
                    trail_offset_px=None,
                    trail_activation=None,
                )
                return
            # Same-bar fill at touched level — fall through to realize PnL
        elif price is None or _is_na(price):
            # Exit slip: long close sells (worse), short cover buys (worse).
            px = self._slip(self._mark, "short" if d == "long" else "long")
        else:
            px = float(price)

        self._realize_close(
            close_qty,
            float(px),
            from_entry=from_entry,
            exit_id=str(id) if id is not None else "",
            exit_comment=str(comment) if comment else "",
        )
        # Market close keeps direction; stop/limit exit already emitted above.
        if not is_exit:
            self._emit(
                event_kind,
                id=id,
                qty=close_qty,
                comment=comment,
                direction=d,
                limit=limit_p,
                stop=stop_p,
            )

    def _place_exit_pending(
        self,
        *,
        base: str,
        exit_dir: str,
        close_qty: float,
        limit_p: float | None,
        stop_p: float | None,
        comment: str | None,
        from_entry: str | None,
        trail_offset_px: float | None,
        trail_activation: float | None,
    ) -> None:
        """Install pending close leg(s) for strategy.exit brackets / trail."""
        for oid in list(self.pending_orders.keys()):
            if oid == base or oid.startswith(base + ":"):
                del self.pending_orders[oid]
        cmt = str(comment) if comment else ""
        has_trail = trail_offset_px is not None and trail_offset_px > 0
        trail_kw: dict[str, Any] = {}
        if has_trail:
            trail_kw = {
                "trail_offset": float(trail_offset_px),
                "trail_activation": trail_activation,
                "trail_active": trail_activation is None,
            }

        if limit_p is not None and (stop_p is not None or has_trail):
            self.pending_orders[f"{base}:limit"] = PendingOrder(
                order_id=f"{base}:limit",
                order_type="limit",
                direction=exit_dir,
                quantity=close_qty,
                limit_price=limit_p,
                stop_price=None,
                comment=cmt,
                oca_name=base,
                oca_type="cancel",
                is_entry=False,
                from_entry=from_entry,
            )
            # limit+stop → :stop; limit+trail-only → :trail (interpret parity)
            stop_id = f"{base}:stop" if stop_p is not None else f"{base}:trail"
            self.pending_orders[stop_id] = PendingOrder(
                order_id=stop_id,
                order_type="stop",
                direction=exit_dir,
                quantity=close_qty,
                limit_price=None,
                stop_price=stop_p,
                comment=cmt,
                oca_name=base,
                oca_type="cancel",
                is_entry=False,
                from_entry=from_entry,
                **trail_kw,
            )
        elif limit_p is not None:
            self.pending_orders[base] = PendingOrder(
                order_id=base,
                order_type="limit",
                direction=exit_dir,
                quantity=close_qty,
                limit_price=limit_p,
                stop_price=None,
                comment=cmt,
                is_entry=False,
                from_entry=from_entry,
            )
        elif has_trail:
            self.pending_orders[base] = PendingOrder(
                order_id=base,
                order_type="stop",
                direction=exit_dir,
                quantity=close_qty,
                limit_price=None,
                stop_price=stop_p,
                comment=cmt,
                is_entry=False,
                from_entry=from_entry,
                **trail_kw,
            )
        else:
            self.pending_orders[base] = PendingOrder(
                order_id=base,
                order_type="stop",
                direction=exit_dir,
                quantity=close_qty,
                limit_price=None,
                stop_price=stop_p,
                comment=cmt,
                is_entry=False,
                from_entry=from_entry,
            )

    def _realize_close(
        self,
        close_qty: float,
        px: float,
        *,
        from_entry: str | None = None,
        exit_id: str = "",
        exit_comment: str = "",
    ) -> None:
        """Reduce open legs (optional ``from_entry`` filter) and realize PnL."""
        self._ensure_legs()
        fe = str(from_entry) if from_entry else None
        if fe is not None and not any(leg.entry_id == fe for leg in self.open_legs):
            return

        model = self.avg_price_model or "stock"
        use_sticky = model in {"futures", "inverse"}
        sticky_avg = float(self.position_avg_price) if self.position_avg_price == self.position_avg_price else 0.0

        eligible = (
            [leg for leg in self.open_legs if leg.entry_id == fe] if fe is not None else list(self.open_legs)
        )
        total_close = min(float(close_qty), float(sum(leg.size for leg in eligible)))
        if total_close <= 0:
            return
        exit_comm_total = self._commission(total_close, px)
        remaining = total_close
        trade_profit = 0.0
        trade_comm = 0.0
        trade_entry_notional = 0.0  # size-weighted entry for record
        trade_entry_bar = self._bar_index
        trade_entry_time = self._bar_time
        trade_entry_id = ""
        trade_entry_comment = ""
        trade_max_dd = 0.0
        trade_max_ru = 0.0
        trade_dir = "long"
        new_legs: list[OpenLeg] = []
        closed_any = False

        for leg in self.open_legs:
            if fe is not None and leg.entry_id != fe:
                new_legs.append(leg)
                continue
            if remaining <= 1e-12:
                new_legs.append(leg)
                continue
            cq = min(float(leg.size), remaining)
            entry_comm = float(leg.commission) * (cq / leg.size) if leg.size else 0.0
            exit_comm = exit_comm_total * (cq / total_close) if total_close > 0 else 0.0
            basis = sticky_avg if use_sticky else float(leg.entry_price)
            if leg.direction == "long":
                profit = (px - basis) * cq - entry_comm - exit_comm
            else:
                profit = (basis - px) * cq - entry_comm - exit_comm
            trade_profit += profit
            trade_comm += entry_comm + exit_comm
            trade_entry_notional += basis * cq
            # Aggregate open-leg extremes (MAE/MFE) across reduced legs
            trade_max_dd = max(trade_max_dd, float(leg.max_drawdown))
            trade_max_ru = max(trade_max_ru, float(leg.max_runup))
            if not closed_any:
                trade_entry_bar = int(leg.entry_bar)
                trade_entry_time = int(leg.entry_time)
                trade_entry_id = str(leg.entry_id or "")
                trade_entry_comment = str(leg.entry_comment or "")
                trade_dir = leg.direction
            closed_any = True
            leftover = float(leg.size) - cq
            if leftover > 1e-12:
                new_legs.append(
                    self._new_leg(
                        entry_id=leg.entry_id,
                        size=leftover,
                        entry_price=leg.entry_price,
                        direction=leg.direction,
                        commission=float(leg.commission) - entry_comm,
                        entry_bar=leg.entry_bar,
                        entry_time=leg.entry_time,
                        entry_comment=leg.entry_comment,
                        max_drawdown=float(leg.max_drawdown),
                        max_runup=float(leg.max_runup),
                    )
                )
            remaining -= cq

        if not closed_any:
            return

        self.open_legs = new_legs
        self.netprofit += trade_profit
        self.closed_trades += 1
        entry_px = (trade_entry_notional / total_close) if total_close > 0 else float(px)
        exit_time = int(self._bar_time)
        self.closed_trade_records.append(
            ClosedTradeRecord(
                entry_id=trade_entry_id if fe is None else str(fe),
                size=float(total_close),
                entry_price=float(entry_px),
                exit_price=float(px),
                profit=float(trade_profit),
                commission=float(trade_comm),
                direction=trade_dir,
                entry_bar=int(trade_entry_bar),
                entry_time=int(trade_entry_time),
                exit_bar=int(self._bar_index),
                exit_time=exit_time,
                exit_id=str(exit_id or ""),
                entry_comment=trade_entry_comment,
                exit_comment=str(exit_comment or ""),
                max_drawdown=float(trade_max_dd),
                max_runup=float(trade_max_ru),
            )
        )
        self._note_filled_order()
        if trade_profit > 0:
            self.wintrades += 1
            self.grossprofit += trade_profit
        elif trade_profit < 0:
            self.losstrades += 1
            self.grossloss += abs(trade_profit)
        else:
            self.eventrades += 1
        # Risk day cascade (cons loss days / max_intraday_loss)
        self.note_closed_trade_day(exit_time, float(trade_profit))

        if not self.open_legs or sum(leg.size for leg in self.open_legs) <= 1e-12:
            self.open_legs = []
            self.position_size = 0.0
            self.position_avg_price = float("nan")
            self.position_entry_name = ""
            self.position_commission = 0.0
            self.open_entry_count = 0
        else:
            total = float(sum(leg.size for leg in self.open_legs))
            d0 = self.open_legs[0].direction
            self.position_size = total if d0 == "long" else -total
            if use_sticky:
                self.position_avg_price = sticky_avg
            else:
                self.position_avg_price = sum(leg.entry_price * leg.size for leg in self.open_legs) / total
            self.position_entry_name = str(self.open_legs[0].entry_id)
            self.position_commission = float(sum(leg.commission for leg in self.open_legs))
            self.open_entry_count = len(self.open_legs)
        self._update_equity_extremes()

    def close_all(self, comment: str | None = None, price: float | None = None, **_kwargs: Any) -> None:
        """Flatten any open position then emit ``close_all``."""
        if self.position_size != 0:
            self.close(id=None, qty=abs(self.position_size), comment=comment, price=price)
        self._emit("close_all", comment=comment)

    def order(
        self,
        id: str = "order",
        direction: str = "long",
        qty: float | None = None,
        limit: float | None = None,
        stop: float | None = None,
        oca_name: str | None = None,
        oca_type: str | None = None,
        comment: str | None = None,
        price: float | None = None,
        max_fill_per_bar: float = 0.0,
        **_kwargs: Any,
    ) -> None:
        """Place pending order (market fills on next process_pending_orders)."""
        d = _norm_dir(direction)
        if d is None:
            self._emit(
                "order",
                id=str(id),
                direction=None,
                qty=0.0,
                order_type="market",
                comment="invalid_direction",
            )
            return
        status, parsed_q = _parse_qty(qty)
        if status == "invalid" or (status == "ok" and parsed_q <= 0):
            self._emit(
                "order",
                id=str(id),
                direction=d,
                qty=0.0,
                order_type="market",
                comment="invalid_qty",
            )
            return
        if price is None or _is_na(price):
            px_hint = self._mark
        else:
            px_hint = float(price)
        q = self._resolve_default_qty(px_hint) if status == "missing" else abs(parsed_q)
        ot = self._classify_order_type(limit, stop)
        otype = str(oca_type or "none").lower()
        if otype in {"strategy.oca.reduce", "oca.reduce"}:
            otype = "reduce"
        elif otype in {"strategy.oca.cancel", "oca.cancel"}:
            otype = "cancel"
        elif otype in {"strategy.oca.none", "oca.none"}:
            otype = "none"
        # Closing order if opposite to current position size sign and qty matches cover intent
        is_entry = True
        if (d == "short" and self.position_size > 0) or (d == "long" and self.position_size < 0):
            is_entry = False
        self.pending_orders[str(id)] = PendingOrder(
            order_id=str(id),
            order_type=ot,
            direction=d,
            quantity=q,
            limit_price=_opt_float(limit),
            stop_price=_opt_float(stop),
            comment=comment,
            oca_name=None if oca_name is None else str(oca_name),
            oca_type=otype,
            max_fill_per_bar=float(max_fill_per_bar or 0.0),
            is_entry=is_entry,
        )
        self._emit(
            "order",
            id=str(id),
            direction=d,
            qty=q,
            order_type="market" if ot == "market" else "limit" if ot == "limit" else "stop",
            limit=_opt_float(limit),
            stop=_opt_float(stop),
            oca_name=None if oca_name is None else str(oca_name),
            comment=comment,
        )
        # Optional: unused price for market immediate path reserved
        _ = price

    def cancel(self, id: str | None = None, **_kwargs: Any) -> None:
        """Cancel a pending order by id (no-op if missing); always emits event."""
        if id is not None and str(id) in self.pending_orders:
            del self.pending_orders[str(id)]
        self._emit("cancel", id=id)

    def cancel_all(self, **_kwargs: Any) -> None:
        """Clear the entire pending book."""
        self.pending_orders.clear()
        self._emit("cancel_all")

    def _pct_of_initial(self, amount: float) -> float:
        """Percent of initial capital (Pine ``*_percent`` series)."""
        ic = float(self.initial_capital)
        if ic == 0:
            return 0.0
        return 100.0 * float(amount) / ic

    @property
    def equity(self) -> float:
        """Cash + closed netprofit + open MTM at current mark."""
        return self.initial_capital + self.netprofit + self.openprofit

    @property
    def openprofit(self) -> float:
        """Unrealized PnL of the open position at current mark (0 if flat).

        Subtracts remaining entry commission so equity dips on fill the same
        way as the interpret broker.
        """
        mark = self._mark
        ps = self.position_size
        mtm = 0.0
        if ps > 0 and mark == mark:
            mtm = (mark - self.position_avg_price) * ps
        elif ps < 0 and mark == mark:
            mtm = (self.position_avg_price - mark) * (-ps)
        else:
            return 0.0
        return mtm - float(self.position_commission or 0.0)

    @property
    def openprofit_percent(self) -> float:
        """Open profit as percent of initial capital."""
        return self._pct_of_initial(self.openprofit)

    @property
    def netprofit_percent(self) -> float:
        """Realized net profit as percent of initial capital."""
        return self._pct_of_initial(self.netprofit)

    @property
    def grossprofit_percent(self) -> float:
        """Gross profit as percent of initial capital."""
        return self._pct_of_initial(self.grossprofit)

    @property
    def grossloss_percent(self) -> float:
        """Gross loss as percent of initial capital."""
        return self._pct_of_initial(self.grossloss)

    @property
    def capital_held(self) -> float:
        """Margin locked in open positions (notional / leverage). Pine ``opentrades.capital_held``."""
        ps = self.position_size
        if ps == 0.0 or self.position_avg_price != self.position_avg_price:
            return 0.0
        notional = abs(float(self.position_avg_price) * float(ps))
        lev = float(self.leverage) if self.leverage and self.leverage > 0 else 1.0
        return notional / lev

    @property
    def cash(self) -> float:
        """Approximate free cash: equity minus margin locked (notional / leverage)."""
        return float(self.equity) - float(self.capital_held)

    @property
    def margin_liquidation_price(self) -> float:
        """Simple isolated liq estimate: entry ± entry/leverage; nan if flat or lev≤1."""
        ps = self.position_size
        avg = self.position_avg_price
        if ps == 0.0 or avg != avg or avg <= 0:
            return float("nan")
        lev = float(self.leverage) if self.leverage and self.leverage > 0 else 1.0
        if lev <= 1.0:
            return float("nan")
        if ps > 0:
            return float(avg) * (1.0 - 1.0 / lev)
        return float(avg) * (1.0 + 1.0 / lev)

    @property
    def avg_trade(self) -> float:
        """Mean closed-trade PnL (netprofit / closed_trades); 0 if none closed."""
        n = int(self.closed_trades)
        return float(self.netprofit) / n if n else 0.0

    @property
    def avg_trade_percent(self) -> float:
        """:attr:`avg_trade` as percent of initial capital."""
        return self._pct_of_initial(self.avg_trade)

    @property
    def avg_winning_trade(self) -> float:
        """Mean winning-trade PnL (grossprofit / wintrades); 0 if none."""
        n = int(self.wintrades)
        return float(self.grossprofit) / n if n else 0.0

    @property
    def avg_winning_trade_percent(self) -> float:
        """:attr:`avg_winning_trade` as percent of initial capital."""
        return self._pct_of_initial(self.avg_winning_trade)

    @property
    def avg_losing_trade(self) -> float:
        """Mean losing-trade loss magnitude (grossloss / losstrades); 0 if none."""
        n = int(self.losstrades)
        return float(self.grossloss) / n if n else 0.0

    @property
    def avg_losing_trade_percent(self) -> float:
        """:attr:`avg_losing_trade` as percent of initial capital."""
        return self._pct_of_initial(self.avg_losing_trade)

    def _update_equity_extremes(self) -> None:
        """Track peak/trough equity for max_drawdown / max_runup series."""
        eq = self.equity
        if eq != eq:  # NaN
            return
        if eq > self._equity_peak:
            self._equity_peak = eq
        if eq < self._equity_trough:
            self._equity_trough = eq
        dd = self._equity_peak - eq
        if dd > self._max_drawdown:
            self._max_drawdown = dd
            if self._equity_peak > 0:
                self._max_drawdown_percent = 100.0 * dd / self._equity_peak
        ru = eq - self._equity_trough
        if ru > self._max_runup:
            self._max_runup = ru
            if self._equity_trough != 0:
                self._max_runup_percent = 100.0 * ru / abs(self._equity_trough)

    def _update_leg_extremes(self) -> None:
        """Approximate per-open-leg MAE/MFE from bar high/low (currency units).

        Long: favorable at high, adverse at low; short: inverted. Values are
        max adverse excursion (``max_drawdown``) and max favorable
        (``max_runup``) observed while the leg is open. Commission is ignored
        for extremes (cheap OHLC path; not tick-accurate).
        """
        if not self.open_legs:
            return
        hi = float(self._high)
        lo = float(self._low)
        if hi != hi or lo != lo:
            return
        for leg in self.open_legs:
            ep = float(leg.entry_price)
            sz = float(leg.size)
            if sz <= 0 or ep != ep:
                continue
            if leg.direction == "long":
                fav = (hi - ep) * sz
                adv = (ep - lo) * sz
            else:
                fav = (ep - lo) * sz
                adv = (hi - ep) * sz
            if fav > leg.max_runup:
                leg.max_runup = float(fav)
            if adv > leg.max_drawdown:
                leg.max_drawdown = float(adv)

    @property
    def max_drawdown(self) -> float:
        """Peak-to-trough equity drawdown (absolute currency units)."""
        return float(self._max_drawdown)

    @property
    def max_runup(self) -> float:
        """Trough-to-peak equity run-up (absolute currency units)."""
        return float(self._max_runup)

    @property
    def max_drawdown_percent(self) -> float:
        """Max drawdown as percent of equity peak when recorded."""
        return float(self._max_drawdown_percent)

    @property
    def max_runup_percent(self) -> float:
        """Max run-up as percent of equity trough when recorded."""
        return float(self._max_runup_percent)

    # --- strategy.opentrades.* / strategy.closedtrades.* query surface -------

    def _open_leg_at(self, trade_index: Any) -> OpenLeg | None:
        """Return open leg at *trade_index*, or synthetic single-lot leg."""
        try:
            i = int(trade_index) if trade_index is not None else 0
        except (TypeError, ValueError):
            i = 0
        if i < 0:
            return None
        if self.open_legs:
            if i < len(self.open_legs):
                return self.open_legs[i]
            return None
        if abs(self.position_size) > 0 and i == 0:
            d = "long" if self.position_size > 0 else "short"
            return self._new_leg(
                entry_id=str(self.position_entry_name or ""),
                size=abs(float(self.position_size)),
                entry_price=float(self.position_avg_price)
                if self.position_avg_price == self.position_avg_price
                else 0.0,
                direction=d,
                commission=float(self.position_commission or 0.0),
            )
        return None

    def _closed_at(self, trade_index: Any) -> ClosedTradeRecord | None:
        try:
            i = int(trade_index) if trade_index is not None else 0
        except (TypeError, ValueError):
            i = 0
        if i < 0 or i >= len(self.closed_trade_records):
            return None
        return self.closed_trade_records[i]

    def opentrades_size(self, trade_index: Any = 0, **_kwargs: Any) -> float:
        leg = self._open_leg_at(trade_index)
        return float(leg.size) if leg is not None else 0.0

    def opentrades_entry_price(self, trade_index: Any = 0, **_kwargs: Any) -> float:
        leg = self._open_leg_at(trade_index)
        if leg is None:
            return float("nan")
        return float(leg.entry_price)

    def opentrades_entry_id(self, trade_index: Any = 0, **_kwargs: Any) -> str:
        leg = self._open_leg_at(trade_index)
        return str(leg.entry_id) if leg is not None else ""

    def opentrades_entry_bar_index(self, trade_index: Any = 0, **_kwargs: Any) -> int:
        leg = self._open_leg_at(trade_index)
        return int(leg.entry_bar) if leg is not None else 0

    def opentrades_entry_time(self, trade_index: Any = 0, **_kwargs: Any) -> int:
        leg = self._open_leg_at(trade_index)
        return int(leg.entry_time) if leg is not None else 0

    def opentrades_commission(self, trade_index: Any = 0, **_kwargs: Any) -> float:
        leg = self._open_leg_at(trade_index)
        return float(leg.commission) if leg is not None else 0.0

    def opentrades_profit(self, trade_index: Any = 0, **_kwargs: Any) -> float:
        """Mark-to-market open-leg PnL at current bar close (minus entry commission)."""
        leg = self._open_leg_at(trade_index)
        if leg is None:
            return 0.0
        mark = float(self._mark)
        if mark != mark:
            return 0.0
        if leg.direction == "long":
            return (mark - float(leg.entry_price)) * float(leg.size) - float(leg.commission)
        return (float(leg.entry_price) - mark) * float(leg.size) - float(leg.commission)

    def opentrades_entry_comment(self, trade_index: Any = 0, **_kwargs: Any) -> str:
        leg = self._open_leg_at(trade_index)
        return str(leg.entry_comment) if leg is not None else ""

    def opentrades_max_drawdown(self, trade_index: Any = 0, **_kwargs: Any) -> float:
        leg = self._open_leg_at(trade_index)
        return float(leg.max_drawdown) if leg is not None else 0.0

    def opentrades_max_runup(self, trade_index: Any = 0, **_kwargs: Any) -> float:
        leg = self._open_leg_at(trade_index)
        return float(leg.max_runup) if leg is not None else 0.0

    def closedtrades_profit(self, trade_index: Any = 0, **_kwargs: Any) -> float:
        rec = self._closed_at(trade_index)
        return float(rec.profit) if rec is not None else 0.0

    def closedtrades_size(self, trade_index: Any = 0, **_kwargs: Any) -> float:
        rec = self._closed_at(trade_index)
        return float(rec.size) if rec is not None else 0.0

    def closedtrades_entry_price(self, trade_index: Any = 0, **_kwargs: Any) -> float:
        rec = self._closed_at(trade_index)
        return float(rec.entry_price) if rec is not None else 0.0

    def closedtrades_exit_price(self, trade_index: Any = 0, **_kwargs: Any) -> float:
        rec = self._closed_at(trade_index)
        return float(rec.exit_price) if rec is not None else 0.0

    def closedtrades_commission(self, trade_index: Any = 0, **_kwargs: Any) -> float:
        rec = self._closed_at(trade_index)
        return float(rec.commission) if rec is not None else 0.0

    def closedtrades_entry_id(self, trade_index: Any = 0, **_kwargs: Any) -> str:
        rec = self._closed_at(trade_index)
        return str(rec.entry_id) if rec is not None else ""

    def closedtrades_exit_id(self, trade_index: Any = 0, **_kwargs: Any) -> str:
        rec = self._closed_at(trade_index)
        return str(rec.exit_id) if rec is not None else ""

    def closedtrades_entry_bar_index(self, trade_index: Any = 0, **_kwargs: Any) -> int:
        rec = self._closed_at(trade_index)
        return int(rec.entry_bar) if rec is not None else 0

    def closedtrades_exit_bar_index(self, trade_index: Any = 0, **_kwargs: Any) -> int:
        rec = self._closed_at(trade_index)
        return int(rec.exit_bar) if rec is not None else 0

    def closedtrades_entry_time(self, trade_index: Any = 0, **_kwargs: Any) -> int:
        rec = self._closed_at(trade_index)
        return int(rec.entry_time) if rec is not None else 0

    def closedtrades_exit_time(self, trade_index: Any = 0, **_kwargs: Any) -> int:
        rec = self._closed_at(trade_index)
        return int(rec.exit_time) if rec is not None else 0

    def closedtrades_entry_comment(self, trade_index: Any = 0, **_kwargs: Any) -> str:
        rec = self._closed_at(trade_index)
        return str(rec.entry_comment) if rec is not None else ""

    def closedtrades_exit_comment(self, trade_index: Any = 0, **_kwargs: Any) -> str:
        rec = self._closed_at(trade_index)
        return str(rec.exit_comment) if rec is not None else ""

    def closedtrades_max_drawdown(self, trade_index: Any = 0, **_kwargs: Any) -> float:
        rec = self._closed_at(trade_index)
        return float(rec.max_drawdown) if rec is not None else 0.0

    def closedtrades_max_runup(self, trade_index: Any = 0, **_kwargs: Any) -> float:
        rec = self._closed_at(trade_index)
        return float(rec.max_runup) if rec is not None else 0.0

    def to_events(self) -> list[dict[str, Any]]:
        """Return the live event list for host packing as ``__events``.

        Broker is single-use per compiled run; no copy (callers must not mutate
        after the run returns if they retain the handle).
        """
        return self.events
