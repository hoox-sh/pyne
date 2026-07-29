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

"""stdio entry point for the Pine Script Language Server.

Installed as console script::

    pynescript-lsp = pynescript.langserver.__main__:main

Also runnable as::

    python -m pynescript.langserver

Constructs :class:`~pynescript.langserver.server.PynescriptLanguageServer` and
calls ``start_io()`` (JSON-RPC over stdin/stdout). This is separate from the
``pynescript`` Click CLI (:mod:`pynescript.__main__`).
"""

from __future__ import annotations

from pynescript.langserver.server import PynescriptLanguageServer


def main() -> None:
    """Start the Language Server on stdio (blocking until the client exits)."""
    server = PynescriptLanguageServer()
    server.start_io()


if __name__ == "__main__":
    main()
