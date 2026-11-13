---
type: "Document"
title: "Data plane"
description: "Engine-owned OHLCV series store and data-bound live sessions — /data/series and /data/session."
resource: "docs/pyne/api/endpoints/data-plane.mdx"
tags: [api, doc, docs, pyne]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-11-13T13:46:36Z
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
- Storage
- Failure modes
- Internals (map)
- See also
