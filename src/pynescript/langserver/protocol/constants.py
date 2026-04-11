# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

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
