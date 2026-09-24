---
type: "Code Module"
title: "backend"
description: "Pynescript Pro API backend package."
resource: "backend"
tags: [backend, code]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:40:25Z
sources:
  - id: tree
    resource: "backend"
    title: "backend"
    author: process:git
okf_lock: generated
---

# Files

* `__init__.py`
* `alert_forwarder.py` — build_alert_payload, default_webhook_url, filter_alerts_for_bar, forward_alerts, http_post_json, is_webhook_url_safe, maybe_forward_run_alerts, normalize_webhook_url
* `app.py` — compile_prewarm, create_api_key, execute_optimize_payload, execute_run_payload, get_usage, health_check, not_found, optimize_strategy, payload_too_large, run_pine_script, run_pine_script_batch, server_error
* `evaluator.py`
* `runtime.py`
* `series.py`

# Other files

* `requirements.txt`

# Nested

* [backend/api](/code/backend/api.md)
* [backend/middleware](/code/backend/middleware.md)
* [backend/runner](/code/backend/runner.md)
* [backend/services](/code/backend/services.md)
