---
type: "Document"
title: "Helper API"
description: "parse, sha256 LRU cache, unparse, dump, walk, literaleval, and location utilities — the public AST surface."
resource: "docs/pyne/core/helper-api.mdx"
tags: [core, doc, docs, pyne]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
sources:
  - id: tree
    resource: "docs/pyne/core/helper-api.mdx"
    title: "docs/pyne/core/helper-api.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/core/helper-api.mdx`.

# Outline

* Abstract
* Conceptual model
* Interface surface
  * parse(source, filename="<unknown", mode="exec") - AST
  * Parse cache
  * unparse(node) - str
  * dump(node, , annotatefields=True, includeattributes=False, indent=None) - str
  * literaleval(nodeorstring, context=None, datafeed=None, dataprovider=None) - Any
  * Tree navigation
  * Location utilities
  * all export list
* Internals
  * Path
  * Parse pipeline (parse)
  * Annotation algorithm (addannotations)
  * Stream helpers
* Invariants
* Worked examples
  * Inspect a tree
  * Source segment
  * Literal evaluation
  * Parse cache
* Failure modes
* See also

# Mentions

* [src/pynescript/ast](/code/src/pynescript/ast.md)
* [src/pynescript/ast/evaluator](/code/src/pynescript/ast/evaluator.md)
