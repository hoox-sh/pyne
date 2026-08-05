# AGENT 06 — Strategy dual-path (Round 8)

| Field | Value |
| --- | --- |
| **Role / ID** | Agent 06 — Strategy dual-path |
| **Verdict** | **partial** |
| **Date** | 2026-08-04 |

## What you did (files touched)

| File | Change |
| --- | --- |
| `src/pynescript/compiler/strategy_broker.py` | Exit fill-price parity for compiler-mapped `strategy.exit` → `close(stop=…, limit=…)`; emit `kind=exit`; `openprofit_percent` / `netprofit_percent` / gross % / `cash` / avg_trade*; `default_qty_type`/`value` + resolve when qty omitted; eventrades on zero PnL |
| `src/pynescript/ast/evaluator/builtins/strategy.py` | Sanitize `bar_time`/`bar_index` on all strategy events (`PineSeries` → int); exit/cancel use `_bar_time()` / `_bar_index()` |
| `tests/test_compiler_strategy.py` | Goldens for exit limit fill, openprofit_percent plot, percent_of_equity qty, JSON-safe bar_time |

Did **not** edit `compiler.py` / `numba_builtins.py` (other agents).

## Root causes fixed

1. **`strategy.exit` compile path ignored stop/limit**  
   Visitor maps `exit` → `__strategy.close(..., stop=…, limit=…)`. `close()` dropped those kwargs and closed at **mark**, so netprofit/open series diverged from interpret (which fills at the chosen limit/stop leg price, including the legacy “between legs → pick limit” oracle used by parity fixtures).

2. **Missing compile series attributes**  
   Plots of `strategy.openprofit_percent` / `netprofit_percent` raised  
   `AttributeError: 'CompileStrategyBroker' object has no attribute 'openprofit_percent'` → `compile_error`.

3. **Interpret event `bar_time` was sometimes `PineSeries`**  
   `strategy.exit` / `cancel` used raw `context["time"]`. Broke `tests/test_parity.py` JSON compare (`TypeError: Object of type PineSeries is not JSON serializable`).

4. **Default qty**  
   Compile `entry(qty=None)` always used 1.0. Broker now resolves fixed / percent_of_equity / cash when `default_qty_*` is set on the ctor (visitor still must pass them — see handoff).

## Before / after

### Unit / dual-path probes

| Case | Before | After |
| --- | --- | --- |
| Exit + fixed stop/limit | `np`/`ps` diverge (compile @ mark) | **Series + event kinds match** interpret |
| `plot(openprofit_percent)` compile | **compile_error** | **OK** series parity |
| Simple fixed entry/close plots | mostly OK | still OK (`ps`/`op`/`np`/`eq`) |
| `default_qty_type=percent_of_equity` full script | qty 1 vs ~10 | still mismatch **until Agent 03 wires ctor** (broker ready) |
| Parity fixtures `strategy_06` / `07` | FAIL (PineSeries bar_time) | **PASS** with rest of strategy suite |

### Builtin strategy plot parity (`compare_interp_compile`, bars=100)

`barupdn_strategy`, `macd_strategy`, `supertrend_strategy` → **3/3 OK** after fixes.

### Known corpus samples (PROMPT list)

| Script | Status | Notes |
| --- | --- | --- |
| `set01/strategies/045_str_ha_univlong…` | **MISMATCH** remains | `plot_0`/`plot_1` = SSL from **heikinashi `request.security`** + `Hlv[1]` history — **not** position-derived. Handoff Agent **08** / history. |
| `set01/strategies/073_str_stochrsi…` | **MISMATCH** remains | Tendence MA / Supertrend values — **TA kernels** (Agent **02** / **05**). Strategy body does not drive those plots. |
| `set02/strategies/071_str_multi_vwap…` | **MISMATCH** (slow) | Entry/SL/TP **and** Midnight/Session VWAP. VWAP cascade + UDT-heavy script; position plots depend on signals. Not fixed in broker alone. |

## Tests run

```bash
PYTHONPATH=src:. .venv/bin/python -m pytest \
  tests/test_compiler_strategy.py \
  tests/test_oca_commission.py \
  tests/test_strategy_runtime.py \
  tests/test_order_fills.py \
  tests/test_parity.py \
  tests/test_strategy_events.py \
  -q --tb=line
# 117 passed

PYTHONPATH=src:. .venv/bin/python scripts/compare_interp_compile.py \
  --files tests/data/builtin_scripts/{barupdn,macd,supertrend}_strategy.pine \
  --bars 100 --ignore-hline-keys --ignore-fill-keys
# 3 OK
```

New goldens in `TestCompileExitAndSeriesParity` all green.

## Residual / handoff

### Agent 03 (`compiler/compiler.py`) — needed for remaining dual-path

1. **Wire `default_qty_type` / `default_qty_value` into `CompileStrategyBroker(...)`**  
   Same loop as `initial_capital` / `pyramiding` (~L860). Broker already accepts and uses them.

2. **`strategy.cash` series vs constant**  
   `cash` is treated as qty-type constant (`return repr(attr)` → `'cash'`), so  
   `plot(strategy.cash)` becomes `safe_float('cash')`. Put `"cash": "__strategy.cash"` in `series_map` **before** the constant list (or disambiguate series vs type token).

3. **`begin_bar(..., bar_time=time_arr[__bar_idx])`**  
   Compile events still have `bar_time=0`. Interpret has real times. Plot series unaffected; event consumers care.

4. Optional: map `"exit": "exit"` and add broker `exit()` alias (currently `close` handles stop/limit; works but naming is confusing).

### Agent 02 / 05

- `073` supertrend / EMA length-200 na policy  
- Any crossover timing that makes strategy entries diverge when both paths use market entry

### Agent 08

- `045` heikinashi `request.security` + history na on early bars

### Agent 12 (harness)

- nan vs `None` already equal in `series_allclose` — no change required for flat `position_avg_price`

### Intentional interpret oracle retained

`strategy.exit` with both stop and limit still **immediately** realizes at a chosen leg price even when mark is between legs (parity fixture `strategy_06_exit_stop_limit`). Compile now matches that oracle; true TV pending brackets are **not** modeled on either path.

## Verdict

**partial** — recovered exit/openprofit series dual-path + fixed compile AttributeError and event JSON bar_time; builtin strategy plot smoke green. Corpus MISMATCH samples 045/073/071 remain for security/TA/VWAP owners; percent_of_equity end-to-end still needs compiler ctor wiring (broker ready).
