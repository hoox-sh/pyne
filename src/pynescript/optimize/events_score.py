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


def _event_price(ev: dict[str, Any]) -> float | None:
    raw = ev.get("price")
    if isinstance(raw, (int, float)) and raw == raw:
        return float(raw)
    ohlc = ev.get("ohlc")
    if isinstance(ohlc, (list, tuple)) and len(ohlc) >= 4:
        close = ohlc[3]
        if isinstance(close, (int, float)) and close == close:
            return float(close)
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


def build_strategy_stats(events: list[dict[str, Any]] | None) -> StrategyStats:
    """Pair fills into closed trades and aggregate tester stats."""
    if not events:
        return StrategyStats()
    open_pos: dict[str, dict[str, Any]] = {}
    pnls: list[float] = []

    def close_one(oid: str, o: dict[str, Any], exit_price: float, close_qty: float) -> None:
        qty = close_qty if close_qty > 0 else float(o["qty"])
        sign = -1.0 if o["dir"] == "short" else 1.0
        pnls.append((exit_price - float(o["entry"])) * sign * qty)

    for ev in events:
        if not isinstance(ev, dict):
            continue
        t = _event_time(ev)
        p = _event_price(ev)
        if t is None or p is None:
            continue
        kind = _event_kind(ev)
        if not kind or kind in {"cancel", "cancel_all", "order"}:
            continue
        eid = str(ev.get("id") or "_default")
        if "entry" in kind or kind in {"long", "short"}:
            open_pos[eid] = {
                "entry": p,
                "time": t,
                "dir": _event_dir(ev, kind),
                "qty": _event_qty(ev, 1.0),
            }
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
                close_one(oid, o, p, float(o["qty"]))
            open_pos.clear()
            continue
        match = _match_id(ev)
        o = open_pos.get(match)
        closed_id = match
        if o is None and match != eid:
            o = open_pos.get(eid)
            closed_id = eid
        if o is None and len(open_pos) == 1:
            closed_id = next(iter(open_pos))
            o = open_pos[closed_id]
        if o is None:
            continue
        del open_pos[closed_id]
        close_one(closed_id, o, p, _event_qty(ev, float(o["qty"])))

    if not pnls:
        return StrategyStats()
    wins = [x for x in pnls if x > 0]
    losses = [x for x in pnls if x <= 0]
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
