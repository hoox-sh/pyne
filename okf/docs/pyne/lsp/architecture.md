---
type: "Document"
title: "LSP Architecture"
description: "PynescriptLanguageServer lifecycle, Workspace document model, capability declaration, and STDIO transport."
resource: "docs/pyne/lsp/architecture.mdx"
tags: [doc, docs, lsp, pyne]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
sources:
  - id: tree
    resource: "docs/pyne/lsp/architecture.mdx"
    title: "docs/pyne/lsp/architecture.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/lsp/architecture.mdx`.

# Outline

* Abstract
* Conceptual model
* Interface surface
  * Process entry
  * Server class
  * Document sync
  * Capability set (declared)
* Internals
  * Workspace
  * Feature dispatch pattern
  * Pull diagnostics
  * Workspace symbols
* Invariants and edge cases
* Worked example — minimal initialize
* Failure modes
* See also

# Mentions

* [src/pynescript](/code/src/pynescript.md)
* [src/pynescript/langserver](/code/src/pynescript/langserver.md)
