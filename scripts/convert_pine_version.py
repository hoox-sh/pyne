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

"""CLI wrapper for :mod:`pynescript.util.pine_convert` (roadmap L1).

::

    python scripts/convert_pine_version.py <v5|v6> <file.pine>

``v5`` rewrites toward v5; ``v6`` (or any other token) toward v6.
Converted source is printed to stdout. Prefer ``pynescript convert``.
"""

from __future__ import annotations

import sys

from pathlib import Path

from pynescript.util.pine_convert import convert_pine


_MIN_ARGS = 3


def main() -> None:
    if len(sys.argv) < _MIN_ARGS:
        sys.stderr.write("Usage: python scripts/convert_pine_version.py <v5|v6> <file.pine>\n")
        raise SystemExit(1)
    direction = sys.argv[1].lower().lstrip("v")
    path = Path(sys.argv[2])
    src = path.read_text(encoding="utf-8")
    to = 5 if direction == "5" else 6
    sys.stdout.write(convert_pine(src, to=to))
    if not src.endswith("\n"):
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
