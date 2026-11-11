---
type: "Code Module"
title: "backend/middleware"
description: "Flask middleware helpers for the Pro API."
resource: "backend/middleware"
tags: [backend, code, middleware]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-11-11T18:36:33Z
sources:
  - id: tree
    resource: "backend/middleware"
    title: "backend/middleware"
    author: process:git
okf_lock: generated
---

# Files

* `__init__.py`
* `auth.py` — APIKey, APIKeyStore, get_key_store, require_admin_token, require_api_key, reset_key_store, track_usage
* `free_limits.py` — acquire_free_slot, check_free_rate_limit, client_ip, free_data_source_allowed, free_rate_limit, free_tier_limits_enabled, is_trusted_client, max_free_bars, max_free_concurrent, max_free_script_chars, release_free_slot, trusted_client_bypass
* `key_store_redis.py` — RedisKeyStore
* `key_store_sqlite.py` — SQLiteKeyStore
* `schemas.py` — validate
* `sessions.py` — SessionStore
* `window.py` — apply_window, normalize_window
