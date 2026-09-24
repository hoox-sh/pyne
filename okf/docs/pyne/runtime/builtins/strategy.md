---
type: "Document"
title: "Strategy builtins"
description: "Orders, fills, OCA, commission, risk gates, position metrics, and StrategyState."
resource: "docs/pyne/runtime/builtins/strategy.mdx"
tags: [doc, docs, pyne, runtime]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:54:45Z
sources:
  - id: tree
    resource: "docs/pyne/runtime/builtins/strategy.mdx"
    title: "docs/pyne/runtime/builtins/strategy.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/runtime/builtins/strategy.mdx`.

# Outline

* Abstract
* Conceptual model
* Interface surface
  * Order placement
  * strategy.exit surface (0.3.4+)
  * Position and performance series
  * Trade queries
  * Risk (interpret + compile halt cascade)
  * Declaration
  * Average price model (pynescript extension)
  * Leverage (pynescript extension — simpler futures UI)
* Internals
  * StrategyState (strategy.py)
  * Order and fills
  * OCA
* Invariants & edge cases
* Worked examples
  * Market long / close
  * Pending stop entry
  * OCA bracket sketch
* Failure modes
* See also

# Mentions

* [tests](/code/tests.md)
