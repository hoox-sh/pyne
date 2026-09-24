---
type: "Document"
title: "Drawing and plotting"
description: "plot side effects, DrawingRegistry objects, and export shapes for hosts and AXIS."
resource: "docs/pyne/runtime/builtins/drawing-plotting.mdx"
tags: [doc, docs, pyne, runtime]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
sources:
  - id: tree
    resource: "docs/pyne/runtime/builtins/drawing-plotting.mdx"
    title: "docs/pyne/runtime/builtins/drawing-plotting.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/runtime/builtins/drawing-plotting.mdx`.

# Outline

* Abstract
* Conceptual model
* Interface surface
  * Plotting (PlottingFunctionsMixin)
  * Title defaults and series keys
  * hline — constant series (both modes)
  * fill — titled series key for key-set parity (both modes)
  * Import stubs must not leak as series strings
  * Drawing objects (DrawingBuiltinsMixin)
  * Registry lifecycle
  * Drawing GC (maxcount)
  * fill + plotmeta for AXIS
* Internals
  * Compile object-mode notes
* Invariants & edge cases
* Worked examples
  * Dual plot + fill
  * Label on last bar
* Failure modes
* See also

# Mentions

* [src/pynescript/ast/evaluator](/code/src/pynescript/ast/evaluator.md)
* [src/pynescript/ast/evaluator/builtins](/code/src/pynescript/ast/evaluator/builtins.md)
* [src/pynescript/compiler](/code/src/pynescript/compiler.md)
* [src/pynescript/runtime](/code/src/pynescript/runtime.md)
* [tests](/code/tests.md)
