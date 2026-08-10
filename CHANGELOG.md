# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.4] - 2026-08-10

### Added
- **Package Runtime SoT** (`pynescript.runtime`): bar-loop host, series, CustomEvaluator live in the installable package; `backend.*` re-exports for Pro API.
- **First-party dual-host TA goldens** (ATR / Supertrend / Keltner) and full `test_ta_incremental` CI gate.
- **Strategy exit surface**: pending stop/limit + OCA; `from_entry` multi-leg (interpret + compile); `qty_percent`; minimal trail (interpret + compile); compile risk halt cascade (`allow_entry_in`, `max_position_size`, `max_drawdown`, `max_cons_loss_days`, `max_intraday_loss`, `max_intraday_filled_orders`); open/closed trade fields + MAE/MFE.
- **`request.security` honesty + HTF resample**: policy meta on Runtime; same-symbol coarser TF OHLCV bucketing; allowlisted simple `ta.sma`/`ema`/`rsi`/`atr` on HTF.
- **Realtime host simulation**: `realtime_last_bar` / `realtime_ticks` / `realtime_bars` / `realtime_from_bar` for `varip` multi-tick tests.
- Free-tier Pro API guards (bar/script caps, rate, concurrency, SSRF-safe webhooks, chart/mock-only free data).
- Hash-only JSON API key store; first-party fixtures under `tests/fixtures/first_party/`.
- pine-worker series lookback polarity + parity smoke (`series[1]` previous bar).
- Plot host: `plot.style_*` constants, style/linestyle capture, plotshape size export.

### Fixed
- EMA dual-host seed (full-list SMA seed matches incremental/Numba).
- `ta.atr` Wilder RMA on interpret + Numba.
- AugAssign / tuple unpack series binding; unparser `visit_Simple`; linter C004/W002.
- Enum/string series history so `d[1]` works for plotshape flips.
- vscode-extension transitive `brace-expansion` Dependabot high (2.1.4).

### Changed
- CI Core runtime gates parity, strategy, series, TA incremental, first-party goldens, runtime package, free-limits.
- Docs: `docs/known_divergences.md`, audit sprint status notes.

## [0.3.3] - 2026-08-09

### Fixed
- **Corpus residual (C1, set01–04):** dual-namespace user methods vs bare ta aliases
  (`method dmi` / `float dmi = dmi(...)` no longer mis-routes to `ta.dmi` after series assign);
  `line.get_price` / line getters soft-na on `na` line or endpoints and coerce PineSeries
  samples; `request.security` OHLCVT + `time` list unpack on different TF; sanitize dangling
  binary ops inside unclosed trailing calls (truncated docs scrapes).
- `ta.dmi` soft-na on unresolved / `na` length (aligned with other TA period soft-na).

### Changed
- Local open-source corpus set01–04 (2477 scripts, not shipped in git): **parse 99.96%**
  (2476/2477) and **Runtime interpret 100% excl. EXPECTED_FAIL** (2466 OK + 11 intentional
  demos); set01 Runtime **249/249**. Harness classifies path-listed intentional demos
  (library `runtime.error`, lower-TF guards, pathological loops) as EXPECTED_FAIL.
- Docs / landing: README, compatibility, roadmap, missing-features, and marketing numbers
  updated to the 2026-08-09 corpus snapshot (not TradingView® platform parity).

## [0.3.2] - 2026-08-09

### Changed
- **Console scripts**: preferred names are **`pyne`** and **`pyne-lsp`**.
  Legacy **`pynescript`** / **`pynescript-lsp`** remain installed as aliases
  (same callables). Import package is still `pynescript`; PyPI dist is
  `hoox-pyne`. Docs, VS Code auto-detect, and editor client configs prefer
  `pyne*` with fallback to `pynescript*`.

## [0.3.1] - 2026-08-09

