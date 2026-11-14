---
type: "Document"
title: "Collections"
description: "Pine collections—arrays, matrices, and maps—are mutable values that live in the evaluator context (often under var so identity persists across bars). PYNE maps them to Python…"
resource: "docs/pyne/runtime/builtins/collections.mdx"
tags: [doc, docs, pyne, runtime]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-11-14T19:45:25Z
sources:
  - id: tree
    resource: "docs/pyne/runtime/builtins/collections.mdx"
    title: "docs/pyne/runtime/builtins/collections.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/runtime/builtins/collections.mdx`.

# Outline

- Abstract
- Conceptual model
- Interface surface
  - Arrays (array.)
  - Matrices (matrix.)
  - Maps (map.)
- Internals
- Invariants & edge cases
- Worked examples
  - Rolling buffer
  - Matrix element
  - Map counter
  - Binary search on a UDT array
- Failure modes
- See also

# Mentions

- [src/pynescript/ast/evaluator](/code/src/pynescript/ast/evaluator.md)
- [src/pynescript/ast/evaluator/builtins](/code/src/pynescript/ast/evaluator/builtins.md)
- [tests](/code/tests.md)
