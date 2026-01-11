# Copyright 2024-2025 Yunseong Hwang, jango_blockchained
#
# Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.gnu.org/licenses/lgpl-3.0.en.html
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: LGPL-3.0-or-later

import pytest
from pynescript.ast.evaluator import NodeLiteralEvaluator
from pynescript.ast.evaluator.builtins.alerts import AlertEvent

class TestAlerts:
    def test_alert_function(self):
        """Test alert() function execution and event capture."""
        evaluator = NodeLiteralEvaluator()
        
        # Test basic alert
        evaluator.evaluate_script('alert("Simple Alert")')
        alerts = evaluator.get_triggered_alerts()
        assert len(alerts) == 1
        assert alerts[0].message == "Simple Alert"
        assert alerts[0].freq == "freq_once_per_bar"
        
        # Test alert with frequency
        evaluator.clear_alerts()
        evaluator.evaluate_script('alert("Complex Alert", "freq_all")')
        alerts = evaluator.get_triggered_alerts()
        assert len(alerts) == 1
        assert alerts[0].message == "Complex Alert"
        assert alerts[0].freq == "freq_all"

    def test_alertcondition_function(self):
        """Test alertcondition() registration."""
        evaluator = NodeLiteralEvaluator()
        
        # Test basic alertcondition
        evaluator.evaluate_script('alertcondition(true, "Title", "Message")')
        # Access private member for testing since there's no public getter for conditions yet
        conditions = evaluator._alert_conditions
        assert len(conditions) == 1
        assert conditions[0].condition is True
        assert conditions[0].title == "Title"
        assert conditions[0].message == "Message"
        
        # Test alertcondition with defaults
        evaluator.clear_alerts()
        evaluator.evaluate_script('alertcondition(false)')
        conditions = evaluator._alert_conditions
        assert len(conditions) == 1
        assert conditions[0].condition is False
        assert conditions[0].title == "Alert"
        assert conditions[0].message == "Alert"

    def test_alert_context_capture(self):
        """Test that alerts capture context like bar_index."""
        context = {"bar_index": 100, "time": 1600000000}
        evaluator = NodeLiteralEvaluator(context=context)
        
        evaluator.evaluate_script('alert("Context Alert")')
        alerts = evaluator.get_triggered_alerts()
        assert len(alerts) == 1
        assert alerts[0].bar_index == 100
        assert alerts[0].time == 1600000000
