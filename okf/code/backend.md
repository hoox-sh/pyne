---
type: "Code Module"
title: "backend"
description: "Pynescript Pro API backend package."
resource: "backend"
tags: [backend, code]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-10-31T14:46:08Z
sources:
  - id: tree
    resource: "backend"
    title: "backend"
    author: process:git
okf_lock: generated
---

# Files

* `__init__.py`
* `__main__.py`
* `alert_forwarder.py` — build_alert_payload, default_webhook_url, filter_alerts_for_bar, forward_alerts, http_post_json, is_webhook_url_safe, maybe_forward_run_alerts, normalize_webhook_url
* `app.py` — compile_prewarm, create_api_key, create_data_session_route, create_session_route, data_session_tick_route, execute_optimize_payload, execute_run_payload, get_stats, get_usage, health_check, main, not_found
* `evaluator.py`
* `logging_setup.py` — configure_logging, debug_report, install_debug_handler
* `runtime.py`
* `series.py`

# Other files

* `requirements.txt`

# Nested

* [backend/api](/code/backend/api.md)
* [backend/datastore](/code/backend/datastore.md)
* [backend/middleware](/code/backend/middleware.md)
* [backend/runner](/code/backend/runner.md)
* [backend/services](/code/backend/services.md)
