---
type: "Document"
title: "Numerical validation"
description: "Methodology and error bounds for PYNE technical and math builtins versus reference Pine Script(TM) implementations."
resource: "docs/pyne/reference/numerical-validation.mdx"
tags: [doc, docs, pyne, reference]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-11-23T14:33:25Z
sources:
  - id: tree
    resource: "docs/pyne/reference/numerical-validation.mdx"
    title: "docs/pyne/reference/numerical-validation.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/reference/numerical-validation.mdx`.

# Outline

- Abstract
- Conceptual model
- Interface surface
  - Acceptable thresholds (report)
  - Metric definitions
  - Category highlights
  - Dual-host formula alignment (interpret ↔ compile)
  - Error distribution (report aggregate)
- Internals
  - Methodology (report)
- Invariants & edge cases
- Worked examples
  - Relative error helper
  - Run TA tests
- Failure modes
- See also

# Mentions

- [scripts](/code/scripts.md)
- [tests](/code/tests.md)
