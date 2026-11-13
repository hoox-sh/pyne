---
type: "Code Module"
title: "src/pynescript/mcp/codemode"
description: "Opt-in Code Mode for the PYNE MCP server."
resource: "src/pynescript/mcp/codemode"
tags: [code, codemode, mcp, pynescript]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-11-13T10:52:37Z
sources:
  - id: tree
    resource: "src/pynescript/mcp/codemode"
    title: "src/pynescript/mcp/codemode"
    author: process:git
okf_lock: generated
---

# Files

* `__init__.py` — code_mode_enabled
* `bridge.py` — create_handlers, destructive_allowed
* `harness.mjs`
* `protocol.py` — CodeModeLimits, SandboxRequest, SandboxResult
* `sandbox.py` — PlanError, SandboxPlan, build_bwrap_plan, build_subprocess_plan, default_plan, harness_path, redact_text, resolve_js_runtime, resolve_sandbox_kind, run_in_sandbox
* `tools.py` — register_code_mode
* `view.py` — CatalogEntry, build_catalog, build_namespaces, compact_catalog, describe_tool

# Packages

`node:process`, `node:vm`
