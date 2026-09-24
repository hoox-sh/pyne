---
type: "Document"
title: "Pro API Usage"
description: "Call the PYNE Flask Pro API as a consumer: health, /run, /run/batch, /optimize, chart preview, indicator preview, quick backtest, and auth."
resource: "docs/pyne/enduser/guides/pro-api-usage.mdx"
tags: [doc, docs, enduser, pyne]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
sources:
  - id: tree
    resource: "docs/pyne/enduser/guides/pro-api-usage.mdx"
    title: "docs/pyne/enduser/guides/pro-api-usage.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/enduser/guides/pro-api-usage.mdx`.

# Outline

* Abstract
* Conceptual model
* Interface surface
  * Run the server (local)
  * Health
  * POST /run
  * POST /run/batch
  * POST /preview/chart (Pro)
  * POST /preview/indicator (Pro)
  * POST /backtest/quick (Pro)
  * POST /compile/prewarm (free)
  * Auth helpers
* Internals (repo paths)
* Invariants & edge cases
* Worked examples
  * Python requests client for /run
  * Batch two indicators
  * Bind published libraries
  * Wire optional CCXT data source
* Failure modes
* See also

# Mentions

* [src/pynescript/runtime](/code/src/pynescript/runtime.md)
