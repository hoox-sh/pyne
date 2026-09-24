---
type: "Document"
title: "Docker"
description: "Buildx multi-target images, Compose profiles, and Cloud Run production contract for the PYNE Pro API."
resource: "docs/pyne/devops/docker.mdx"
tags: [devops, doc, docs, pyne]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
sources:
  - id: tree
    resource: "docs/pyne/devops/docker.mdx"
    title: "docs/pyne/devops/docker.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/devops/docker.mdx`.

# Outline

* Abstract
* Conceptual model
* Interface surface
  * Dockerfile targets
  * Buildx Bake (docker-bake.hcl)
  * Compose
  * Environment variables
  * Published image names
* Internals
  * Build stages
  * .dockerignore
  * Compose healthchecks
* Invariants & edge cases
* Worked examples
  * Production-like local API (bake)
  * Compose with Redis
  * Optional LSP container
  * CLI image
  * Production overlay
* Failure modes
* See also

# Mentions

* [scripts](/code/scripts.md)
