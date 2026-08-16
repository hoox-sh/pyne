# Copyright (C) 2024-2026 jango_blockchained
#
# SPDX-License-Identifier: AGPL-3.0-or-later

# Agent 03 — Runtime semantics + builtins

**Worktree:** `/home/jango/.grok/worktrees/git-pynescript/subagent-01a009bb-118a-7e01-b58e-372f103b6606`  
**Package:** hoox-pyne **0.3.10**  
**Verdict:** **updated**

No pages added or deleted. `docs.json` not edited.

## Pages read

- `docs/pyne/runtime/index.mdx`
- `docs/pyne/runtime/series-and-history.mdx`
- `docs/pyne/runtime/expressions-statements.mdx`
- `docs/pyne/runtime/libraries.mdx`
- `docs/pyne/runtime/events.mdx`
- `docs/pyne/runtime/alerts.mdx`
- `docs/pyne/runtime/builtins/index.mdx`
- `docs/pyne/runtime/builtins/technical.mdx`
- `docs/pyne/runtime/builtins/strategy.mdx`
- `docs/pyne/runtime/builtins/collections.mdx`
- `docs/pyne/runtime/builtins/drawing-plotting.mdx`
- `docs/pyne/runtime/builtins/request-input.mdx`

Did **not** edit `docs/pyne/runtime/compiler/**` (Agent 04) or `docs.json`.

## Pages edited

All twelve assigned pages.

## Pages added / deleted

None.

## Code checked

- `src/pynescript/__about__.py` (`0.3.10`)
- `CHANGELOG.md` 0.3.4–0.3.10
- `src/pynescript/runtime/{__init__,host,series,evaluator}.py`
- `backend/{runtime,series,evaluator}.py` (identity re-export shims)
- `src/pynescript/ast/evaluator/{names,expressions,statements,libraries}.py`
- `src/pynescript/ast/evaluator/builtins/{strategy,request,arrays,drawing,alerts,plotting}.py`
- `src/pynescript/ast/evaluator/builtins/technical_submodules/{core,volume,volatility,basic,moving_averages,oscillators}.py`
- `backend/app.py` (`libraries` slice of 32)
- Flags in `series.py` / `host.py` / `evaluator.py`: `PYNE_SERIES_CAP` on, `PYNE_TA_INCREMENTAL` on, `PYNE_SERIES_RING` off, `PYNE_LIGHT_PLOTS` off

## What was stale (fixed)

| Claim | Reality |
| --- | --- |
| `backend/runtime.py` / `backend/evaluator.py` / `backend/series.py` as design SoT | Package SoT is `src/pynescript/runtime/`; backend files are `sys.modules` aliases |
| `strategy.exit` `profit`/`loss` “still coerced as prices” | Ticks from entry avg (`ticks * mintick`); absolute `limit`/`stop` win |
| `trail_points=0` disables trail | 0.3.8: `na` / `≤0` ignored so `trail_offset` still applies |
| Incremental TA: “ATR remains EMA-of-TR / F1” | 0.3.4+: Wilder RMA of TR (`ta.rma(ta.tr, length)`) interpret + Numba |
| Incremental volume table incomplete | Added `accdist`; 0.3.10 `obv`/`wad`/`wvad`/`cmf`/`klinger` already listed |
| Compile drawing `delete` “MVP no-op” | 0.3.6 `fold_compile_drawing_mutations` applies `kind: delete` |
| Missing `force_overlay` / `linefill` export | Line/box/label `force_overlay`; `type: "linefill"` quads |
| Negative `[]` “raises” (series + expressions) | Soft-fail to `na` |
| BoolOp via Python `all`/`any` | Manual short-circuit loop |
| `request.security` hub omitted HTF | Interpret last-completed HTF + `sma`/`ema`/`rsi`/`atr` allowlist; compile same-symbol OHLCV only |
| Libraries TODO + “max 32” on Runtime | Lazy-load **does** finalize on first import; 32 is Pro API `[:32]` |
| `unshift (if present)` | `array.unshift` is implemented |

Also filled landed host surface: `timeout_seconds` / `timed_out`, `libraries=` (auto forwards, 0.3.9), `PYNE_LIGHT_PLOTS`, `realtime_*`, `var` start-of-bar history carry, omitted bid/ask stay `na`, `meta.request_security`, `bar_index+1` drawing extrapolation (0.3.5), `plot.style_*`.

Already correct (left in place): derived-series skip + `ta.vwap` → `hlc3`; UDT `array.binary_search*` `sort_field` (0.3.6); drawing `max_*_count` GC; foreign-na + HTF allowlist on request-input; `PYNE_SERIES_RING` default off.

## Remaining holes

- Incremental table is still **non-exhaustive** (also incremental: `alma`, `correlation`, percentiles, `dev`/`variance`, `sum`, `valuewhen`, …). Residual full-list remains `ta.nvi` / `ta.pvi` plus many exotic `ta.*` helpers.
- Compile `request.security` does **not** run HTF TA resample (passthrough simple same-symbol OHLCV or `na`).
- `barmerge.gaps_*` / `lookahead_*` accepted but unused; no LTF re-eval engine.
- Alerts stay interpret-only (`mode=compile` → `alerts: []`).
- Drawing GC / `*.all` / last-bar helpers are interpret-registry; compile fold is final-geometry only.
- Strategy compile broker still trails interpret on some `closedtrades.*` analytics.
- `FunctionDef.returns` is parse/unparse (0.3.9), not a runtime evaluator concern.
- Compiler pages still cite `backend/runtime.py` as `_run_compiled` SoT — Agent 04.

## Verdict

**updated**
