---
type: Reference
title: Architecture
description: The project shape and the OpenOrchestrate team.
tags: [architecture, openorchestrate]
status: stable
---

# Architecture

pyne uses OpenOrchestrate. Languages: Python, TypeScript, JavaScript, Shell.

## Runtime surfaces

PYNE — an independent toolchain for the Pine Script language: ANTLR4 grammar,
ASDL AST, a dual-engine bar-loop runtime, a language server, and an HTTP
evaluate surface. Pine is modelled as an inspectable pipeline rather than a
host-embedded black box.

- **Entry points:** the `pynescript` package, plus the `pyne`, `pyne-lsp`, and
  `pyne-mcp` CLIs (aliases `pynescript`, `pynescript-lsp`).
- **Run:** `pip install "hoox-pyne[lsp,compile,pro]"` from PyPI.
- **Verify:** `./scripts/verify.sh` runs `bun fmt --check`, `ruff check .`,
  `bun run check`, and `pytest`.

## The team

| Seat    | Title              | Agent        |
| ------- | ------------------ | ------------ |
| Chief   | Chief of Staff     | `oo-chief`   |
| Ops     | Head of Operations | `oo-ops`     |
| Checker | Quality Gate       | `oo-checker` |
| Docs    | Head of Docs       | `oo-spec-1`  |
| Deploy  | Head of Deploy     | `oo-spec-2`  |
| Misc    | General Desk       | `oo-misc`    |

## The board

The board lives at `.openorchestrate/board.md`. It has five statuses:
Todo, Working, Blocked, Ready for Review, Done. A card moves to Done only with proof.

## Related

- [Development](development.md)
- [Security](security.md)
