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

"""CLI entry point for the Pynescript Language Server.

Usage:
    python -m pynescript.langserver
    pynescript lsp
    pynescript lsp --tcp --port 8765
"""

from __future__ import annotations

from pynescript.langserver.server import PynescriptLanguageServer


def main() -> None:
    """Start the Pynescript Language Server."""
    server = PynescriptLanguageServer()
    server.start_io()


if __name__ == "__main__":
    main()
