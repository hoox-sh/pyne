# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

"""Pynescript Language Server.

Provides Language Server Protocol (LSP) support for Pine Script,
enabling professional IDE integration in VS Code, Neovim, Zed, and more.

Usage:
    python -m pynescript.langserver
    pynescript lsp
"""

from __future__ import annotations

from pynescript.langserver.server import PynescriptLanguageServer
from pynescript.langserver.workspace import Workspace, TextDocumentState

__version__ = "0.1.0"
__all__ = [
    "PynescriptLanguageServer",
    "Workspace",
    "TextDocumentState",
]
