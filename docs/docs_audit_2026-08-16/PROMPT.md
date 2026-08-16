# Copyright (C) 2024-2026 jango_blockchained
#
# SPDX-License-Identifier: AGPL-3.0-or-later

# PYNE full documentation audit — 6 agents
# Date: 2026-08-16
# Package: hoox-pyne **0.3.10** (`src/pynescript/__about__.py`)
# Hosted: https://hoox.sh/pyne/docs

You audit and update **Mintlify product docs** so every assigned page matches
the live codebase. Edit, add, or delete only what the code justifies.

## Voice (docs/WRITING.md)

- Academic + precise systems prose. No marketing filler.
- Sentence-case headings. Second person.
- Page skeleton when you rewrite: Abstract → conceptual model → interface
  surface → internals (repo paths) → invariants → examples → failure modes →
  see also.
- Internal links: `/pyne/docs/...` (no `.mdx`, no `../`).
- Pine Script™ / TradingView® disclaimer **only** on product `index.mdx`.
- `from __future__ import annotations` is irrelevant (docs only).
- Copyright AGPL header on every MDX file (keep existing headers).

## Facts (do not contradict)

- Dist **`hoox-pyne` 0.3.10**; import **`pynescript`**; CLIs **`pyne` / `pyne-lsp`**.
- Runtime SoT: `src/pynescript/runtime/` (`backend.*` re-exports).
- Interpret 0.3.10: dispatch inlining, unused derived OHLCV skip, incremental
  volume TA (`obv`/`wad`/`cmf`/`klinger`). `PYNE_SERIES_RING` default **off**.
- Corpus set01–04 (2026-08-09): parse 99.96%, Runtime 100% excl. EXPECTED_FAIL.
  Not TradingView® platform parity.
- AXIS / HOOX are **sister products** — cross-link, do not document their
  internals here.

## How to work

1. Read each assigned page.
2. Open the cited source files. If a path, CLI flag, env var, API field, or
   semantic claim is wrong, **fix the page** (do not invent code).
3. Drop stale version pins (`0.3.8`, `backend/runtime.py` as SoT, pine-worker
   colocated, etc.).
4. Fill missing surface that users already have in code (modes, libraries,
   timeout, incremental TA, package Runtime).
5. Delete only **duplicate or false** pages; if you delete, say so in the
   report and do **not** edit `docs.json` (parent updates nav).
6. New pages: write the MDX; list the exact `docs.json` insertion in the report.
7. Do not edit other agents’ files.

## Report

Write `docs/docs_audit_2026-08-16/AGENT_NN_<slug>.md`:

- Pages read / edited / added / deleted
- Code you checked
- Remaining holes
- Verdict: **clean** | **updated** | **needs-parent-nav**
