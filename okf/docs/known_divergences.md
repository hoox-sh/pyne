---
type: "Document"
title: "Known divergences from reference Pine semantics"
description: "Status: intentional or residual gaps; track until closed or product-scoped."
resource: "docs/known_divergences.md"
tags: [doc, docs, known-divergences]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
sources:
  - id: tree
    resource: "docs/known_divergences.md"
    title: "docs/known_divergences.md"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/known_divergences.md`.

# Outline

* Status at a glance
  * Open divergences
  * Fixed
* Strategy
  * strategy.exit pending brackets (fixed Wave B — trail still OHLC-approx)
  * strategy.risk. partial on compile path
  * Open/closed trade query surface (compile) — partial honesty
* Technical analysis
  * ta.atr Wilder RMA (fixed Wave B — re-golden dependents)
  * EMA seed (fixed — dual-host SMA seed)
* Evaluator / series
  * var / varip realtime (partial Wave B)
  * timeframe.change (calendar D/W/M, fixed-width otherwise)
  * AugAssign / tuple unpack series bind (fixed Wave B)
  * Omitted bid/ask
* Request / multi-timeframe
  * request.security is not a full HTF re-eval engine
* Linter (tooling, not runtime)
* Product scope notes

# Mentions

* [tests](/code/tests.md)
