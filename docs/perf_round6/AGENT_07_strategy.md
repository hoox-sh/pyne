# Round 6 — AGENT 07: Strategy correctness + compile broker

**AGENT_ID:** 07  
**ROLE:** Strategy correctness + compile broker (CORRECTNESS + PERF)  
**BASE_SHA:** 32697c97f7e56de817325356e4dbd692809ecbe8  
**Date:** 2026-07-31

## 1. Scope & files touched

| File | Change |
| --- | --- |
| `src/pynescript/ast/evaluator/builtins/strategy.py` | Exit commission + exit slippage; strict qty/direction parse; reject bad args |
| `src/pynescript/compiler/strategy_broker.py` | Same commission/slippage model; pyramiding; reverse event parity; reject bad args |
| `src/pynescript/compiler/compiler.py` | Wire `pyramiding=` into `CompileStrategyBroker(...)` |
| `tests/test_oca_commission.py` | Updated commission oracle; exit slip / invalid args / pyramiding parity |
| `tests/test_compiler_strategy.py` | Net 79 (entry+exit); pyramiding decl wiring |

**Not touched:** events.py shape types, interpret dispatch, TA, LSP, Runtime host.

## 2. Bugs found

| Severity | Bug | Fix |
| --- | --- | --- |
| **High** | Compile broker ignored `pyramiding` (always averaged market adds); compiler never passed the kwarg | Track `open_entry_count`; market entry respects room; ctor + visitor wire `pyramiding` |
| **High** | Bad `qty` (`"not_a_number"`, `NaN`) silent-filled as 1.0 / NaN size via `_coerce_number` | `_parse_order_qty` → reject with `comment="invalid_qty"`, no position |
| **Medium** | Invalid direction (`"sideways"`) opened a position with garbage direction | `_normalize_entry_direction` / `_norm_dir` → `invalid_direction` event |
| **Medium** | Exit fills charged **no** commission (entry-only); TV charges both sides | Both paths charge exit commission on close; openprofit still entry-only drag |
| **Medium** | Exit fills ignored slippage (entry-only slip) | Close / reverse / market exit apply adverse slip |
| **Low** | Compile reverse emitted `close` + `close_all`; interpret only `close` | Reverse uses `close(..., comment="reverse")` only |

## 3. Changes (what / why)

1. **Commission model (TV-closer, compile↔interpret parity)**  
   - Entry: charge & store on open trade / `position_commission` (openprofit drag).  
   - Exit: `_calc_commission` / `_commission` on close qty×price; subtract from trade profit.  
   - Example: 10@100 → 110 @ 1% → net **79** = 100 − 10 entry − 11 exit (was 90 entry-only).

2. **Exit slippage**  
   - Long close / cover short: slip against trader (sell lower / buy higher).  
   - Explicit `price=` on compile close skips re-slip (pending fills already slipped).

3. **Pyramiding (market entry)**  
   - Compile matches interpret: same id → replace overwrite; different id + room → add; else ignore.  
   - Pending order fills still average (documented residual).

4. **Safer order args**  
   - Emit diagnostic `kind="order"` with `qty=0` and `comment=invalid_qty|invalid_direction`.  
   - Pine `na` qty remains “missing” → default sizing (not a hard error).

## 4. Benchmarks

Correctness agent — no perf claim. Broker hot paths (`begin_bar`, empty pending skip) unchanged structurally.

## 5. Tests run

```bash
PYTHONPATH=src:backend:. .venv/bin/python -m pytest \
  tests/test_oca_commission.py tests/test_order_fills.py \
  tests/test_compiler_strategy.py tests/test_strategy_runtime.py \
  tests/test_strategy_events.py tests/test_strategy_risk_enforcement.py \
  tests/test_parity.py -q --tb=line
# 94 passed, 1 xfailed (pre-existing bar-mode SMA)
```

## 6. Residual risks / follow-ups

| Item | Notes |
| --- | --- |
| Pending-fill pyramiding | Order fills still average when `pyramiding≤0` (R5 residual); market path is strict |
| `cash_per_order` on partials | One fee per close call (not pro-rated by partial fraction beyond percent model) |
| Same-id replace | Overwrites without realizing PnL (interpret oracle); not a full cancel+rebook |
| Slippage on limit/stop exit prices | Trigger prices used as-is; only pure market exits re-slip |
| Scripts assuming entry-only commission | Netprofit lower by exit commission when `commission_value>0` — intentional model fix |

## 7. Out of scope

- Interpret visit/dispatch, TA kernels, LSP, Runtime wrap, grammar  
- Full TV margin / `process_orders_on_close` / `calc_on_every_tick`  
- Commit / push (parent merge)
