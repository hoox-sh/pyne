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

"""Alert and alertcondition builtin behavior in the evaluator.

Covers fire frequencies, once-per-bar dedup, context capture, and export.
"""

from __future__ import annotations

from pynescript.ast.evaluator import NodeLiteralEvaluator
from pynescript.ast.evaluator.builtins.alerts import FREQ_ALL
from pynescript.ast.evaluator.builtins.alerts import FREQ_ONCE_PER_BAR
from pynescript.ast.evaluator.builtins.alerts import export_alerts_from_evaluator


class TestAlerts:
    def test_alert_function(self):
        """Test alert() function execution and event capture."""
        evaluator = NodeLiteralEvaluator()

        # Test basic alert
        evaluator.evaluate_script('alert("Simple Alert")')
        alerts = evaluator.get_triggered_alerts()
        assert len(alerts) == 1
        assert alerts[0].message == "Simple Alert"
        assert alerts[0].freq in (FREQ_ONCE_PER_BAR, "freq_once_per_bar")

        # Test alert with frequency
        evaluator.clear_alerts()
        evaluator.evaluate_script('alert("Complex Alert", "freq_all")')
        alerts = evaluator.get_triggered_alerts()
        assert len(alerts) == 1
        assert alerts[0].message == "Complex Alert"
        assert alerts[0].freq in (FREQ_ALL, "freq_all", "all")

    def test_alertcondition_function(self):
        """Test alertcondition() registration and fire-on-true."""
        evaluator = NodeLiteralEvaluator()

        # Test basic alertcondition
        evaluator.evaluate_script('alertcondition(true, "Title", "Message")')
        # Access private member for testing since there's no public getter for conditions yet
        conditions = evaluator._alert_conditions
        assert len(conditions) == 1
        assert conditions[0].condition is True
        assert conditions[0].title == "Title"
        assert conditions[0].message == "Message"
        # Engine fires when condition is true
        fired = evaluator.get_triggered_alerts()
        assert any(a.message == "Message" and a.source == "alertcondition" for a in fired)

        # Test alertcondition with defaults (false → no fire)
        evaluator.clear_alerts()
        evaluator.evaluate_script("alertcondition(false)")
        conditions = evaluator._alert_conditions
        assert len(conditions) == 1
        assert conditions[0].condition is False
        assert conditions[0].title == "Alert"
        assert conditions[0].message == "Alert"
        assert evaluator.get_triggered_alerts() == []

    def test_alert_context_capture(self):
        """Test that alerts capture context like bar_index."""
        context = {"bar_index": 100, "time": 1600000000}
        evaluator = NodeLiteralEvaluator(context=context)

        evaluator.evaluate_script('alert("Context Alert")')
        alerts = evaluator.get_triggered_alerts()
        assert len(alerts) == 1
        assert alerts[0].bar_index == 100
        assert alerts[0].time == 1600000000
        # Host export helper
        exported = export_alerts_from_evaluator(evaluator)
        assert exported and exported[0]["message"] == "Context Alert"

    def test_once_per_bar_dedup(self):
        evaluator = NodeLiteralEvaluator(context={"bar_index": 1, "time": 10})
        evaluator.evaluate_script('alert("dup")\nalert("dup")')
        assert len(evaluator.get_triggered_alerts()) == 1

