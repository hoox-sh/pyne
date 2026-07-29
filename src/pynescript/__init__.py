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

"""Pyne — TradingView Pine Script toolchain (PyPI package ``pynescript``).

Library surface re-exports only the package version. Parse / dump / unparse
live under :mod:`pynescript.ast` (helpers often imported as
``from pynescript.ast.helper import parse, unparse``).

**Console scripts** (see ``pyproject.toml`` ``[project.scripts]``):

- ``pynescript`` → :func:`pynescript.__main__.cli` (Click CLI group)
- ``pynescript-lsp`` → :func:`pynescript.langserver.__main__.main` (stdio LSP)

**Module entrypoints:**

- ``python -m pynescript`` → same CLI as ``pynescript``
- ``python -m pynescript.langserver`` → Language Server (stdio)

**Subpackages:**

- :mod:`pynescript.ast` — parse, unparse, evaluate, lint
- :mod:`pynescript.langserver` — pygls LSP (optional ``[lsp]`` extra)
- :mod:`pynescript.ext` — Pygments lexer and integrations
- :mod:`pynescript.util` — data providers, Pine facade helpers

Version is defined in :mod:`pynescript.__about__` and exported as
:data:`__version__` (also used by the LSP server identity).
"""

from __future__ import annotations

from pynescript.__about__ import __version__


__all__ = ["__version__"]
