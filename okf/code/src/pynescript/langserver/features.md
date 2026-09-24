---
type: "Code Module"
title: "src/pynescript/langserver/features"
description: "LSP feature handlers (one module per capability area)."
resource: "src/pynescript/langserver/features"
tags: [code, features, langserver, pynescript]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:40:25Z
sources:
  - id: tree
    resource: "src/pynescript/langserver/features"
    title: "src/pynescript/langserver/features"
    author: process:git
okf_lock: generated
---

# Files

* `__init__.py`
* `completion.py` — handle_completion, handle_completion_resolve
* `convert.py` — convert_payload, handle_code_action, handle_convert_to_v6, whole_document_edit
* `definitions.py` — DefinitionFinder, handle_definition
* `diagnostics.py` — create_diagnostic_related_info, create_quick_fix, lint_warnings_to_diagnostics
* `formatting.py` — handle_formatting, handle_range_formatting
* `hover.py` — handle_hover
* `inlay_hints.py` — handle_inlay_hints
* `references.py` — ReferencesFinder, handle_references
* `semantic_tokens.py` — handle_semantic_tokens
* `symbols.py` — DocumentSymbolCollector, handle_document_symbols
