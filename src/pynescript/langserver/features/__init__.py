# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

"""LSP feature implementations.

Provides implementations for LSP methods:
- diagnostics: textDocument/publishDiagnostics, pull diagnostics
- (more features coming in future phases)
"""

from __future__ import annotations

from pynescript.langserver.features import diagnostics


__all__ = ["diagnostics"]
