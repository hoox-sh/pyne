---
type: "Document"
title: "Runtime Bridge"
description: "pynescript.runtime.Runtime — package SoT bar-loop evaluate façade, PineSeries context, compile mode, and result packaging."
resource: "docs/pyne/api/runtime-bridge.mdx"
tags: [api, doc, docs, pyne]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
sources:
  - id: tree
    resource: "docs/pyne/api/runtime-bridge.mdx"
    title: "docs/pyne/api/runtime-bridge.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/api/runtime-bridge.mdx`.

# Outline

* Abstract
* Conceptual model
* Interface surface
  * Construction
  * run(sourcecode, ohlcvdata, datafeed=None, dataprovider=None, mode="interpret", …)
  * PineSeries (pynescript.runtime.series)
  * Context namespaces
* Internals
* Invariants and edge cases
* Worked example
* Failure modes
* See also

# Mentions

* [src/pynescript/ast](/code/src/pynescript/ast.md)
* [src/pynescript/compiler](/code/src/pynescript/compiler.md)
* [src/pynescript/runtime](/code/src/pynescript/runtime.md)
