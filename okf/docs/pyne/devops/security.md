---
type: "Document"
title: "Security"
description: "API keys, CORS, body limits, secrets hygiene, Fernet metadata keys, and threat-aware defaults for PYNE ops."
resource: "docs/pyne/devops/security.mdx"
tags: [devops, doc, docs, pyne]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
sources:
  - id: tree
    resource: "docs/pyne/devops/security.mdx"
    title: "docs/pyne/devops/security.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/devops/security.mdx`.

# Outline

* Abstract
* Conceptual model
* Interface surface
  * HTTP application controls (backend/app.py)
  * API keys (backend/middleware/auth.py)
  * Build / release secrets
  * Container hardening (Dockerfile target api)
  * Admin minting
  * Key store backends (STOREBACKEND)
* Internals
  * Audit notes encoded in source
* Invariants & edge cases
* Worked examples
  * Harden CORS for a single origin
  * Point key store at a volume
  * Rotate metadata key (ops procedure sketch)
* Failure modes
* See also

# Mentions

* [src/pynescript/langserver/providers](/code/src/pynescript/langserver/providers.md)
