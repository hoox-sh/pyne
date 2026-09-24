---
type: "Document"
title: "Strategy events"
description: "StrategyEvent shape, emission points, parity corpus, and host serialization."
resource: "docs/pyne/runtime/events.mdx"
tags: [doc, docs, pyne, runtime]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:54:13Z
sources:
  - id: tree
    resource: "docs/pyne/runtime/events.mdx"
    title: "docs/pyne/runtime/events.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/runtime/events.mdx`.

# Outline

* Abstract
* Conceptual model
* Interface surface
  * StrategyEvent fields
  * Emission sources
  * Host collection pattern
  * Compile path
* Internals
* Invariants & edge cases
* Worked examples
  * Expected single entry
  * Cancel after OCA
* Failure modes
* See also

# Mentions

* [src/pynescript/ast/evaluator](/code/src/pynescript/ast/evaluator.md)
* [src/pynescript/ast/evaluator/builtins](/code/src/pynescript/ast/evaluator/builtins.md)
* [src/pynescript/compiler](/code/src/pynescript/compiler.md)
* [tests](/code/tests.md)
* [tests/fixtures/parity](/code/tests/fixtures/parity.md)
