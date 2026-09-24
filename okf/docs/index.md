# docs

# Concepts

* [COMPILER_PLAN.md](COMPILER_PLAN.md) - Pynescript historically executed scripts with an AST-walking interpreter in pure Python. Because Pine Script evaluation is dominated by per-bar traversal of time series, that…
* [PROGRESS_REPORT.md](PROGRESS_REPORT.md) - This project provides a capable Pine Script v5/v6 toolchain: parser, AST, evaluator, linter, LSP. The parser is mature; the evaluator covers a broad set of builtins, indicators,…
* [README.md](README.md) - Self-hosted product manuals (HOOX-style MDX) for this monorepo.
* [REFACTORING_EXECUTIVE_SUMMARY.md](REFACTORING_EXECUTIVE_SUMMARY.md) - Status: ✅ PHASE 1 COMPLETE (85% Overall).
* [ROADMAP.md](ROADMAP.md) - Live package: hoox-pyne 0.6.7. The date below is the last narrative edit of this file, not the current version.
* [WRITING.md](WRITING.md) - Source of truth for agents authoring MDX under docs/pyne/ and docs/axis/.
* [compatibility_guarantee.md](compatibility_guarantee.md) - Test Coverage: 1100+ automated tests (full suite; re-run make test for live counts).
* [gcp_cost_estimate.md](gcp_cost_estimate.md) - CI/CD: Cloud Build → Artifact Registry → Cloud Run (already configured in cloudbuild.yaml).
* [index.md](index.md) - docs/index.md document.
* [Known divergences from reference Pine semantics](known_divergences.md) - Status: intentional or residual gaps; track until closed or product-scoped.
* [license.md](license.md) - docs/license.md document.
* [missing_features.md](missing_features.md) - Live package: hoox-pyne 0.6.7 (src/pynescript/about.py). The paragraph below is the 2026-08-19 narrative (then 0.3.17), not the current version stamp.
* [numerical_validation_report.md](numerical_validation_report.md) - Validation Period: 15-20 November 2025.
* [optimization_notes.md](optimization_notes.md) - This document describes the performance optimizations applied to PyneScript core features to improve parsing, evaluation, and AST manipulation efficiency.
* [pine_v6_full_surface_inventory.md](pine_v6_full_surface_inventory.md) - Scope: Every registered evaluator builtin, major series/variables, language constructs, and known gaps.
* [pinescript_implementation_status.md](pinescript_implementation_status.md) - This document is the checklist SoT summarized by docs/pyne/reference/implementation-status.mdx. Status is implementation judgment for hoox-pyne 0.4.4, not TradingView® platform…
* [rating.md](rating.md) - This rating is based on the published claims and evidence in docs/compatibilityguarantee.md.
* [reference.md](reference.md) - The following pages are generated directly from the source tree with sphinx-apidoc. Regenerate them by running hatch run docs:build after making code changes.
* [usage.md](usage.md) - Install the latest release from PyPI (hoox-pyne). The distribution name is hoox-pyne; the import package remains pynescript; preferred CLIs are pyne / pyne-lsp (aliases:…

# Nested

* [axis](axis/) - Nested concepts.
* [pyne](pyne/) - Nested concepts.
