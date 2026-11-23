---
type: "Code Module"
title: "backend/middleware"
description: "Flask middleware helpers for the Pro API."
resource: "backend/middleware"
tags: [backend, code, middleware]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-11-23T12:58:39Z
sources:
  - id: tree
    resource: "backend/middleware"
    title: "backend/middleware"
    author: process:git
okf_lock: generated
---

# Files

- `__init__.py`
- `auth.py` — APIKey, APIKeyStore, get_key_store, optional_api_key, require_admin_token, require_api_key, reset_key_store, track_usage
- `free_limits.py` — acquire_free_slot, auth_rate_limit, check_auth_rate_limit, check_free_rate_limit, check_lsp_rate_limit, client_ip, free_data_source_allowed, free_rate_limit, free_tier_limits_enabled, is_trusted_client, lsp_rate_limit, max_free_bars
- `key_store_redis.py` — RedisKeyStore
- `key_store_sqlite.py` — SQLiteKeyStore
- `schemas.py` — validate
- `sessions.py` — SessionStore
- `window.py` — apply_window, normalize_window
