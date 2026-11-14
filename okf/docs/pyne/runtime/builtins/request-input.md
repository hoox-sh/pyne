---
type: "Document"
title: "`request.*` and `input.*`"
description: "Two namespaces couple scripts to the host environment: input. declares parameters (with defaults and UI metadata), and request. pulls data from other symbols, timeframes, or…"
resource: "docs/pyne/runtime/builtins/request-input.mdx"
tags: [doc, docs, pyne, runtime]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-11-14T19:45:25Z
sources:
  - id: tree
    resource: "docs/pyne/runtime/builtins/request-input.mdx"
    title: "docs/pyne/runtime/builtins/request-input.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/runtime/builtins/request-input.mdx`.

# Outline

- Abstract
- Conceptual model
- Interface surface
  - input. (InputBuiltinsMixin)
  - request. (RequestBuiltinsMixin)
- Mode selection (mode=auto)
- Host series bind (interpret)
- Internals
- Invariants & edge cases
- Worked examples
  - Parameterized length
  - Multi-timeframe close / simple HTF TA (chart symbol)
  - Intentional na — dividend yield (fundamentals missing)
  - Intentional na — CVI / UPVOL-style foreign OHLCV
- Failure modes
- See also

# Mentions

- [src/pynescript/ast/evaluator](/code/src/pynescript/ast/evaluator.md)
- [src/pynescript/ast/evaluator/builtins](/code/src/pynescript/ast/evaluator/builtins.md)
- [src/pynescript/compiler](/code/src/pynescript/compiler.md)
- [src/pynescript/runtime](/code/src/pynescript/runtime.md)
- [src/pynescript/util](/code/src/pynescript/util.md)
- [tests](/code/tests.md)
