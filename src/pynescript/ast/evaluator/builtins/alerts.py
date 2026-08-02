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

"""Pine ``alert()`` / ``alertcondition()`` builtins + host alert engine helpers.

Hosts (Pro API, pyne-worker) collect :class:`AlertEvent` records after each run
and forward them to webhooks / cron consumers. Frequency constants match TV:

- ``alert.freq_once_per_bar`` — first fire per bar only
- ``alert.freq_once_per_bar_close`` — fire only when ``barstate.isconfirmed``
- ``alert.freq_all`` — every call
"""

from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from typing import Any

from .base import BuiltinDispatchMixin
from .base import BuiltinHandler

# Normalized frequency tokens used in AlertEvent.freq
FREQ_ONCE_PER_BAR = "once_per_bar"
FREQ_ONCE_PER_BAR_CLOSE = "once_per_bar_close"
FREQ_ALL = "all"

_FREQ_ALIASES: dict[str, str] = {
    "once_per_bar": FREQ_ONCE_PER_BAR,
    "freq_once_per_bar": FREQ_ONCE_PER_BAR,
    "alert.freq_once_per_bar": FREQ_ONCE_PER_BAR,
    "once_per_bar_close": FREQ_ONCE_PER_BAR_CLOSE,
    "freq_once_per_bar_close": FREQ_ONCE_PER_BAR_CLOSE,
    "alert.freq_once_per_bar_close": FREQ_ONCE_PER_BAR_CLOSE,
    "all": FREQ_ALL,
    "freq_all": FREQ_ALL,
    "alert.freq_all": FREQ_ALL,
}


def normalize_alert_freq(freq: Any) -> str:
    """Map TV / string freq tokens to a short canonical form."""
    if freq is None:
        return FREQ_ONCE_PER_BAR
    s = str(freq).strip().lower().replace(" ", "_")
    return _FREQ_ALIASES.get(s, FREQ_ONCE_PER_BAR if not s else s)


