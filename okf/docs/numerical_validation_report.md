---
type: "Document"
title: "numerical_validation_report.md"
description: "Validation Period: 15-20 November 2025."
resource: "docs/numerical_validation_report.md"
tags: [doc, docs, numerical-validation-report]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
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

* Executive Summary
  * Key Findings
  * Dual-host formula alignment (post-report; 2026)
  * Confidence Level
* Methodology
  * Test Data Generation
  * Validation Process
  * Error Metrics
  * Acceptable Thresholds
* Results by Category
  * 1. Moving Averages
  * 2. Oscillators
  * 3. Trend Indicators
  * 4. Volume Indicators
  * 5. Statistical Functions
  * 6. Math Functions
  * 7. Array Operations
* Edge Case Validation
  * 1. Extreme Values
  * 2. Special Cases
  * 3. Boundary Conditions
* Error Distribution Analysis
  * Histogram of Relative Errors (All Indicators)
  * Error Distribution Statistics
* Systematic Bias Analysis
  * Method
  * Results
* Precision Loss Sources
  * 1. IEEE 754 Floating-Point Limitations
  * 2. Algorithmic Differences
  * 3. Accumulation in Long Series
* Validation Confidence
  * Statistical Confidence Intervals
  * Test Coverage Confidence
* Comparison: PyneScript vs. TradingView®
  * Advantages of PyneScript
  * Functional Equivalence
  * Known Differences
* Recommendations
  * For Users

# Mentions

* [scripts](/code/scripts.md)
* [tests](/code/tests.md)
