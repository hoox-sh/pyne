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

"""Pynescript Pro API backend package.

Flask application, Pine runtime host, API blueprints, auth middleware, and
preview/backtest services. Run with ``python -m backend.app`` (default
``:5002``) or via gunicorn in production.

Layout:

- :mod:`backend.app` — Flask app factory surface and free/auth HTTP routes
- :mod:`backend.runtime` — bar-mode Runtime host (interpret / compile / auto)
- :mod:`backend.evaluator` — plot-capturing :class:`CustomEvaluator`
- :mod:`backend.series` — ``PineSeries`` and host list-cap policy
- :mod:`backend.api` — preview, LSP-HTTP, git OAuth blueprints
- :mod:`backend.middleware` — API keys, schemas, store backends
- :mod:`backend.services` — chart PNG rendering and quick backtests
- :mod:`backend.alert_forwarder` — alert webhook delivery for ``POST /run``
"""

from __future__ import annotations
