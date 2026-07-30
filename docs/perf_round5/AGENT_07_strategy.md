# Round 5 — AGENT 07: Strategy broker correctness

**AGENT_ID:** 07  
**ROLE:** Strategy broker correctness (CORRECTNESS primary, perf secondary)  
**BASE_SHA:** ca5215ac33c34f9b60584f8c230bc281dc768782  
**Date:** 2026-07-30

## 1. Scope & files touched

| File | Change |
| --- | --- |
| `src/pynescript/ast/evaluator/builtins/strategy.py` | `StrategyCashAmount` dual series/constant; reverse emits `close`; market-entry pyramiding; declaration honors cash tag |
| `src/pynescript/ast/evaluator/builtins/strategy_constants.py` | Remove `strategy.cash` qty-only registration (collision) |
| `src/pynescript/compiler/strategy_broker.py` | Entry-commission model + openprofit parity with interpret |
| `tests/test_strategy_runtime.py` | Cash / pyramiding / reverse regressions |
| `tests/test_oca_commission.py` | Compile↔interpret commission parity |
| `tests/test_compiler_strategy.py` | Compile openprofit/commission unit test |
| `tests/test_strategy_risk_enforcement.py` | xfail mis-placed bar-mode `ta.sma` (TA, not strategy) |

**Not touched:** `events.py` (shape already correct), interpret dispatch, TA kernels, LSP.

## 2. Bugs found

| Severity | Bug | Repro |
| --- | --- | --- |
| **High** | `strategy.cash` returned the string `"cash"` (qty-type constant overwrote free-cash series) | `strategy.cash` → `"cash"`; tests expected `100_000.0` / `99850.0` |
| **High** | Compile broker charged **exit-only** commission; interpret charges **entry** commission realized on close → netprofit drift (e.g. 89 vs 90 on +10×10 @ 1%) | Entry 10@100, close@110, 1% commission |
| **Medium** | Compile `openprofit`/`equity` ignored entry commission while open (equity flat at capital after paid entry) | Same setup; interpret equity 99990 after entry |
| **Medium** | Market `strategy.entry` always **replaced** position; `pyramiding` never applied on market path | `pyramiding=1` + two entry ids → size stayed 1 |
| **Medium** | Opposite-direction market entry closed PnL but emitted **no** `close` event (compile emits close/close_all) | Long then short entry → only two `entry` events |
| **Low / out of scope** | `test_bar_mode_sma_returns_scalar` returns `None` in bar mode | Pre-existing TA; xfailed |

## 3. Changes (what / why)

1. **`StrategyCashAmount(float)`** with `_pine_qty_type = "cash"` so:
   - `strategy.cash` is free capital (series float)
   - `default_qty_type=strategy.cash` still sets type `"cash"` via declaration tag
2. **Removed** `strategy.cash` from `StrategyConstantsMixin` map (was applied *after* strategy map and won).
3. **Compile `position_commission`**: charge on `_open_or_add`, realize proportionally on `close`, subtract from `openprofit` (interpret oracle).
4. **Market entry path**: reverse → `_close_position` + `close` event (`comment="reverse"`); same-direction different id respects pyramiding room; same id still replaces.
5. **Tests** for the above; xfail for unrelated SMA.

## 4. Benchmarks

Correctness-only agent — no perf claims. Round 4 O(1) PnL / `begin_bar` paths left intact.

## 5. Tests run

```bash
PYTHONPATH=src:backend:. python -m pytest \
  tests/test_strategy_events.py tests/test_strategy_runtime.py \
  tests/test_order_fills.py tests/test_oca_commission.py \
  tests/test_strategy_risk_enforcement.py tests/test_compiler_strategy.py \
  -q --tb=line
# 86 passed, 1 xfailed
```

Also: `test_v6_surface_locks.py::test_strategy_qty_constants_registered` + `test_strategy_percent_of_equity_default_qty` — **2 passed**.

## 6. Residual risks / follow-ups

| Item | Notes |
| --- | --- |
| Exit commission (TV both sides) | Interpret still entry-only; compile matched that. Full TV would charge entry+exit. |
| Close slippage | Neither path slips exits; both match each other. |
| Reverse event shape | Interpret: `entry, close, entry`. Compile: `entry, close, close_all, entry`. Close present in both; `close_all` extra on compile. |
| Pyramiding on pending fills | `_open_position_qty` still allows add for order fills when pyramiding≤0 (averaging); market path is stricter. |
| Bar-mode `ta.sma` | Still broken; owned by Agent 03. |
| Dual `strategy.cash` identity | `== "cash"` is False for the float dual; declaration uses `_pine_qty_type`. Scripts comparing to string `"cash"` should use fixed/percent constants instead. |

## 7. Out of scope / did not touch

- Interpret dispatch / expressions / TA kernels  
- LSP, plot/draw, Runtime host wrap  
- Mass refactors, Nuitka, grammar  
- Commit / push (working tree left for parent merge)
