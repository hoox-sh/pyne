---
type: "Document"
title: "Observability"
description: "PYNEDEBUG logging, GET /stats runtime counters, health endpoints, gunicorn process model, Cloud Logging, and operational signals."
resource: "docs/pyne/devops/observability.mdx"
tags: [devops, doc, docs, pyne]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-10-25T19:46:42Z
sources:
  - id: tree
    resource: "docs/pyne/devops/observability.mdx"
    title: "docs/pyne/devops/observability.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/devops/observability.mdx`.

# Outline

* Abstract
* Conceptual model
* Interface surface
  * Health
  * Runtime statistics
  * Debug logging (PYNEDEBUG)
  * Process model (production)
  * Logs
  * CI / quality signals
  * Usage metering (app-layer)
* Internals
* Invariants & edge cases
* Worked examples
  * Local health + stats loop
  * Explain a slow run
  * Inspect live-session delta stats
  * Docker health
* Failure modes
* See also

# Mentions

* [src/pynescript](/code/src/pynescript.md)
* [src/pynescript/compiler](/code/src/pynescript/compiler.md)
* [src/pynescript/runtime](/code/src/pynescript/runtime.md)
* [src/pynescript/util](/code/src/pynescript/util.md)
