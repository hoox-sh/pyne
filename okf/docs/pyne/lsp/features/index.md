# docs/pyne/lsp/features

# Concepts

* [Completion](completion.md) - textDocument/completion and completionItem/resolve from builtin metadata, module-dot triggers, and fuzzy filter.
* [Diagnostics](diagnostics.md) - Push and pull diagnostics: parse errors, lint rules, opt-in semantic checks, severity mapping, and W001/W002/W101/W104/W105/C002 QuickFixes.
* [Document color](document-color.md) - textDocument/documentColor and colorPresentation for hex, color., and literal color calls.
* [Document links](document-link.md) - textDocument/documentLink for http(s) URLs in comments and strings, and documentLink/resolve tooltip.
* [Folding ranges](folding.md) - textDocument/foldingRange for Pine blocks, type/enum/function bodies, and //region comments.
* [Formatting](formatting.md) - Document, range, and on-type formatting via AST parse → NodeUnparser round-trip.
* [Hover](hover.md) - textDocument/hover — Markdown cards for builtins, types, namespaces, keywords, and user declarations.
* [Inlay Hints](inlay-hints.md) - Display-only builtin parameter names. Hints never insert text or modify the document.
* [Linked editing](linked-editing.md) - textDocument/linkedEditingRange — live multi-cursor ranges for user identifiers.
* [Navigation](navigation.md) - Go-to-definition, find-references, document highlight, rename across open documents, document outline, and workspace symbol search over the ASDL AST.
* [Selection ranges](selection-range.md) - textDocument/selectionRange expands from an ident or smallest AST node to the enclosing statement and block.
* [Semantic Tokens](semantic-tokens.md) - textDocument/semanticTokens/full and /range — AST visitor, custom legend, and LSP delta encoding.
