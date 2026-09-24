---
type: "Document"
title: "Unparser"
description: "NodeUnparser: precedence-aware AST → Pine Script source regeneration."
resource: "docs/pyne/core/unparser.mdx"
tags: [core, doc, docs, pyne]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
sources:
  - id: tree
    resource: "docs/pyne/core/unparser.mdx"
    title: "docs/pyne/core/unparser.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/core/unparser.mdx`.

# Outline

* Abstract
* Conceptual model
* Interface surface
  * Precedence (low → high binding)
  * Buffer helpers (internal but useful when subclassing)
  * Node coverage (high level)
* Internals
  * Path
  * Visit vs traverse
  * If / else if chains
  * Type body ordering
  * Constants
* Invariants
* Worked examples
  * Precedence
  * Function forms
  * Reassignment vs declaration
* Failure modes
* See also

# Mentions

* [src/pynescript/ast](/code/src/pynescript/ast.md)
