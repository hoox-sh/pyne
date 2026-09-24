---
type: "Playbook"
title: "PYNE map"
description: "Where the parser, compiler, runtime, language server, and Pro API live."
tags: [pyne, playbook, architecture]
status: stable
okf_lock: human
generated:
  by: human:jango_blockchained
  at: 2026-09-24T00:00:00Z
sources:
  - id: readme
    resource: README.md
    title: PYNE README
---

# Language

The package import name is `pynescript`. The console scripts are `pyne` and `pyne-lsp`.

* [src/pynescript/ast](/code/src/pynescript/ast.md) is the grammar and AST. The evaluator lives under it.
* [src/pynescript/compiler](/code/src/pynescript/compiler.md) lowers Pine to a bar-loop module.
* [src/pynescript/runtime](/code/src/pynescript/runtime.md) is the runtime support next to the compiler.
* [src/pynescript/langserver](/code/src/pynescript/langserver.md) is the language server.
* [backend](/code/backend.md) is the Pro API on port 5002.

Do not edit `src/pynescript/ast/grammar/antlr4/generated/` or `asdl/generated/`. Those trees are regenerated and are not in this bundle. Grammar sources stay under `src/pynescript/ast/grammar/`.

# Sisters

AXIS is the charting PWA and calls this engine. It does not implement Pine. HOOX is the edge trading framework. `pyne-worker` is a separate repository. Their maps are their own `okf/` bundles.
