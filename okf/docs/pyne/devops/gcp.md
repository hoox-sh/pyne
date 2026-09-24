---
type: "Document"
title: "GCP & Cloud Run"
description: "Cloud Build pipeline, Cloud Run Pro API sizing, cost model, and substitution secrets for PYNE deployments."
resource: "docs/pyne/devops/gcp.mdx"
tags: [devops, doc, docs, pyne]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
sources:
  - id: tree
    resource: "docs/pyne/devops/gcp.mdx"
    title: "docs/pyne/devops/gcp.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/devops/gcp.mdx`.

# Outline

* Abstract
* Conceptual model
* Interface surface
  * Substitutions (cloudbuild.yaml)
  * Build steps
  * Cloud Run flags (as configured)
  * Machine / budget knobs
* Internals
  * Cost envelope (planning)
  * Free-tier leverage (GCP)
* Invariants & edge cases
* Worked examples
  * Manual deploy sketch (operator)
  * Smoke health after deploy
* Failure modes
* See also

# Mentions

* [scripts/build](/code/scripts/build.md)
* [src/pynescript](/code/src/pynescript.md)