### Added
- **Strategy average-price models** (pynescript extension): `strategy(..., avg_price_model=)`
  - `"stock"` (default) — multi-leg FIFO reweight of `position_avg_price` on partial close (TV-like)
  - `"futures"` — sticky net AEP until flat (linear USDT-M / BTCUSDT-style)
  - `"inverse"` — accepted; sticky reduce (harmonic add deferred)
  - Tokens: `strategy.avg_price_stock` / `avg_price_futures` / `avg_price_inverse`
- **Leverage for futures UI** (pynescript extension): `strategy(..., leverage=N)`
  - Scales percent/cash default qty: `qty = margin × leverage / price`
  - Margin held = notional / leverage; free cash adjusts accordingly
  - Simple `strategy.margin_liquidation_price` when leverage > 1
  - Derives TV-style `margin_long`/`margin_short` % as `100/leverage`
  - Read-back: `strategy.leverage`
- Dual-path wiring: interpret + compile broker + compiler emit for both options
- Docs: stock vs futures avg semantics; TV vs PYNE notes on `input` before `strategy()`

### Fixed
- Compile broker ctor no longer emits `name_arr[__bar_idx]` for strategy kwargs
  (undefined at ctor time). Const-like input/literal defvals fold into ctor
  (e.g. `lev = input.float(10)` then `strategy(..., leverage=lev)` → `leverage=10`).

### Changed
- Compile emit allowlist also wires `default_qty_type` / `default_qty_value` into
  `CompileStrategyBroker(...)`.

## [0.3.0] - 2026-08-06

First public **PYNE** release. PyPI distribution name is **`hoox-pyne`**
(plain `pyne` / `PyNE` is taken by an unrelated package; import/CLIs remain
`pynescript` / `pynescript-lsp`). Install: `pip install "hoox-pyne[lsp]"`.

### Added
- **Alert engine** (`AlertsMixin`): TV-style `alert.freq_*` normalization, once-per-bar dedup, once-per-bar-close gating, `alertcondition` fire-on-true, host helpers `export_alerts` / `export_alerts_from_evaluator`.
- **Dual-host alerts export**: Pro API + pyne-worker `Runtime` clear/export `alerts` (and optional `alert_conditions`) on interpret `/run`.
- **L2 alert webhooks**: Pro API `backend/alert_forwarder.py` (`webhook_url`, `ALERT_WEBHOOK_URL`, last-bar filter, batch JSON); pyne-worker edge webhooks + cron last-bar delivery. Docs: `docs/pyne/runtime/alerts.mdx`.
- Roadmap residual backlog IDs **H1–L3** (dual-host, corpus tail, warm compile, series/TA, optional fidelity, long-horizon); see `docs/ROADMAP.md` (2026-08-01). **L2 closed** (Pro API + edge).
- Corpus C1 residual goldens: bare `tonumber`, `math.isfinite`, strategy `closedtrades`/`opentrades` entry_id/comment/max_drawdown/max_runup accessors; tests in `tests/test_corpus_runtime_residuals.py`.
- Interpret↔compile plot parity harness: `scripts/compare_interp_compile.py` (multiprocess series compare with `--file-list`, `--timeout-sec`, `--ignore-hline-keys`, `--ignore-fill-keys`, and wave workers).
- Parity tests: `tests/test_interp_compile_parity.py`, `tests/test_dividend_yield_parity.py`, and R8/R9 kernel suites.
- Compiler: `time_arr` on the compiled execute signature; `numba_timestamp` / `numba_utc_parts`; titled `fill()` series export; `clear_numba_function_caches` with corrupt-cache recovery.
- Compile path for `numba_rci` / `ta.rci`.
- Strategy events system: StrategyEvent dataclass, full emission from strategy.* builtins, parity test corpus.
- pine-worker/ as colocated extra tool: TypeScript evaluator port + Python to TS converter script.
- var / varip declaration modes and ReAssign support.
- Multi-target Docker image (`api` / `api-dev` / `lsp`), `docker-bake.hcl`, prod compose overlay, Makefile docker helpers.
- Key-store backends selectable via `STORE_BACKEND` (`json` | `sqlite` | `redis`) for multi-worker / multi-replica deploys.
- PyPI publish workflow (Trusted Publishing on `v*` tags) and package build job in CI.
- Compiler disk IR/module cache (`PYNE_COMPILE_DISK_CACHE`, default on) + typed `CompileError*` hierarchy + `prewarm_numba_builtins()`.
- Runtime structured errors: `error_kind` (`parse|compile|runtime|data|order|mode`), `error_type`, `error_bar` (API `/run` forwards).

