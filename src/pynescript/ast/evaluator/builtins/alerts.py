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

from .base import BuiltinDispatchMixin
from .base import BuiltinHandler


@dataclass
class AlertEvent:
    """Represents a triggered alert event."""
    message: str
    freq: str
    bar_index: int | None = None
    time: int | None = None


@dataclass
class AlertCondition:
    """Represents a registered alert condition."""
    condition: bool
    title: str
    message: str


class AlertsMixin(BuiltinDispatchMixin):
    """Alert-related built-in functions and execution engine."""

    def __init__(self):
        super().__init__()
        self._triggered_alerts: list[AlertEvent] = []
        self._alert_conditions: list[AlertCondition] = []

    def _alerts_builtin_map(self) -> dict[str, BuiltinHandler]:
        return {
            "alert": self._builtin_alert,
            "alertcondition": self._builtin_alertcondition,
        }

    def _builtin_alert(self, args: list[Any]) -> None:
        """Send an alert notification.
        
        Signature: alert(message, freq)
        """
        if not args or len(args) < 1:
            self._error("alert() requires at least a message argument")

        message = str(args[0])
        freq = "freq_once_per_bar"  # Default

        if len(args) > 1 and args[1] is not None:
            freq = str(args[1])

        # Capture context if available (bar_index, time)
        # Assuming self.context has these if running in a loop
        bar_index = self.context.get("bar_index", None)
        time_val = self.context.get("time", None)

        event = AlertEvent(
            message=message,
            freq=freq,
            bar_index=bar_index,
            time=time_val
        )
        self._triggered_alerts.append(event)

    def _builtin_alertcondition(self, args: list[Any]) -> None:
        """Define an alert condition.
        
        Signature: alertcondition(condition, title, message)
        """
        if len(args) < 1:
            self._error("alertcondition() requires at least a condition argument")

        condition = bool(args[0])
        title = "Alert"
        message = "Alert"

        if len(args) > 1 and args[1] is not None:
            title = str(args[1])

        if len(args) > 2 and args[2] is not None:
            message = str(args[2])

        # We store the condition state for the current execution
        # In a real engine, this metadata is static, but the condition evaluation is dynamic.
        # Here we just record that an alertcondition was evaluated with a certain result.
        self._alert_conditions.append(AlertCondition(condition, title, message))

    def get_triggered_alerts(self) -> list[AlertEvent]:
        """Get all alerts triggered during execution."""
        return self._triggered_alerts

    def clear_alerts(self) -> None:
        """Clear triggered alerts."""
        self._triggered_alerts.clear()
        self._alert_conditions.clear()
