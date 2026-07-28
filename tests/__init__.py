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
