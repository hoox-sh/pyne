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

"""LSP protocol constants."""

from __future__ import annotations

from lsprotocol import types as lsp


DIAGNOSTIC_SEVERITY_MAP = {
    "E": lsp.DiagnosticSeverity.Error,
    "W": lsp.DiagnosticSeverity.Warning,
    "C": lsp.DiagnosticSeverity.Information,
    "I": lsp.DiagnosticSeverity.Hint,
}

COMPLETION_ITEM_KINDS = {
    "function": lsp.CompletionItemKind.Function,
    "method": lsp.CompletionItemKind.Method,
    "variable": lsp.CompletionItemKind.Variable,
    "type": lsp.CompletionItemKind.TypeParameter,
    "keyword": lsp.CompletionItemKind.Keyword,
    "constant": lsp.CompletionItemKind.Constant,
    "class": lsp.CompletionItemKind.Class,
    "module": lsp.CompletionItemKind.Module,
    "property": lsp.CompletionItemKind.Property,
    "snippet": lsp.CompletionItemKind.Snippet,
}

SYMBOL_KINDS = {
    "script": lsp.SymbolKind.File,
    "function": lsp.SymbolKind.Function,
    "type": lsp.SymbolKind.Class,
    "variable": lsp.SymbolKind.Variable,
    "parameter": lsp.SymbolKind.Variable,
    "annotation": lsp.SymbolKind.Namespace,
}
