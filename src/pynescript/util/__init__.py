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

"""Utility helpers for market data, corpus cleanup, and host math.

Submodules:

- :mod:`pynescript.util.data` — historical OHLCV providers (mock, Yahoo, CCXT, …)
- :mod:`pynescript.util.datafeed` — async realtime feeds (CCXT Pro / mock)
- :mod:`pynescript.util.corpus_sanitize` — strip page chrome from scraped Pine
- :mod:`pynescript.util.pine_facade` — download TradingView builtin templates
- :mod:`pynescript.util.time_parts` — fast UTC calendar parts from bar ms
- :mod:`pynescript.util.itertools` — small iteration helpers (e.g. ``grouper``)
"""

from __future__ import annotations
