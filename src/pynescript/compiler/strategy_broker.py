# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# SPDX-License-Identifier: LGPL-3.0-or-later

"""Lightweight strategy broker for the compile (object-mode) path.

Generated bar loops call into :class:`CompileStrategyBroker` so strategy
scripts produce events and position state without going through the full
AST interpreter.
"""

from __future__ import annotations

from typing import Any


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
        self._bar_index: int = 0
        self._bar_time: int = 0
        self._mark: float = 0.0

    def set_bar(self, bar_index: int, bar_time: int = 0, mark: float = 0.0) -> None:
        self._bar_index = int(bar_index)
        self._bar_time = int(bar_time)
        if mark == mark:  # not NaN
            self._mark = float(mark)

    def _slip(self, price: float, direction: str) -> float:
        if self.slippage_ticks <= 0:
            return float(price)
        slip = self.slippage_ticks * self.mintick
        return float(price) + slip if direction == "long" else float(price) - slip

    def _commission(self, qty: float, price: float) -> float:
        val = self.commission_value
        if val == 0:
            return 0.0
        q, p = abs(float(qty)), abs(float(price))
        ct = self.commission_type.lower()
        if ct in {"percent", "strategy.commission.percent"}:
            return q * p * (val / 100.0)
        if ct in {"cash_per_order", "strategy.commission.cash_per_order"}:
            return val
        if ct in {"cash_per_contract", "strategy.commission.cash_per_contract"}:
            return val * q
        return 0.0

    def _emit(self, kind: str, **fields: Any) -> None:
        ev = {
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
            "ohlc": [0.0, 0.0, 0.0, 0.0],
        }
        self.events.append(ev)

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
        d = str(direction).lower()
        if d in {"strategy.long", "1", "buy"}:
            d = "long"
        elif d in {"strategy.short", "-1", "sell"}:
            d = "short"
        q = abs(float(qty))
        px = float(price if price is not None else self._mark)
        if limit is not None and str(limit).lower() not in {"na", "nan", "none", ""}:
            try:
                px = float(limit)
            except (TypeError, ValueError):
                pass
        px = self._slip(px, d)
        # Reverse if opposite
        if (d == "long" and self.position_size < 0) or (d == "short" and self.position_size > 0):
            self.close_all(comment="reverse", price=px)
        signed = q if d == "long" else -q
        # Average-in same direction
        if (self.position_size > 0 and d == "long") or (self.position_size < 0 and d == "short"):
            old = abs(self.position_size)
            self.position_avg_price = (self.position_avg_price * old + px * q) / (old + q)
            self.position_size += signed
        else:
            self.position_size = signed
            self.position_avg_price = px
        self.position_entry_name = str(id)
        self._emit("entry", id=str(id), direction=d, qty=q, comment=comment, limit=limit, stop=stop)

    def close(
        self,
        id: str | None = None,
        qty: float | None = None,
        comment: str | None = None,
        price: float | None = None,
        **_kwargs: Any,
    ) -> None:
        if self.position_size == 0:
            self._emit("close", id=id, qty=0.0, comment=comment)
            return
        px = float(price if price is not None else self._mark)
        close_qty = abs(self.position_size) if qty is None else min(abs(float(qty)), abs(self.position_size))
        if close_qty <= 0:
            return
        d = "long" if self.position_size > 0 else "short"
        if d == "long":
            profit = (px - self.position_avg_price) * close_qty
            self.position_size -= close_qty
        else:
            profit = (self.position_avg_price - px) * close_qty
            self.position_size += close_qty
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
        **_kwargs: Any,
    ) -> None:
        """Market-style order in compile path: acts like entry in direction."""
        d = str(direction).lower()
        if d in {"strategy.long", "long", "1", "buy"}:
            d = "long"
        elif d in {"strategy.short", "short", "-1", "sell"}:
            d = "short"
        # Record order event then enter
        self._emit(
            "order",
            id=str(id),
            direction=d,
            qty=abs(float(qty)),
            order_type="market",
            limit=limit,
            stop=stop,
            oca_name=oca_name,
            comment=comment,
        )
        self.entry(id=str(id), direction=d, qty=qty, price=price, comment=comment)

    def cancel(self, id: str | None = None, **_kwargs: Any) -> None:
        self._emit("cancel", id=id)

    def cancel_all(self, **_kwargs: Any) -> None:
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
        return list(self.events)
