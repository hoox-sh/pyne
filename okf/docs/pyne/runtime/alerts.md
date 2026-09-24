---
type: "Document"
title: "Alerts"
description: "alert() / alertcondition() engine, host export, and L2 HTTP webhooks (Pro API + pyne-worker)."
resource: "docs/pyne/runtime/alerts.mdx"
tags: [doc, docs, pyne, runtime]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
sources:
  - id: tree
    resource: "docs/pyne/runtime/alerts.mdx"
    title: "docs/pyne/runtime/alerts.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/runtime/alerts.mdx`.

# Outline

* Abstract
* Conceptual model
* Pine surface
  * alert(message, freq)
  * alertcondition(condition, title, message)
  * Event shape (todict / API)
* Host export
  * Pro API (POST /run)
  * pyne-worker
* L2 webhooks
  * Pro API request flags
  * Batch body
  * Response meta
* Worked example
* Invariants
* See also

# Mentions

* [src/pynescript/ast/evaluator/builtins](/code/src/pynescript/ast/evaluator/builtins.md)
* [src/pynescript/runtime](/code/src/pynescript/runtime.md)