### Changed
- GitHub / package metadata for org **`hoox-sh/pyne`**: project URLs, Docker image source label, docs, CONTRIBUTING, and PyPI Trusted Publisher owner. See `docs/pyne/devops/publish-checklist.mdx`.
- **PyPI distribution name is `hoox-pyne`** (import/CLIs remain `pynescript` / `pynescript-lsp`). Avoids collision with upstream elbakramer `pynescript` and the unrelated pre-existing `pyne`/`PyNE` project on PyPI.
- Default image version labels / bake / Cloud Build substitution aligned to **0.3.0**.
- Compile `request.security` policy: same-symbol simple OHLCV only; other foreign tickers and complex expressions resolve to `na`.
- Disk IR meta version bumped when titled fill series export landed (and again for R8/R9 parity kernels).
- Interpret bar-loop residual wins (visit/Call arg plans, series last-sample, residual TA): ~1.24× `ta_combo` vs Round 5 (~137 ms @ 2k bars).
- Compiler stays numeric for more history/math/chart surface; viewport right bar time is `(n_bars-1)*60000` in compile mode.
- Runtime `mode=auto`: non-empty `inputs` forces interpret with clear fallback reason; object-mode compile no longer requires Numba.
- VS Code extension rebrand: **PYNE — Pine Script™ for VS Code** (`pyne` 0.3.0), HOOX logo icon, marketplace description as part of the HOOX open trading stack, TradingView® / Pine Script™ trademark disclaimer, and richer TextMate syntax highlighting.
- VS Code extension packaging: esbuild-bundle `vscode-languageclient` into the VSIX, explicit `onCommand` activation, resilient command handlers, and shared output channel.
- CI rewritten for the post-AXIS-extract repo: Python lint/test matrix, package build, Docker smoke; removed dead `frontend/` jobs.
- `require_admin_token` enforces `ADMIN_TOKEN` + `X-Admin-Token` (fail-closed); prod compose drops host source mounts via `volumes: !override`.
- `pyproject.toml` project URLs, Alpha classifier, Python 3.13, `pro` extra includes `redis`.
- Updated documentation (ROADMAP, missing_features, implementation status, LSP plan, devops Docker) to reflect current state.

