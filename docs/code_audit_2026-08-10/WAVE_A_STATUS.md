# Wave A implementation status — 2026-08-10

Implemented after the full-repo audit. Scope: **security + CI honesty + docs**.

## Done

| Item | Status | Notes |
|------|--------|-------|
| SSRF lock-down on webhooks | **Done** | `backend/alert_forwarder.py` blocks private/loopback/metadata; `ALERT_WEBHOOK_ALLOW_PRIVATE=1` opt-in |
| Free-path bar/script/rate/concurrency limits | **Done** | `backend/middleware/free_limits.py`; wired into `/run`, `/run/batch`, `/compile/prewarm`, WS run |
| Free-path external data sources blocked | **Done** | Only `chart` / `mock` / empty on free routes |
| Hash-only JSON API key store | **Done** | Raw secrets never written; legacy raw-key files migrated on load |
| CI core-runtime job | **Done** | First-party parity, strategy, series, expr, free-limits |
| First-party always-on fixtures | **Done** | `tests/data/first_party/*.pine` |
| Silent-pass → skip | **Done** | `test_parity_r9_kernels`, optional corpus in `test_parity` / interp_compile |
| Known divergences doc | **Done** | `docs/known_divergences.md` |

## Env knobs (ops)

| Variable | Default | Meaning |
|----------|---------|---------|
| `FREE_MAX_BARS` | 5000 | Max OHLCV bars on free runs |
| `FREE_MAX_SCRIPT_CHARS` | 262144 | Max Pine source length |
| `FREE_MAX_CONCURRENT` | 4 | Simultaneous free runs per worker (`0` = off) |
| `FREE_RATE_LIMIT` | 60 | Max free requests per IP per window (`0` = off) |
| `FREE_RATE_WINDOW_SEC` | 60 | Rate-limit window |
| `ALERT_WEBHOOK_ALLOW_PRIVATE` | unset | Allow private webhook URLs (dev only) |

## Tests

```bash
FREE_RATE_LIMIT=0 FREE_MAX_CONCURRENT=0 ADMIN_TOKEN=ci-test-admin-token \
 python -m pytest \
 tests/test_interp_compile_parity.py tests/test_parity.py \
 tests/test_expr_parity_r8.py tests/test_strategy_runtime.py \
 tests/test_order_fills.py tests/test_series_cap.py \
 tests/test_series_ring_buffer.py tests/test_alert_forwarder.py \
 tests/test_free_limits.py tests/test_backend.py \
 -q -k "not optional_corpus"
```

Local result (2026-08-10): **core-runtime gate 162 passed / 7 skipped**; backend suite **57 passed**.

## Deferred to Wave B+

- `strategy.exit` pending bracket semantics
- `ta.atr` → Wilder RMA
- `varip` realtime semantics
- `AugAssign` series bind funnel
- Linter C004 / unparser `visit_Simple`
- `test_ta_incremental` residual failures (kept out of CI gate)
- Full `test_compiler_numba` PR gate (too slow / large)
