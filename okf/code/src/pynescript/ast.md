---
type: "Code Module"
title: "src/pynescript/ast"
description: "Pine Script abstract syntax tree package."
resource: "src/pynescript/ast"
tags: [ast, code, pynescript]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:40:25Z
sources:
  - id: tree
    resource: "src/pynescript/ast"
    title: "src/pynescript/ast"
    author: process:git
okf_lock: generated
---

# Files

* `__init__.py`
* `__main__.py` — main
* `builder.py` — PinescriptASTBuilder, PinescriptASTLocator, PinescriptCommentParser
* `collector.py` — StatementCollector
* `error.py` — IndentationError, SyntaxError, SyntaxErrorDetails
* `helper.py` — clear_parse_cache, copy_location, dump, fix_missing_locations, get_source_segment, increment_lineno, iter_child_nodes, iter_fields, literal_eval, parse, parse_cache_info, unparse
* `linter.py` — LintWarning, PineLinter, lint_file, lint_script
* `node.py`
* `transformer.py` — NodeTransformer
* `type_system.py` — ArrayType, BuiltinType, BuiltinTypeKind, Field, MapType, MatrixType, MethodResolver, MethodSignature, ObjectInstance, Type, TypeQualifier, TypeRegistry
* `unparser.py` — NodeUnparser, Precedence, unparse_node
* `visitor.py` — NodeVisitor

# Nested

* [src/pynescript/ast/evaluator](/code/src/pynescript/ast/evaluator.md)
* [src/pynescript/ast/grammar](/code/src/pynescript/ast/grammar.md)
