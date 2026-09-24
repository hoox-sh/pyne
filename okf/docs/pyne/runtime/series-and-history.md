---
type: "Document"
title: "Series and history"
description: "Pine series model: history operator, na propagation, var/varip persistence, and bar-mode scalars."
resource: "docs/pyne/runtime/series-and-history.mdx"
tags: [doc, docs, pyne, runtime]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
sources:
  - id: tree
    resource: "docs/pyne/runtime/series-and-history.mdx"
    title: "docs/pyne/runtime/series-and-history.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/runtime/series-and-history.mdx`.

# Outline

* Abstract
* Conceptual model
* Interface surface
  * History operator (visitSubscript)
  * Series wrappers
  * Assigning host series (copy, not alias)
  * UDF series parameters (0.6.2)
  * var / varip / const
  * na propagation
  * ta.highestbars / ta.lowestbars offsets
  * Bar mode vs full-series mode
  * Host series caps (PYNESERIESCAP)
  * Unused derived series (0.3.10)
* Internals
* Invariants & edge cases
* Worked examples
  * History lag
  * var counter
  * Element-wise NA
* Failure modes
* See also

# Mentions

* [src/pynescript/ast/evaluator](/code/src/pynescript/ast/evaluator.md)
* [src/pynescript/ast/evaluator/builtins](/code/src/pynescript/ast/evaluator/builtins.md)
* [src/pynescript/ast/evaluator/builtins/technical_submodules](/code/src/pynescript/ast/evaluator/builtins/technical_submodules.md)
* [src/pynescript/runtime](/code/src/pynescript/runtime.md)
