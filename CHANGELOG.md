# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.4] - 2026-09-05

### Added

- **`once` conditional structure** (Pine Script, August 2026). Executes its
  block the first time the optional condition is true on a closed bar, then
  never again. Soft keyword so existing `once` identifiers still parse.
  Interpret honors realtime rollback (unconfirmed ticks can re-fire);
  compile is historical (`isconfirmed` always true).

## [0.4.3] - 2026-09-04

### Added

- **`pynescript convert --to 5|6`** — source-level v5 ↔ v6 rewriter (`//@version`,
  `study(` → `indicator(` on the way to v6, bare `security(` / `financial(` / …
  ↔ `request.*`). Comments and string literals are left alone. Not a semantic
  migrator (bool-as-int, `na` tightening).

### Fixed

- Compile `plot(..., display=)` bitfield is folded into `plot_attrs` so
  `plot_meta` carries it (follow-up to 0.4.2).
- UDF `var` + history (`x[1]`) is per call site; interpret no longer drops
  every-other-bar `na` vs compile (e.g. `moon_phases.pine`).
- `table.merge_cells` no-ops on `na` coordinates instead of `int(None)` on
  the last bar.
- Remaining CodeQL: stack traces not returned in alert-forward errors; ReDoS
  regexes rewritten as linear scans.

### Changed

- **Pro API key store (breaking for SHA-256-only records):** keys are
  PBKDF2-HMAC-SHA256 (`v2:`). JSON files keyed by the raw secret are rehashed
  on load. Orphaned 64-hex SHA-256 records are skipped — remint those keys.
- CI: ruff E/F/W over `backend/`; VS Code VSIX packaged with `@vscode/vsce`
  (`@types/vscode` pinned to `engines.vscode` 1.91); `download-artifact@v8`;
  PyPI publish `skip-existing` so a duplicate tag run does not 400.
- Dependabot weekly updates landed (Actions, docs, vscode-languageclient 10,
  TypeScript 7, wrangler).

## [0.4.2] - 2026-08-26

### Fixed

- Compile `plot(..., display=)` is stored on `plot_attrs` so `plot_meta`
  exports the display bitfield.
- First CodeQL pass: errors, high, and medium alerts on the tagged tree.

## [0.4.1] - 2026-08-26

### Fixed

- Compile `plot_meta` backfills hline linestyle from `__drawings`.

## [0.4.0] - 2026-08-25

### Changed

- **VPS origin is Hetzner `pynescript.online` (`204.168.138.51`)** — `scripts/deploy_vps.sh` defaults to SSH host `pynescript` and skips AXIS dist (PWA is on Cloudflare Pages). API-only gunicorn behind nginx; `axis-pwa.service` is optional.

## [0.3.18] - 2026-08-25

### Added

- AXIS contract parity: `plot_meta` exports Pine visual params (`offset`,
  `histbase`, `trackprice`, `join`, `editable`, `show_last`) on interpret and
  compile hosts; omitted keys equal Pine defaults.
- `plotcandle` / `plotbar` export OHLC as close-primary series plus
  `<title>.open/.high/.low` siblings referenced from `plot_meta`
  (`open`/`high`/`low`/`close`), with `wickcolor` / `bordercolor`.
- Drawing/table exports gain stored-but-unexported styling: box
  extend/border_style/text styling, label tooltip/alignment/formatting,
  polyline curved/fill_color/force_overlay, table frame_width/border_color/
  border_width plus `merged_cells`.
- LSP builtin metadata carries canonical Pine v6 signatures for plot-family
  builtins.

### Fixed

- Positional `plot(...)` calls misread linewidth/style indices (now
  linewidth = 3rd arg, style = 4th per Pine v6 signature).
- `table.clear(t, r0, c0, r1, c1)` clears only the requested range;
  `table.merge_cells` records ranges and exports them.
- Compile-mode `plot_meta` no longer hardcodes `linewidth=1` when source
  declares constant linewidth/style/offset/histbase.
- Compile IR cache no longer shares entries whose titles/kinds/attrs diverge
  (metadata bleed across sources).
- Positional wickcolor/bordercolor args on plotcandle/plotbar are captured
  (previously kwargs-only).

## [0.3.17] - 2026-08-19

