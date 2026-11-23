---
type: "Document"
title: "Data plane"
description: "POST /run takes its bars in the request. That is fine for a one-shot evaluate, but a live chart re-sends the entire history on every tick and asks the exchange for bars the…"
resource: "docs/pyne/api/endpoints/data-plane.mdx"
tags: [api, doc, docs, pyne]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-11-23T12:58:39Z
sources:
  - id: tree
    resource: "docs/pyne/api/endpoints/data-plane.mdx"
    title: "docs/pyne/api/endpoints/data-plane.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/api/endpoints/data-plane.mdx`.

# Outline

- Abstract
- Conceptual model
- Series key
- Interface surface
  - GET /data/series
  - GET /data/series/bars
  - POST /data/series/provide
  - POST /data/series/fetch
  - POST /data/session
  - POST /data/session/<sessionid/tick
- Datafeed gateway
- Storage
- Failure modes
- Internals (map)
- See also
