---
type: "Code Module"
title: "backend/runner"
description: "Optional hosted script runner for Flask / Docker / VPS / Containers."
resource: "backend/runner"
tags: [backend, code, runner]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-11-13T13:46:36Z
sources:
  - id: tree
    resource: "backend/runner"
    title: "backend/runner"
    author: process:git
okf_lock: generated
---

# Files

- `__init__.py` — db_path, poll_seconds, runner_enabled, runner_workers, scheduler_enabled, store_backend
- `scheduler.py` — fetch_ohlcv, maybe_start_background, tick
- `store.py` — acquire_tick_lock, delete_script, get_cron_state, get_script, list_enabled, list_runs, list_scripts, normalized_record, put_cron_state, put_script, record_run, reset_store
- `store_redis.py` — RunnerRedisStore