### Fixed
- **Compile object-mode residuals** — user `round()` UDF call sites pass free/chart formals; missing library `alias.method(...)` stubs are `na` not Python `None`; same-arity `negate(float|bool|color)` dispatches by argument type so hex colors stay off float64 series; method overloads on UDT fields (`this.wins.getAvgProfit()`) pick the field's type, not the outer receiver.

## [0.3.16] - 2026-08-19

### Fixed
- **Compile object-mode corpus residuals (set06)** — UDF `int m = if` stays a local (not script `m_arr`); nested UDFs still receive script-level `a_arr` when a param shadows `a`; UDF `var vol` does not steal chart `vol_arr` (`get_counts` arity); `Type.new()` locals mark UDT returns so `s.strength` is not `float(dict)`; statement-form `x = switch` no longer emits invalid `x = if`; `chart.point.copy` / `box.copy` clone dicts instead of `list(None)`.
- **Numba object-mode helpers** — `None` no longer TypingErrors `numba_max`/`min`/`abs` and related scalars; `timestamp` skips a leading timezone string; `valuewhen` and running max/min fall back on object arrays; Pine `int(na)` is `na` (`pine_int`, not Python `int(nan)`); `ta.pivothigh` na lengths; `ta.cum` uses `safe_float`.
- **Matrix handles** — UDF/`kron` results stay list-of-lists objects; builtins do not `len()` a numpy scalar.
- **Corpus sanitize** — keep trailing commas on wrapped `=>` calls; tab-indented bodies after `) =>`; drop Hugo/markdown tails after a complete script; keep nested `/* */` comments; stub jinja/markdown planning docs.
- **Grammar** — `NEWLINE+` before indented `=>` / if / for / while / switch bodies.

### Changed
- Docs: missing-features / implementation-status / roadmap / progress report aligned with compile object-mode residual recovery (P1p plot MISMATCH tail still open).

## [0.3.15] - 2026-08-19

### Added
- **`pynescript download-builtins`** — catalog + download TradingView builtin Pine templates via pine-facade (`--list` / `--yes` / `--limit`).
- **`scripts/search_clone_pine_pool.py`** — search and shallow-clone GitHub Pine repos for corpus collection.
- **`cf/`** — Cloudflare Containers Worker that fronts the Pro API and keeps a named instance warm.

### Improved
- **LSP hover** — types/qualifiers (`series` / `float`), namespaces (`ta` in `ta.sma`), user functions/assignments/`type`/`enum`, and longer keyword briefs. Builtin cards keep signature fence + params when metadata has them.

### Fixed
- **Compile set06 residuals** — missing `array`/`map`/`matrix` helpers, `for`+`continue` increment, for/while-as-expression emit, multi-value and default-only `switch`, `/* */` comments, map `for-in` pairs, `ta.dmi` scalar assign, `matrix.set` expression form, `np` unpack shadowing, nopython `TypingError` object-mode retry, tuple/UDT stores off float64 series.
- **Corpus sanitize** — RST/Hugo/MDX chrome, mustache `{{IDENT}}`, indented `study` bodies, column-1 ternary tails, torn string fixtures.

## [0.3.14] - 2026-08-18

### Fixed
- **`strategy.position_avg_price`** — repeating `strategy.entry("L")` no longer overwrites a filled position (avg was tracking last close). Extra same-direction entries only when `pyramiding` allows; interpret and compile.
- **`strategy()` leverage vs margin** — when `leverage=` is set it wins (margins derived from it). `margin_long` / `margin_short` only apply when leverage is omitted. Compile broker accepts those kwargs the same way.

### Changed
- Docs / comments: PYNE open-entry cap is `pyramiding + 1` (TV `pyramiding` default 1 ≡ PYNE 0). Unused compile-broker `replace_same_id` kwarg removed.
- Tests: leverage-vs-margin (both set), compile margin-only 5× cash sizing, same-id pyramid VWAP (third fill blocked), pending same-id limit/stop replacement; free-tier rate/slot no-ops when the switch is off.
- **Free-tier `/run` guards are opt-in** — `FREE_TIER_LIMITS` (default off). Bar/script/rate/concurrency and chart/mock-only `data_source` apply only when set to `1`/`true`/`yes`/`on`. Production compose still enables them (`FREE_TIER_LIMITS=1`). Health `features.free_tier_limits` reports the flag. Pro API / endpoint abstracts no longer read as always-on.
- Product landing and end-user hub list `pyne optimize` / `POST /optimize`.

