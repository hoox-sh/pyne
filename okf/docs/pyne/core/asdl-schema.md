---
type: "Document"
title: "ASDL Schema"
description: "Algebraic AST definition in Pinescript.asdl, generated dataclasses, and how schema changes flow into the pipeline."
resource: "docs/pyne/core/asdl-schema.mdx"
tags: [core, doc, docs, pyne]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:54:45Z
sources:
  - id: tree
    resource: "docs/pyne/core/asdl-schema.mdx"
    title: "docs/pyne/core/asdl-schema.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/core/asdl-schema.mdx`.

# Outline

* Abstract
* Conceptual model
* Interface surface
  * Module roots (mod)
  * Statements (stmt)
  * Expressions (expr)
  * Auxiliaries
  * Importing nodes
* Internals
  * Paths
  * Generated class shape
  * Regeneration
  * Dual nature of structures
* Invariants
* Worked examples
  * Map ASDL to a short script
  * Dump fields programmatically
* Failure modes
* See also

# Mentions

* [src/pynescript/ast](/code/src/pynescript/ast.md)
* [src/pynescript/ast/grammar/asdl](/code/src/pynescript/ast/grammar/asdl.md)
* [src/pynescript/ast/grammar/asdl/tool](/code/src/pynescript/ast/grammar/asdl/tool.md)
