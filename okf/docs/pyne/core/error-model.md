---
type: "Document"
title: "Error Model"
description: "SyntaxError, IndentationError, SyntaxErrorDetails, and PinescriptErrorListener bridge from ANTLR to diagnostics."
resource: "docs/pyne/core/error-model.mdx"
tags: [core, doc, docs, pyne]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
sources:
  - id: tree
    resource: "docs/pyne/core/error-model.mdx"
    title: "docs/pyne/core/error-model.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/core/error-model.mdx`.

# Outline

* Abstract
* Conceptual model
* Interface surface
  * SyntaxErrorDetails (NamedTuple)
  * SyntaxError(Exception)
  * IndentationError(SyntaxError)
  * PinescriptErrorListener
* Internals
  * Paths
  * Filename resolution order (InputStream)
  * End span from offending token
  * Relationship to linter E001
  * LSP / tooling
* Invariants
* Worked examples
  * Catching a parse error
  * Distinguishing indentation
  * Manual construction (tests)
* Failure modes
* See also

# Mentions

* [src/pynescript/ast](/code/src/pynescript/ast.md)
* [src/pynescript/ast/grammar/antlr4](/code/src/pynescript/ast/grammar/antlr4.md)
* [src/pynescript/ast/grammar/antlr4/resource](/code/src/pynescript/ast/grammar/antlr4/resource.md)
