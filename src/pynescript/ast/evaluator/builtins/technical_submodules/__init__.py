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

"""``ta.*`` indicator implementation submodules for the evaluator.

Split from a monolithic technical module. Each submodule defines a mixin of
``_builtin_ta_*`` handlers that subclass
:class:`~.core.TechnicalHelpers`. They are composed by
:class:`~pynescript.ast.evaluator.builtins.technical.TechnicalAnalysisMixin`,
which builds the dispatch table consumed by
:class:`~pynescript.ast.evaluator.builtins.BuiltinEvaluator`.

Modules
-------
- **core** — series/period validation and shared TA helpers
- **basic** / **common** / **moving_averages** — core MAs and utilities
- **oscillators** / **volatility** / **volume** — classic indicator families
- **patterns** / **economics** / **strategies** / **synthesizer** / **advanced**
  — pattern recognition and extended analytics
"""

from __future__ import annotations
