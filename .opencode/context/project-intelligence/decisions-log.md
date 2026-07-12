<!-- Context: project-intelligence/decisions | Priority: medium | Version: 1.1 | Updated: 2026-07-12 -->

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

## Practical Experience: Pine v6 Multiline Strings + ANTLR (2026-07)

**Date**: 2026-07-12 | **Status**: Experience captured (not a formal ADR)

**Context**: Implementing support for v6 multiline triple-quoted strings (`"""..."""`) and reviewing other April 2026 features (`sort_field` on matrices).

**What we learned**:
- Resource grammar edits are mandatory; generated/ must be treated as build artifact.
- ANTLR4's own grammar for lexer fragments is sensitive to how you quote multi-character literals containing `'` or `"`. Factored start fragments (`TRIPLE_SQ_START`) were required.
- The custom `LexerBase` (indent machine + string post-processing) was already prepared for the feature (`_handle_STRING_token` checks for triple prefixes).
- Full regeneration is risky because `builder.py` makes direct calls on generated context objects. Selective refresh of only the lexer side worked.
- Direct use of `pynescript.ast.helper.parse` + `unparse` on tiny examples gives much faster feedback than the full 500-case corpus.
- Documentation (`missing_features.md`) had drifted from the actual code state (footprint was already substantially implemented as mocks + method dispatch).

**Recommended workflow for future syntax features**:
1. Edit `resource/*.g4` + `resource/*Base.py` only.
2. Reproduce the exact token stream with a minimal script.
3. Use temp dir for `antlr4` invocation.
4. Copy only what is safe (lexer + base).
5. Immediately add a test in `tests/test_parse_and_unparse.py` or `test_v6_features.py`.
6. Record the gotchas here and in the grammar guide.

This experience was turned into concrete additions in `AGENTS.md`, `DESIGN.md`, and `guides/grammar-changes.md`.
