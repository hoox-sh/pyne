---
type: "Document"
title: "Numba path"
description: "JIT bar loops, numbabuiltins kernels, NA-as-NaN, and performance characteristics."
resource: "docs/pyne/runtime/compiler/numba.mdx"
tags: [doc, docs, pyne, runtime]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
sources:
  - id: tree
    resource: "docs/pyne/runtime/compiler/numba.mdx"
    title: "docs/pyne/runtime/compiler/numba.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/runtime/compiler/numba.mdx`.

# Outline

* Abstract
* Conceptual model
* Interface surface
  * Kernel table (interpret-parity highlights)
  * Calendar / timearr
  * History access
  * Control flow
* Cache
* Internals
* Invariants & edge cases
* Worked examples
  * Benchmark mental model
  * Using from Pro API
* Failure modes
* Performance notes
* See also

# Mentions

* [src/pynescript/compiler](/code/src/pynescript/compiler.md)
* [tests](/code/tests.md)