## [0.3.13] - 2026-08-17

### Fixed
- Optimize scores broker fills (not `strategy.exit` placements); trail-only exits; warmup pairing; JSON-safe study scores.
- Walk-forward train+test run cap; HTTP `min_trades=0` / 400 mapping; CLI walk-forward windows; continuous Random/TPE sampling; grid product cap.
- Incremental `ta.dpo` / `ta.kst` dispatch; `timeframe.change("1M")` is monthly; compile table cells/colors and deleted linefills.

## [0.3.12] - 2026-08-17

### Added
- **Strategy hyperparameter search** — `pynescript.optimize` (TPE / random / grid, holdout + walk-forward) scores real `Runtime` strategy events. `POST /optimize` (same free-tier gates as `/run`) and `pyne optimize`. Not `/backtest/quick`; not a Pine builtin.
- Real **`timeframe.change`** on interpret and compile (UTC fixed-width buckets; bar 0 is a new period).
- HTF `request.security` allowlist includes **`ta.wma`** and **`ta.rma`**.
- Incremental interpret kernels for **`ta.aroon`**, **`ta.dpo`**, **`ta.donchian`**, and **`ta.kst`**.
- Dual-host plot/drawing identity: compile geometry-only AXIS export, plot_meta kinds, coordinate snapshot at create/set.

## [0.3.11] - 2026-08-16

### Added
- Incremental interpret **`ta.nvi` / `ta.pvi`** plus matching compile `numba_nvi_inc` / `numba_pvi_inc`.
- Flask `POST /run` `timeout_seconds` and `POST /run/batch` `libraries`.
- Dual-host goldens: Supertrend mid±factor·ATR, trail OHLC, foreign `request.*` → `na`, compile plot keys.

### Changed
- Interpret **`ta.pvt` / `ta.vpt`** is cumulative (matches compile / TV). Bar 0 is `0.0`.
- `pynets/` submodule pin **v0.2.0** (interpret + JS compile). Python Runtime remains the oracle.

### Fixed
- Compile MACD signal SMA-seeds the MACD line; OBV skips the first close change.
- Compile `ta.ao` / `ta.aroon` kernels (were all-`na`).
- Compile foreign `request.security` tuple unpack no longer invents chart close.
- Compile titled `bgcolor` / empty `plot(..., title="")` keys match interpret (disk IR v10).
- Compile `strategy.exit` keeps the Pine exit id for trail events.

## [0.3.10] - 2026-08-16

### Added
- Incremental interpret kernels for **`ta.obv`**, **`ta.wad`/`wvad`**, **`ta.cmf`**, and **`ta.klinger`** (`PYNE_TA_INCREMENTAL`).

### Changed
- Runtime interpret hot path (Round 9): direct Assign/`plot`/Call dispatch, skip unused derived OHLCV series, plot bar-reuse. Same-machine bench @ 2000 bars: minimal **2.7×**, `ta_sma` **2.0×**, `ta_combo` **1.45×**. `PYNE_SERIES_RING` still default off.
- `ta.vwap()` with no source still updates `hlc3` when that identifier is absent from the script.

## [0.3.9] - 2026-08-16

### Added
- **`FunctionDef.returns`** — UDF/method return types survive parse → unparse (`int ilog2(...)`).
- Incremental **`ta.median`** / **`ta.cmo`** Numba kernels; statement **`hline`/`fill`** stay nopython with synthesized drawings.
- Thread-local ANTLR lexer/parser reuse (warm SLL DFA across distinct sources).
- **LSP Docker image** `ghcr.io/hoox-sh/pyne/lsp` (stdio `pyne-lsp`, slim `[lsp]` only). Published on `v*` tags with api/cli.

### Changed
- Grammar left-factors typed names; bare `x =` is `Assign`, `=` reassignment only on attribute/subscript.
- Evaluator: `var` history carry at bar start; series maxlen matches host ≥1000; `_pine_site_id` for UDF/call-expr history.
- **pyne-vscode** publisher namespace is **`hoox-sh`** (extension id `hoox-sh.pyne`).

### Fixed
- **`Runtime.run(mode="auto", libraries=)`** forwards `libraries` into interpret fallback.
- Windows CLI `--help` no longer crashes on cp1252. Open VSX unknown-publisher no longer fails Build & Release.
- **CORS** — AXIS product Origins + `/health` free CORS path (also in 0.3.8 notes).
- **Build & Release:** Create Release no longer downloads Docker Buildx cache artifacts.

