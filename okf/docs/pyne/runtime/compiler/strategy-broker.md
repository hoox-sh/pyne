---
type: "Document"
title: "Compile strategy broker"
description: "CompileStrategyBroker: pending orders, OHLC fills, OCA, commission, and event export."
resource: "docs/pyne/runtime/compiler/strategy-broker.mdx"
tags: [doc, docs, pyne, runtime]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
sources:
  - id: tree
    resource: "docs/pyne/runtime/compiler/strategy-broker.mdx"
    title: "docs/pyne/runtime/compiler/strategy-broker.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/runtime/compiler/strategy-broker.mdx`.

# Outline

* Abstract
* Conceptual model
* Interface surface
  * Construction (from strategy() kwargs when lowered)
  * Bar context
  * Orders
  * Fill logic (triggerprice)
  * OCA
  * Economics
  * Events
* Internals
* Invariants & edge cases
* Worked examples
  * Generated prologue (illustrative)
  * Limit buy pending
* Failure modes
* See also

# Mentions

* [src/pynescript/ast/evaluator/builtins](/code/src/pynescript/ast/evaluator/builtins.md)
* [src/pynescript/compiler](/code/src/pynescript/compiler.md)
* [tests](/code/tests.md)
