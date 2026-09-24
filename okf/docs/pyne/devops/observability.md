---
type: "Document"
title: "Observability"
description: "Health endpoints, gunicorn process model, Cloud Logging, coverage artifacts, and operational signals for PYNE."
resource: "docs/pyne/devops/observability.mdx"
tags: [devops, doc, docs, pyne]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
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
  * Process model (production)
  * Logs
  * CI / quality signals
  * Usage metering (app-layer)
* Internals
* Invariants & edge cases
* Worked examples
  * Local health loop
  * Docker health
  * Tail Cloud Run (gcloud)
* Failure modes
* See also
