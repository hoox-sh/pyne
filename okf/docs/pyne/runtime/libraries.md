---
type: "Document"
title: "Libraries"
description: "In-process library export/import, LibraryRegistry, and evaluate-order requirements."
resource: "docs/pyne/runtime/libraries.mdx"
tags: [doc, docs, pyne, runtime]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
sources:
  - id: tree
    resource: "docs/pyne/runtime/libraries.mdx"
    title: "docs/pyne/runtime/libraries.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/runtime/libraries.mdx`.

# Outline

* Abstract
* Conceptual model
* Interface surface
  * Library script
  * Consumer import
  * API on the evaluator
  * Host evaluate (0.3.7+)
  * LibraryModule
* Internals
* Invariants & edge cases
* Worked examples
  * Explicit registration
  * Path registration without pre-eval
* Failure modes
* See also

# Mentions

* [src/pynescript/ast/evaluator](/code/src/pynescript/ast/evaluator.md)
* [src/pynescript/runtime](/code/src/pynescript/runtime.md)
* [tests](/code/tests.md)