## [0.3.8] - 2026-08-15

### Added
- Compile UDT field defaults on `Type.new()` (omitted `bool x = false` stays `False`; `bool(np.nan)` no longer trips flags). Fixes interpret↔compile `071` Entry plot.
- `register_library_source` finalizes library exports so `Runtime.run(..., libraries=)` / `POST /run` `import ns/Lib/1` actually binds members.
- Supertrend first-party goldens lock the simplified mid±factor·ATR contract (interpret full/inc + Numba).
- LSP: user-enum completion/hover/outline; soft-keyword hover; `plot(ta.` leaf insert; drop C001/C003 false positives.

### Fixed
- `trail_points=0` / `na` no longer disables a valid `trail_offset` (interpret + compile).
- VPS deploy AXIS health probe uses `:80` (not stale `:8081`).

### Changed
- Compile disk IR cache meta version **7 → 8** (UDT defaults).
- Docs honesty: tick-offset `profit`/`loss`, omitted bid/ask `na`, H1 Runtime unify done.

## [0.3.7] - 2026-08-15

### Added
- **`Runtime.run(..., libraries=)`** — optional `[{namespace, name, version, source}]` registered via `register_library_source` before interpret so AXIS `import ns/Name/ver` resolves published git folders. Pro API `POST /run` accepts the same `libraries` field.

### Changed
- Runtime hot path: skip series dual-write when `PYNE_SERIES_RING=1`; tick-offset exits, incremental MA, plot pack, kernels.

### Removed
- Colocated **`pine-worker/`** TypeScript extra tool (parser/evaluator port). Lives in the sibling `pine-worker` checkout, not this repo.

## [0.3.6] - 2026-08-13

### Added
- **Binary search in UDT arrays** (Pine August 2026): `array.binary_search()`, `array.binary_search_leftmost()`, and `array.binary_search_rightmost()` accept `sort_field` (const int field index, default 0, or const string field name) so they can search arrays of user-defined types. The array must be sorted by the same field in ascending order. Interpret + compile object-mode, with dual-host parity tests.
- **Runtime `timeout_seconds`**: optional wall-clock circuit breaker on interpret (every 32 bars); partial results with `timed_out` + `error_kind=runtime` for edge/cron budgets (shared by Pro API and pyne-worker).
- **`linefill.new` export** — `DrawingRegistry.export_for_api` serializes line fills as `type: "linefill"` quads (line1 + line2 endpoints) so AXIS can paint the band.
- **Compile drawing set_* fold** — `fold_compile_drawing_mutations` applies `line.set_*` / `label.set_*` / … onto live handles and drops set events so compile `/run` drawings match interpret final state.
- **Compile drawing `*.delete`** — `line.delete` / `label.delete` / `box.delete` / `polyline.delete` / `table.delete` emit `kind: 'delete'` events on `__drawings` (target = `*.new` handle); `fold_compile_drawing_mutations` drops deleted objects (was MVP no-op).
- **`force_overlay` on export** — line/box/label payloads include `force_overlay` for AXIS pane routing.

### Changed
- **H1 dual-host:** pyne-worker `pynescript_backend` is a thin wrap over package `pynescript.runtime` (strict OHLCV validation only); vendor via `./scripts/sync_vendor.sh`.

## [0.3.5] - 2026-08-12

### Fixed
- **Drawing export (`line.new`)** — `export_for_api` no longer drops lines whose `xloc.bar_index` is past the last bar (classic `bar_index + 1` on `barstate.islast`). Extrapolates from series period; empty `bar_times` passes bare bar index for AXIS logical mapping.

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
- Round 6 multi-agent pass (perf + correctness + error handling + compiler coverage).
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

[0.4.4]: https://github.com/hoox-sh/pyne/compare/v0.4.3...v0.4.4
[0.4.3]: https://github.com/hoox-sh/pyne/compare/v0.4.2...v0.4.3
[0.4.2]: https://github.com/hoox-sh/pyne/compare/v0.4.1...v0.4.2
[0.4.1]: https://github.com/hoox-sh/pyne/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/hoox-sh/pyne/compare/v0.3.18...v0.4.0
