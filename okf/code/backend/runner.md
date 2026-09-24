---
type: "Code Module"
title: "backend/runner"
description: "Optional hosted script runner for Flask / Docker / VPS / Containers."
resource: "backend/runner"
tags: [backend, code, runner]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:40:25Z
sources:
  - id: tree
    resource: "backend/runner"
    title: "backend/runner"
    author: process:git
okf_lock: generated
---

# Files

* `__init__.py` — db_path, poll_seconds, runner_enabled, scheduler_enabled
* `scheduler.py` — fetch_ohlcv, maybe_start_background, tick
* `store.py` — delete_script, get_cron_state, get_script, list_enabled, list_scripts, put_cron_state, put_script, reset_store, set_enabled, validate_script_id
