# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

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
