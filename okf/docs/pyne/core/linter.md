---
type: "Document"
title: "Linter"
description: "PineLinter static rules: syntax via parse, version, deprecations, naming, style codes."
resource: "docs/pyne/core/linter.mdx"
tags: [core, doc, docs, pyne]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
sources:
  - id: tree
    resource: "docs/pyne/core/linter.mdx"
    title: "docs/pyne/core/linter.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/core/linter.mdx`.

# Outline

* Abstract
* Conceptual model
* Interface surface
  * LintWarning
  * PineLinter.lint(source, filename="<input") - list[LintWarning]
  * File helper
* Rule catalog
  * Syntax
  * Version
  * Deprecated patterns (checkdeprecated)
  * Naming (checknaming)
  * Style (checkstyle)
* Internals
  * Path
  * Design stance
  * Integration points
* Invariants
* Worked examples
  * Clean modern script
  * Missing version
  * Programmatic filter
* Failure modes
* See also

# Mentions

* [src/pynescript/ast](/code/src/pynescript/ast.md)
