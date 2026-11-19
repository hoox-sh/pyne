---
type: "Code Module"
title: "src/pynescript/ast/evaluator"
description: "Pine Script AST evaluator package."
resource: "src/pynescript/ast/evaluator"
tags: [ast, code, evaluator, pynescript]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-11-19T01:34:38Z
sources:
  - id: tree
    resource: "src/pynescript/ast/evaluator"
    title: "src/pynescript/ast/evaluator"
    author: process:git
okf_lock: generated
---

# Files

- `__init__.py` — NodeLiteralEvaluator
- `base.py` — BaseEvaluator
- `events.py` — StrategyEvent
- `expressions.py` — ExpressionEvaluator, pine_call_site_id, pop_udf_call_site, push_udf_call_site
- `libraries.py` — LibraryModule, LibraryRegistry, bind_tradingview_ta_stub_exports
- `literals.py` — LiteralEvaluator
- `names.py` — NameEvaluator, ast_qualified_name
- `series_buffer.py` — ChronoTailView, ChronologicalSeriesBuffer, NewestFirstHistoryView, RingPineSeries, evaluator_history_length, make_series
- `statements.py` — BreakLoop, ContinueLoop, StatementEvaluator, has_applicable_overload
- `types.py` — EvaluatorProtocol

# Nested

- [src/pynescript/ast/evaluator/builtins](/code/src/pynescript/ast/evaluator/builtins.md)
