# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Strategy events system: StrategyEvent dataclass, full emission from strategy.* builtins, parity test corpus.
- pine-worker/ as colocated extra tool: TypeScript evaluator port + Python to TS converter script (convert-python-to-ts.py).
- var / varip declaration modes and ReAssign support.
- Consolidation of main with recent plan branch work (2026-07-09).

### Changed
- Updated documentation (ROADMAP, missing_features, implementation status, LSP plan) to reflect current state.
- Backend test collection fixes post-integration.