@dataclass
class AlertEvent:
    """Represents a triggered alert event."""

    message: str
    freq: str
    bar_index: int | None = None
    time: int | None = None
    title: str | None = None
    source: str = "alert"  # "alert" | "alertcondition"

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe dict for API / worker payloads."""
        d = asdict(self)
        # Drop empty title for compact payloads
        if not d.get("title"):
            d.pop("title", None)
        return d


@dataclass
class AlertCondition:
    """Represents a registered alert condition evaluation on a bar."""

    condition: bool
    title: str
    message: str
    bar_index: int | None = None
    time: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AlertsMixin(BuiltinDispatchMixin):
    """Alert-related built-in functions and execution engine."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._triggered_alerts: list[AlertEvent] = []
        self._alert_conditions: list[AlertCondition] = []
        # (source, title, message, freq) → last bar_index that fired (once_per_bar*)
        self._alert_fire_bars: dict[tuple[str, str, str, str], int] = {}

    def _alerts_builtin_map(self) -> dict[str, BuiltinHandler]:
        return {
            "alert": self._builtin_alert,
            "alertcondition": self._builtin_alertcondition,
            # TV frequency constants (also used as bare strings)
            "alert.freq_once_per_bar": FREQ_ONCE_PER_BAR,
            "alert.freq_once_per_bar_close": FREQ_ONCE_PER_BAR_CLOSE,
            "alert.freq_all": FREQ_ALL,
        }

    def _alert_bar_index(self) -> int | None:
        ctx = getattr(self, "context", None) or {}
        bi = ctx.get("bar_index")
        if bi is None:
            return None
        try:
            return int(bi)
        except (TypeError, ValueError):
            return None

    def _alert_time(self) -> int | None:
        ctx = getattr(self, "context", None) or {}
        t = ctx.get("time")
        # PineSeries → current
        cur = getattr(t, "current", None)
        if cur is not None and not isinstance(t, (int, float)):
            t = cur
        if t is None:
            return None
        try:
            return int(t)
        except (TypeError, ValueError):
            return None

    def _bar_is_confirmed(self) -> bool:
        """True when host marks the bar closed (barstate.isconfirmed / islast)."""
        ctx = getattr(self, "context", None) or {}
        bs = ctx.get("barstate")
        if bs is not None:
            conf = getattr(bs, "isconfirmed", None)
            if conf is None and isinstance(bs, dict):
                conf = bs.get("isconfirmed")
            if conf is not None:
                return bool(conf)
            islast = getattr(bs, "islast", None)
            if islast is None and isinstance(bs, dict):
                islast = bs.get("islast")
            if islast is not None:
                return bool(islast)
        # Flat keys some hosts inject
        if "barstate.isconfirmed" in ctx:
            return bool(ctx.get("barstate.isconfirmed"))
        return True  # interpret hosts without barstate: treat as confirmed

    def _should_fire_alert(
        self,
        *,
        source: str,
        title: str,
        message: str,
        freq: str,
        bar_index: int | None,
    ) -> bool:
        """Apply TV frequency rules before recording an alert."""
        freq_n = normalize_alert_freq(freq)
        if freq_n == FREQ_ALL:
            return True
        if freq_n == FREQ_ONCE_PER_BAR_CLOSE and not self._bar_is_confirmed():
            return False
        if bar_index is None:
            return True
        key = (source, title or "", message, freq_n)
        last = self._alert_fire_bars.get(key)
        if last is not None and last == bar_index:
            return False
        self._alert_fire_bars[key] = bar_index
        return True

    def _emit_alert(
        self,
        message: str,
        freq: str = FREQ_ONCE_PER_BAR,
        *,
        title: str | None = None,
        source: str = "alert",
    ) -> None:
        bar_index = self._alert_bar_index()
        freq_n = normalize_alert_freq(freq)
        if not self._should_fire_alert(
            source=source,
            title=title or "",
            message=message,
            freq=freq_n,
            bar_index=bar_index,
        ):
            return
        self._triggered_alerts.append(
            AlertEvent(
                message=str(message),
                freq=freq_n,
                bar_index=bar_index,
                time=self._alert_time(),
                title=title,
                source=source,
            )
        )

    def _builtin_alert(self, args: list[Any]) -> None:
        """Send an alert notification.

        Signature: ``alert(message, freq)``.

        Zero-arg ``alert()`` (linter signature demos / truncated scrapes) is a
        soft no-op rather than a hard Runtime Error so residual corpus scripts
        keep evaluating other statements.
        """
        if not args or len(args) < 1:
            return

        message = str(args[0] if args[0] is not None else "")
        freq: Any = FREQ_ONCE_PER_BAR
        if len(args) > 1 and args[1] is not None:
            freq = args[1]
        self._emit_alert(message, freq, source="alert")

    def _builtin_alertcondition(self, args: list[Any]) -> None:
        """Define / evaluate an alert condition.

        Signature: ``alertcondition(condition, title, message)``

        On each bar where *condition* is true, the engine records the condition
        and fires a host alert (``source=alertcondition``) with
        ``freq_once_per_bar`` semantics so cron / API consumers see firings.
        """
        if len(args) < 1:
            self._error("alertcondition() requires at least a condition argument")

        raw_cond = args[0]
        # Pine series / na → bool
        if raw_cond is None:
            condition = False
        elif hasattr(raw_cond, "current"):
            cur = raw_cond.current
            condition = bool(cur) if cur is not None else False
        else:
            try:
                condition = bool(raw_cond)
            except (TypeError, ValueError):
                condition = False

        title = "Alert"
        message = "Alert"
        if len(args) > 1 and args[1] is not None:
            title = str(args[1])
        if len(args) > 2 and args[2] is not None:
            message = str(args[2])

        bar_index = self._alert_bar_index()
        time_val = self._alert_time()
        self._alert_conditions.append(
            AlertCondition(
                condition=condition,
                title=title,
                message=message,
                bar_index=bar_index,
                time=time_val,
            )
        )
        if condition:
            self._emit_alert(
                message,
                FREQ_ONCE_PER_BAR,
                title=title,
                source="alertcondition",
            )

    def get_triggered_alerts(self) -> list[AlertEvent]:
        """Get all alerts triggered during execution."""
        return list(self._triggered_alerts)

    def export_alerts(self) -> list[dict[str, Any]]:
        """JSON-safe alert list for Runtime / worker API."""
        return [a.to_dict() for a in self._triggered_alerts]

    def export_alert_conditions(self) -> list[dict[str, Any]]:
        """JSON-safe alertcondition evaluations (debug / UI)."""
        return [c.to_dict() for c in self._alert_conditions]

    def clear_alerts(self) -> None:
        """Clear triggered alerts and condition log for a new run."""
        self._triggered_alerts.clear()
        self._alert_conditions.clear()
        self._alert_fire_bars.clear()


def export_alerts_from_evaluator(evaluator: Any) -> list[dict[str, Any]]:
    """Host helper: pull alerts from any evaluator that exposes the mixin API."""
    if evaluator is None:
        return []
    exp = getattr(evaluator, "export_alerts", None)
    if callable(exp):
        try:
            out = exp()
            return list(out) if out else []
        except Exception:  # noqa: BLE001
            return []
    raw = getattr(evaluator, "_triggered_alerts", None) or getattr(
        evaluator, "get_triggered_alerts", None
    )
    if callable(raw):
        try:
            items = raw()
        except Exception:  # noqa: BLE001
            return []
    else:
        items = raw
    if not items:
        return []
    out: list[dict[str, Any]] = []
    for a in items:
        if hasattr(a, "to_dict"):
            out.append(a.to_dict())
        elif isinstance(a, dict):
            out.append(a)
        else:
            out.append(
                {
                    "message": str(getattr(a, "message", a)),
                    "freq": str(getattr(a, "freq", FREQ_ONCE_PER_BAR)),
                    "bar_index": getattr(a, "bar_index", None),
                    "time": getattr(a, "time", None),
                    "source": getattr(a, "source", "alert"),
                }
            )
    return out
