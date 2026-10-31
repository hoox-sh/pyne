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

Installed as console scripts::

    pyne-lsp = pynescript.langserver.__main__:main
    pynescript-lsp = pynescript.langserver.__main__:main   # alias

Also runnable as::

    python -m pynescript.langserver

Constructs :class:`~pynescript.langserver.server.PynescriptLanguageServer` and
calls ``start_io()`` (JSON-RPC over stdin/stdout). This is separate from the
``pyne`` / ``pynescript`` Click CLI (:mod:`pynescript.__main__`).
"""

from __future__ import annotations

import logging

from pynescript.langserver.server import PynescriptLanguageServer


class _DropBenignCancelNoise(logging.Filter):
    """Drop pygls' "unknown message id" cancel warnings.

    Clients routinely cancel a request that has already completed (for
    example hover or semantic-tokens requests while typing). pygls looks up
    the future, finds none, and logs a warning; the request is already
    answered, so this is harmless. The server writes logs to stderr, which
    VS Code surfaces as an error, so keep the channel quiet.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        return not record.getMessage().startswith("Cancel notification for unknown message id")


def _configure_logging() -> None:
    """Install the pygls noise filter once per process."""
    logger = logging.getLogger("pygls.protocol.json_rpc")
    if not any(isinstance(existing, _DropBenignCancelNoise) for existing in logger.filters):
        logger.addFilter(_DropBenignCancelNoise())


def main() -> None:
    """Start the Language Server on stdio (blocking until the client exits)."""
    _configure_logging()
    server = PynescriptLanguageServer()
    server.start_io()


if __name__ == "__main__":
    main()
