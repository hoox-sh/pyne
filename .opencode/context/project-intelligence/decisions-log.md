<!-- Context: project-intelligence/decisions | Priority: medium | Version: 1.0 | Updated: 2026-06-03 -->

# Decisions Log

Architecture decisions for pynescript.

## ADR-001: ANTLR4 for Pine Script Parsing
**Date**: 2024 | **Status**: ✅ Accepted

**Context**: Need a robust parser for Pine Script that handles the full grammar.
**Decision**: Use ANTLR4 with a separate grammar file (`.g4`) and generate the lexer/parser.
**Rationale**: ANTLR4 supports adaptive LL(*) parsing, handles ambiguous Pine Script grammar well, and generates Python 3 output.

## ADR-002: ASDL for AST Node Definitions
**Date**: 2024 | **Status**: ✅ Accepted

**Context**: AST node classes need a compact, maintainable definition format.
**Decision**: Use ASDL (Abstract Syntax Description Language) to define AST nodes, with auto-generated Python classes.
**Rationale**: One-source-of-truth for node definitions; generated code is never manually edited.

## ADR-003: Mixin Composition for Builtins
**Date**: 2024 | **Status**: ✅ Accepted

**Context**: 482 builtin functions need to be organized into a maintainable dispatch system.
**Decision**: Each builtin category (numeric, string, array, technical, etc.) is a mixin class. `BuiltinEvaluator` composes all mixins via multiple inheritance.
**Rationale**: Isolated categories, easy to add new ones, each mixin owns its dispatch table via `_*_builtin_map()`.

## ADR-004: pygls for LSP Server
**Date**: 2025 | **Status**: ✅ Accepted

**Context**: Need LSP server implementation compatible with VS Code, Neovim, Zed, Emacs.
**Decision**: Use pygls library for LSP protocol handling; separate features into `features/` module.
**Rationale**: pygls abstracts LSP protocol details; modular features per capability (diagnostics, completion, hover).

## ADR-005: Flask for Pro API Backend
**Date**: 2025 | **Status**: ✅ Accepted

**Context**: Cloud API for script execution, chart previews, backtesting.
**Decision**: Flask with flask-cors, blueprints for route organization, API key authentication middleware.
**Rationale**: Lightweight, well-known, easy to deploy with gunicorn + Docker.

## ADR-006: Nuitka for Standalone Binary
**Date**: 2025 | **Status**: ✅ Accepted

**Context**: Users shouldn't need Python installed to run the LSP server.
**Decision**: Compile LSP server to standalone binary via Nuitka; encrypt `builtin_metadata.json` with Fernet.
**Rationale**: Zero-dependency deployment for VS Code extension; metadata is proprietary.

## ADR-007: Modular Technical Indicators
**Date**: 2025 | **Status**: ✅ Accepted

**Context**: `technical.py` grew to 5,142 lines — unmaintainable.
**Decision**: Split into category submodules (`technical_submodules/`) with shared `core.py` base and composition wrapper.
**Rationale**: 94% reduction in file complexity, isolated changes, granular testing.

## 📂 Codebase References
- ANTLR grammar: `src/pynescript/ast/grammar/antlr4/resource/`
- ASDL definitions: `src/pynescript/ast/grammar/asdl/resource/`
- Mixin composition: `src/pynescript/ast/evaluator/builtins/__init__.py`
- LSP features: `src/pynescript/langserver/features/`
- Flask API: `backend/app.py`
- Nuitka build: `scripts/build/compile.py`
- Technical submodules: `src/pynescript/ast/evaluator/builtins/technical_submodules/`
