---
type: "Document"
title: "Grammar (ANTLR4)"
description: "Resource .g4 grammars, generated artifacts, INDENT/DEDENT, regeneration, and the never-edit-generated rule."
resource: "docs/pyne/core/grammar-antlr4.mdx"
tags: [core, doc, docs, pyne]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
sources:
  - id: tree
    resource: "docs/pyne/core/grammar-antlr4.mdx"
    title: "docs/pyne/core/grammar-antlr4.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/core/grammar-antlr4.mdx`.

# Outline

* Abstract
* Conceptual model
* Interface surface
  * Entry rules (PinescriptParser.g4)
  * Lexer structural facts
  * Parser structural facts
* Internals
  * Paths
  * LexerBase responsibilities
  * Regeneration
  * Downstream after grammar change
* Invariants
* Worked examples
  * Minimal grammar-level mental model
  * v6 triple-quoted strings
  * Typed names and = vs := (0.3.9)
  * Case study: targeted lexer refresh (2026-07)
* Failure modes
* See also

# Mentions

* [src/pynescript/ast](/code/src/pynescript/ast.md)
* [src/pynescript/ast/grammar/antlr4](/code/src/pynescript/ast/grammar/antlr4.md)
* [src/pynescript/ast/grammar/antlr4/resource](/code/src/pynescript/ast/grammar/antlr4/resource.md)
* [src/pynescript/ast/grammar/antlr4/tool](/code/src/pynescript/ast/grammar/antlr4/tool.md)
