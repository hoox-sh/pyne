---
type: "Document"
title: "Technical analysis (ta.*)"
description: "ta. indicators: series helpers, bar mode, interpret↔compile parity, and submodule layout."
resource: "docs/pyne/runtime/builtins/technical.mdx"
tags: [doc, docs, pyne, runtime]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
sources:
  - id: tree
    resource: "docs/pyne/runtime/builtins/technical.mdx"
    title: "docs/pyne/runtime/builtins/technical.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/runtime/builtins/technical.mdx`.

# Outline

* Abstract
* Conceptual model
  * Incremental hot path
* Interface surface
  * Argument conventions
  * Stateful crosses
* Internals
* Interpret ↔ compile parity
  * Parity harness
* Invariants & edge cases
* Worked examples
  * Classic overlay
  * Cross entry signal
  * Multi-value unpack
* Failure modes
* See also

# Mentions

* [scripts](/code/scripts.md)
* [src/pynescript/ast/evaluator/builtins](/code/src/pynescript/ast/evaluator/builtins.md)
* [src/pynescript/compiler](/code/src/pynescript/compiler.md)
* [tests](/code/tests.md)
