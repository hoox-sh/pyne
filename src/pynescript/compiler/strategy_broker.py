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

Supports market entry/close plus pending limit/stop/stop-limit orders with
per-bar OHLC fills (aligned with the interpreter's process_pending_orders).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _is_na(value: Any) -> bool:
    if value is None:
        return True
    # NaN float (incl. numpy floating) — cheap identity check first
    if isinstance(value, float):
        return value != value
    if isinstance(value, str) and value.lower() in {"", "na", "nan", "none"}:
        return True
    return False


def _opt_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, float):
        return None if value != value else value
    if isinstance(value, (int, bool)):
        return float(value)
    if isinstance(value, str) and value.lower() in {"", "na", "nan", "none"}:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if f != f else f


def _norm_dir(direction: Any) -> str:
    # Hot path: already-normalized tokens from generated object-mode code
    if direction == "long" or direction == "short":
        return direction  # type: ignore[return-value]
    d = str(direction).lower()
    if d in {"strategy.long", "long", "1", "buy"}:
        return "long"
    if d in {"strategy.short", "short", "-1", "sell"}:
        return "short"
    return d


@dataclass
class PendingOrder:
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

    @property
    def remaining(self) -> float:
        r = self.quantity - self.filled_qty
        return r if r > 0.0 else 0.0


