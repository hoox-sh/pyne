# Board

> One place for work. Statuses: Todo · Working · Blocked · Ready for Review · Done.
> Nothing is done until this file says Done.

| task                                                                | owner      | status | priority | proof                                                                                                                                                                                                             | blockedReason | source | updated    | Id                                        |
| ------------------------------------------------------------------- | ---------- | ------ | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------- | ------ | ---------- | ----------------------------------------- |
| Flask RUN_SCHEMA: add timeframe so AXIS POST /run is not 400        | oo-checker | Done   |          | `.venv/bin/python -m pytest tests/test_schemas_coverage.py tests/test_backend.py::TestRun tests/test_backend_ws.py::TestWsEnvelopePayload -v --tb=short` → 54 passed, exit 0. Handoff: from oo-misc → oo-checker. |               | AXIS   | 2026-11-09 | flask-run-schema-add-timeframe-s-23893b80 |
| /ws/live script full.count matches evaluated prefix (AXIS lag loop) | pyne / HQ  | Done   | P0       | `PYTHONPATH=src .venv/bin/python -m pytest tests/test_live_ws.py -q --tb=short` → 22 passed. Handoff: `.openorchestrate/handoff/pyne-live-full-count.md`.                                                         |               | AXIS   | 2026-11-09 | ws-live-script-full-count-matche-04ad964a |

## Rules

- Every card has one owner.
- Five statuses, no more: Todo · Working · Blocked · Ready for Review · Done.
- If you are stuck, set Blocked, write why, and ping the Chief.
- Pass work as a handoff, not a transcript.
- A card moves to Done only with proof attached.

## Handoff format

```text
from:
to:
objective:
artifacts:
decisions:
open questions:
next gate:
```
