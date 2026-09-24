---
type: "Document"
title: "Auth and Keys"
description: "API key model, tiers, requireapikey / trackusage decorators, JSON/SQLite/Redis stores, and admin createkey."
resource: "docs/pyne/api/auth-and-keys.mdx"
tags: [api, doc, docs, pyne]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
sources:
  - id: tree
    resource: "docs/pyne/api/auth-and-keys.mdx"
    title: "docs/pyne/api/auth-and-keys.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/api/auth-and-keys.mdx`.

# Outline

* Abstract
* Conceptual model
* Interface surface
  * Tiers (TIERLIMITS)
  * Endpoints
  * Decorators
  * Client presentation
* Internals
  * APIKey dataclass
  * Stores
  * Schemas
* Invariants and edge cases
* Worked example
* Failure modes
* See also
