# AGENT 08 — Hardened error handling (Runtime + evaluator)

**Role:** CORRECTNESS — fail closed; classify errors; improve messages  
**Date:** 2026-07-31  
**BASE_SHA:** `32697c97f7e56de817325356e4dbd692809ecbe8`

## Scope & files

| File | Change |
| --- | --- |
| `backend/runtime.py` | `_error_payload` / `_format_exc_message`; classified error kinds; bar index in messages; OHLCV pack data errors |
| `backend/app.py` | Forward `error_kind` / `error_type` / `error_bar` on `/run` failures |
| `backend/evaluator.py` | Document `_maybe_registry` soft-fail surface (plot ids optional) |
| `src/pynescript/ast/evaluator/expressions.py` | `_type_error_from_callee` — body TypeError fails closed; signature mismatch still → `na` |
| `src/pynescript/ast/evaluator/builtins/base.py` | Same for kwargs dispatch retries in `_call_builtin` |
| `src/pynescript/ast/evaluator/builtins/__init__.py` | Re-raise TypeError/AttributeError/ValueError from `_apply_strategy_declaration` |
| `src/pynescript/ast/evaluator/statements.py` | Reassignment: only AttributeError/TypeError soft; other Exception → `_error` |
| `src/pynescript/ast/evaluator/builtins/utility.py` | Comment: setattr soft-fail is mock/frozen only |
| `src/pynescript/ast/evaluator/builtins/request.py` | Module doc: intentional mock soft-fail (do not hard-fail) |
| `tests/test_error_handling.py` | New regressions |

## Bugs found

1. **Call dispatch swallowed body `TypeError` as `na`.**  
   `except TypeError: return None` (and kwargs-arity retries) treated *all* TypeErrors as signature mismatch. A callable that raised TypeError *inside* its body produced silent `na` / successful empty plots instead of a Runtime error.
2. **Strategy declaration apply soft-failed all exceptions.**  
   Bad `initial_capital` / numeric coercion errors left `StrategyState` defaults without surfacing.
3. **Reassignment `setattr` bare `except Exception`.**  
   Unexpected errors could fall through without a clear `_error` if dict path also missed.
4. **Runtime errors were untyped strings only.**  
   Hosts could not distinguish parse vs compile vs runtime vs order vs data without prefix scraping; bar index missing from messages.

## Changes (hardened sites)

### Runtime (`backend/runtime.py`)

| Site | Before | After |
| --- | --- | --- |
| Unknown mode | `{"error": "..."}` | `error_kind=mode` |
| Parse failure | `"Parse Error: {e}"` | `error_kind=parse`, `error_type`, `Parse Error: Type: detail` |
| Order fill | message only | `error_kind=order`, bar index + type |
| Bar-loop `visit` | message only | `error_kind=runtime`, `error_bar` / `error_bar_time`, type in message |
| Compile import / no numba | message only | `error_kind=compile` |
| `compile_script` | message only | `error_kind=compile` + type |
| OHLCV pack | uncaught / opaque | `error_kind=data` |
| Compiled run | message only | `error_kind=runtime` + type |
| `resolve_request_sources` | soft `except Exception` | **unchanged** (intentional → mocks) |
| Logger / drawings / color JSON | soft | **unchanged** (host plumbing) |

Error kinds: `parse` | `compile` | `runtime` | `data` | `order` | `mode`.

### Evaluator call sites

| Site | Hardening |
| --- | --- |
| `expressions._SITE_B` / `_SITE_BB` user callables | Re-raise if `_type_error_from_callee` |
| `expressions._ext_method` / extension methods | same |
| `expressions._visit_Call_general` final call | same |
| `expressions` UDT field callable | same |
| `builtins.base._call_builtin` kwargs retry | Re-raise body TypeError before next convention |
| `builtins.__init__` strategy() apply | Propagate TypeError/AttributeError/ValueError |
| `statements` reassignment setattr | Narrow soft-fail; unexpected → `_error` |
| `request.*` data fetch | **Preserved soft-fail** (documented) |

### API

`/run` error body may include additive fields: `error_kind`, `error_type`, `error_bar`. Legacy `message` / `error` string kept.

## Benchmarks

N/A (correctness only; no hot-path allocation changes beyond a traceback attribute check on TypeError paths).

## Tests run

```bash
PYTHONPATH=src:. .venv/bin/python -m pytest tests/test_error_handling.py -v --tb=short
# 10 passed

PYTHONPATH=src:. .venv/bin/python -m pytest \
  tests/test_error_handling.py tests/test_request_data_feed.py \
  tests/test_parity.py tests/test_strategy_runtime.py \
  tests/test_datafeed_wiring.py tests/test_evaluator.py -q --tb=line
# 306 passed
```

## Residual risks

- Traceback-depth heuristic: C-extension TypeErrors with atypical frames might still soft-fail or hard-fail incorrectly (rare for Pine UDFs).
- Pine-native arithmetic still maps many bad ops to `na` by design (not TypeError) — unchanged.
- Strategy soft-fail remaining only for non-programming Exception subclasses on apply (should be rare).
- Compile auto-fallback still uses string `compile_fallback_reason` (may include new typed prefixes).

## Out of scope

- Hard-failing `request.*` on missing mock/live data  
- Full structured error codes for every builtin  
- expressions binary-op na soft-map redesign  
- Massive Runtime refactor / dual-host worker patch  
- Logging subsystem for host-side structured telemetry  

## ≤20-line summary

Classified Runtime errors (`error_kind` ∈ parse/compile/runtime/data/order/mode) with `error_type` + bar index; improved messages. Call dispatch no longer maps **body** TypeError → silent `na` (signature mismatch still soft). Strategy declaration ValueError/TypeError propagates. Reassignment setattr narrowed. `request.*` mock soft-fail preserved + documented. Tests in `tests/test_error_handling.py` (10). No push.
