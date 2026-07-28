#!/usr/bin/env python3
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

"""Regenerate all parity JSON fixtures from the ``.pine`` sources.

Usage::

    python tests/fixtures/parity/generate_fixtures.py

This reads every ``pine/*.pine``, runs it through ``Runtime.run`` with the
shared OHLCV dataset, and writes ``json/*.json`` with the expected events.
"""

from __future__ import annotations

import json
import os
import sys


# Ensure the project root is on sys.path
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.runtime import Runtime
from tests.fixtures.parity.ohlcv import OHLCV


FIXTURE_DIR = os.path.dirname(__file__)
PINE_DIR = os.path.join(FIXTURE_DIR, "pine")
JSON_DIR = os.path.join(FIXTURE_DIR, "json")


def main() -> None:
    os.makedirs(JSON_DIR, exist_ok=True)

    scripts = sorted(f for f in os.listdir(PINE_DIR) if f.endswith(".pine"))

    for sname in scripts:
        path = os.path.join(PINE_DIR, sname)
        with open(path) as f:
            source = f.read()

        result = Runtime().run(source, OHLCV)

        if "error" in result:
            print(f"SKIP: {sname} ({result['error'][:80]})")
            continue

        events = result["events"]
        for ev in events:
            ev.pop("script_id", None)
            ev.pop("run_id", None)

        jname = sname.replace(".pine", ".json")
        jpath = os.path.join(JSON_DIR, jname)
        with open(jpath, "w") as f:
            json.dump(events, f, indent=2)

        print(f"OK: {sname} -> {jname} ({len(events)} events)")

    print("\nDone.")


if __name__ == "__main__":
    main()
