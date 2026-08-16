# Copyright (C) 2024-2026 jango_blockchained
#
# This file is part of pynescript.
#
# SPDX-License-Identifier: AGPL-3.0-or-later

# Agent 07 — lock foreign `request.*` → `na`

| Field | Value |
| --- | --- |
| **Role / ID** | 07 — foreign `request.*` honest-na (no live feed) |
| **Verdict** | **win** |
| **Date** | 2026-08-16 |

## Policy (locked)

- **Same-symbol simple OHLCV** on the chart TF → passthrough (interpret + compile).
- **Foreign ticker** (`NOT_THE_CHART`, `UPVOL.NY`, `MSFT` under host `AAPL`, `ticker.new("ESD_FACTSET", …)`) → **`na`** on both hosts.
- **Foreign + complex UDF** (`year_sum(close)`, …) → **`na`** (never invent chart close as dividends / UPVOL).
- **No live foreign data** (no CCXT / Yahoo). Standalone `NodeLiteralEvaluator` without a host chart identity may still serve legacy mock OHLCV for offline demos.

## What was broken

`visit_Call` already emitted `np.nan` for `plot(request.security("UPVOL.NY", "D", close))`.

The **destructure / unpack** path did not consult chart-symbol identity. It visited the expression tuple and stored **chart** OHLCV:

```pine
[o, h, l, c] = request.security("UPVOL.NY", "D", [open, high, low, close])
[x] = request.security("NOT_THE_CHART", "D", close)
```

| Host | Before | After |
| --- | --- | --- |
| Interpret | all-`na` (foreign_na) | all-`na` |
| Compile unpack | `o_arr = open_arr`, `x_arr = close_arr` | `*_arr = np.nan` |
| Compile `plot(request.security(foreign, …, close))` | already `np.nan` | unchanged |

Same-symbol unpack (`syminfo.tickerid`, `""`, `ticker.heikinashi(...)`) is unchanged.

## Files touched

| File | Change |
| --- | --- |
| `src/pynescript/compiler/compiler.py` | Foreign unpack → `np.nan`; `_security_unpack_symbol_is_foreign` |
| `src/pynescript/ast/evaluator/builtins/request.py` | `request.security_lower_tf` foreign + host chart → `na` (no mock intrabar) |
| `tests/test_request_foreign_na.py` | **new** dual-host goldens |
| `tests/test_dividend_yield_parity.py` | ESD_FACTSET UDF now compile + interpret |
| `docs/gaps_close_2026-08-16/AGENT_07_request_na.md` | this report |

## Dual-host goldens (`tests/test_request_foreign_na.py`)

| Case | Interpret | Compile |
| --- | --- | --- |
| `request.security(syminfo.tickerid, "D", close)` on daily bars | chart close | chart close |
| `request.security("", "D", [open,…,close])` | chart OHLCV | chart OHLCV |
| `"NOT_THE_CHART"` close / `"close"` | all-`na` | all-`na` |
| `"UPVOL.NY"` close / `"close"` | all-`na` | all-`na` |
| `"NOT_THE_CHART"` + `year_sum(close)` | all-`na` | all-`na` |
| `"UPVOL.NY"` tuple unpack | all-`na` | all-`na` (emit `np.nan`) |
| `"NOT_THE_CHART"` single unpack `[x]` | all-`na` | all-`na` |

Existing: `test_foreign_security_string_close_is_na_both_modes`, `test_foreign_security_udf_expression_is_na` (now both modes).

## Tests run

```text
PYTHONPATH=src:. .venv/bin/python -m pytest \
  tests/test_dividend_yield_parity.py \
  tests/test_request_data_feed.py \
  tests/test_v6_features.py -k "security" \
  -q --tb=short
  → 23 passed, 45 deselected

PYTHONPATH=src:. .venv/bin/python -m pytest tests/test_request_foreign_na.py -q --tb=short
  → 8 passed

also: compiler security stubs + HA tuple unpack + Camarilla unpack
  → 37 passed (combined selection)
```

## Residual

- Compile still cannot treat an explicit host ticker string (`"AAPL"` under `Runtime(symbol="AAPL")`) as same-symbol — only `syminfo.tickerid` / `""` / `SYMBOL` / HA. Interpret does. Honest: compile emits `na` for the explicit foreign-looking string.
- Compile still does **not** HTF-resample; same-symbol simple OHLCV is chart passthrough. Dual-host last-value equality holds on same TF (`"D"` + daily bars).
- Other `request.*` (dividends / earnings / financial / quandl / economic) still mock on **standalone** eval (no host chart). Compile already stubs them as `np.nan`. No live adapters added.
- IR/disk compile cache can share plot titles when generated Python is identical; goldens use unique indicator names + `plot_N` fallback.

## Verdict

**win** — compile no longer lowers foreign security unpack as chart close; dual-host goldens lock same-symbol passthrough vs foreign/`NOT_THE_CHART`/`UPVOL.NY`/UDF → `na`.
