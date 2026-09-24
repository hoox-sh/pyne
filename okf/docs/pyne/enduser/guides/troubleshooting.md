---
type: "Document"
title: "Troubleshooting"
description: "Diagnose pynescript install, parse, lint, evaluation, LSP, data providers, and Pro API failures with concrete checks."
resource: "docs/pyne/enduser/guides/troubleshooting.mdx"
tags: [doc, docs, enduser, pyne]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
sources:
  - id: tree
    resource: "docs/pyne/enduser/guides/troubleshooting.mdx"
    title: "docs/pyne/enduser/guides/troubleshooting.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/enduser/guides/troubleshooting.mdx`.

# Outline

* Abstract
* Conceptual model
* Interface surface (diagnostic commands)
* Internals (where errors originate)
* Invariants & edge cases
* Worked examples (by symptom)
  * 1. pyne / pynescript: command not found
  * 2. ModuleNotFoundError: pynescript
  * 3. Parse / SyntaxError
  * 4. Round-trip looks “wrong”
  * 5. Lint noise / CI red
  * 6. literaleval fails
  * 7. Runtime / /run execution error
  * 8. Schema validation errors
  * 9. CORS from AXIS / browser
  * 10. LSP will not start
  * 11. Data provider failures
  * 12. Version / parity confusion
* Failure modes (quick matrix)
* See also

# Mentions

* [src/pynescript](/code/src/pynescript.md)
* [src/pynescript/ast](/code/src/pynescript/ast.md)
* [src/pynescript/util](/code/src/pynescript/util.md)
