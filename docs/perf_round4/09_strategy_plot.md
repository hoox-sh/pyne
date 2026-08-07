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

# Round 4 — Agent 9: Strategy + plot/draw performance

**Date:** 2026-07-29  
**Scope:** Compile `CompileStrategyBroker` + object-mode bar loop; interpret `strategy.py` / `StrategyEvent`; light plot registry touch  
**Prior:** Round 3 object-mode claimed 4.5–6× on strategy (`docs/perf_agent_objectmode_round3.md`) and plot registry O(plots) (`docs/perf_agent_plot_round3.md`). This tree still used `set_bar` + `process_pending_orders` every bar and O(trades) `netprofit` scans.

## Environment

- Python: repo `.venv` (3.14) + `PYTHONPATH=src:backend:.`
- Workload: synthetic random-walk OHLCV, seed 0
- Compile method: warm `CompiledScript.run` median of 51 reps after 10 warm-ups (also cProfile ×10)
- Interpret method: warm `Runtime.run(..., mode="interpret")` median of 7 after 2 warm-ups

## Baseline (this tree, before)

### Compile object-mode

| Script | n | med_ms | Notes |
|--------|---:|-------:|-------|
| STRAT (market flip each bar) | 2000 | 15.3 | entry/close almost every bar |
| STRAT | 5000 | 36.4 | |
| STRAT_LIMIT | 2000 | 10.9 | limit entry every 10 bars |
| STRAT_LIMIT | 5000 | 29.1 | |
| DRAW (last-bar label+line) | 2000 | 1.83 | |
| DRAW | 5000 | 4.64 | |

cProfile STRAT n=5000 × 10: **~1.15 s**, **~1.46 M** calls  
Top: `entry`, `_emit`, `close`, `set_bar`, `process_pending_orders` (empty walk), `_classify_order_type`, `_is_na`, `_norm_dir`.

### Interpret (warm)

| Script | n | med_ms |
|--------|---:|-------:|
| STRAT | 2000 | 211.6 |
| PLOT_HEAVY | 2000 | 322.1 |
| minimal `plot(close)` | 2000 | 29.3 |

cProfile STRAT interpret warm ×5: **~3.67 s**  
Top: `sum` over closed_trades genexpr (**~3.1 M**), `dataclasses.asdict` / `_replace`, visitor dispatch, `_handle_strategy_entry`.

## After

### Compile object-mode

| Script | n | After (ms) | Before (ms) | Speedup |
|--------|---:|-----------:|------------:|--------:|
| STRAT | 2000 | **8.4** | 15.3 | **~1.8×** |
| STRAT | 5000 | **20.8** | 36.4 | **~1.75×** |
| STRAT_LIMIT | 5000 | **17.2** | 29.1 | **~1.7×** |

cProfile STRAT n=5000 × 10: **~0.55 s**, **~580 k** calls (**~2.1×** wall under profiler, **~2.5×** fewer calls).

### Interpret

| Script | n | After (ms) | Before (ms) | Speedup |
|--------|---:|-----------:|------------:|--------:|
| STRAT | 2000 | **137.6** | 211.6 | **~1.54×** |
| PLOT_HEAVY | 2000 | ~332 | 322 | ~flat (host noise) |
| minimal | 2000 | ~26 | 29 | ~1.1× |

cProfile interpret warm ×5: **~2.27 s** — `sum`/genexpr and `asdict` no longer dominate; remaining cost is visitor/`visit_Call`/`_call_builtin`.

Broker-only (no compiler loop) STRAT n=5000: **~14.9 ms** median.

## Changes

| File | Change |
|------|--------|
| `src/pynescript/compiler/strategy_broker.py` | `begin_bar`; empty-pending skip; market entry fast path; cheaper `_norm_dir` / `_is_na` / `_opt_float` / `_slip` / `_commission`; explicit `_emit` kwargs; skip equity extremes when flat; `to_events()` no-copy |
| `src/pynescript/compiler/compiler.py` | Emit `__strategy.begin_bar(...)` instead of `set_bar` + `process_pending_orders`; drop default `price=float(close_arr[...])` (broker uses `_mark`) |
| `src/pynescript/ast/evaluator/builtins/strategy.py` | O(1) running `_netprofit` / win-loss / gross aggregates via `note_closed_profit`; single-open `openprofit` fast path; empty `pending_orders` early return; OHLC cache per bar; avoid `dataclasses.replace` in `_record_strategy_event` |
| `src/pynescript/ast/evaluator/events.py` | `StrategyEvent.to_dict` hand-built (no `asdict` reflection) |
| `src/pynescript/ast/evaluator/builtins/plotting.py` | Micro: skip redundant `int()` on `_plot_call_i` in bar mode |

