---
type: "Document"
title: "Design"
description: "A high-level look at how pynescript is put together and why. For what to."
resource: "DESIGN.md"
tags: [design, doc]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
sources:
  - id: tree
    resource: "DESIGN.md"
    title: "DESIGN.md"
    author: process:git
okf_lock: generated
---

# Source

Repo path `DESIGN.md`.

# Outline

* 1. Mission
* 2. System Architecture
* 3. Repository Layout
* 4. Data Flow
  * 4.1 Parse and Unparse (round-trip)
  * 4.2 Evaluation
  * 4.3 LSP Request (e.g. completion)
* 5. Pine Script v6 Support & Practical Lessons (2026)
  * Grammar Challenges Encountered
  * Current State (as of 2026-07)
  * 4.4 Pro API Request
* 5. Key Design Decisions
  * 5.1 ANTLR4 for the grammar (not a hand-rolled parser)
  * 5.2 ASDL for AST nodes (not dataclasses)
  * 5.3 One Python package, three delivery shapes
  * 5.4 Fernet-encrypted metadata (closed-source strategy)
  * 5.5 The Pro API is a separate Flask process
  * 5.6 Lint rules as a separate static phase
  * 5.7 Tests parametrized over a real .pine corpus
  * 5.8 Ruff, not Black + isort + flake8
  * 5.9 Generated modules are excluded from lint/type
* 6. Distribution Tiers
* 7. Non-Goals
* 8. Where to Read More

# Mentions

* [src/pynescript](/code/src/pynescript.md)
* [src/pynescript/ast](/code/src/pynescript/ast.md)
* [src/pynescript/ast/grammar/asdl](/code/src/pynescript/ast/grammar/asdl.md)
* [src/pynescript/langserver/providers](/code/src/pynescript/langserver/providers.md)
* [tests](/code/tests.md)
