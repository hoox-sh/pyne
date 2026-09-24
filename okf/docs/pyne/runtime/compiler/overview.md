---
type: "Document"
title: "Compiler overview"
description: "Source-to-source compilation: CompilerVisitor, numeric vs object mode, run(time=…), and engine API."
resource: "docs/pyne/runtime/compiler/overview.mdx"
tags: [doc, docs, pyne, runtime]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:54:45Z
sources:
  - id: tree
    resource: "docs/pyne/runtime/compiler/overview.mdx"
    title: "docs/pyne/runtime/compiler/overview.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/runtime/compiler/overview.mdx`.

# Outline

* Abstract
* Conceptual model
* Interface surface
  * CompiledScript.run signature
  * Warm compile (product defaults)
  * Mode selection
  * What numeric mode lowers today
  * Object mode extras
  * Compile-path limits (notable)
* Internals
  * Data layout
  * Caches and corrupt-Numba recovery
* Invariants & edge cases
* Worked example
  * Interpret↔compile parity
* Failure modes
* Remaining work (summary)
* See also

# Mentions

* [scripts](/code/scripts.md)
* [src/pynescript/compiler](/code/src/pynescript/compiler.md)
* [src/pynescript/runtime](/code/src/pynescript/runtime.md)
* [tests](/code/tests.md)