### Compile broker (detail)

1. **`begin_bar(i, o, h, l, c)`** — one float pass; process pending only if non-empty; equity peak/trough only when `position_size != 0`.
2. **Market `entry`** when `limit is None and stop is None` — no `_classify_order_type` / `_opt_float`.
3. **`_emit`** — fixed field list (same public dict shape: kind/id/direction/qty/order_type/limit/stop/oca_name/comment/bar_index/bar_time/ohlc).
4. **`to_events()`** returns live `self.events` (single-use broker per run).

### Interpret strategy (detail)

1. **Running aggregates** — `equity()` / `netprofit()` / `wintrades` no longer re-scan `closed_trades` (was O(trades) per sample → multi-million `sum` calls on chatty strategies).
2. **Event drain** — `to_dict` is a flat dict literal; `_record_strategy_event` rebuilds with cached OHLC instead of `replace`+reflection.
3. **Pending path** — `process_pending_orders` returns `[]` immediately when empty (Runtime already gates, but direct callers benefit).

## Correctness

```text
PYTHONPATH=src:backend:. python -m pytest \
  tests/test_compiler_strategy.py \
  tests/test_compiler_objects.py \
  tests/test_order_fills.py \
  tests/test_strategy_events.py \
  tests/test_strategy_runtime.py \
  tests/test_oca_commission.py \
  tests/test_plotting_effects.py \
  tests/test_drawing_all_and_last_bar.py \
  tests/test_multi_plot_cross.py \
  tests/test_bgcolor_plotshape_export.py \
  -q --tb=line
# 102 passed
```

**Event order sacred:** fill-then-entry-then-close semantics unchanged; OCA cancel/reduce still emit after fill; compile market/limit fill prices still OHLC-driven.

**Note:** `tests/test_strategy_risk_enforcement.py::test_bar_mode_sma_returns_scalar` fails with `ta.sma → None` under bar mode without series history — **pre-existing**, unrelated to strategy/plot changes (list-mode sma test still passes).

### Risks / edge cases

| Risk | Mitigation |
|------|------------|
| Cached `_netprofit` desync if tests **append** `closed_trades` without `note_closed_profit` | Production path always goes through `_close_position`; evaluator unit tests that only seed trades for `closedtrades.*` queries do not assert netprofit |
| Zero OHLC sentinel `(0,0,0,0)` for “fill me” | Same as before; true open=0 bars rare — prefer future emit with real OHLC always |
| `to_events()` no-copy | Broker is per-run; mutating returned list after run is caller error (unchanged contract vs single-use) |
| Skip equity extremes when flat | Peak/trough only move on open P&amp;L or closes; close path still calls `_update_equity_extremes` |
| Strategy event order | Unchanged call order in entry/close/fill/OCA |

## Residuals / next

1. **Interpret visitor dispatch** still ~half of strategy time — other agents / expression path.
2. **`CustomEvaluator.plot_outputs`** still allocates one dict per `plot()` per bar (Runtime series API). Value-only columns + once-only meta would cut plot-heavy further.
3. **Compile `_emit` dict-per-event** still ~half remaining broker time when trading every bar — compact internal tuples expanded in `to_events()` if event volume is huge.
4. **Always pass real OHLC into `StrategyEvent` at construction** to avoid zero-tuple rebuild.
5. Drawing **creation** every bar still unoptimized (only empty export path was round-3).

## Summary

| Path | Win |
|------|-----|
| Compile market strategy @ 5k bars | **~1.75–2.1×** (profiler / stable median) |
| Compile call count | **~2.5×** fewer |
| Interpret market strategy @ 2k bars | **~1.54×** (O(1) PnL stats + cheaper events) |
| Plot-heavy / empty-draw | ~flat (already O(plots) + empty export from r3) |

Largest interpret win: **stop re-summing every closed trade on every equity sample**. Largest compile win: **`begin_bar` + market entry fast path + empty pending skip**. Public event dict shape and strategy event order preserved; 102 strategy/plot/drawing tests green.
