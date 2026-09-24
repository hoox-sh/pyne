---
type: "Document"
title: "Evaluate Contract"
description: "Shared request/response evaluate contract across Flask Pro API, pyne-worker, and in-process Runtime.run (Python + PyneTS)."
resource: "docs/pyne/api/contract.mdx"
tags: [api, doc, docs, pyne]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
sources:
  - id: tree
    resource: "docs/pyne/api/contract.mdx"
    title: "docs/pyne/api/contract.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/api/contract.mdx`.

# Outline

* Abstract
* Conceptual model
* Interface surface
  * Request (single evaluate)
  * Response (success)
  * Response (failure)
  * Batch evaluate (Flask extension)
* Internals — reference mapping
* Divergences to remember
* Invariants and edge cases
* Worked example — host-agnostic client sketch
* Failure modes
* See also

# Mentions

* [tests](/code/tests.md)
