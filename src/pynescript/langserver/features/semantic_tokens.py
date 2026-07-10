"""Basic semantic tokens provider (stub + partial implementation).

Marks builtins, keywords, etc. for better syntax highlighting in supporting editors.
"""

from __future__ import annotations

import lsprotocol.types as lsp

from pynescript.ast import helper as ast_helper


def handle_semantic_tokens(
    params: lsp.SemanticTokensParams,
    source: str | None,
) -> lsp.SemanticTokens | None:
    """Handle textDocument/semanticTokens/full request.

    Returns a simple token list. Full implementation would use a proper
    visitor to produce delta tokens etc.
    """
    if not source:
        return lsp.SemanticTokens(data=[])

    try:
        tree = ast_helper.parse(source)
    except Exception:
        return lsp.SemanticTokens(data=[])

    # Very basic: for now return empty. Real version would walk and emit
    # (line, col, len, token_type, modifiers) encoded.
    # This at least registers the capability without crashing.
    return lsp.SemanticTokens(data=[])
