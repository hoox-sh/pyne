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

    @property
    def remaining(self) -> float:
        """Unfilled quantity (never negative)."""
        return max(0.0, float(self.quantity) - float(self.filled_qty))


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
        leverage: float = 1.0,
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
        ``inverse``. Compile broker is a single net lot: partial close already
        keeps ``position_avg_price`` sticky (futures-like). The flag is stored
        for dual-path parity and future multi-leg / inverse harmonic work.

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
        try:
            lev = float(leverage) if leverage is not None else 1.0
        except (TypeError, ValueError):
            lev = 1.0
        if lev != lev or lev <= 0:  # NaN / non-positive
            lev = 1.0
        self.leverage: float = 1.0 if lev < 1.0 else lev
        self.position_size: float = 0.0  # signed: +long / -short
        self.position_avg_price: float = float("nan")
        self.position_entry_name: str = ""
        # Count of open entry legs (market path pyramiding / replace parity).
        self.open_entry_count: int = 0
        # Remaining entry commission on the open position (openprofit drag).
        # Exit commission is charged at close time and never sits on the open.
        self.position_commission: float = 0.0
        self.netprofit: float = 0.0
        self.closed_trades: int = 0
        self.wintrades: int = 0
        self.losstrades: int = 0
        self.eventrades: int = 0
        self.grossprofit: float = 0.0
        self.grossloss: float = 0.0
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
        *,
        respect_pyramiding: bool = False,
        replace_same_id: bool = False,
    ) -> bool:
        """Open / add / reverse a position.

        Returns False when the entry was blocked (pyramiding / invalid).

        Parameters
        ----------
        respect_pyramiding:
            Market ``strategy.entry`` path: different id needs room;
            ``replace_same_id`` replaces the open leg when ids match.
            Pending order fills keep averaging (``respect_pyramiding=False``).
            When ``pyramiding <= 0``, pending averages stay a **single** entry
            leg (``open_entry_count == 1``) with VWAP avg (F2).
        """
        d = direction if direction == "long" or direction == "short" else _norm_dir(direction)
        if d is None:
            return False
        q = abs(float(qty))
        if q <= 0 or not math.isfinite(q):
            return False
        # Reverse if opposite — emit close only (interpret parity; no close_all).
        if (d == "long" and self.position_size < 0) or (d == "short" and self.position_size > 0):
            self.close(id=str(entry_id), qty=abs(self.position_size), comment="reverse", price=px)
        same_dir = (self.position_size > 0 and d == "long") or (self.position_size < 0 and d == "short")
        if same_dir and abs(self.position_size) > 0:
            same_id = self.position_entry_name == str(entry_id)
            if respect_pyramiding and replace_same_id and same_id:
                # Interpret oracle: same-id re-entry overwrites without realizing PnL.
                pass  # fall through to flat open below
            elif respect_pyramiding and not same_id:
                max_entries = int(self.pyramiding) + 1 if self.pyramiding is not None else 1
                if not (self.pyramiding > 0 and self.open_entry_count < max_entries):
                    return False  # pyramiding blocked
                comm = self._commission(q, px)
                signed = q if d == "long" else -q
                old = abs(self.position_size)
                self.position_avg_price = (self.position_avg_price * old + px * q) / (old + q)
                self.position_size += signed
                self.position_commission += comm
                self.position_entry_name = str(entry_id)
                self.open_entry_count += 1
                self._emit("entry", id=str(entry_id), direction=d, qty=q, comment=comment)
                return True
            elif not (respect_pyramiding and replace_same_id and same_id):
                # Average-add (pending order fills / non-replace path).
                # F2: pyramiding<=0 → single leg + VWAP; pyramiding>0 leaves
                # open_entry_count unchanged (max(1, …)) — no silent multi-leg.
                comm = self._commission(q, px)
                signed = q if d == "long" else -q
                old = abs(self.position_size)
                self.position_avg_price = (self.position_avg_price * old + px * q) / (old + q)
                self.position_size += signed
                self.position_commission += comm
                self.position_entry_name = str(entry_id)
                # Always one logical entry for pending averages when pyramiding
                # is off; when on, still do not invent extra legs without market
                # respect_pyramiding (compile pending has no open-trade list).
                self.open_entry_count = 1 if self.pyramiding <= 0 else max(1, self.open_entry_count)
                self._emit("entry", id=str(entry_id), direction=d, qty=q, comment=comment)
                return True
        # Flat open, reverse re-entry, or same-id replace overwrite
        comm = self._commission(q, px)
        signed = q if d == "long" else -q
        self.position_size = signed
        self.position_avg_price = px
        self.position_commission = comm
        self.position_entry_name = str(entry_id)
        self.open_entry_count = 1
        self._emit("entry", id=str(entry_id), direction=d, qty=q, comment=comment)
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
                d, q, px, str(id), comment, respect_pyramiding=True, replace_same_id=True
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
            d, q, px, str(id), comment, respect_pyramiding=True, replace_same_id=True
        )

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
        **_kwargs: Any,
    ) -> None:
        """Close (part of) the open position at mark or *price*; update PnL.

        When ``stop`` / ``limit`` (or ``loss`` / ``profit``) are provided the
        compiler has mapped ``strategy.exit`` → ``close``. Match the interpret
        oracle: pick an exit fill price from those legs and emit ``kind=exit``.
        """
        # Compiler maps strategy.exit → close(..., stop=..., limit=...).
        limit_p = _opt_float(limit if limit is not None else profit)
        stop_p = _opt_float(stop if stop is not None else loss)
        is_exit = limit_p is not None or stop_p is not None
        event_kind = "exit" if is_exit else "close"

        if self.position_size == 0:
            self._emit(
                event_kind,
                id=id,
                qty=0.0,
                comment=comment,
                limit=limit_p,
                stop=stop_p,
            )
            return
        if qty is not None and not _is_na(qty):
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
        d = "long" if self.position_size > 0 else "short"
        pos_before = abs(self.position_size)
        if qty is None or _is_na(qty):
            close_qty = pos_before
        else:
            close_qty = min(abs(float(qty)), pos_before)
        if close_qty <= 0 or not math.isfinite(close_qty):
            return

        if is_exit:
            # Pending bracket: only fill when OHLC touches; else place pending.
            px = self._exit_fill_price(
                limit=limit_p,
                stop=stop_p,
                is_long=(d == "long"),
                is_short=(d == "short"),
            )
            # Always emit exit event (placement / intent) for host parity.
            self._emit(
                "exit",
                id=id,
                qty=close_qty,
                comment=comment,
                direction=None,
                limit=limit_p,
                stop=stop_p,
            )
            if px is None:
                # Place pending close order(s) — filled by process_pending_orders.
                exit_dir = "short" if d == "long" else "long"  # close direction
                base = str(id) if id is not None else "exit"
                # Drop prior legs with same base id
                for oid in list(self.pending_orders.keys()):
                    if oid == base or oid.startswith(base + ":"):
                        del self.pending_orders[oid]
                if limit_p is not None and stop_p is not None:
                    self.pending_orders[f"{base}:limit"] = PendingOrder(
                        order_id=f"{base}:limit",
                        order_type="limit",
                        direction=exit_dir,
                        quantity=close_qty,
                        limit_price=limit_p,
                        stop_price=None,
                        comment=str(comment) if comment else "",
                        oca_name=base,
                        oca_type="cancel",
                        is_entry=False,
                    )
                    self.pending_orders[f"{base}:stop"] = PendingOrder(
                        order_id=f"{base}:stop",
                        order_type="stop",
                        direction=exit_dir,
                        quantity=close_qty,
                        limit_price=None,
                        stop_price=stop_p,
                        comment=str(comment) if comment else "",
                        oca_name=base,
                        oca_type="cancel",
                        is_entry=False,
                    )
                elif limit_p is not None:
                    self.pending_orders[base] = PendingOrder(
                        order_id=base,
                        order_type="limit",
                        direction=exit_dir,
                        quantity=close_qty,
                        limit_price=limit_p,
                        stop_price=None,
                        comment=str(comment) if comment else "",
                        is_entry=False,
                    )
                else:
                    self.pending_orders[base] = PendingOrder(
                        order_id=base,
                        order_type="stop",
                        direction=exit_dir,
                        quantity=close_qty,
                        limit_price=None,
                        stop_price=stop_p,
                        comment=str(comment) if comment else "",
                        is_entry=False,
                    )
                return
            # Same-bar fill at touched level — fall through to realize PnL
        elif price is None or _is_na(price):
            # Exit slip: long close sells (worse), short cover buys (worse).
            px = self._slip(self._mark, "short" if d == "long" else "long")
        else:
            px = float(price)
        if d == "long":
            trade_profit = (px - self.position_avg_price) * close_qty
            self.position_size -= close_qty
        else:
            trade_profit = (self.position_avg_price - px) * close_qty
            self.position_size += close_qty
        # Realize proportional *entry* commission + charge *exit* commission.
        entry_comm = 0.0
        if pos_before > 0 and self.position_commission:
            entry_comm = float(self.position_commission) * (close_qty / pos_before)
            self.position_commission = max(0.0, float(self.position_commission) - entry_comm)
        exit_comm = self._commission(close_qty, px)
        trade_profit -= entry_comm + exit_comm
        self.netprofit += trade_profit
        self.closed_trades += 1
        if trade_profit > 0:
            self.wintrades += 1
            self.grossprofit += trade_profit
        elif trade_profit < 0:
            self.losstrades += 1
            self.grossloss += abs(trade_profit)
        else:
            self.eventrades += 1
        if abs(self.position_size) < 1e-12:
            self.position_size = 0.0
            self.position_avg_price = float("nan")
            self.position_entry_name = ""
            self.position_commission = 0.0
            self.open_entry_count = 0
        self._update_equity_extremes()
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
    def cash(self) -> float:
        """Approximate free cash: equity minus margin locked (notional / leverage)."""
        ps = self.position_size
        if ps == 0.0 or self.position_avg_price != self.position_avg_price:
            return float(self.equity)
        notional = abs(float(self.position_avg_price) * float(ps))
        lev = float(self.leverage) if self.leverage and self.leverage > 0 else 1.0
        held = notional / lev
        return float(self.equity) - held

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

    def to_events(self) -> list[dict[str, Any]]:
        """Return the live event list for host packing as ``__events``.

        Broker is single-use per compiled run; no copy (callers must not mutate
        after the run returns if they retain the handle).
        """
        return self.events
