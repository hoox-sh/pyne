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

"""Optional hosted script runner for Flask / Docker / VPS / Containers.

Off unless ``PYNE_RUNNER`` is truthy (``1`` / ``true`` / ``yes`` / ``on``).
When on: SQLite registry + ``/scripts`` / ``/cron/*``. Background bar-close
polling is a second switch (``PYNE_RUNNER_SCHEDULER``).
"""

from __future__ import annotations

import os


def _flag(name: str, default: str = "0") -> bool:
    raw = os.environ.get(name, default).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def runner_enabled() -> bool:
    """Master switch — HTTP registry + cron tick endpoints."""
    return _flag("PYNE_RUNNER")


def scheduler_enabled() -> bool:
    """In-process poll loop (bar-close). Requires :func:`runner_enabled`."""
    return runner_enabled() and _flag("PYNE_RUNNER_SCHEDULER")


def poll_seconds() -> float:
    """Scheduler interval. Default 60s. Floor 5s."""
    raw = os.environ.get("PYNE_RUNNER_POLL_SECONDS", "60").strip()
    try:
        value = float(raw)
    except ValueError:
        value = 60.0
    return max(5.0, value)


def db_path() -> str:
    """SQLite file for deployed scripts + cron state."""
    override = os.environ.get("PYNE_RUNNER_DB", "").strip()
    if override:
        return override
    if os.path.isdir("/data"):
        return "/data/runner.db"
    return os.path.join(os.environ.get("TMPDIR", "/tmp"), "pyne_runner.db")
