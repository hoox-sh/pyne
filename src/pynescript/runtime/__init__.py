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

"""Bar-loop Runtime host — public package surface for multi-bar evaluation.

This package is the **source of truth** for the interpret / compile / auto
host used by the Pro API (``POST /run``), CLI tools, and library callers.

Prefer::

    from pynescript.runtime import Runtime

``backend.runtime`` remains a thin re-export shim for backward compatibility.

Layout:

- :mod:`pynescript.runtime.host` — :class:`Runtime`, host namespaces, packing
- :mod:`pynescript.runtime.evaluator` — plot-capturing :class:`CustomEvaluator`
- :mod:`pynescript.runtime.series` — :class:`PineSeries` and series-cap policy
"""

from __future__ import annotations

from pynescript.runtime.evaluator import CustomEvaluator
from pynescript.runtime.host import (
    ERROR_KIND_COMPILE,
    ERROR_KIND_DATA,
    ERROR_KIND_MODE,
    ERROR_KIND_ORDER,
    ERROR_KIND_PARSE,
    ERROR_KIND_RUNTIME,
    Barstate,
    Chart,
    Chartinfo,
    LazyCalendarContext,
    Runtime,
    Syminfo,
    Timeframe,
)
from pynescript.runtime.series import (
    DEFAULT_SERIES_MAX,
    PineSeries,
    make_pine_series,
    parse_max_bars_back_from_source,
    pineseries_history_length,
    resolve_series_cap,
    series_cap_enabled,
    series_cap_limit,
    trim_series_lists,
)


__all__ = [
    "DEFAULT_SERIES_MAX",
    "ERROR_KIND_COMPILE",
    "ERROR_KIND_DATA",
    "ERROR_KIND_MODE",
    "ERROR_KIND_ORDER",
    "ERROR_KIND_PARSE",
    "ERROR_KIND_RUNTIME",
    "Barstate",
    "Chart",
    "Chartinfo",
    "CustomEvaluator",
    "LazyCalendarContext",
    "PineSeries",
    "Runtime",
    "Syminfo",
    "Timeframe",
    "make_pine_series",
    "parse_max_bars_back_from_source",
    "pineseries_history_length",
    "resolve_series_cap",
    "series_cap_enabled",
    "series_cap_limit",
    "trim_series_lists",
]
