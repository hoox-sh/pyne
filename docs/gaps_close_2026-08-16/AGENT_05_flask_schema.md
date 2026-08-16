# Copyright (C) 2024-2026 jango_blockchained
#
# SPDX-License-Identifier: AGPL-3.0-or-later

# Agent 05 — Flask schema holes (`timeout_seconds` / batch `libraries`)

**Role / ID:** 05 — Flask `/run` + `/run/batch` schema  
**Date:** 2026-08-16  
**Owns:** `backend/middleware/schemas.py`, `backend/app.py` (`execute_run_payload` + batch inner), `tests/test_backend.py`  
**Verdict:** **closed**

## Goal

Close two residual Flask schema holes:

1. `POST /run` rejected `timeout_seconds` (`UNKNOWN_FIELDS`) even though `Runtime.run` already implements the wall-clock breaker.
2. `POST /run/batch` rejected `libraries`, so AXIS git-publish `import ns/Name/ver` only worked on single `/run`.

Existing clients that omit the new fields must keep working. Unknown extra keys must still be `UNKNOWN_FIELDS` 400.

## What we did

### `backend/middleware/schemas.py`

- `RUN_SCHEMA`: optional `"timeout_seconds": (float, False, None)`. Missing / `null` → `None` (no timeout).
- `RUN_BATCH_SCHEMA`: `"libraries": (list, False, [])` and the same optional `timeout_seconds` (cheap; applied to every script in the loop).

### `backend/app.py`

- `_parse_run_libraries` — shared max-32 `{namespace, name, version, source}` parse used by `/run` and `/run/batch`.
- `_timeout_seconds_kwarg` — passes `timeout_seconds=` into `Runtime.run` **only** when the value is set and `> 0`.
- `/run` (`_execute_run_payload_inner`) forwards timeout and surfaces `timed_out` on both the 500 `EXECUTION_ERROR` body and the success body if Runtime set it.
- `/run/batch` (`_run_pine_script_batch_inner`) passes `libraries=` (and optional timeout) into each `runtime.run` in the loop; per-script errors include `timed_out` when present.

### Tests (`tests/test_backend.py`)

1. `test_run_timeout_seconds_accepted` — `/run` with `timeout_seconds: 30.0` is 200, plots match, not `timed_out`.
2. `test_run_unknown_field_rejected` — extra key still 400 `UNKNOWN_FIELDS` even when `timeout_seconds` is also sent.
3. `test_run_batch_libraries_git_publish` — `/run/batch` with the same `import ns/Lib/1` payload as `test_run_libraries_git_publish` returns `[1.5, 1.5]`.

Omit-field clients remain covered by `test_run_success` / `test_run_batch_success`.

### Docs (surgical)

- `docs/pyne/api/endpoints/run.mdx` — `timeout_seconds` on `/run`; `libraries` + `timeout_seconds` on `/run/batch`.
- `docs/pyne/api/contract.mdx` — same; `timed_out` mapping no longer “not Flask”.
- `docs/pyne/enduser/guides/evaluate-scripts.mdx` — no longer claims `/run` rejects timeout.
- `docs/pyne/enduser/guides/pro-api-usage.mdx` — field table + batch + invariants.
- `docs/pyne/enduser/reference/modes.mdx` — timeout / libraries surfaces include HTTP.
- Residual rows removed from `COMPATIBILITY.md`; matching accordion/failure-mode lines in `docs/pyne/reference/compatibility.mdx`.

Did **not** touch TA, compiler plot keys, pynets, or trail.

## Verify

```
PYTHONPATH=src:. .venv/bin/python -m pytest tests/test_backend.py -q --tb=short
```

## Residual / not in this close

- `/run/batch` still has no `inputs` (out of scope).
- Timeout still returns HTTP 500 `EXECUTION_ERROR` when Runtime sets both `error` and `timed_out` (existing error-key contract). Body now includes `timed_out: true`.
- Interpret timeout is still checked every 32 bars (Runtime host; unchanged).
- Docs outside the allowed list (e.g. `runtime-bridge.mdx`, `glossary.mdx`, `troubleshooting.mdx`) may still say timeout is library-only.
