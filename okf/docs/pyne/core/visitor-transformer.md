---
type: "Document"
title: "Visitor & Transformer"
description: "NodeVisitor and NodeTransformer: read-only traversal vs in-place AST rewrite with caching dispatch."
resource: "docs/pyne/core/visitor-transformer.mdx"
tags: [core, doc, docs, pyne]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
sources:
  - id: tree
    resource: "docs/pyne/core/visitor-transformer.mdx"
    title: "docs/pyne/core/visitor-transformer.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/core/visitor-transformer.mdx`.

# Outline

* Abstract
* Conceptual model
* Interface surface
  * NodeVisitor
  * NodeTransformer
  * StatementCollector
* Internals
  * Paths
  * Dispatch cache
  * In-place lists
* Invariants
* Worked examples
  * Strip all Expr statements that call plot
  * Collect all string constants
* Failure modes
* See also

# Mentions

* [src/pynescript/ast](/code/src/pynescript/ast.md)
