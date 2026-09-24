---
type: "Code Module"
title: "src/pynescript/compiler"
description: "Pine Script → Numba / object-mode compile pipeline."
resource: "src/pynescript/compiler"
tags: [code, compiler, pynescript]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:40:25Z
sources:
  - id: tree
    resource: "src/pynescript/compiler"
    title: "src/pynescript/compiler"
    author: process:git
okf_lock: generated
---

# Files

* `__init__.py`
* `engine.py` — CompileEmitError, CompileError, CompileLoadError, CompileNumbaRequiredError, CompileWarmupError, CompiledScript, clear_compile_cache, clear_disk_compile_cache, clear_numba_function_caches, compile_cache_stats, compile_deploy_config, compile_script
* `numba_builtins.py` — array_abs, array_binary_search, array_binary_search_leftmost, array_binary_search_rightmost, array_every, array_fill, array_mode, array_normalized, array_percentile_linear_interpolation, array_percentile_nearest_rank, array_percentrank, array_range
* `strategy_broker.py` — ClosedTradeRecord, CompileStrategyBroker, OpenLeg, PendingOrder

# Other files

* `compiler.py`
