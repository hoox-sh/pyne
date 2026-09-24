---
type: "Document"
title: "Library API"
description: "Embed pynescript: parse, dump, unparse, walk, transform, and lint Pine Script™ from Python."
resource: "docs/pyne/enduser/guides/library-api.mdx"
tags: [doc, docs, enduser, pyne]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
sources:
  - id: tree
    resource: "docs/pyne/enduser/guides/library-api.mdx"
    title: "docs/pyne/enduser/guides/library-api.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/enduser/guides/library-api.mdx`.

# Outline

* Abstract
* Conceptual model
* Interface surface
  * Imports
  * parse(source, filename="<unknown", mode="exec") - AST
  * unparse(node) - str
  * dump(node, , annotatefields=True, includeattributes=False, indent=None) - str
  * walk(node) - Iterator[AST]
  * Location helpers
  * Visitors and transformers
  * Linter
  * literaleval (bridge to evaluation)
* Internals (repo paths)
* Invariants & edge cases
* Worked examples
  * Strategy hyperparameter search (0.3.12)
  * End-to-end inspect
  * Collect all call names
  * Lint programmatically with fail semantics
  * Expression mode for tooling
* Failure modes
* See also

# Mentions

* [src/pynescript/ast](/code/src/pynescript/ast.md)
* [src/pynescript/ast/grammar/asdl](/code/src/pynescript/ast/grammar/asdl.md)
