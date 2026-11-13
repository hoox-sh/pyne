---
type: "Document"
title: "numerical_validation_report.md"
description: "Validation Period: 15–20 November 2025."
resource: "docs/numerical_validation_report.md"
tags: [doc, docs, numerical-validation-report]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-11-13T13:46:36Z
sources:
  - id: tree
    resource: "docs/numerical_validation_report.md"
    title: "docs/numerical_validation_report.md"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/numerical_validation_report.md`.

# Outline

- Executive Summary
  - Key findings (from this report)
  - Dual-host formula alignment (post-report; 2026)
- Methodology
  - Test data generation
  - Validation process
  - Error metrics
  - Acceptable thresholds
- Results by Category
  - 1. Moving averages
  - 2. Oscillators
  - 3. Trend indicators
  - 4. Volume indicators
  - 5. Statistical functions
  - 6. Math functions
  - 7. Array operations
- Edge Case Validation
  - Extreme values
  - Special cases
  - Boundary conditions
- Error Distribution Analysis
  - Histogram of relative errors (all indicators)
  - Error distribution statistics
- Systematic Bias Analysis
- Precision Loss Sources
  - IEEE 754 floating-point limitations
  - Algorithmic differences
  - Accumulation in long series
- Honesty Notes
- Comparison: PYNE vs. TradingView®
- Recommendations
  - For users
  - For developers
- Conclusion
- Appendices
  - Appendix A: Test data specifications
  - Appendix B: TradingView® export process
  - Appendix C: Error calculation code

# Mentions

- [scripts](/code/scripts.md)
- [tests](/code/tests.md)
