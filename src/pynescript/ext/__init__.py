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

"""PyneScript Extensions and Integrations.

Optional integrations with external tools and frameworks:
- pygments: Syntax highlighting lexer for Pine Script
- nautilus_trader: Integration with Nautilus Trader trading bot framework
- jupyter: Jupyter notebook integration with magic commands and helpers

Usage in Jupyter:
    from pynescript.ext.jupyter import load_ipython_extension
    load_ipython_extension(ipython)
"""

from __future__ import annotations
