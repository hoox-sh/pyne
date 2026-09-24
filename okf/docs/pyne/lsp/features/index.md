# docs/pyne/lsp/features

# Concepts

* [Completion](completion.md) - textDocument/completion and completionItem/resolve from builtin metadata, module-dot triggers, and fuzzy filter.
* [Diagnostics](diagnostics.md) - Push and pull diagnostics: parse errors, lint rules, severity mapping, and code-action stubs.
* [Formatting](formatting.md) - Document and range formatting via AST parse → NodeUnparser round-trip.
* [Hover](hover.md) - textDocument/hover — Markdown documentation cards for Pine builtins from metadata.
* [Inlay Hints](inlay-hints.md) - Inferred type annotations on simple assignments — const, series, and input kinds.
* [Navigation](navigation.md) - Go-to-definition, find-references, document outline, and workspace symbol search over the ASDL AST.
* [Semantic Tokens](semantic-tokens.md) - textDocument/semanticTokens/full — AST visitor, custom legend, and LSP delta encoding.