### Fixed
- **R8/R9 interpret↔compile corpus parity**: foreign-na / MTF `request.security`, Heikin-Ashi security, TA call-site slots, UDF series locals per Call site, series assign bar key `(site, name)`, PineSeries snapshot for typed float/`nz`/`array.set` (BBI ring buffer), `ta.vwap(hlc3[, anchor])`, `time(...)[1]` call-expr history, strategy `position_size`/`avg`/`closedtrades[n]` end-of-bar history, Pine `==`/`!=` with `na` (`na==na` True; other na compares False via `numba_pine_eq`/`ne`).
- Builtin kwargs merge no longer drops explicit trailing `None` / Pine `na` (e.g. `array.push(id=a, value=na)`), unblocking many corpus library scripts.
- Corpus C1 8-agent residual pass: `str.replace` 4-arg/occurrence + coerce; richer `timestamp` date strings + TZ-first; series negative/na/OOB index → `na`; TA float/series periods; color hex/string channels; `syminfo.prefix`/`ticker` dual-mode; array get/set soft index + `index_2d_to_1d` stub polyfill; `hour`/`dayofmonth`/… series+timezone arity.
- set05 6-agent pass: `timestamp(9999,…)` year-first + calendar overflow; `strategy.initial_capital =` reassignment; `timenow`/`dayofweek.*`; sanitize keeps `type == "SMA"` ternary chains; v4 `random`/`offset`/`round_to_mintick` + `ticker.pointfigure` full arity; call-site cache stored on AST node (fixes id reuse collisions).
- set05 residual round 2 (6 agents): bare TA series `obv`/`accdist`/`vwap`; `ta.linreg` length&lt;2→na; `ta.kama` 2-arg; UDF name clobber restore; array.push soft arity + `newcolor` aliases; multi-island sanitize merge for UDF defs; missing UDF soft-na; int()/tonumber soft coerce; ticker.modify `adjustment=`; kwargs merge + timestamp const-fold + static for-to.
- Round 6 multi-agent pass (perf + correctness + error handling + compiler coverage); see `docs/perf_round6/`.
- Compiler nopython kernels: `ta.dmi` / `ta.adx` / `ta.supertrend` / `ta.alma` / `ta.percentrank` (match interpret oracle).
- Incremental interpret TA for residual full-history paths: `mfi`, `sar`, `kc`/`kcw`, `alma`, `correlation`, percentiles (behind `PYNE_TA_INCREMENTAL`).
- Strategy exit commission and exit slippage on interpret + compile paths; bad order args emit events instead of silent fills.
- Stable `CRYPTO_KEY` / `METADATA_KEY` resolution for Fernet metadata encryption (GitHub secrets wired).
- User series no longer shadows bare builtins (`ad` / `tr` / `obv` / `pvt`): `plot(ad)` emits the user series instead of re-emitting the Chaikin A/D stub.
- `highestbars` / `lowestbars` use negative TradingView-style offsets (Aroon parity).
- Compile Wilder RSI matches interpret (was a rolling SMA of gains).
- NaN-safe EMA/RMA seed for ATR custom `ma_function` and nested DEMA.
- UDF last assign of `na` no longer retains a prior tuple unpack (ADX early zeros).
- `math.avg` propagates `na`; `ta.roc` uses the standard formula; `wma` requires a full non-`na` window; `ta.cum` treats `na` / IEEE NaN as 0.
- `request.security`: foreign tickers and complex expressions resolve to `na` instead of inventing chart close; `dividend_yield` / CVI interpret↔compile parity.
- Import stub plot cells are not serialized as color strings.
- `auto_fib` interpret and compile raise the same insufficient-pivot errors; `for`/`to` auto step; `chart.point` object dtype.
- Interpreter: `ta.rising` / `ta.falling` / `ta.highestbars` / `ta.lowestbars` no longer raise `TypeError` on Pine `na` (e.g. VIDYA warmup on MA-STER).
- Crossover equality aligned with TV/numba (`<=`/`>=` on previous bar); short series rising/falling in bar mode.
- Body `TypeError` in call dispatch no longer soft-fails to `na` (signature mismatches still soft); strategy `strategy()` apply fails closed.
- Compile object-mode: `array.sort`/`sort_indices` honor `sort_field`; `array.fill` range; `map.keys`/`values` not coerced via `safe_float`.
- Corpus sanitize: multi-version islands, UI chrome, safer ternary/call/type-field repairs without FP on `?` in input titles.
- CI Ruff E,F,W gate: F821/`Any` imports and F401 unused imports cleaned for green CI on main.

### Removed
- Stale `Dockerfile.api` (folded into multi-target `Dockerfile`).
- Dead `technical_refactored.py` and internal refactoring notes from the published package tree.
- Broken AXIS-only GitHub workflows (`axis-nightly`, PWA/e2e jobs) — AXIS CI lives in [jango-blockchained/axis](https://github.com/jango-blockchained/axis).
