---
type: "Document"
title: "Diagnostics"
description: "Push and pull diagnostics: parse errors, lint rules, severity mapping, and code-action stubs."
resource: "docs/pyne/lsp/features/diagnostics.mdx"
tags: [doc, docs, lsp, pyne]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
sources:
  - id: tree
    resource: "docs/pyne/lsp/features/diagnostics.mdx"
    title: "docs/pyne/lsp/features/diagnostics.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/lsp/features/diagnostics.mdx`.

# Outline

* Abstract
* Conceptual model
* Interface surface
  * Push (always on)
  * Pull
  * Diagnostic shape
* Internals
  * Severity map
  * Parse errors
  * Quick fixes (feature module)
* Invariants and edge cases
* Worked example
* Failure modes
* See also

# Mentions

* [src/pynescript/ast](/code/src/pynescript/ast.md)
* [src/pynescript/langserver](/code/src/pynescript/langserver.md)
* [src/pynescript/langserver/features](/code/src/pynescript/langserver/features.md)
