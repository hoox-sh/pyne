---
type: "Code Module"
title: "src/pynescript/mcp/ops"
description: "Library-backed operations used by PYNE MCP tools (no Click, no Flask)."
resource: "src/pynescript/mcp/ops"
tags: [code, mcp, ops, pynescript]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-11-13T13:46:36Z
sources:
  - id: tree
    resource: "src/pynescript/mcp/ops"
    title: "src/pynescript/mcp/ops"
    author: process:git
okf_lock: generated
---

# Files

- `__init__.py`
- `axb1.py` — bundled_vectors_path, encode_frame_spec, frame_from_spec, verify_axb1_vectors
- `builtins.py` — list_builtins, list_facade_templates, lookup_builtin
- `common.py` — call_path, load_source, parse_error_fields, script_declaration, synthetic_ohlcv_cols, synthetic_ohlcv_rows, version_from_source
- `compile.py` — compile_source, prewarm_sources, run_synthetic
- `data.py` — fetch_data
- `execute.py` — execute_source, parity_source
- `info.py` — has_mcp_sdk, info_payload
- `language.py` — check_sources, convert_source, diagnostics_source, dump_source, format_source, lint_source, parse_source, symbols_source, unparse_source
- `lsp.py` — complete_source, hover_source, signature_source
- `optimize.py` — optimize_source
- `runner.py` — runner_delete, runner_deploy, runner_enable, runner_history, runner_jobs, runner_list, runner_show, runner_tick
- `sessions.py` — inspect_sessions
