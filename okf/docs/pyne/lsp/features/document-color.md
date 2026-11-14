---
type: "Document"
title: "Document color"
description: "textDocument/documentColor reports editor color swatches for Pine color literals. Each hit is a 0–1 RGBA ColorInformation covering the AST node. textDocument/colorPresentation…"
resource: "docs/pyne/lsp/features/document-color.mdx"
tags: [doc, docs, lsp, pyne]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-11-14T19:45:25Z
sources:
  - id: tree
    resource: "docs/pyne/lsp/features/document-color.mdx"
    title: "docs/pyne/lsp/features/document-color.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/lsp/features/document-color.mdx`.

# Outline

- Abstract
- Conceptual model
- Interface surface
  - Reported swatches
  - Pine transparency
  - colorPresentation
- Internals
- Invariants and edge cases
- Worked example
- Failure modes
- See also

# Mentions

- [src/pynescript/ast/evaluator/builtins](/code/src/pynescript/ast/evaluator/builtins.md)
- [src/pynescript/langserver](/code/src/pynescript/langserver.md)
- [src/pynescript/langserver/features](/code/src/pynescript/langserver/features.md)
- [tests](/code/tests.md)
