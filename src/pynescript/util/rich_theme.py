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

"""Shared Rich theme for the ``pyne`` CLI (HOOX landing **volt** pack).

Hex snapshot of ``:root[data-color-pack="volt"]`` in the landing
``app/globals.css`` (oklch → sRGB). ``/pyne`` routes set ``data-color-pack=volt``.
"""

from __future__ import annotations

import os
import sys
from typing import Any

# ── volt pack (landing ``/pyne``) ───────────────────────────────────────────
# Accent unchanged; surfaces follow the current volt block (muted/border
# lifted for contrast vs the older showcase snapshot).
ACCENT = "#B7EF09"  # --accent / --pack-volt     oklch(0.88 0.22 125)
ACCENT_DIM = "#76A000"  # darker volt pulse         oklch(0.65 0.18 125)
FG = "#EEEEEE"  # --foreground                 oklch(0.95 0 0)
MUTED = "#9E9F98"  # --muted-foreground           oklch(0.70 0.01 110)
PROSE = "#C4C5BF"  # --prose                      oklch(0.82 0.008 110)
BORDER = "#3D3E37"  # --border                     oklch(0.36 0.012 110)
BACKGROUND = "#030302"  # --background                oklch(0.10 0.005 110)
CARD = "#0C0C0A"  # --card                       oklch(0.155 0.006 110)
OK = ACCENT
WARN = "#EBA941"  # terminal amber               oklch(0.78 0.14 75)
FAIL = "#E7000B"  # brand destructive            oklch(0.577 0.245 27)


# Backward-compatible aliases used by older call sites
_PYNE_ACCENT = ACCENT
_PYNE_ACCENT_DIM = ACCENT_DIM
_PYNE_FG = FG
_PYNE_MUTED = MUTED
_PYNE_BORDER = BORDER
_PYNE_OK = OK
_PYNE_WARN = WARN
_PYNE_FAIL = FAIL


def has_rich() -> bool:
    try:
        import rich  # noqa: F401

        return True
    except ImportError:
        return False


def use_rich(*, force: bool = False, plain: bool = False) -> bool:
    if plain or os.environ.get("NO_COLOR"):
        return False
    if not has_rich():
        return False
    if force:
        return True
    return bool(sys.stdout.isatty())


def rich_theme() -> Any:
    """Return a Rich ``Theme`` for PYNE volt styles."""
    from rich.theme import Theme

    return Theme(
        {
            "pyne.accent": f"bold {ACCENT}",
            "pyne.accent_dim": ACCENT_DIM,
            "pyne.fg": FG,
            "pyne.muted": MUTED,
            "pyne.prose": PROSE,
            "pyne.ok": f"bold {OK}",
            "pyne.fail": f"bold {FAIL}",
            "pyne.warn": f"bold {WARN}",
            "pyne.border": BORDER,
            "pyne.card": CARD,
            "pyne.bg": BACKGROUND,
        }
    )


def console(*, force: bool = False, plain: bool = False) -> Any | None:
    """Rich console when enabled; honors ``NO_COLOR`` and ``--plain``.

    When *force* is true, pin truecolor so redirected / CI runs still render
    the volt hex palette.
    """
    if not use_rich(force=force, plain=plain):
        return None
    from rich.console import Console

    if force:
        return Console(force_terminal=True, color_system="truecolor", theme=rich_theme())
    return Console(theme=rich_theme())
