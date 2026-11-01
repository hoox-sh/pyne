---
type: "Document"
title: "Diagnostics"
description: "Push and pull diagnostics: parse errors, lint rules, opt-in semantic checks, severity mapping, and W001/W002/W101/W104/W105/C002 QuickFixes."
resource: "docs/pyne/lsp/features/diagnostics.mdx"
tags: [doc, docs, lsp, pyne]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-11-01T01:55:41Z
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
  * Version gating
  * Style diagnostics
  * Semantic diagnostics (opt-in)
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
