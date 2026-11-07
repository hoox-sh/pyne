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

"""Background healer for holes in engine-owned OHLCV series.

A stored series can lose minutes in the middle: the venue feed jumps over a
stall, an upstream walk starts after the stored anchor, or a `provide` batch is
sparse. A hole is not cosmetic — every script evaluated over that window gets a
Pine `na` for the missing bars, so a chart shows a gap in its indicators, and
`GET /data/series/bars` readers (AXIS) see an engine series that is internally
short even though its tip is current.

The tick path already fills one page per tick (:func:`backend.api.data_series.
_fill_one_gap`), but only while a client data session is running. A quiet tab,
or a hole the tick gave up on, used to leave the series short of minutes until
an unrelated full fetch happened to cover it.

This module closes that hole (literally) with one bounded sweep: every
:data:`SWEEP_S` seconds, for series written recently, fill up to
:data:`MAX_PAGES` pages into the widest hole. It never raises, never blocks a
request, and touches at most :data:`MAX_SERIES` series per sweep.

Env knobs:

- ``PYNE_GAP_HEAL=0`` disables the healer entirely.
- ``PYNE_GAP_SWEEP_S`` sweep interval in seconds (default 60).
- ``PYNE_GAP_HEAL_MAX_SERIES`` series per sweep (default 4).
- ``PYNE_GAP_HEAL_MAX_PAGES`` pages per series per sweep (default 1).
- ``PYNE_GAP_ACTIVE_S`` only heal series written in this window (default 900).
"""

from __future__ import annotations

import logging
import os
import threading

from typing import Any

from backend.api import data_series
from backend.datastore import series as series_store


logger = logging.getLogger(__name__)

#: Sweep interval in seconds.
SWEEP_S = 60.0
#: Series healed per sweep (bounds upstream work per cycle).
MAX_SERIES = 4
#: Pages written per series per sweep (one page ≤ ``TICK_MAX_BARS`` bars).
MAX_PAGES = 1
#: Only series written within this window are healed (a dormant series is not
#: worth an upstream walk).
ACTIVE_S = 900

_started = False
_start_guard = threading.Lock()
_thread: threading.Thread | None = None
# Sweep telemetry for `/stats` (in-process; resets with the worker).
_sweeps = 0
_filled = 0
_last_sweep_at = 0.0


def stats() -> dict[str, Any]:
    """Healer state for ``/stats``: armed, sweep count, pages filled, last sweep."""
    return {
        "enabled": enabled(),
        "armed": bool(_started and _thread is not None and _thread.is_alive()),
        "sweeps": _sweeps,
        "filled": _filled,
        "last_sweep_at": int(_last_sweep_at) if _last_sweep_at else None,
        "sweep_s": _env_float("PYNE_GAP_SWEEP_S", SWEEP_S),
    }


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def enabled() -> bool:
    """Whether the healer may run in this process (``PYNE_GAP_HEAL=0`` opts out)."""
    return os.environ.get("PYNE_GAP_HEAL", "").strip() not in ("0", "false", "off", "no")


def sweep_once(now_s: int | None = None) -> dict[str, Any]:
    """Heal holes for a bounded set of recently used series.

    @param now_s clock override for tests
    @returns counters: ``series`` scanned, ``holes`` seen, ``filled`` pages
    """
    now = series_store.now_seconds() if now_s is None else int(now_s)
    active_s = int(_env_float("PYNE_GAP_ACTIVE_S", float(ACTIVE_S)))
    max_series = int(_env_int("PYNE_GAP_HEAL_MAX_SERIES", MAX_SERIES))
    max_pages = int(_env_int("PYNE_GAP_HEAL_MAX_PAGES", MAX_PAGES))
    report: dict[str, Any] = {"series": 0, "holes": 0, "filled": 0}
    try:
        store = series_store.get_store()
        keys = store.active_keys(updated_since=now - active_s, limit=max_series * 4)
    except Exception as exc:  # a store failure must not kill the thread
        logger.warning("gap healer: store unavailable: %s", exc)
        return report
    for key in keys:
        if report["series"] >= max_series:
            break
        try:
            step = key.interval_seconds
            if not store.holes(key, step, limit=1):
                continue
            report["series"] += 1
            report["holes"] += 1
            report["filled"] += data_series.heal_series_gaps(
                key,
                max_pages=max_pages,
                now_s=now,
            )
        except Exception as exc:  # per-series failure never stops the sweep
            logger.warning("gap healer: %s failed: %s", key.text, exc)
    global _sweeps, _filled, _last_sweep_at
    _sweeps += 1
    _filled += int(report["filled"])
    _last_sweep_at = float(now)
    if report["filled"]:
        logger.info(
            "gap healer: filled %s page(s) across %s series",
            report["filled"],
            report["series"],
        )
    return report


def _loop() -> None:
    interval = _env_float("PYNE_GAP_SWEEP_S", SWEEP_S)
    while True:
        threading.Event().wait(interval)
        try:
            sweep_once()
        except Exception as exc:  # never let the thread die
            logger.warning("gap healer sweep failed: %s", exc)


def start_gap_healer() -> bool:
    """Start the daemon sweep once per process. @returns whether it is running."""
    global _started, _thread
    if not enabled():
        return False
    if os.environ.get("PYTEST_CURRENT_TEST"):
        # A background sweep must never mutate a test's store mid-case (the
        # suite creates holes on purpose). ``sweep_once`` stays callable.
        return False
    with _start_guard:
        if _started and _thread is not None and _thread.is_alive():
            return True
        thread = threading.Thread(target=_loop, name="pyne-gap-healer", daemon=True)
        thread.start()
        _thread = thread
        _started = True
    logger.info(
        "gap healer started (sweep %ss, %s series/sweep)",
        _env_float("PYNE_GAP_SWEEP_S", SWEEP_S),
        _env_int("PYNE_GAP_HEAL_MAX_SERIES", MAX_SERIES),
    )
    return True


def _reset_gap_healer_for_tests() -> None:
    """Forget the started flag so a test can start/stop the sweep."""
    global _started, _thread
    with _start_guard:
        _started = False
        _thread = None