class CompileStrategyBroker:
    """Per-run strategy state for compiled object-mode scripts."""

    def __init__(
        self,
        initial_capital: float = 100_000.0,
        commission_value: float = 0.0,
        commission_type: str = "percent",
        slippage_ticks: int = 0,
        mintick: float = 0.01,
    ) -> None:
        self.initial_capital = float(initial_capital)
        self.commission_value = float(commission_value)
        self.commission_type = str(commission_type)
        self.slippage_ticks = int(slippage_ticks)
        self.mintick = float(mintick)
        self.position_size: float = 0.0  # signed: +long / -short
        self.position_avg_price: float = float("nan")
        self.position_entry_name: str = ""
        self.netprofit: float = 0.0
        self.closed_trades: int = 0
        self.events: list[dict[str, Any]] = []
        self.pending_orders: dict[str, PendingOrder] = {}
        self._bar_index: int = 0
        self._bar_time: int = 0
        self._mark: float = 0.0
        self._open: float = 0.0
        self._high: float = 0.0
        self._low: float = 0.0
        self._close: float = 0.0

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
        self._bar_index = bar_index if isinstance(bar_index, int) else int(bar_index)
        self._bar_time = bar_time if isinstance(bar_time, int) else int(bar_time)
        # Prefer direct assignment for already-float values (numpy.float64 is float).
        if close is not None:
            c = close if isinstance(close, float) else float(close)
        else:
            c = mark if isinstance(mark, float) else float(mark)
        if open_ is not None:
            o = open_ if isinstance(open_, float) else float(open_)
        else:
            o = c
        if high is not None:
            h = high if isinstance(high, float) else float(high)
        else:
            h = o if o >= c else c
        if low is not None:
            l = low if isinstance(low, float) else float(low)
        else:
            l = o if o <= c else c
        self._open, self._high, self._low, self._close = o, h, l, c
        self._mark = c

    def begin_bar(
        self,
        bar_index: int,
        open_: float,
        high: float,
        low: float,
        close: float,
    ) -> None:
        """Hot path: set OHLC from pre-indexed series values and fill pendings.

        Generated object-mode loops call this once per bar instead of
        ``set_bar`` + ``process_pending_orders`` with repeated ``float()`` wraps.
        """
        self._bar_index = bar_index
        self._bar_time = 0
        self._open = open_
        self._high = high
        self._low = low
        self._close = close
        self._mark = close
        if self.pending_orders:
            self.process_pending_orders()

    def process_pending_orders(
        self,
        open_: float | None = None,
        high: float | None = None,
        low: float | None = None,
        close: float | None = None,
    ) -> list[str]:
        """Fill pending orders against this bar's OHLC. Returns fully filled ids."""
        pending = self.pending_orders
        if not pending:
            return []
        o = self._open if open_ is None else (open_ if isinstance(open_, float) else float(open_))
        h = self._high if high is None else (high if isinstance(high, float) else float(high))
        l = self._low if low is None else (low if isinstance(low, float) else float(low))
        c = self._close if close is None else (close if isinstance(close, float) else float(close))
        fully: list[str] = []
        for oid in list(pending.keys()):
            order = pending.get(oid)
            if order is None:
                continue
            if order.remaining <= 0:
                pending.pop(oid, None)
                fully.append(oid)
                continue
            fill_px = self._trigger_price(order, o, h, l, c)
            if fill_px is None:
                continue
            fill_qty = order.remaining
            max_fill = order.max_fill_per_bar
            if max_fill and max_fill > 0:
                fill_qty = min(fill_qty, float(max_fill))
            if fill_qty <= 0:
                continue
            self._apply_fill(order, fill_px, fill_qty)
            if order.remaining <= 1e-12:
                fully.append(oid)
        return fully

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
        # Closing opposite / reducing
        if not order.is_entry:
            # Force close in this direction (sell covers long, buy covers short)
            if d == "short" and self.position_size > 0:
                self.close(id=order.order_id, qty=fill_qty, price=px, comment=order.comment)
            elif d == "long" and self.position_size < 0:
                self.close(id=order.order_id, qty=fill_qty, price=px, comment=order.comment)
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

    def _open_or_add(
        self,
        direction: str,
        qty: float,
        px: float,
        entry_id: str,
        comment: str | None,
    ) -> None:
        # direction is already "long"/"short" on the hot path from entry()
        d = direction if direction == "long" or direction == "short" else _norm_dir(direction)
        q = qty if qty >= 0 else -qty
        pos = self.position_size
        # Reverse if opposite
        if (d == "long" and pos < 0) or (d == "short" and pos > 0):
            self.close_all(comment="reverse", price=px)
            pos = self.position_size
        signed = q if d == "long" else -q
        if (pos > 0 and d == "long") or (pos < 0 and d == "short"):
            old = pos if pos >= 0 else -pos
            self.position_avg_price = (self.position_avg_price * old + px * q) / (old + q)
            self.position_size = pos + signed
        else:
            self.position_size = signed
            self.position_avg_price = px
        self.position_entry_name = entry_id if isinstance(entry_id, str) else str(entry_id)
        self._emit("entry", id=self.position_entry_name, direction=d, qty=q, comment=comment)

    def _slip(self, price: float, direction: str) -> float:
        ticks = self.slippage_ticks
        if ticks <= 0:
            return price
        slip = ticks * self.mintick
        d = direction if direction == "long" or direction == "short" else _norm_dir(direction)
        return price + slip if d == "long" else price - slip

    def _commission(self, qty: float, price: float) -> float:
        val = self.commission_value
        if not val:
            return 0.0
        q = qty if qty >= 0 else -qty
        p = price if price >= 0 else -price
        ct = self.commission_type
        # Default commission_type is "percent"; avoid .lower() every fill
        if ct == "percent" or ct == "strategy.commission.percent":
            return q * p * (val / 100.0)
        ct_l = ct.lower()
        if ct_l in {"percent", "strategy.commission.percent"}:
            return q * p * (val / 100.0)
        if ct_l in {"cash_per_order", "strategy.commission.cash_per_order"}:
            return val
        if ct_l in {"cash_per_contract", "strategy.commission.cash_per_contract"}:
            return val * q
        return 0.0

    def _emit(self, kind: str, **fields: Any) -> None:
        # Build once; avoid repeated .get on a tiny kwargs dict via local binding
        self.events.append(
            {
                "kind": kind,
                "id": fields.get("id"),
                "direction": fields.get("direction"),
                "qty": fields.get("qty"),
                "order_type": fields.get("order_type"),
                "limit": fields.get("limit"),
                "stop": fields.get("stop"),
                "oca_name": fields.get("oca_name"),
                "comment": fields.get("comment"),
                "bar_index": self._bar_index,
                "bar_time": self._bar_time,
                "ohlc": (self._open, self._high, self._low, self._close),
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

    def entry(
        self,
        id: str = "entry",
        direction: str = "long",
        qty: float = 1.0,
        limit: float | None = None,
        stop: float | None = None,
        comment: str | None = None,
        price: float | None = None,
        **_kwargs: Any,
    ) -> None:
        d = direction if direction == "long" or direction == "short" else _norm_dir(direction)
        if isinstance(qty, (int, float)):
            q = qty if qty >= 0 else -qty
        else:
            q = abs(float(qty))
        # Market hot path (default emitted entry has no limit/stop)
        if limit is None and stop is None:
            if price is None or (isinstance(price, float) and price != price):
                px = self._mark
            elif isinstance(price, float):
                px = price
            else:
                px = float(price) if not _is_na(price) else self._mark
            if self.slippage_ticks:
                px = self._slip(px, d)
            eid = id if isinstance(id, str) else str(id)
            self._open_or_add(d, q, px, eid, comment)
            return
        ot = self._classify_order_type(limit, stop)
        eid = id if isinstance(id, str) else str(id)
        # Pending stop/limit entry
        lim = _opt_float(limit)
        stp = _opt_float(stop)
        self.pending_orders[eid] = PendingOrder(
            order_id=eid,
            order_type=ot,
            direction=d,
            quantity=q,
            limit_price=lim,
            stop_price=stp,
            comment=comment,
            is_entry=True,
        )
        self._emit(
            "order",
            id=eid,
            direction=d,
            qty=q,
            order_type=ot if ot == "limit" else "stop",
            limit=lim,
            stop=stp,
            comment=comment,
        )

    def close(
        self,
        id: str | None = None,
        qty: float | None = None,
        comment: str | None = None,
        price: float | None = None,
        **_kwargs: Any,
    ) -> None:
        pos = self.position_size
        if pos == 0:
            self._emit("close", id=id, qty=0.0, comment=comment)
            return
        if price is None or (isinstance(price, float) and price != price):
            px = self._mark
        elif isinstance(price, float):
            px = price
        else:
            px = float(price) if not _is_na(price) else self._mark
        abs_pos = pos if pos >= 0 else -pos
        if qty is None:
            close_qty = abs_pos
        else:
            qv = qty if isinstance(qty, (int, float)) else float(qty)
            qv = qv if qv >= 0 else -qv
            close_qty = qv if qv < abs_pos else abs_pos
        if close_qty <= 0:
            return
        d = "long" if pos > 0 else "short"
        if d == "long":
            profit = (px - self.position_avg_price) * close_qty
            self.position_size = pos - close_qty
        else:
            profit = (self.position_avg_price - px) * close_qty
            self.position_size = pos + close_qty
        profit -= self._commission(close_qty, px)
        self.netprofit += profit
        self.closed_trades += 1
        if abs(self.position_size) < 1e-12:
            self.position_size = 0.0
            self.position_avg_price = float("nan")
            self.position_entry_name = ""
        self._emit("close", id=id, qty=close_qty, comment=comment, direction=d)

    def close_all(self, comment: str | None = None, price: float | None = None, **_kwargs: Any) -> None:
        if self.position_size != 0:
            self.close(id=None, qty=abs(self.position_size), comment=comment, price=price)
        self._emit("close_all", comment=comment)

    def order(
        self,
        id: str = "order",
        direction: str = "long",
        qty: float = 1.0,
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
        q = abs(float(qty))
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
        if id is not None and str(id) in self.pending_orders:
            del self.pending_orders[str(id)]
        self._emit("cancel", id=id)

    def cancel_all(self, **_kwargs: Any) -> None:
        self.pending_orders.clear()
        self._emit("cancel_all")

    @property
    def equity(self) -> float:
        mark = self._mark
        open_pnl = 0.0
        if self.position_size > 0 and mark == mark:
            open_pnl = (mark - self.position_avg_price) * self.position_size
        elif self.position_size < 0 and mark == mark:
            open_pnl = (self.position_avg_price - mark) * abs(self.position_size)
        return self.initial_capital + self.netprofit + open_pnl

    def to_events(self) -> list[dict[str, Any]]:
        # No copy: broker is single-use per execute_script_compiled run.
        return self.events
