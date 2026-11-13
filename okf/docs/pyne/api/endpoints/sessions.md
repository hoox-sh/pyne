---
type: "Document"
title: "Live sessions"
description: "POST /session and friends — O(1) forming-bar ticks, O(delta) appends, and response windowing on /run."
resource: "docs/pyne/api/endpoints/sessions.mdx"
tags: [api, doc, docs, pyne]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-11-13T13:46:36Z
sources:
  - id: tree
    resource: "docs/pyne/api/endpoints/sessions.mdx"
    title: "docs/pyne/api/endpoints/sessions.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/api/endpoints/sessions.mdx`.

# Outline

- Abstract
- Conceptual model
- Interface surface
  - POST /session
  - POST /session/<sessionid/tick
  - POST /session/<sessionid/append
  - GET /session/<sessionid
  - DELETE /session/<sessionid
- Tick semantics
- Response windowing
- Capacity, TTL, and the single-worker constraint
- Restart recovery
- Failure modes
- Internals (map)
- See also

# Mentions

- [src/pynescript/runtime](/code/src/pynescript/runtime.md)
