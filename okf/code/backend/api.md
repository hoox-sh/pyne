---
type: "Code Module"
title: "backend/api"
description: "HTTP API blueprints for the Pro API (beyond core /run routes)."
resource: "backend/api"
tags: [api, backend, code]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:40:25Z
sources:
  - id: tree
    resource: "backend/api"
    title: "backend/api"
    author: process:git
okf_lock: generated
---

# Files

* `__init__.py`
* `datafeed.py` — bind_session, fetch_markets, fetch_ohlcv, gateway_health, register_watch_route, run_watch_producer, unbind_session, watch_rest_poll
* `git_oauth.py` — device_poll, device_start
* `lsp_http.py` — lsp_completion, lsp_convert, lsp_diagnostics, lsp_hover
* `preview.py` — chart_preview, indicator_preview, quick_backtest
* `runner.py` — cron_run, delete_script, get_cron_jobs, get_script, list_scripts, put_cron_jobs, put_script
