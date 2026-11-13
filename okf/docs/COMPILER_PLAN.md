---
type: "Document"
title: "COMPILER_PLAN.md"
description: "Pynescript historically executed scripts with an AST-walking interpreter in pure Python. Because Pine Script evaluation is dominated by per-bar traversal of time series, that…"
resource: "docs/COMPILER_PLAN.md"
tags: [compiler-plan, doc, docs]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-11-13T13:46:36Z
sources:
  - id: tree
    resource: "docs/COMPILER_PLAN.md"
    title: "docs/COMPILER_PLAN.md"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/COMPILER_PLAN.md`.

# Outline

- Architecture
  - Numeric Mode
  - Object Mode
  - Warm-Compile
- Implementation Status
  - Landed Correctness and Host Surface
  - Performance
  - Interpret-to-Compile Parity
- Recent Releases (0.6.10–0.6.14)
  - 0.6.10 — Observability and Engine Parity
  - 0.6.11 — Live Plane and Sessions
  - 0.6.12 — Production Hardening
  - 0.6.13 — Dual-host HTF
  - 0.6.14 — HTF allowlist expansion

# Mentions

- [scripts](/code/scripts.md)
- [tests](/code/tests.md)
