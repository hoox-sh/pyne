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

"""PyneScript Test Suite.

Regression tests for parse/unparse stability with actual Pine Script examples
from TradingView, organized by feature tier:

- Tier 1-2: Basic expressions and statements
- Tier 3-4: Collections and advanced features
- Tier 5-7: Indicators and technical analysis
- Tier 8: Advanced constructs
- UDT: User-defined types and methods
- Evaluator: AST evaluation and built-in functions

Key Test Data:
- tests/data/builtin_scripts/: Actual Pine Script code downloaded from TradingView
- Tests verify parse -> dump -> unparse round-trip consistency
"""

from __future__ import annotations
