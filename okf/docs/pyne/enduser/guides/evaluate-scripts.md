---
type: "Document"
title: "Evaluate Scripts"
description: "Run Pine expressions and multi-bar scripts with literaleval, pynescript.runtime.Runtime (libraries=, timeoutseconds, mode), data providers, and strategy events."
resource: "docs/pyne/enduser/guides/evaluate-scripts.mdx"
tags: [doc, docs, enduser, pyne]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
sources:
  - id: tree
    resource: "docs/pyne/enduser/guides/evaluate-scripts.mdx"
    title: "docs/pyne/enduser/guides/evaluate-scripts.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/enduser/guides/evaluate-scripts.mdx`.

# Outline

* Abstract
* Conceptual model
* Runtime modes (interpret | compile | auto)
  * Warm compile / prewarm
  * When compile falls back (or is skipped)
  * Plot series parity
  * Compare interpret vs compile (corpus harness)
* Interface surface
  * Expression evaluation
  * Script evaluation helper
  * Bar-loop Runtime (package SoT · HTTP contract shape)
  * Persistent interpret sessions (0.6.1)
  * Data providers and feeds
  * Educational bar executor
* Internals (repo paths)
* Invariants & edge cases
* Worked examples
  * RSI on a synthetic series
  * Multi-indicator expressions
  * Full script via Runtime
  * Strategy event inspection
  * request. with resolved sources
* Failure modes
* See also

# Mentions

* [scripts](/code/scripts.md)
* [src/pynescript](/code/src/pynescript.md)
* [src/pynescript/ast](/code/src/pynescript/ast.md)
* [src/pynescript/ast/evaluator](/code/src/pynescript/ast/evaluator.md)
* [src/pynescript/runtime](/code/src/pynescript/runtime.md)
* [src/pynescript/util](/code/src/pynescript/util.md)
* [tests](/code/tests.md)
