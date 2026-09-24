---
type: "Document"
title: "Expressions and statements"
description: "How the AST walker evaluates operations, calls, control flow, assignments, and user definitions."
resource: "docs/pyne/runtime/expressions-statements.mdx"
tags: [doc, docs, pyne, runtime]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
sources:
  - id: tree
    resource: "docs/pyne/runtime/expressions-statements.mdx"
    title: "docs/pyne/runtime/expressions-statements.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/runtime/expressions-statements.mdx`.

# Outline

* Abstract
* Conceptual model
* Interface surface
  * Expressions (ExpressionEvaluator)
  * Names (NameEvaluator)
  * Statements (StatementEvaluator)
  * Calls and multi-dispatch
* Internals
* Invariants & edge cases
* Worked examples
  * Ternary and comparison chain
  * User function with series
  * once (August 2026)
  * Intrabar rollback on realtime ticks (0.6.0)
  * Method multi-dispatch sketch
* Failure modes
* See also

# Mentions

* [src/pynescript/ast/evaluator](/code/src/pynescript/ast/evaluator.md)
