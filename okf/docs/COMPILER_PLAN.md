---
type: "Document"
title: "COMPILER_PLAN.md"
description: "Pynescript historically executed scripts with an AST-walking interpreter in pure Python. Because Pine Script evaluation is dominated by per-bar traversal of time series, that…"
resource: "docs/COMPILER_PLAN.md"
tags: [compiler-plan, doc, docs]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
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

* Implementation Status
  * Landed correctness / host surface (2026-08 residual)
* Architecture
  * 1. CompilerVisitor (AST to executable Python)
  * 2. Numba Built-ins Module
  * 3. Data Structure Overhaul
  * 4. Engine API and integration with backend/runtime.py
* Benefits
* Product warm-compile path (H2, 2026-08)
  * Runtime modes
  * Cache layers
  * Prewarm hooks
  * SLOs (indicative, workstation + Numba; see Round 6 benches)
* Remaining Work

# Mentions

* [scripts](/code/scripts.md)
* [src/pynescript/compiler](/code/src/pynescript/compiler.md)
* [tests](/code/tests.md)
