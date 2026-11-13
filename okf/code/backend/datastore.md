---
type: "Code Module"
title: "backend/datastore"
description: "Engine-owned OHLCV data plane (PYNE Pro): series store and session binding."
resource: "backend/datastore"
tags: [backend, code, datastore]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-11-13T13:46:36Z
sources:
  - id: tree
    resource: "backend/datastore"
    title: "backend/datastore"
    author: process:git
okf_lock: generated
---

# Files

- `__init__.py`
- `live.py` — SeriesBinding, SyncOutcome, bind_session, binding_of, sync_session
- `series.py` — DataError, SeriesKey, SeriesStore, canonical_interval, check_history_bars, data_dir, get_store, interval_seconds, make_key, normalize_bars, now_seconds
- `session_log.py` — count_records, delete_all_records, delete_record, list_meta, load_meta, load_record, record_append, record_binding, record_create, record_tick, reset_session_log, session_db_path
