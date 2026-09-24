---
type: "Document"
title: "optimization_notes.md"
description: "This document describes the performance optimizations applied to PyneScript core features to improve parsing, evaluation, and AST manipulation efficiency."
resource: "docs/optimization_notes.md"
tags: [doc, docs, optimization-notes]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
sources:
  - id: tree
    resource: "docs/optimization_notes.md"
    title: "docs/optimization_notes.md"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/optimization_notes.md`.

# Outline

* Profiling Results
  * Initial Analysis
  * Post-Optimization Results
* Performance Benchmarks
* Optimizations Implemented
  * 1. AST Location Setting (builder.py)
  * 2. Operator Reference Caching (evaluator/expressions.py)
  * 3. Math Constants Pre-computation (evaluator/base.py)
  * 4. Comment Processing Optimizations (helper.py)
  * 5. Visitor Method Caching (visitor.py)
  * 6. Annotation Processing (helper.py)
* Why ANTLR Parser Cannot Be Easily Optimized
  * Main Hotspots in ANTLR
  * Why We Can't Optimize ANTLR Easily
  * Potential Future Optimizations (High Risk)
* Optimization Guidelines
  * Do's
  * Don'ts
* Impact Analysis
  * Test Suite Performance
  * Memory Impact
  * Code Maintainability
* Recommendations
  * For Current Codebase
  * For Future Work
  * For Users
* Conclusion
