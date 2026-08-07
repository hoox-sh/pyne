# Copyright (C) 2024-2026 jango_blockchained
#
# This file is part of pynescript.
#
# pynescript is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pynescript is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: AGPL-3.0-or-later

# Round 7 — AGENT 10: F2 Pending-fill averaging (pyramiding ≤ 0)

**AGENT_ID:** 10  
**ROLE:** F2 — correct VWAP / single-leg semantics for stacked pending fills  
**BASE_SHA:** `045190203a1991aa683147995b5f42ee71169756`  
**Date:** 2026-08-02

## 1. Scope & files touched

| File | Change |
| --- | --- |
| `src/pynescript/ast/evaluator/builtins/strategy.py` | `_open_position_qty`: when `pyramiding ≤ 0`, merge same-direction pending fills into **one** open trade with VWAP entry (no multi-leg append) |
| `src/pynescript/compiler/strategy_broker.py` | Pending average-add path: document F2; force `open_entry_count = 1` when `pyramiding ≤ 0` |
| `tests/test_order_fills.py` | Golden tests: partial fills, multi-order VWAP, limit entries, short side, pyramiding>0 multi-leg preserved, close PnL vs avg, compile broker parity |
| `docs/perf_round7/AGENT_10_pending_fill.md` | This report |
| `docs/perf_round7/STATUS.md` | Agent 10 row |

**Not touched:** market-entry path (already strict), TA, LSP, Runtime host, grammar, expressions/call-site cache.

## 2. Semantics (interpret SoT)

### Before (loose residual from R5/R6)

When `pyramiding ≤ 0`, pending fills **did** update position size and position VWAP, but each fill **appended** a new `OpenTrade`. Effects:

- `strategy.opentrades` grew beyond 1 with default pyramiding
- Exit/FIFO closed multiple legs at each fill’s price instead of one VWAP book
- Partial fills of the **same** order looked like multiple pyramid entries

Market `strategy.entry` already blocked extra ids when `pyramiding ≤ 0` (R5).

### After (F2)

| Path | `pyramiding ≤ 0` | `pyramiding > 0` |
| --- | --- | --- |
| **Pending fills** (`strategy.order`, limit/stop `strategy.entry`) | Same-direction adds **merge** into a single open trade; size += fill; `entry_price` / leg price = **VWAP**; first leg’s `entry_id` / bar / time retained; **one entry event per fill** (event order unchanged) | Unchanged: append legs up to `pyramiding + 1`; further fills ignored |
| **Market `strategy.entry`** | Unchanged: different id blocked; same id replaces | Unchanged: room → add leg |

VWAP formula (long or short size absolute):

```text
new_avg = (old_avg * old_size + fill_price * fill_qty) / (old_size + fill_qty)
```

Commission on the merged leg = sum of prior leg commissions + this fill’s commission.

### Compile broker

Pending path still average-adds size / `position_avg_price` (no open-trade list). F2 locks `open_entry_count = 1` when `pyramiding ≤ 0`. Market path still uses `respect_pyramiding=True`.

## 3. Tests

```bash
PYTHONPATH=src:backend:. .venv/bin/python -m pytest \
  tests/test_order_fills.py \
  tests/test_oca_commission.py \
  tests/test_compiler_strategy.py \
  tests/test_strategy_runtime.py::TestStrategyCashAndPyramiding \
  tests/test_strategy_events.py \
  tests/test_strategy_risk_enforcement.py \
  -q --tb=line
# 81 passed, 1 xfailed (pre-existing bar-mode SMA)
```

New goldens in `tests/test_order_fills.py`:

| Test | Asserts |
| --- | --- |
| `test_pyramiding0_partial_fills_single_leg_vwap` | Partial same order → 1 leg, VWAP across fill prices |
| `test_pyramiding0_multiple_pending_orders_vwap_single_leg` | Two limits → size 6, VWAP, 1 leg, 2 entry events |
| `test_pyramiding0_limit_entry_pending_single_leg` | Two limit entries merge |
| `test_pyramiding0_short_pending_fills_vwap` | Short sell limits average |
| `test_pyramiding_gt0_pending_still_appends_legs` | `pyramiding=1` still 2 legs; third blocked |
| `test_pyramiding0_pending_vwap_close_uses_avg` | Close PnL vs single VWAP entry |
| `test_compile_pyramiding0_pending_fill_vwap` | Compile multi-order VWAP + `open_entry_count==1` |
| `test_compile_pyramiding0_partial_pending_vwap` | Compile partial fills VWAP |

## 4. Benchmarks

Correctness-only agent — no perf claim. Pending-fill hot path cost is one less `OpenTrade` allocation on merge vs append (minor).

## 5. Remaining TV oracle gaps

| Gap | Notes |
| --- | --- |
| TV `pyramiding` default naming | TV docs: default **1** = max open trades from `strategy.entry`. Pyne: default **0** = max **additional** (`max = pyramiding + 1`). Unchanged modeling choice. |
| `strategy.order` vs `strategy.entry` vs pyramiding | Live TV: pyramiding gates **entry** orders; `strategy.order` is freer. Pyne pending path averages under `pyramiding ≤ 0` (single leg) rather than hard-blocking a second order id. Market entry remains strict. |
| Pending + `pyramiding > 0` multi-leg on compile | Compile has no open-trade list; pending averages without incrementing `open_entry_count` beyond `max(1, …)`. Market path tracks legs. |
| Same-id market replace | Still overwrites without realizing PnL (prior residual). |
| Call-site / parse-cache pollution | Pre-existing: `_pine_call_site` bound method on shared parse AST ties `strategy.entry('L', strategy.long, 2.0)` to the first evaluator. Causes flaky failures in some `test_strategy_runtime` series tests when the same source string is reused across evaluators. **Not F2**; see `expressions.py` + parse cache. Workaround in tests: unique source strings or direct builtin map. |
| Full TV margin / `process_orders_on_close` / `calc_on_every_tick` | Out of scope. |

## 6. Verdict

**win** — F2 closed for interpret + compile pending fills: `pyramiding ≤ 0` stacked fills keep a single open leg with correct VWAP / size / close PnL; `pyramiding > 0` multi-leg behavior preserved under explicit goldens; market path untouched.
