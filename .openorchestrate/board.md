# Board

> One place for work. Statuses: Todo · Working · Blocked · Ready for Review · Done.
> Nothing is done until this file says Done.

| task                                                         | owner      | status           | priority | proof                                                                                                                                                                                                             | blockedReason | source |
| ------------------------------------------------------------ | ---------- | ---------------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------- | ------ |
| Flask RUN_SCHEMA: add timeframe so AXIS POST /run is not 400 | oo-checker | Ready for Review |          | `.venv/bin/python -m pytest tests/test_schemas_coverage.py tests/test_backend.py::TestRun tests/test_backend_ws.py::TestWsEnvelopePayload -v --tb=short` → 54 passed, exit 0. Handoff: from oo-misc → oo-checker. |               | AXIS   |

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
