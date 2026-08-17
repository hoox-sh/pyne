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

"""Pair Runtime strategy events into closed trades + :class:`StrategyStats`.

Mirrors AXIS ``buildStrategyReport`` enough for HPO scoring: entry/exit
pairing by id, money PnL from prices × qty, max drawdown on cumulative
equity. Uses bar close (``ohlc[3]``) as the fill when no explicit price.
"""

from __future__ import annotations

from typing import Any

from pynescript.optimize.types import StrategyStats


def _event_kind(ev: dict[str, Any]) -> str:
    return str(ev.get("kind") or ev.get("type") or ev.get("event") or "").lower()


def _event_time(ev: dict[str, Any]) -> float | None:
    raw = ev.get("bar_time", ev.get("time"))
    if raw is None:
        return None
    try:
        n = float(raw)
    except (TypeError, ValueError):
        return None
    return n if n == n else None


def _finite_num(raw: Any) -> float | None:
    if isinstance(raw, (int, float)) and raw == raw:
        return float(raw)
    return None


def _event_price(ev: dict[str, Any]) -> float | None:
    # Broker fills carry limit/stop (order price) and bar OHLC; they do not
    # serialize a ``price`` field. Prefer the order level over bar close.
    comment = str(ev.get("comment") or "")
    if comment.startswith("fill"):
        for key in ("limit", "stop"):
            n = _finite_num(ev.get(key))
            if n is not None:
                return n
    n = _finite_num(ev.get("price"))
    if n is not None:
        return n
    ohlc = ev.get("ohlc")
    if isinstance(ohlc, (list, tuple)) and len(ohlc) >= 4:
        return _finite_num(ohlc[3])
    return None


def _event_qty(ev: dict[str, Any], fallback: float = 1.0) -> float:
    raw = ev.get("qty")
    if raw is None or raw == "":
        return fallback
    try:
        n = float(raw)
    except (TypeError, ValueError):
        return fallback
    if n != n or n == 0:
        return fallback
    return abs(n)


def _event_dir(ev: dict[str, Any], kind: str) -> str:
    raw = str(ev.get("direction") or ev.get("dir") or "").lower()
    if raw and raw not in {"null", "none", "undefined"}:
        return "short" if "short" in raw else "long"
    return "short" if "short" in kind else "long"


def _match_id(ev: dict[str, Any]) -> str:
    for key in ("from_entry", "entry_id", "id"):
        v = ev.get(key)
        if v is not None and str(v):
            return str(v)
    return "_default"


def _is_fill_order(kind: str, ev: dict[str, Any]) -> bool:
    """True for broker fills (``comment`` ``fill`` / ``fill:…``), not placements."""
    if kind != "order":
        return False
    return str(ev.get("comment") or "").startswith("fill")


def _is_exit_placement(kind: str) -> bool:
    """Every ``strategy.exit`` emit is an intent; closes come from fill/close."""
    return "exit" in kind


def build_strategy_stats(
    events: list[dict[str, Any]] | None,
    *,
    score_window: tuple[float, float] | None = None,
) -> StrategyStats:
    """Pair fills into closed trades and aggregate tester stats.

    When ``score_window`` is ``(t0, t1)``, the open book still sees every
    event (warmup entries stay paired) but only closes inside the window
    count toward PnL.
    """
    if not events:
        return StrategyStats()
    open_pos: dict[str, dict[str, Any]] = {}
    pnls: list[float] = []

    def close_one(
        oid: str,
        o: dict[str, Any],
        exit_price: float,
        close_qty: float,
        close_time: float | None,
    ) -> None:
        open_qty = float(o["qty"])
        qty = close_qty if close_qty > 0 else open_qty
        if qty > open_qty:
            qty = open_qty
        if qty <= 0:
            return
        leftover = open_qty - qty
        if abs(leftover) < 1e-12:
            open_pos.pop(oid, None)
        else:
            o["qty"] = leftover
        if score_window is not None:
            t0, t1 = score_window
            if close_time is None or close_time < t0 or close_time > t1:
                return
        sign = -1.0 if o["dir"] == "short" else 1.0
        pnls.append((exit_price - float(o["entry"])) * sign * qty)

    def resolve_open(ev: dict[str, Any], eid: str) -> str | None:
        match = _match_id(ev)
        if match in open_pos:
            return match
        if eid in open_pos:
            return eid
        if len(open_pos) == 1:
            return next(iter(open_pos))
        return None

    def open_one(oid: str, ev: dict[str, Any], price: float, time: float, kind: str) -> None:
        open_pos[oid] = {
            "entry": price,
            "time": time,
            "dir": _event_dir(ev, kind),
            "qty": _event_qty(ev, 1.0),
        }

    for ev in events:
        if not isinstance(ev, dict):
            continue
        t = _event_time(ev)
        p = _event_price(ev)
        if t is None or p is None:
            continue
        kind = _event_kind(ev)
        if not kind or kind in {"cancel", "cancel_all"}:
            continue
        is_fill = _is_fill_order(kind, ev)
        if kind == "order" and not is_fill:
            continue
        if _is_exit_placement(kind):
            continue
        eid = str(ev.get("id") or "_default")
        if is_fill:
            target = resolve_open(ev, eid)
            if target is not None:
                # Own-id fill of the lot we just opened (entry fill), not a close.
                from_entry = ev.get("from_entry") or ev.get("entry_id")
                if not from_entry and str(ev.get("id") or "") == target:
                    continue
                if ev.get("qty") == 0:
                    continue
                close_one(
                    target,
                    open_pos[target],
                    p,
                    _event_qty(ev, float(open_pos[target]["qty"])),
                    t,
                )
            else:
                open_one(eid, ev, p, t, kind)
            continue
        if "entry" in kind or kind in {"long", "short"}:
            open_one(eid, ev, p, t, kind)
            continue
        if not (
            "close" in kind
            or "exit" in kind
            or kind in {"closelong", "closeshort"}
        ):
            continue
        if ev.get("qty") == 0:
            continue
        is_all = kind in {"close_all", "closeall"} or "close_all" in kind
        if is_all:
            for oid, o in list(open_pos.items()):
                close_one(oid, o, p, float(o["qty"]), t)
            open_pos.clear()
            continue
        closed_id = resolve_open(ev, eid)
        if closed_id is None:
            continue
        close_one(
            closed_id,
            open_pos[closed_id],
            p,
            _event_qty(ev, float(open_pos[closed_id]["qty"])),
            t,
        )

    if not pnls:
        return StrategyStats()
    wins = [x for x in pnls if x > 0]
    losses = [x for x in pnls if x < 0]
    total = sum(pnls)
    gp = sum(wins)
    gl = abs(sum(losses))
    pf = (gp / gl) if gl > 0 else (float("inf") if gp > 0 else 0.0)
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for x in pnls:
        equity += x
        if equity > peak:
            peak = equity
        dd = (peak - equity) / max(1.0, abs(peak) + 1.0)
        if dd > max_dd:
            max_dd = dd
    n = len(pnls)
    return StrategyStats(
        total_pnl=total,
        win_rate=(len(wins) / n) * 100.0,
        profit_factor=pf,
        avg_trade=total / n,
        max_dd=max_dd,
        wins=len(wins),
        losses=len(losses),
        trades=n,
    )
