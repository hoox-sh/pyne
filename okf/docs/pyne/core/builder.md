---
type: "Document"
title: "AST Builder"
description: "PinescriptASTBuilder: ANTLR parse-tree visitor that constructs ASDL nodes, locations, and comment kinds."
resource: "docs/pyne/core/builder.mdx"
tags: [core, doc, docs, pyne]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
sources:
  - id: tree
    resource: "docs/pyne/core/builder.mdx"
    title: "docs/pyne/core/builder.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/core/builder.mdx`.

# Outline

* Abstract
* Conceptual model
* Interface surface
  * Locator API
  * Comment kinds
  * Store context
  * Representative visit methods
* Internals
  * Path
  * Statement list flattening
  * Export flag
  * Assign vs ReAssign
  * Field / enum members
* Invariants
* Worked examples
  * What x = close + 1 becomes
  * Export const initialization
  * Typed UDF (FunctionDef.returns)
  * Debugging a missing visitor
* Failure modes
* See also

# Mentions

* [src/pynescript/ast](/code/src/pynescript/ast.md)
* [src/pynescript/ast/grammar/antlr4](/code/src/pynescript/ast/grammar/antlr4.md)
