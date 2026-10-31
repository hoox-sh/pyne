## [Unreleased]

### Changed

- **VS Code themes tuned for calm reading.** Brand accents stay exact (void indigo `#939FFF`, volt lime `#B7EF09`, orange signal `#FE6A00`); the extra green / cyan / amber token hues are gone. Comments — including `//@…` annotations — are neutral gray italic in every theme, strings are a light accent tint, numbers use the foreground, and punctuation / series builtins are gray. Surfaces and hairline borders are darker, and the hover / autocomplete widgets sit on dark-grey panels.
- **Themes renamed to the product names** — **AXIS Void**, **Hoox Signal**, **PYNE Volt** (`pynescript.syntaxHighlighting` values: `none` · `void` · `signal` · `volt`; legacy `orange` still resolves to `signal`).
- **Workbench theme switching disabled.** The extension no longer writes `workbench.colorTheme` on activation, install, or settings change. `pynescript.theme` and the **PYNE: Select Workbench Theme** command are commented out for now; the three themes remain contributed and selectable from VS Code's own **Preferences: Color Theme** picker.
- **Settings regrouped and rewritten** into `PYNE: Appearance`, `PYNE: Language Server`, `PYNE: Editor Features`, `PYNE: Installation`, and `PYNE: Pro & Backend`, ordered by how often they are changed. Descriptions now state the default, the `none` behaviour, and cross-link related keys.

## [0.6.28] — 2026-10-31

### Added

- **VS Code extension 0.5.3 — separate workbench theme and syntax highlighting.** `pynescript.theme` (workbench UI + hover cards; `none` / `void` / `volt` / `orange`, default `none` = keep the user/system theme) and `pynescript.syntaxHighlighting` (Pine TextMate + semantic tokens; `none` / `void` / `volt` / `orange`, default `void`, `none` = active theme) are now independent settings with their own commands: **PYNE: Select Workbench Theme** and **PYNE: Select Syntax Highlighting**. Both accept `none`.

### Changed

- Removed `pynescript.theme.applyWorkbench`; setting `pynescript.theme` to `none` supersedes it.
- Syntax palettes are applied as language-scoped `[pinescript]` `editor.tokenColorCustomizations` / `editor.semanticTokenColorCustomizations` loaded from the bundled theme JSON, so they work with any workbench theme.

## [0.6.27] — 2026-10-31

### Added

- **VS Code extension 0.5.2 — PYNE product themes.** Contributed **PYNE Void**, **PYNE Volt**, and **PYNE Orange** color themes matching the HOOX color packs and the AXIS editor's syntax roles (keyword → accent, string → green, number → amber, builtin → cyan, library → purple, type → amber). Hover and autocomplete widgets use the selected theme; `pynescript.theme` + **PYNE: Select Theme** switch between them.
- **README**: Mermaid pipeline diagram, compact feature table, dedicated MCP section; removed the dated corpus snapshot.

### Changed

- Extension token colors now come from the contributed themes instead of hardcoded `editor.tokenColorCustomizations`.

## [0.6.26] — 2026-10-31

### Added

- **VS Code extension 0.5.1.** Library annotation hover cards (`//@function`, `//@param`, `//@returns`, `//@type`, `//@field`, `//@variable`, `//@description`) with multi-line Markdown continuation; per-feature settings and toggle commands for every LSP capability; Pine snippets; semantic-token theme defaults; diagnostics severity mapping; format-on-save; auto-install of `hoox-pyne[lsp]` with automatic venv creation for PEP 668 Python; backend URL + hosted `pynescript.online` toggle; Install/Start/Test Backend commands; ESLint flat config and `@vscode/test-electron` tests.
- **`hoox-pyne-backend` wheel.** Standalone backend distribution (`packages/backend`) that packages `backend/` and exposes the `pyne-backend` console script; `backend.app:main()` and `backend/__main__.py` make `python -m backend` work from a pip install.
- **Pyodide engine 0.6.26.** AXIS vendors the rebuilt `pynescript-0.6.26` browser wheel.

### Changed

- **`make package`** builds the main sdist/wheel and the backend wheel; new `make build-backend-wheel`.
- **Docs** updated for the extension release, backend wheel, and library annotation hover.

## [0.6.25] — 2026-10-31

### Fixed

- **Selector-UDF string misclassification.** A single UDF whose first param merely selects by string (`ma(type, src, len)`) was misclassified as string-returning by the overload branch of `_call_returns_string`, so the result series became a string buffer and `close > upperk` compared Float64 vs Str (`UFuncTypeError: ufunc 'greater'`) — or leaked an object array into an njit call (`TypingError: non-precise array(pyobject)`). Only a genuine multi-impl overload set now trips the string branch. (7 set05 scripts)
- **Tuple-returning builtin stored to a single var.** `macdValue = ta.macd(...)` treated the raw tuple as a float64 scalar → `ValueError: setting an array element with a sequence`. `_is_safe_numeric_expr` now rejects tuple-returning numba builtins (macd/dmi/supertrend/bb/kc/stochrsi/aroon/vwap) unless the expr is explicitly indexed `(...)[k]`, wrapping the store in `safe_float` (first element). (3 set05 scripts)
- **UDF declared after a same-named input.** `maType = input.string(...)` followed by `maType(src, ...) =>` rebound the Python def, so every `maType(...)` call raised `'str' object is not callable`. Top-level UDF names are now hoisted before the body walk so the input renames to `maType__loc` while calls still resolve to the function. (2 set05 scripts)
- **Drawing/table handle classified as a UDT series.** A `{'kind': …}` drawing/table dict tripped `_looks_like_object_handle_expr` and went through the UDT *series* branch (`t_arr[__bar_idx]`) before the drawing branch could make it a scalar handle. The UDT branch now skips drawing RHS. (1 set05 script)
- **Crossover with a `None` level.** A security-tuple stub level of `None` crashed `float(None)` in `_cross_pair`. Object mode now emits `na_num(level)` (None → nan); njit numeric levels stay a bare `float()` cast. (2 set05 scripts)
- **User array named `X_arr` colliding with a series buffer.** `var float[] ph_arr` and the series buffer for `bool ph` (also `ph_arr`) lowered to the same Python identifier, so the per-bar `ph_arr[__bar_idx]` write hit `IndexError: list assignment index out of range` on the user's short list. The user handle is renamed to `X_arr__hdl` and threaded via `ident_map`. (8 set05 scripts)

### Tests

- **`tests/test_set05_corpus_regressions.py`.** Locks all five compiler defects above with minimal reproduction cases (transpile assertions + compile/run parity), bringing 22 previously-failing set05 corpus scripts to green.

## [0.6.24] — 2026-10-26

### Added

- **`pyne corpus` CLI.** Rich front-end over the Runtime corpus engine (`list` + `run`) for set01–set06. Modes: interpret / compile / auto / parse. Shared engine lives in `pynescript.util.corpus_runtime` (scripts/corpus_run_runtime.py is a thin wrapper).

### Changed

- **Rich CLI volt palette.** Shared `pynescript.util.rich_theme` tracks the HOOX landing `/pyne` `data-color-pack=volt` tokens (accent `#B7EF09`, muted `#9E9F98`, border `#3D3E37`, fg `#EEEEEE`). Used by `pyne` / `corpus` / `download-builtins` / `scripts/showcase.py`.

## [0.6.23] — 2026-10-26

### Fixed

- **`ticker.new(prefix, ticker)` TV idiom.** `ticker_new` now follows TradingView's `(prefix, ticker, session, adjustment)` signature and joins to `PREFIX:TICKER` (one-arg full-symbol shorthand still works). `request.security(ticker.new(syminfo.prefix, syminfo.ticker), …)` matches the chart symbol instead of returning foreign na. Compile emit joins two-arg `ticker.new` the same way.
- **`mode=compile` no longer swallows parse errors.** `compile_script` refuses the corpus `_MINIMAL_STUB` substitution when the raw input is not already that stub, so garbage like `@@@not pine` fails with `error_kind=parse` under both interpret and compile.
- **Docs no longer describe the brand kit or Cloud Build.** The README banner, the GCP page, and the `cloudbuild.yaml` sections are gone. `/devops/gcp` redirects to the Docker page.
- **Optimizer TPE follows the out-of-sample score.** Holdout and walk-forward trials were split into TPE's good and bad sets by in-sample score, so the next suggestions walked the training peak. The split now uses `oos_score` when the trial has one, and `is_score` only when it does not.
- **Cloudflare Container setup.** The readiness probe is `localhost/health` (`http://${pingEndpoint}`; a bare `/health` never reached Flask). Gunicorn in the container matches the production entrypoint (`gthread`, 1 worker, 100 threads, 120s timeout, max-requests 5000). A Worker `ADMIN_TOKEN` secret is copied into the container when the instance starts. Wrangler in `cf/` is 4.152.0.

### Tests

- **Coverage wave 3.** Compiler emit/engine edges (array/matrix/map/UDT/switch/strategy compile scripts + interpret↔compile parity smokes), deeper `request.*` / host packing paths, arrays/strategy/TA-core helpers, backend app auth/404/stats edges. `tests/test_known_bugs_regression.py` locks the two defects fixed above.
- **Coverage wave 2.** Direct `numba_builtins` `*_inc` kernels (SMA/EMA/RSI/MACD/ATR/…), `request.*` / drawing / Runtime host edge suites, LSP `server.py` handler coverage (~99%), TA `common.py` helpers, statements/expressions Runtime edges, plus host/pine_facade pure helpers.
- **Broad unit coverage expansion.** New suites pin previously thin modules: shared `strategy_risk_core`, MCP serialize/catalog/dispatch/ops (optimize/runner/builtins), Redis/SQLite key-store fakes, backend services (backtest/chart render) + schema `validate()`, optimize space/objective/events edges, chronological `series_buffer`, LSP protocol utils/workspace helpers, corpus sanitizer pure helpers, datafeed util/poll paths, runner CLI HTTP client, numeric/string/timeframe/utility Runtime edges, and AST error/visitor/collector/type_system.

## [0.6.22] — 2026-10-25

### Added

- **VS Code palette toggles (VSIX 0.4.5).** **Toggle Diagnostics** / **Toggle Completion** flip `pynescript.diagnostics.enabled` and `pynescript.completion.snippets`. **Toggle Inlay Hints**, **Toggle Folding**, and **Toggle Color Preview** flip `[pinescript]` editor overrides (`editor.inlayHints.enabled`, `editor.folding`, `editor.colorDecorators`). Diagnostics off swallows squiggles client-side and clears the collection. Color preview is a real on/off (it previously only turned on, and inlay/folding wrote `formatting.enabled`).

## [0.6.21] — 2026-10-25

### Fixed

- **A clamped series tick fills one page of the hole it skipped.** When the stored anchor was older than `TICK_MAX_BARS`, the tick wrote only the recent window and then treated `newest` as current, so the minutes in between stayed missing (the Donchian axis hole). The hot walk is still clamped. After it, one page of the widest internal gap is written, and `stale` stays true so the client reloads the session. A start that adds no bars is abandoned after three tries. A week-long stall is still not a 200-page walk.
- **`request.currency_rate` 0/1-arg IndexError.** The honest-NA rewrite guarded `to_currency` with `len(args) > 0`, so a short builtin-map call raised `IndexError` instead of defaulting to `"EUR"`. Restored `len(args) > 1`.
- **Purge cascade walks the session journal.** `drop_by_key` only scanned in-memory sessions; a journaled-but-unloaded id survived `DELETE /data/series` and `resume` rebuilt the thrown-away window after a worker recycle. Matching journal rows are now dropped too.
- **Stale pool recreate notifies remaining subscribers.** Dropping a pooled session whose store window moved on publishes `SESSION_GONE` so other tabs re-ensure instead of ticking a gone id. An empty store window is treated as stale. A feed batch against a released session emits `SESSION_GONE` rather than going silent.

### Changed

- **`pyne_sessions` is a true snapshot.** `describe_all` no longer runs the idle TTL sweep, so an inspector pointed at the live journal cannot delete expired rows. String `last_time` anchors coerce for `lag_bars` / `suspect`.

## [0.6.20] — 2026-10-24

### Added

- **MCP `pyne_axb1` golden-vector check.** Verifies the AXB1 encoder against the bundled `tests/data/axb1-vectors.json` contract shared with AXIS (hex-exact per vector, fnv1a32 hash checks, codec reject-rule probes). Accepts inline `vectors` / `vectors_path` and an `only` name filter; callable in-process via `pyne mcp call axb1`.
- **MCP `pyne_sessions` pool inspector (read-only).** Snapshots every live session with its binding anchor against the store window: `lag_bars`, store bounds, and a `suspect` flag when the anchor is provably outside the store window (the pool-zombie shape). Optional `key` filter; never creates or drops sessions.

### Fixed

- **Stale pooled live sessions recreate instead of resuming.** `ensure_live_session` hits by content fingerprint, blind to the bars underneath: after a repair / replace / purge the store window could move hundreds of bars past a pooled session's birth anchor, and every resubscribe resumed the pre-repair window (overlays frozen on old bars across reloads and flushes). A hit lagging the store tail by more than the requested window now drops the entry and creates fresh over the current store; live sessions mid-tick keep sharing. `DELETE /data/series` also cascades into the session pool (`drop_by_key`), so the purge no longer leaves bound sessions evaluating the window it just threw away. Pinned by a stale-recreate test, a healthy-share test, and a `drop_by_key` unit test.

## [0.6.19] — 2026-10-23

### Added

- **Linter W104 (v6-removed kwargs).** AST-based rule flags `when=` on `strategy.*` order calls and `transp=` on drawing/plot calls (`color.new` / `color()` exempt) — both are ignored at runtime since v6 removed them. Surfaces in CLI, `lint_script`, and LSP diagnostics.
- **Linter W105 (numeric literal in boolean condition).** AST-based rule nudges `if 1` / `while 0` / `1 ? a : b` toward an explicit comparison or `bool()` cast. The evaluator stays permissively compatible; strictness lives in lint, not runtime.
- **`export method` import coverage.** `tests/test_library_export_method.py` pins the full cross-script path (UDT + exported method via `register_library_source` and direct evaluation, alias construction, receiver-form call).
- **String-interpolation scope + `bool` edge pins.** `tests/test_string_bool_edges.py` locks bare `"{0}"` staying literal, `str.format` substitution, `bool(na)`/`not na`/`na and/or` edges, and permissive numeric conditions at runtime.
- **`strategy.risk.max_position_size` contracts mode.** `PYNE_STRATEGY_RISK_CONTRACTS=1` treats the value as an absolute contracts cap (reference Pine semantics) on both interpret and compile hosts; default stays pinned %-of-equity. Invalid values are ignored. Pinned by `tests/test_strategy_risk_contracts.py` (dual-host + invalid-input cases).
- **`strategy.entry` pending `max_fill_per_bar`.** Stop/limit entries now carry the kwarg into the pending book like `strategy.order` does, so large entries fill across bars on both hosts (default `0` = full fill, unchanged).

- **AXB1 binary encoder + negotiated `encoding: "axb1"` on `WS /ws/live`.** New `pynescript.runtime.axb1` — a pure-stdlib byte-for-byte mirror of the AXIS AXB1 v1 wire codec (`axis/src/hp/axb1/encode.ts`), pinned by the cross-repo golden vectors (`tests/data/axb1-vectors.json`, shared with `axis/tests/hp/axb1-vectors.json`; 12 envelope vectors + FNV-1a hash checks asserted by `tests/test_axb1.py`). `WS /ws/live` accepts `encoding: "axb1"` on `subscribe`: mappable frames (status, series `full` snapshots, forming re-tip deltas, closes, errors) leave as `AXB1` bytes; JSON remains the default, and unmapped frames (script frames, multi-bar deltas, `idle` status, control frames, anything without a subscription id) fall back to JSON untouched. A single-bar delta is classified re-tick vs append by the per-subscription cursor (bar time vs newest seen) because pyne's delta envelope is byte-identical for both — an append is never guessed as a tip.

### Fixed

- **Fundamental `request.*` calls are honest-`na` without a provider hook.** `request.dividends` / `earnings` / `splits` / `financial` / `quandl` / `economic` / `currency_rate` no longer return invented mock tables (hardcoded AAPL/MSFT values, static FX rates, canned Quandl/economic series) when no host supplies the data. Without a `fetch_fundamental(kind, symbol, **params)` hook on `data_feed` / `data_provider` (or a live feed FX pair for `currency_rate`) they return `na` and record a `fundamental_na` policy tag — matching the compile host, which already lowers these calls to `na`. `request.seed` (RNG utility) is unchanged. Pinned by `tests/test_request_fundamentals_honest.py`; mock-pinned assertions in `tests/test_evaluator.py` and `tests/test_request_data_feed.py` updated to `na`.

## [0.6.18] — 2026-10-21

### Added

- **Public LSP docs for `documentLink/resolve` tooltip.** `docs/pyne/lsp/features/document-link.mdx` documents `documentLink/resolve` filling `tooltip` with the URL when tooltip is unset (`documentLinkProvider.resolveProvider=True`). Architecture, VS Code extension, and LSP index capability tables list the resolve method.
- **LSP document-link resolve.** `documentLink/resolve` fills `tooltip` with the URL. Advertised via `documentLinkProvider.resolveProvider`.
- **LSP 2-arg `ta.bbw(length, mult)` parameter-name inlays.** `ta.bbw(20, 2)` inlay as `length:`/`mult:` (not `source:`/`length:`). 1-arg `ta.bbw(20)` stays `length:`; 3-arg `ta.bbw(close, 20, 2)` stays `source:`/`length:`/`mult:`.
- **LSP arity-aware well-known parameter names.** 1-arg `ta.cci`/`ta.adx`/`ta.mfi`/`ta.bbw` inlay as `length:`; 2-arg `ta.cci(close, 14)` stays `source:`/`length:`, 2-arg `ta.adx(14, 14)` stays `diLength:`/`adxSmoothing:`.
- **LSP well-known parameter-name inlays for more builtins.** `textDocument/inlayHint` uses Pine v6 names (`ta.atr` `length`, `ta.correlation` `source1`/`source2`/`length`, `strategy.entry` `id`/`direction`/`qty`, `input.int` `defval`/`title`, plus `ta.cci`/`roc`/`mom`/`linreg`/`adx`/`mfi`/`bbw`/`dpo`/`crossover`/`crossunder`) when metadata snippets are generic `paramN`. Existing `ta.sma`/`ema`/… hints and assignment type hints are unchanged.
- **VS Code extension docs catch-up.** `docs/pyne/lsp/vscode-extension.mdx` documents the hosted `pyne-lsp` methods the 0.4.4 LanguageClient already forwards: `textDocument/semanticTokens/range`, `textDocument/onTypeFormatting` (trigger `\n`), `textDocument/linkedEditingRange`, `inlayHint/resolve` type textEdits plus builtin parameter-name hints, `textDocument/documentLink` (`http(s)` in comments/strings), and `textDocument/documentColor` / `colorPresentation` (`#hex`). GHCR example tag `ghcr.io/hoox-sh/pyne/lsp:0.6.19`. VSIX remains **0.4.4**.
- **Public LSP docs for documentLink and documentColor.** Dedicated Mintlify pages `docs/pyne/lsp/features/document-link.mdx` (`textDocument/documentLink` for `http(s)` URLs in comments and strings) and `docs/pyne/lsp/features/document-color.mdx` (`textDocument/documentColor` / `colorPresentation` for `#hex`, named `color.*`, and literal `color.rgb` / `color.new` / `color()` / `color.from_gradient`). GHCR client example tag `ghcr.io/hoox-sh/pyne/lsp:0.6.19`.
- **LSP architecture and index docs catch-up.** `docs/pyne/lsp/architecture.mdx` and `docs/pyne/lsp/index.mdx` now list range semantic tokens, on-type formatting, inlay resolve plus parameter-name hints, linked editing, and document links.
- **Public LSP docs catch-up.** Mintlify pages under `docs/pyne/lsp/features/` now document hover Pine v6 function-reference links, `textDocument/semanticTokens/range`, `textDocument/onTypeFormatting`, `inlayHint/resolve` plus parameter-name hints, and `textDocument/linkedEditingRange`.
- **LSP parameter inlay hints.** `textDocument/inlayHint` shows builtin parameter names before positional args (`ta.sma(close, 14)` → `source:` / `length:`). Assignment type hints and `inlayHint/resolve` textEdits are unchanged.
- **`DELETE /data/series` drops one stored series.** The engine's series store is its cache of the venue's OHLCV; a client that flushed its own dataset could not drop the engine's copy, so the engine kept serving the old (stale, holed) window. The route takes the same key fields as `GET /data/series` and removes the series' bars plus its metadata row. Per key only — the store is shared, so a purge never touches another series.
- **LSP inlay-hint resolve.** `inlayHint/resolve` fills `textEdits` that insert the inferred type annotation at the hint position. Advertised via `inlayHintProvider.resolveProvider`.
- **LSP on-type formatting.** `textDocument/onTypeFormatting` formats the just-completed line after newline using the same NodeUnparser as range formatting. Empty or unparsed documents return `[]`. Advertised via `documentOnTypeFormattingProvider` (trigger `\n`).
- **LSP linked editing ranges.** `textDocument/linkedEditingRange` returns same-document ranges for the user ident under the cursor (keywords and builtin namespaces stay unlinked). Advertised via `linkedEditingRangeProvider`.
- **LSP semantic tokens range.** `textDocument/semanticTokens/range` returns the same token legend as `/full`, clipped to the requested range. Empty or unparsed documents return an empty `data` array. Advertised via `semanticTokensProvider.range`.
- **Bar-mode incremental `ta.volatility_regime` (T2).** Last-sample kernel matches full recompute: last-N numeric ATR samples → `"low"` / `"medium"` / `"high"` / `"extreme"` (`"medium"` while the window is short).
- **LSP hover docs links.** Builtin hover cards (`ta.sma`, `strategy.entry`, …) include a markdown link to the public Pine v6 function reference. Keywords, types, and user declarations stay link-free.
- **Bar-mode incremental `ta.momentum_filter` (T2).** Last-sample kernel matches full recompute: last-N volume-weighted momentum (`0.0` while the window is short or volume_sum is 0).
- **Bar-mode incremental `ta.acceleration_factor` (T2).** Last-sample kernel matches full recompute: last-(period+1) momentum, clamp to [-2, 2], 0.0 while short or old_mom ~ 0.
- **Bar-mode incremental `ta.mean_reversion_score` (T2).** Last-sample kernel matches full recompute: last close/sma/stdev vs period warmup, score 0–100 (`50.0` while short or stdev is 0).
- **Bar-mode incremental `ta.market_condition` (T2).** Last-sample kernel matches full recompute: last close/atr vs SMA/stdev windows → `"ranging"` / `"volatile"` / `"trending_up"` / `"trending_down"` (`"ranging"` while short).
- **Bar-mode incremental `ta.order_flow_imbalance` (T2).** Last-sample kernel matches full recompute: last-N buy vs sell volume (`0.0` while short or volume total is 0).
- **Bar-mode incremental `ta.volume_thrust` (T2).** Last-sample kernel matches full recompute: last close vs prev close and volume vs volume_sma (`False` while empty).
- **Bar-mode incremental `ta.liquidity_score` (T2).** Last-sample kernel matches full recompute: last-N volume/volatility/spread mix (`50.0` while short).
- **Bar-mode incremental `ta.fear_greed_index` (T2).** Last-sample kernel matches full recompute: last rsi/vix/put_call/breadth mix, clamp [-100, 100].
- **Bar-mode incremental `ta.crowd_sentiment` (T2).** Last-sample kernel matches full recompute: mean of three last samples × 100, clamp [0, 100].
- **Bar-mode incremental `ta.smart_money_flow` (T2).** Last-sample kernel matches full recompute: volume-scaled signed flow from last price_change vs time_since_high/low, clamp [-1, 1].
- **Bar-mode incremental `ta.trend_confirmation_score` (T2).** Last-sample kernel matches full recompute: five last samples mixed, clamp [0, 100].
- **Bar-mode incremental `ta.atr_stop` (T2).** Last-sample kernel matches full recompute: last close ± last ATR × multiplier.
- **Bar-mode incremental `ta.max_loss_level` (T2).** Last-sample kernel matches full recompute: last entry/account/max_loss_pct → stop price.
- **Bar-mode incremental `ta.profit_lock_level` (T2).** Last-sample kernel matches full recompute: last entry/current/trail_pct/direction → trailing stop.

### Fixed

- **`request.security` resamples allowlisted 1-arg `ta.adx(length)` / `ta.mfi(length)` on HTF (D-06).** Same-symbol `ta.adx(14)` (HTF high/low/close) / `ta.mfi(14)` (HTF high/low/close/volume) on a coarser TF run the interpret TA helper on unique completed HTF bars (interpret **and** object-mode compile), with the same `gaps_on` / `lookahead_on` as `ta.sma`. Nested `ta.*`, 2-arg `ta.adx(diLength, adxSmoothing)`, and 4-arg explicit-series adx stay `na`. Disk IR cache v36.
- **`request.security` resamples allowlisted 0-arg `ta.obv()` / 1-arg `ta.cmf(length)` on HTF (D-06).** Same-symbol `ta.obv()` (HTF close+volume, running signed volume; 0 until 3 unique bars) / `ta.cmf(14)` (HTF high/low/close/volume) on a coarser TF run the interpret TA helper on unique completed HTF bars (interpret **and** object-mode compile), with the same `gaps_on` / `lookahead_on` as `ta.sma`. Nested `ta.*`, 2-arg `ta.obv(close, volume)`, and 5-arg explicit-series cmf stay `na`. Disk IR cache v37.
- **`request.security` resamples allowlisted 0-arg `ta.nvi()` / `ta.pvi()` on HTF (D-06).** Same-symbol `ta.nvi()` / `ta.pvi()` (HTF close+volume, seed 1000; later bars multiply by `(1 + close_change)` when volume decreases / increases) on a coarser TF run the interpret TA helper on unique completed HTF bars (interpret **and** object-mode compile), with the same `gaps_on` / `lookahead_on` as `ta.sma`. Nested `ta.*` and 2-arg `ta.nvi(close, volume)` / `ta.pvi(close, volume)` stay `na`. Disk IR cache v38.
- **`request.security` resamples allowlisted 0-arg `ta.accdist()` / `ta.wad()` on HTF (D-06).** Same-symbol `ta.accdist()` / `ta.wad()` (HTF high/low/close/volume; accdist is CLV × volume running sum, wad is Williams A/D with first unique bar 0) on a coarser TF run the interpret TA helper on unique completed HTF bars (interpret **and** object-mode compile), with the same `gaps_on` / `lookahead_on` as `ta.sma`. Nested `ta.*` and 4-arg `ta.accdist(high, low, close, volume)` / `ta.wad(high, low, close, volume)` stay `na`. Disk IR cache v39.
- **`request.security` resamples allowlisted 0-arg `ta.tr()` / 2-arg `ta.tsi(short, long)` on HTF (D-06).** Same-symbol `ta.tr()` (HTF high/low/close; first unique bar `na`) / `ta.tsi(13, 25)` (HTF close, extra=short, length=long) on a coarser TF run the interpret TA helper on unique completed HTF bars (interpret **and** object-mode compile), with the same `gaps_on` / `lookahead_on` as `ta.sma`. Nested `ta.*` and 3-arg `ta.tr(high, low, close)` / `ta.tsi(source, short, long)` stay `na`. Disk IR cache v40.
- **`request.security` resamples allowlisted 2-arg / 3-arg `ta.bbw` on HTF (D-06).** Same-symbol `ta.bbw(close, 20, 2)` / `ta.bbw(20, 2)` (HTF source, extra=mult; width is `2*mult*stdev/sma` while SMA ≠ 0) on a coarser TF run the interpret TA helper on unique completed HTF bars (interpret **and** object-mode compile), with the same `gaps_on` / `lookahead_on` as `ta.sma`. Nested `ta.bbw(ta.sma(...), n, 2)` and 1-arg `ta.bbw` stay `na`. Disk IR cache v41.
- **`request.security` resamples allowlisted 1-arg / 2-arg `ta.stoch` %K on HTF (D-06).** Same-symbol `ta.stoch(14)` / `ta.stoch(14, 3)` (HTF high/low/close, %K only; dPeriod stored unused) on a coarser TF run the interpret TA helper on unique completed HTF bars (interpret **and** object-mode compile), with the same `gaps_on` / `lookahead_on` as `ta.sma`. Nested `ta.*` and 4-arg `ta.stoch(source, high, low, length)` stay `na`. Disk IR cache v42.
- **`request.security` resamples allowlisted 2-arg `ta.pivothigh` / `ta.pivotlow` on HTF (D-06).** Same-symbol `ta.pivothigh(left, right)` (HTF high) / `ta.pivotlow(left, right)` (HTF low; optional 3-arg OHLCV source) on a coarser TF run the interpret TA helper on unique completed HTF bars (interpret **and** object-mode compile), with the same `gaps_on` / `lookahead_on` as `ta.sma`. Nested `ta.*` stay `na`. Disk IR cache v43.
- **`request.security` resamples allowlisted 3-arg `ta.percentile_nearest_rank` / `ta.percentile_linear_interpolation` on HTF (D-06).** Same-symbol `ta.percentile_nearest_rank(source, n, percentage)` / `ta.percentile_linear_interpolation(source, n, percentage)` (percentage a const int, 0 ok) on a coarser TF run the interpret TA helper on unique completed HTF bars (interpret **and** object-mode compile), with the same `gaps_on` / `lookahead_on` as `ta.sma`. Nested `ta.*` and non-int percentage stay `na`. Disk IR cache v44.
- **`request.security` resamples allowlisted 1-arg `ta.dpo(n)` / 2-arg `ta.crossover` / `ta.crossunder` of OHLCV names on HTF (D-06).** Same-symbol `ta.dpo(21)` (HTF close, `close[n//2+1] - sma(close, n)`) / `ta.crossover(close, open)` / `ta.crossunder(close, open)` (both args OHLCV Names) on a coarser TF run the interpret TA helper on unique completed HTF bars (interpret **and** object-mode compile), with the same `gaps_on` / `lookahead_on` as `ta.sma`. Nested `ta.*` stay `na`. Disk IR cache v45.
- **`request.security` resamples allowlisted 3-arg `ta.correlation` of OHLCV names on HTF (D-06).** Same-symbol `ta.correlation(close, volume, 20)` (both args OHLCV Names; extra=src_b field index) on a coarser TF run last-N Pearson on unique completed HTF bars (interpret **and** object-mode compile), with the same `gaps_on` / `lookahead_on` as `ta.sma`. Nested `ta.*` stay `na`. Disk IR cache v46.
- **`request.security` resamples allowlisted 2-arg `ta.dpo(source, n)` / 2-arg `ta.cross` of OHLCV names on HTF (D-06).** Same-symbol `ta.dpo(close, 21)` (HTF source, `src[n//2+1] - sma(src, n)`) / `ta.cross(close, open)` (both args OHLCV Names; extra=src_b field index; either-direction last two unique HTF samples) on a coarser TF run the interpret TA helper on unique completed HTF bars (interpret **and** object-mode compile), with the same `gaps_on` / `lookahead_on` as `ta.sma`. Nested `ta.*` stay `na`. Disk IR cache v47.
- **`request.security` resamples allowlisted 0-arg `ta.vpt()` / 1-arg `ta.wvad(n)` on HTF (D-06).** Same-symbol `ta.vpt()` / `ta.pvt()` (HTF close+volume, first unique bar `0.0`, later add `vol * (close-prev)/prev`) / `ta.wvad(n)` (HTF high/low/close/volume; 0-arg defaults period 20) on a coarser TF run the interpret TA helper on unique completed HTF bars (interpret **and** object-mode compile), with the same `gaps_on` / `lookahead_on` as `ta.sma`. Nested `ta.*` and 4-arg `ta.wvad` stay `na`. Disk IR cache v48.
- **`request.security` resamples allowlisted 3-arg `ta.uo` / 3-arg `ta.apo` on HTF (D-06).** Same-symbol `ta.uo(7, 14, 28)` (HTF high/low/close; extra packs `n2*1000+n3`) / `ta.apo(close, 10, 20)` (HTF source, extra=fast, length=slow; APO is EMA(fast)−EMA(slow)) on a coarser TF run the interpret TA helper on unique completed HTF bars (interpret **and** object-mode compile), with the same `gaps_on` / `lookahead_on` as `ta.sma`. Nested `ta.*` stay `na`. Disk IR cache v49.
- **`request.security` resamples allowlisted 1-arg `ta.emv(n)` on HTF (D-06).** Same-symbol `ta.emv(14)` (HTF high/low/volume; last-N valid ease-of-movement mean) on a coarser TF runs the interpret TA helper on unique completed HTF bars (interpret **and** object-mode compile), with the same `gaps_on` / `lookahead_on` as `ta.sma`. Nested `ta.*` stay `na`. Disk IR cache v50.

## [0.6.17] — 2026-10-19

### Fixed

- **`WS /ws/live` no longer tears the plane down on a quiet socket.** `simple_websocket` returns `None` on a receive *timeout* (it does not raise) — the live loop read that as a disconnect and closed the socket ~50 ms after the handshake. A slow history ensure or the gap between client heartbeats therefore dropped the subscription before its snapshot arrived (the client saw "no snapshot" and fell back to venue + REST). A timeout now keeps the socket alive; a real disconnect still closes it.

## [0.6.16] — 2026-10-19

### Fixed

- **Session results ship the evaluated window's bar-time axis (`times`).** The engine's stored series can have gaps (a missed minute), so a client that joined the series by index displaced the plot — the band led the candles by the number of missing bars. The session envelope now carries `times` (the evaluated bars' timestamps) and a delta tick carries the tail's, so the client joins by time. AXIS already consumes it (`meta.engineTimes` → `alignSeriesToTimes`).

## [0.6.15] — 2026-10-19

### Added

- **MCP server.** Optional extra `hoox-pyne[mcp]` ships a stdio Model Context Protocol server (`pyne-mcp`, `python -m pynescript.mcp`, Click `pyne mcp` / `pyne mcp config`). Tools wrap every `pyne` CLI command in-process (parse, format, convert, lint, compile, prewarm, run, optimize, data, runner HTTP, facade list) plus structured parse/symbols/diagnostics, `Runtime.run` (`pyne_execute`), interpret/compile last-value parity, builtin lookup, and LSP hover/complete/signature. Resources `pyne://info` and `pyne://builtins[/{name}]`. Prompts `review_pine` / `debug_pine` / `convert_to_v6`. Plot series are truncated; no disk writes; runner tools do not echo tokens.
- **MCP tools are executable from the CLI.** `pyne mcp tools` lists catalog names; `pyne mcp call TOOL [PATH]` runs any tool in-process (no MCP SDK; same `{ok,...}` JSON). First-class commands: `pyne execute` (`Runtime.run`), `pyne symbols`, `pyne parity`, `pyne diagnostics`, `pyne builtin`.
- **LSP document links.** `textDocument/documentLink` reports `http://` / `https://` URLs in comments (`//`, `/* */`, hash `# …`) and string literals as `DocumentLink` ranges whose `target` is the URL. Empty or unparsed documents return `[]`. Advertised via `documentLinkProvider`.
- **LSP documentColor for `color.from_gradient`.** `textDocument/documentColor` reports `color.from_gradient(value, min, max, color1, color2)` as a 0–1 RGBA `ColorInformation` when all five args are literals (numeric value/min/max plus named `color.*` / `#hex` token / quoted hex). Interpolation matches interpret `color.from_gradient` (RGBA lerp, clamp to `[min, max]`, equal min/max → color1). Existing hex / named / `color.rgb` / `color.new` / `color()` paths are unchanged.
- **Bar-mode incremental `ta.rsi_oversold_overbought` (T2).** Last-sample kernel matches full recompute: last RSI sample vs two int levels → `{is_oversold, is_overbought, rsi}` (`False` / `rsi: None` while the series is empty or the last sample is `na`). Oversold is `rsi < oversold`; overbought is `rsi > overbought`.
- **Bar-mode incremental `ta.zigzag` (T2).** Last-sample kernel matches full recompute: last 2 numeric samples → `(recent_high, recent_low, direction)` (`nan`/`nan`/0 while fewer than 2 numeric samples). Direction is `1` if the last numeric is the pair high else `-1`; percent change above the threshold forces `1`.

### Fixed

- **`pyne mcp call` exits non-zero on error findings.** `pyne lint` fails on errors by default (`--fail-on errors`); the MCP call path only failed when the envelope had `ok: false`, so a script with a syntax error passed CI. `pyne mcp call lint` (and `pyne diagnostics`) now exit 1 when the payload carries error-severity findings.
- **The compile packer keeps `__alerts` a list.** An *empty* alert list was coerced to an empty float64 array, which broke truthiness checks in hosts (`ValueError: The truth value of an empty array is ambiguous`) and could drop the alert payload. `__alerts` now passes through like `__drawings` / `__events`.
- **`WS /ws/run` forwards the whole run envelope (`libraries` included).** Published-library imports (`import ns/Name/1`) resolved over `POST /run` but failed over the WebSocket channel: the WS envelope mapper dropped `libraries` (and `timeout_seconds` / `from_bar` / `to_bar`). The mapping is now a shared helper (`backend.app._ws_envelope_to_payload`) that mirrors `RUN_SCHEMA`, so the WS channel has the same surface as HTTP.
- **The Pro API image can no longer ship a broken WebSocket.** gunicorn's `geventwebsocket…GeventWebSocketWorker` upgrades the socket *and* flask-sock upgrades it again — two `101` handshakes, a desynced frame stream, and every WS frame dropped (clients see close code 1002) while REST kept working. The image default is `gthread` (flask-sock owns the upgrade), the prod compose pins it, a repo guard (`tests/test_docker_entrypoint.py`) keeps every deploy path off the gevent worker, and CI now smokes `WS /ws/run` against the built image.
- **`WS /ws/live` history ensure no longer blocks the socket loop.** `subscribe`/`resume`/`repair` run `_ensure()` on a worker so ping/pong keep moving. Per-id generation tokens skip late `_attach` after unsubscribe/close; a resubscribe is not treated as a duplicate of a stale worker.
- **`request.security` resamples allowlisted `ta.cum(source)` / 1-arg `ta.ao(fast)` on HTF (D-06).** Same-symbol `ta.cum(close)` (running sum on unique HTF bars; `na` as 0) / `ta.ao(5)` (HTF hl2, SMA fast − SMA 34) on a coarser TF run the interpret TA helper on unique completed HTF bars (interpret **and** object-mode compile), with the same `gaps_on` / `lookahead_on` as `ta.sma`. Nested `ta.*` stay `na`. Disk IR cache v34.
- **`request.security` resamples allowlisted 1-arg `ta.change(source)` on HTF (D-06).** Same-symbol `ta.change(close)` (length defaults to 1) on a coarser TF run the interpret TA helper on unique completed HTF bars (interpret **and** object-mode compile), with the same `gaps_on` / `lookahead_on` as `ta.sma`. Nested `ta.*` stay `na`. Disk IR cache v35.

## [0.6.14] — 2026-10-19

### Added

- **LSP document colors.** `textDocument/documentColor` reports `#rgb` / `#rrggbb` / `#rrggbbaa` color literals, quoted `"#rrggbb"` / `"#rrggbbaa"` strings, `color.*` named constants (`color.red`, …), `color.rgb(r, g, b[, transp])` with numeric literals, and `color.new(color, transp)` / `color(color, transp)` (Pine alias of `color.new`) when both args are literals (named `color.*`, `#hex` token, or quoted hex) as 0–1 RGBA `ColorInformation`. Pine transparency is 0–100 (0 = opaque). `textDocument/colorPresentation` rewrites the range as `#rrggbb` (or `#rrggbbaa` when alpha ≠ 1), including when the original text was a `color.*` name. Empty or unparsed documents return `[]`. Advertised via `colorProvider`.
- **LSP C002 QuickFix.** `textDocument/codeAction` applies the same whole-document `TextEdit` as `textDocument/formatting` when lint warnings include C002 (line length > 120). Unparsed or unchanged source yields no C002 fix. Advertised as `QuickFix`. Convert-to-v6 / W001 / W002 are unchanged.
- **LSP selection ranges.** `textDocument/selectionRange` expands from the identifier (or smallest AST node) under the cursor to the enclosing statement, then enclosing `if`/`for`/`while`/`switch`/`once` blocks and `FunctionDef`/`TypeDef`/`EnumDef`. Empty or unparsed documents, or no node at the position, return `[]`. Advertised via `selectionRangeProvider`.
- **LSP folding ranges.** `textDocument/foldingRange` for `if`/`for`/`while`/`switch`/`once` blocks, `FunctionDef`/`TypeDef`/`EnumDef`, and `//#region`/`//#endregion` (plus `# region` hash comments). Empty or unparsed documents return `[]`. Advertised via `foldingRangeProvider`.
- **LSP W002 QuickFix.** `textDocument/codeAction` replaces an old `//@version=N` (N < 5) with `//@version=6` on the existing pragma line (does not insert a second pragma). v5 still gets Convert-to-v6 `RefactorRewrite` only.
- **LSP W001 QuickFix.** `textDocument/codeAction` inserts `//@version=6` at the document start when the version pragma is missing. Advertised as `QuickFix` alongside Convert-to-v6 `RefactorRewrite`.
- **LSP rename across open workspace documents.** `textDocument/rename` updates the ident in every currently open document that contains that Pine ident (same rules: no keywords / builtin namespaces; valid Pine ident). Documents that are not open are not in the workspace edit. `prepareRename` stays the cursor document's ident range.
- **LSP document highlight and rename** — `textDocument/documentHighlight`, `textDocument/prepareRename`, and `textDocument/rename` for user identifiers (character-precise). Keywords and builtin namespaces (`ta`, `strategy`, `math`, …) are not renamed. Advertised via `documentHighlightProvider` and `renameProvider` (`prepareProvider`).
- **Compile-mode realtime multi-pass (D-04).** Object-mode compile honors `Runtime.run` `realtime_ticks` / `realtime_bars` / `realtime_from_bar` / `realtime_last_bar`: last-bar `barstate.isrealtime`, intermediate ticks overwrite the same plot cell, `var` commits once, `varip` re-inits, `once` latches only when confirmed. Numeric nopython stays historical unless the script already forced object mode (an active realtime window re-emits object mode).
- **Realtime ticks from `DataFeed.poll_ohlcv` (D-04).** When `Runtime.run(..., data_feed=)` is passed and a realtime window is active, each last-bar tick evaluates the latest forming OHLCV from a sync poll (`MockDataFeed` is scriptable / no sleep; `None` is a no-op) on **interpret and object-mode compile**. Without a feed, ticks still re-visit the same historical OHLC. `InterpretSession.update_last_bar` is unchanged. `CCXTProDataFeed.poll_ohlcv` returns the last cached `watch_ohlcv` / `fetch_latest_ohlcv` candle (no socket in the bar loop).
- **Bar-mode incremental `ta.ema_cross_signal` (T2).** Last-sample kernel matches full recompute: last 2 samples of two series → `{signal, strength, trend_direction}` (`"neutral"` / 0 while `len < 2`; non-numeric samples coerce to 0.0). Buy on crossover with strength > threshold, sell on crossunder.
- **Bar-mode incremental `ta.inside_bar_pattern` (T2).** Last-sample kernel matches full recompute: last 2 highs/lows → `curr_high < prev_high and curr_low > prev_low` (`False` while `len < 2`; non-numeric samples coerce to 0.0).
- **Bar-mode incremental `ta.gap_detector` (T2).** Last-sample kernel matches full recompute: last high/low vs previous close → `{gap_size, gap_type, gap_percent}` (type `1` up, `-1` down, `0` none; zeros while any sample is missing, including bar 0 / na prev_close).

- **Bar-mode incremental `ta.double_top_bottom` (T2).** Last-sample kernel matches full recompute: last-N highs/lows → `{pattern_type, strength, breakout_level}` (`"none"` / 0.0 while the window is short or fewer than 3 numeric highs).
- **Bar-mode incremental `ta.engulfing` / `ta.hammer` (T2).** Last-sample kernels match full recompute: engulfing uses last 2 opens/closes (high/low unused; both flags False and strength 0.0 while `len < 2`); hammer uses last 1 OHLC (defined on bar 0). Same dict keys (`is_bullish`/`is_bearish`/`pattern_strength`, `is_hammer`/`is_doji`/`pattern_strength`).
- **Bar-mode incremental `ta.fractal` (T2).** Last-sample kernel matches full recompute: chart high/low, warmup `2*period+1` (both flags False); current bar is a high/low fractal if it equals the window max/min. Same dict keys (`is_high_fractal`, `is_low_fractal`).
- **Bar-mode incremental `ta.range` / `ta.max` / `ta.min` (T2).** Last-sample kernels match full recompute: range is highest−lowest (two call-site slots, highest then lowest), 2-arg max/min reuse the sliding-extreme kernels. 1-arg max/min stay whole-series full-path.
- **Bar-mode incremental `ta.stoch_smooth` (T2).** Last-sample kernel matches full recompute: raw stochastic per bar (partial window while warming up; na if any high/low/close in the last-N window is non-numeric), then `EMA(stoch, smooth_k)`, then `EMA(that, smooth_d)`.
- **Bar-mode incremental `ta.rsi_divergence` (T2).** Last-sample kernel matches full recompute: last-(period+1) min/max scaled to [-1, 1]; 0.0 while `i < period`, when fewer than 2 numeric values are in the window, or when the range is 0.
- **Bar-mode incremental `ta.sma_weighted` (T2).** Last-sample kernel matches full recompute: last-N weighted SMA with `weight_type` `"linear"` (default, weights 1..n), `"quadratic"` (`(i+1)**2`), or `"sqrt"` (`(i+1)**0.5`). na while the window is short or any slot is non-numeric.
- **Bar-mode incremental `ta.ichimoku` / `ta.apo` / `ta.emv` (T2).** Last-sample kernels match full recompute: Ichimoku reuses highest/lowest windows (stable six-slot order), APO is `EMA(fast) - EMA(slow)`, EMV is the last-N mean of per-bar ease-of-movement (na on bar 0 / zero volume / flat range).
- **Bar-mode incremental `ta.skewness` / `ta.kurtosis` / `ta.beta` (T2).** Last-sample kernels match full recompute: population skew and excess kurtosis over the last-N calendar window (na while any slot is non-numeric; 0.0 when stdev is 0), beta as `cov(s1,s2)/var(s2)` (0.0 when var(s2) is 0).
- **Bar-mode incremental `ta.r_squared` / `ta.comovement` (T2).** Last-sample kernels match full recompute: r_squared is corr² clipped to [0, 1] (0.0 when either variance is 0; na while the window is short or any slot is non-numeric), comovement is the percent of last-N-1 deltas that share sign.
- **Bar-mode incremental `ta.volume_weighted_momentum` (T2).** Last-sample kernel matches full recompute: last-N `(Δprice * vol) / sum(vol)` (0.0 when volume_sum is 0; na while the window is short).
- **Bar-mode incremental `ta.rci` / `ta.bb_pct` / `ta.atr_normalized` (T2).** Last-sample kernels match full recompute: rci is Spearman rho of time vs value ranks (volatility mixin gated), %B is `(close-lower)/(upper-lower)×100` clipped to [0, 100] (50.0 when bands collapse), atr_normalized is ATR/close×100 (na when close is 0).
- **Bar-mode incremental `ta.cumulative_delta` / `ta.volume_momentum` (T2).** Last-sample kernels match full recompute: cumulative_delta is last-N signed volume (`+vol` if close>prev, `−vol` if close<prev; 0.0 while the window is short), volume_momentum is the period-SMA volume ROC clipped to [-100, 100] (0.0 while the window is short or the old SMA is 0). Duplicate mixin copies in `economics.py` / `advanced.py` stay in sync.

### Changed

- **Public product docs are end-user and developer only.** Mintlify (`docs/pyne/**`) no longer carries operator shipping (personal PyPI account, Trusted Publishing / API-token how-to, GCP cost estimates, VPS deploy wiring). `/devops/pypi-publish` and `/devops/publish-checklist` redirect to Contributing. Audience rules live in `docs/WRITING.md`.
- **PYNE docs overview** (`docs/pyne/index.mdx`) no longer dumps an in-page "What's new" changelog; it points at GitHub releases and compatibility.

### Fixed

- **`request.security` resamples allowlisted `ta.vwap()` / `ta.vwap(source)` on HTF (D-06).** Same-symbol 0-arg `ta.vwap()` (HTF hlc3) / 1-arg `ta.vwap(close)` on a coarser TF run cumulative VWAP on unique completed HTF bars (`sum(price×HTF volume)/sum(volume)`; interpret **and** object-mode compile), with the same `gaps_on` / `lookahead_on` as `ta.sma`. Nested `ta.*` and 2-arg anchor / 3-arg bands stay `na`. Disk IR cache v33.
- **`request.security` resamples allowlisted 2-arg `ta.ao(fast, slow)` / 3-arg `ta.linreg(source, n, offset)` on HTF (D-06).** Same-symbol `ta.ao(5, 34)` (HTF hl2, SMA fast − SMA slow) / `ta.linreg(close, 14, 1)` (offset in `extra`; 2-arg is still offset 0) on a coarser TF run the interpret TA helper on unique completed HTF bars (interpret **and** object-mode compile), with the same `gaps_on` / `lookahead_on` as `ta.sma`. Nested `ta.*` stay `na`. Disk IR cache v32.
- **`request.security` resamples allowlisted `ta.swma` / `ta.ao()` / 1-arg `ta.range(n)` on HTF (D-06).** Same-symbol `ta.swma(source)` (fixed 4-period) / 0-arg `ta.ao()` (HTF hl2, SMA 5 − SMA 34) / `ta.range(n)` (HTF high − HTF low over n unique bars) on a coarser TF run the interpret TA helper on unique completed HTF bars (interpret **and** object-mode compile), with the same `gaps_on` / `lookahead_on` as `ta.sma`. Nested `ta.*` and 2-arg `ta.ao(fast, slow)` stay `na`. Disk IR cache v31.
- **`request.security` resamples allowlisted 2-arg `ta.kama` / `ta.rising` / `ta.falling` on HTF (D-06).** Same-symbol `ta.kama(source, n)` (Kaufman fast=2, slow=30) / `ta.rising(source, n)` / `ta.falling(source, n)` on a coarser TF run the interpret TA helper on unique completed HTF bars (interpret **and** object-mode compile), with the same `gaps_on` / `lookahead_on` as `ta.sma`. Nested `ta.*` and `ta.kama` 3/4-arg stay `na`. Disk IR cache v30.
- **`request.security` resamples allowlisted `ta.cog` / `ta.highestbars` / `ta.lowestbars` on HTF (D-06).** Same-symbol 2-arg `(source, length)` forms and 1-arg `ta.highestbars(n)` (HTF high) / `ta.lowestbars(n)` (HTF low) on a coarser TF run the interpret TA helper on unique completed HTF bars (interpret **and** object-mode compile), with the same `gaps_on` / `lookahead_on` as `ta.sma`. Nested `ta.*` stay `na`. Disk IR cache v29.
- **`request.security` resamples allowlisted `ta.mode` / `ta.percentrank` / `ta.change` on HTF (D-06).** Same-symbol 2-arg `(source, length)` forms on a coarser TF run the interpret TA helper on unique completed HTF bars (interpret **and** object-mode compile), with the same `gaps_on` / `lookahead_on` as `ta.sma`. Nested `ta.*` stay `na`. Disk IR cache v28.
- **`request.security` resamples allowlisted `ta.median` / `ta.dev` / `ta.variance` on HTF (D-06).** Same-symbol 2-arg `(source, length)` forms on a coarser TF run the interpret TA helper on unique completed HTF bars (interpret **and** object-mode compile), with the same `gaps_on` / `lookahead_on` as `ta.sma`. Nested `ta.*` stay `na`. Disk IR cache v27.
- **`request.security` resamples allowlisted `ta.highest` / `ta.lowest` (2-arg and 1-arg) and `ta.range` on HTF (D-06).** Same-symbol `ta.highest(source, n)` / `ta.lowest(source, n)` / `ta.range(source, n)` and 1-arg `ta.highest(n)` (HTF high) / `ta.lowest(n)` (HTF low) on a coarser TF run the interpret TA helper on unique completed HTF bars (interpret **and** object-mode compile), with the same `gaps_on` / `lookahead_on` as `ta.sma`. Nested `ta.*` stay `na`. Disk IR cache v26.
- **Nested list/dict contents roll back on unconfirmed realtime ticks (D-04).** Interpret snapshots copy one extra list/dict nesting level (`array.new<array<float>>()` / list-of-lists / dict-of-lists), so an unconfirmed `a.get(0).push(x)` does not leak into the next tick. Restore still writes into the same outer object; `varip` is skipped. Object-mode compile copies inner lists/dicts the same way. Deeper nesting and Matrix/Map internals stay best-effort. Historical `realtime_ticks=1` is unchanged. Disk IR cache v24.
- **`request.security` resamples allowlisted `ta.dema` / `ta.tema` and 1-arg `ta.wpr(length)` on HTF (D-06).** Same-symbol `ta.dema(source, n)` / `ta.tema(source, n)` / `ta.wpr(n)` (HTF high/low/close) on a coarser TF run the interpret TA helper on unique completed HTF bars (interpret **and** object-mode compile), with the same `gaps_on` / `lookahead_on` as `ta.sma`. Nested `ta.*`, 4-arg WPR, and `ta.kama` 3/4-arg stay `na`. Disk IR cache v25.
- **`request.security` resamples allowlisted `ta.hma` / `ta.vwma` and 1-arg `ta.cci(length)` on HTF (D-06).** Same-symbol `ta.hma(source, n)` / `ta.vwma(source, n)` / `ta.cci(n)` (typical price / HTF hlc3) on a coarser TF run the interpret TA helper on unique completed HTF bars (interpret **and** object-mode compile), with the same `gaps_on` / `lookahead_on` as `ta.sma`. Nested `ta.*` and 4-arg CCI stay `na`. Disk IR cache v24.
- **`request.security` resamples allowlisted `ta.cmo` / `ta.stdev` / `ta.linreg` on HTF (D-06).** Same-symbol 2-arg `(source, length)` forms on a coarser TF run the interpret TA helper on unique completed HTF bars (interpret **and** object-mode compile), with the same `gaps_on` / `lookahead_on` as `ta.sma`. Nested `ta.*` still `na`.
- **`request.security` resamples allowlisted `ta.cci` / `ta.roc` / `ta.mom` on HTF (D-06).** Same-symbol 2-arg `(source, length)` forms on a coarser TF run the interpret TA helper on unique completed HTF bars (interpret **and** object-mode compile), with the same `gaps_on` / `lookahead_on` as `ta.sma`. Nested `ta.*` and 4-arg CCI stay `na`. Disk IR cache v23.
- **`request.security` honors `gaps_on` / `lookahead_on` on provider-backed HTF OHLCV (D-06).** When a `data_provider` or feed returns a coarser OHLCV series with bar times, interpret aligns it to chart bars and applies the same bucket-start na-gaps / period-start lookahead leak as chart HTF resample (`provider_htf_ohlcv`). Chart-length / no-timestamp payloads (`ChartOHLCVProvider` ignoring `interval`) stay stubs with unused merge args. Nested `ta.*`, LTF, and passthrough paths are unchanged.
- **Compile-mode `request.security` consumes provider/feed HTF merge (D-06).** Object-mode compile now aligns coarser timestamped `data_provider` / `data_feed` OHLCV the same way interpret does (`gaps_on` / `lookahead_on`). Chart-length / no-timestamp stubs stay unused-merge. Nested `ta.*`, LTF, and passthrough paths are unchanged. Disk IR cache v22.
- **`strategy.risk.max_intraday_loss` resumes the next `syminfo.timezone` calendar day (D-02).** The halt and the day-scoped `max_intraday_filled_orders` cap now use DST-aware midnight-to-midnight buckets (same rules as `timeframe.change`); a bar that is still yesterday in `America/New_York` stays blocked. `max_drawdown` remains a permanent halt. `max_position_size` is still %-of-equity.
- **`CCXTProDataFeed.poll_ohlcv` returns the last cached watch/fetch candle.** Sync and network-free so the realtime bar loop can form last-bar ticks from a live CCXT Pro stream without opening a socket per tick. Empty cache is still `None`.
- **`WS /ws/live` sends `auth.ok` as soon as the upgrade handshake authenticates.** AXIS was blocking connect on that frame while the engine hashed the key; a handshake-authed socket now greets immediately so subscribe is not UNAUTHORIZED.
- **Engine series keys accept AXIS futures aliases and CCXT `defaultType` follows the market.** `linear`/`USDT-M` canonicalizes to `swap`, `inverse`/`COIN-M` to `future`. Live feeds and the cached CCXT provider are per `(exchange, market)` so a USDT-M chart does not reuse the spot Binance client.
- **In-place array / matrix / map / UDT mutations roll back on unconfirmed realtime ticks (D-04).** Intermediate interpret ticks restore container contents into the same objects (aliases keep identity); `varip` containers persist. Object-mode compile copies list/dict contents the same way.
- **Unconfirmed realtime ticks roll back broker fills and pending orders (D-04).** Interpret and object-mode compile snapshot `StrategyState` / `CompileStrategyBroker` (pending book, open/closed trades, position, equity peaks, events, strategy hist) and restore after intermediate ticks, so last-bar `strategy.entry` with `realtime_ticks=N` fills once. Pending OHLC processing stays once per bar (`begin_bar` / `process_pending_orders` remain outside the tick loop). Historical `realtime_ticks=1` is unchanged. Trail stops ratchet from forming-bar high/low after restore (still OHLC-path, no tick path).
- **Trail stops ratchet on forming-bar realtime ticks (D-01).** After `poll_ohlcv` and after each unconfirmed broker restore, pending `trail_*` stops follow the forming bar's high/low (interpret + object-mode compile; `InterpretSession.update_last_bar` too). Fills still roll back on unconfirmed ticks. Historical `realtime_ticks=1` is unchanged. Still OHLC-path (no intra-bar tick path).
- **Open-trade MAE/MFE follow forming-bar realtime ticks (D-03).** After `poll_ohlcv` and after each unconfirmed broker restore, per-trade `max_drawdown` / `max_runup` follow the forming bar's high/low (interpret + object-mode compile; `InterpretSession.update_last_bar` too). Fills still roll back. Historical `realtime_ticks=1` is unchanged. Still OHLC-path (no intra-bar tick path). Disk IR cache v23.
- **`InterpretSession.update_last_bar` rolls back broker fills on forming ticks (D-04 leftover).** Bar-open `StrategyState.snapshot()` is restored before each unconfirmed last-bar tick (pending book, open/closed trades, events); three `strategy.entry` ticks still fill once. Confirmed `append_bars` commits. Historical appends without ticks are unchanged.
- **Compile-mode `alert()` / `alertcondition()` firings are exported.** Object-mode compile records the same envelope as interpret (`message`, `freq`, `bar_index`, `time`, `source`); `/run` `mode=auto` no longer drops them when compile wins. Nopython numeric scripts still return `alerts: []`.

## [0.6.13] — 2026-10-18

### Added

- **LSP signature help** — `textDocument/signatureHelp` for Pine builtins (from `builtin_metadata.json` detail/snippet) and user `FunctionDef`. Trigger characters `(` and `,`; `activeParameter` is the top-level comma count inside the innermost enclosing call. Advertised via `signatureHelpProvider`.

### Changed

- **Live P3 push shape.** Forming re-ticks ship last-value tails only and coalesce on the feed thread (75 ms); close/multi-slot batches flush immediately so `seq` and `close` frames stay ordered. Compact (`BNBUSDT`) and pair-form (`BNB/USDT`) series identities match on tick so journaled sessions survive the AXIS key unification.
- **Live gunicorn topology (P2).** Production compose now hard-pins `GUNICORN_WORKER_CLASS=gthread` (a leftover 0.6.11 `geventwebsocket` value in the host `.env` can no longer restore broken WS frames), defaults `GUNICORN_THREADS=100` and `GUNICORN_TIMEOUT=120`, and raises recycle to `GUNICORN_MAX_REQUESTS=5000` so a live `/ws/live` socket is not torn down every few hundred REST ticks. The retired systemd unit/drop-in match gthread. VPS nginx already upgrades `location /ws/` with a 3600s read timeout.

### Fixed

- **Compile-mode `request.security` resamples the same allowlisted HTF shapes as interpret (D-06).** Same-symbol simple OHLCV, `close[1]`, and `ta.sma/ema/rsi/atr/wma/rma` on a coarser TF now go through the interpret HTF helpers in object mode (`gaps_on` / `lookahead_on` honored on those paths) instead of chart passthrough or `na`. Nested `ta.*`, foreign tickers, LTF, and unparseable TFs are unchanged.
- **A `kind: series` subscription now keeps its series store — and its socket — moving.** The engine's live feed advanced *sessions* walk-free (`apply_feed_candles`) but never the series store, and a `subscribe` for `kind: series` returned `session_id: None`, so `LiveConnection._attach` bailed before any feed listener existed. A series therefore reported `newest` frozen at the bar its history was ensured at: `GET /data/series` lagged the venue forever, every re-subscribe answered the same stale `full` snapshot, and the bars that would have healed it streamed past on the feed with nowhere to land (observed live: a 1m SOLUSDT series reporting `newest` exactly three bars behind the market at every repair, so an AXIS chart could only advance when the client's staleness repair ran). Two halves of one fix: `_emit_ready` now attaches the feed for series-kind subscriptions under the registry's own live id — stable per client + series, so a re-subscribe replaces the listener instead of stacking one per frame — and `attach_feed` upserts every batch into the store (`persist_feed_bars`, throttled per series to `PERSIST_MIN_MS` because a kline stream pushes the forming bar on every trade: a new slot always persists, a re-tick of the current one at most once per window). Upserts are by time and never raise — a store failure logs and leaves the feed alive — and the same sink also keeps the store advancing for script-kind feed subscriptions. Covered by four tests in `tests/test_live_push.py` (bounds advance, forming row upserted + throttle honoured, fail-soft store, and end-to-end subscribe → listener → delta frame + store bounds).

### Security

- **JSON API key-store writes are flock-serialized and replaced atomically.** `APIKeyStore._save` locks a sibling `.lock` file and `os.replace`s a tempfile in the same directory so a concurrent writer cannot truncate `api_keys.json` into invalid JSON. Hash-only layout is unchanged; production compose still uses sqlite.
- **Alert webhook POSTs pin to the IP from one DNS lookup.** `http_post_json` no longer connects by hostname after a cached SSRF verdict: it `getaddrinfo`s once (cache stays for request-time `is_webhook_url_safe` only), refuses RFC1918/metadata unless `ALERT_WEBHOOK_ALLOW_PRIVATE=1`, connects to that IP, and sets HTTPS SNI/`Host` to the original hostname so certificates still validate against the name. Redirects stay refused.

## [0.6.12] — 2026-10-17

### Fixed

- **`WS /ws/run`, `WS /ws/live` and `/datafeed/watch` now actually exchange frames (F-30 correction).** The 0.6.11 default — `geventwebsocket.gunicorn.workers.GeventWebSocketWorker` — completed the HTTP→WS upgrade but then corrupted every frame: that worker's handler upgrades the socket itself (`wsgi.websocket`) while flask-sock ignores `wsgi.websocket` and hijacks `gunicorn.socket` to re-frame the same socket. The app raised immediately after the `101`, so Werkzeug's HTTP error response was written where a WS frame belonged. Clients saw it as a protocol error after a *successful* handshake — Chromium reports `Invalid frame header`, and a strict client aborts with `1002 reserved bits must be 0` (the first byte of `HTTP/...`, `0x48`, sets RSV1). AXIS therefore kept silently falling back to REST, exactly as before F-30, with reconnect churn on top. The default worker class is now `gthread`, which exposes `gunicorn.socket` — the transport flask-sock documents for Gunicorn — and `GUNICORN_THREADS` defaults to 100 (one thread per live WS connection). Verified against the built image: a `gthread` container answers the handshake with a well-formed frame (`{"type":"error","code":"UNAUTHORIZED",…}`) while the gevent-websocket container produces the reserved-bits protocol error. `sync` still cannot upgrade, and `gevent-websocket` remains installed but is no longer selectable by default.

### Changed

- **The worker-class contract in the docs/comments was inverted and is now accurate.** `docker/entrypoint-api.sh` and `backend/requirements.txt` claimed "sync/gthread workers cannot upgrade" and that gevent + gevent-websocket made the flask-sock routes "upgrade natively". Neither holds: gthread is the flask-sock-compatible worker, and the gevent-websocket worker is the one that breaks framing. (Comment-only elsewhere; no behaviour change for an explicit `GUNICORN_WORKER_CLASS` override.)

## [0.6.11] — 2026-10-17

### Added

- **Engine-owned subscription plane over one socket (`WS /ws/live`, F-10–F-15).** A single connection now carries N subscriptions: handshake and per-frame auth, `subscribe` with autonomous history ensure (a miss fetches through the last closed bar), journal-backed resume, per-exchange CCXT Pro feeds (`watchOHLCVForSymbols` fan-in with a REST-poll fallback and a walk-free session commit), a per-subscription `seq` plus `closed_upto` watermark, delta/close push emission, and the degraded REST tail route (`GET /session/<id>/tail`) for clients that cannot upgrade. Advertised on `/health` under `endpoints` and `features.live_stream`, so AXIS detects it without probing.
- **Refcount-pooled shared sessions by content hash (F-29).** Tabs running identical scripts attach to one pooled session instead of each paying a full-window create: `acquire_shared` returns `(id, created)`, `release_shared` drops references (idle TTL still owns expiry), and capacity, journal and evict paths stay consistent; `/stats` reports the shared count.
- **Opt-in delta envelopes for session tick/append routes.** `POST /session/<id>/tick`, `POST /session/<id>/append` and `POST /data/session/<id>/tick` accept `delta: true` and answer tail-only: the last cells of `plots`/`series` plus a `delta` block (`base_index`/`count`/`tail_len`) for positional merging (`full = cached[:base_index] + tail`), or flags-only for unchanged data-session ticks (no plots/series at all — the client reuses its cache). Small fields (events/drawings/alerts/meta) stay full. Window trims still take the full path, and unshapely results fall back to the full envelope instead of a corrupt delta. Advertised as `features.session_delta`; clients that never send the flag see byte-identical responses. Covered by delta cases in `tests/test_backend_sessions.py` and `tests/test_data_series.py` (including tail-equals-full comparisons and flags-only unchanged ticks).
- **Live sessions survive worker recycles and container restarts.** Every session mutation is journaled to SQLite (`backend/datastore/session_log.py`: `sessions` + `session_bars` tables under `PYNE_SESSION_DB`, default `/data/sessions.db` when `/data` exists, memory-only otherwise). The bar log mirrors `InterpretSession._ohlcv_data` exactly — create writes the full bars, tick replaces the last, append extends — so the first access after a restart rebuilds the session with one `create_session` over identical bars under its original id, and ticks are O(1) again after that single re-evaluation. This also fixes the session churn from gunicorn `--max-requests` recycling, which previously dropped every in-flight session silently. The rebuild is a rebase (indicators identical; strategy fills may differ as with a client-side rebase), `GET /session/<id>` answers journaled-but-unloaded sessions from the row without rebuilding, and all journal writes are best-effort (an unreachable db degrades to memory-only). New knobs `SESSION_TTL_SECONDS` / `SESSION_MAX_SESSIONS` (defaults 900 / 64, unchanged). Covered by `tests/test_session_persistence.py` (HTTP create → tick → append → simulated restart → tick round-trips, TTL expiry, capacity, data-session binding).
- **`ccxt` ships in the Pro API image.** `/data/series/fetch` and `/data/session` ticks need an exchange feed, and without it every data tick failed `503 CCXT_UNAVAILABLE`.

### Changed

- **The API image now defaults to the gevent WebSocket worker (F-30).** `gthread`/`sync` workers cannot upgrade, so `/ws/run`, `/ws/live` and `/datafeed/watch` silently fell back to REST under Docker. The default worker class is now `geventwebsocket.gunicorn.workers.GeventWebSocketWorker` (single worker, since greenlets share the process the live sessions require), tunable via `GUNICORN_WORKER_CLASS` — `gthread`/`sync` restore the old behavior, where `GUNICORN_THREADS` applies. `gevent` and `gevent-websocket` were added to `backend/requirements.txt` and the `pro`/`test` extras.
- **Cached CCXT providers and a longer tick-walk reuse window.** Every `/data/session` tick built a fresh `CCXTProvider`, so each cache-missing tick paid `loadMarkets` (a ~3 s floor) before fetching. One provider is now cached per `(exchange, credentials)` with a 30-minute refresh, fetches are serialized per exchange (ccxt rate-limit state is per object), and the tick-walk reuse window widened 5 s → 12 s so staggered chart and indicator ticks share a walk. Measured: `provider.fetch` p50 3219 ms → 274 ms, `http.request` p95 3440 ms → 287 ms.
- **The VPS deploy path is docker-only.** `scripts/deploy_vps.sh` no longer installs or restarts a systemd unit (the old drop-in kept a second runtime bound to the same port while backend fixes never reached the live container). It now rsyncs the tree, rebuilds and recreates the compose base + prod overlay (`api` + `redis`) with volumes preserved, waits for healthy and smokes `:5002`.
- **`.env.example` pins `PYNE_DATA_DIR` to the persistent volume.** The engine-owned series store defaults to a relative `data/` that a container restart discards; the documented value is now `/data/series`.
- `POST /data/session/<id>/tick` responses now include `stale` (walk was clamped because the stored anchor was too old).

### Fixed

- **Concurrent session ticks share one upstream walk (singleflight + cross-session reuse).** AXIS ticks one data session per script instance (chart + N indicators) against the same series within seconds of each other; each tick paid its own CCXT walk for identical candles, and on the single gunicorn worker those walks serialized behind each other — the per-tick seconds observed from AXIS live mode. `sync_data_session` now shares the walk per series for `TICK_WALK_REUSE_S` (5 s): concurrent ticks join the in-flight walk instead of stacking round trips, and sequential ticks for *other* sessions reuse a fresh covering walk. The ticking session itself always refetches so forming-bar re-ticks observe every revision; truncated walks (hit `TICK_MAX_BARS`) are never shared. Covered by `test_concurrent_session_ticks_share_one_upstream_walk`, `test_concurrent_ticks_singleflight_one_walk` and `test_walk_cache_expires_for_new_data` in `tests/test_data_series.py`.
- **Live-session ticks no longer backfill runaway histories (connection-storm fix).** `POST /data/session/<id>/tick` fetched candles from the stored anchor with **no bar cap**, so a stale series (cached restore, failed first fetch, symbol/interval switch) walked CCXT pages across the whole gap — up to `MAX_FETCH_PAGES` × `FETCH_PAGE_LIMIT` = 200,000 bars of sequential upstream round trips per tick. One such tick pinned an HTTP request for 145–240 s, serialized every other request on the same series behind `key_lock`, and wrote ~200k junk bars into the series store per tick; on gunicorn (1 worker × 4 threads, 120 s timeout) a few charts exhausted the pool and the timeout kills dropped every in-flight connection, producing the "connection issues several times a minute" symptom. Now: the walk is capped at `TICK_MAX_BARS` (2,500), a stale anchor is **clamped to a bounded recent window** instead of paging the whole gap, and the tick response flags `stale: true` so AXIS can re-sync history deliberately. The upstream walk also runs **outside** `key_lock` (only the fast local commit — liveness check, persist, session advance — holds it), and a tick aborts with `404 SESSION_GONE` when the session is released mid-flight instead of persisting for a dead session.
- **Series retention ceiling.** `SeriesStore.provide` now trims the oldest bars beyond `MAX_SERIES_BARS` (200,000 — 2× the largest legit window), so a runaway backfill or a chatty client cannot grow a series without bound.
- **The PYNE_DEBUG access log was silently dropped under `make run`.** `python -m backend.app` names the module `__main__`, which `backend.logging_setup` does not manage (its prefixes are `pynescript`/`backend`), so the per-request `METHOD /path -> status in ms` lines and the slow-request lines never appeared while engine/datafeed lines did. `backend/app.py` now logs under an explicit `backend.app` logger; gunicorn was already correct.
- **`.env` is now honored by `python -m backend.app` and gunicorn** (previously only Docker Compose `env_file` read it). A guarded `python-dotenv` loader runs at import, existing environment variables always win, and without `python-dotenv` installed it is a quiet no-op. `python-dotenv` was added to `backend/requirements.txt` and the `[pro]` extra.
- **`X-Api-Key` is allowed cross-origin.** The header was missing from `Access-Control-Allow-Headers` (and Flask-CORS `allow_headers`), so AXIS could not send authenticated requests to the Pro API from `hoox.sh` without a failed CORS preflight.
- **The deploy rsync no longer ships `.git/` or `.env`.** Syncing live git metadata corrupted the host tree once the VPS `.git` diverged, and the host never uses `.git` operationally; `.env` is excluded too, so a local dev override (e.g. `PYNE_DEBUG=1`) can never enable verbose logging in production.

### Security

- **Redis key store is no longer reachable from the internet; auth is opt-in.** The compose `redis` service published `6379` on all interfaces without a password; automated scanners wiped the key store (`FLUSHALL`) and staged cron miner payloads (`backup1-4`). The service now publishes no ports (internal network only — the API is unaffected) and accepts `--requirepass` via `REDIS_PASSWORD`, with `REDIS_URL=redis://:PASSWORD@redis:6379/0` as the matching API side (explicit `REDIS_URL` still wins for Memorystore). Generate with `openssl rand -hex 32`.

## [0.6.10] — 2026-10-14

### Added

- **`PYNE_DEBUG` development logging flag** — one env var turns on detailed logging across the execution engine and the datafeed. Set `PYNE_DEBUG=1` to log the interpreter bar loop (start/end, bars + ms + bars/ms, aborts, timeouts), the compile pipeline (eligibility, cache HIT/MISS, transpile, JIT warm, object-mode / nopython fallback), prewarm (builtins warm, per-script results, total ms), **delta calculation** (`append_bars` delta size + start index, `update_last_bar` forming-bar ticks), the datafeed (CCXT Pro connect / subscribe / updates / reconnects, REST `fetch_ohlcv`, the `/datafeed/*` gateway and `WS /datafeed/watch`), and every HTTP request (method, path, status, ms). It also sets the `pynescript` and `backend` loggers to `DEBUG`; third-party chatter (`urllib3`, `numba`, `matplotlib`, `asyncio`, `werkzeug`) stays at `WARNING`. Optional `PYNE_DEBUG_SCOPE=pynescript.runtime,pynescript.compiler` narrows logging to a logger allowlist. Implementation is split between the new `pynescript.debug` toggle (env parsing, memoized on the raw env string so a live flip takes effect without a restart), `backend/logging_setup.py` (level policy, handler install), and `_dbg(...)` / `_stats.*` call sites inside `pynescript.runtime.host`, `pynescript.compiler.engine`, `pynescript.util.datafeed` and `pynescript.util.data`. Gates sit at run / batch / request boundaries rather than inside per-bar loops, and log payloads are never built when the flag is off, so the disabled path stays cheap; debug output is verbose by design and should stay off in production.
- **`GET /stats`** — public (no API key) process-wide runtime statistics, documented in the route docstring and advertised under `endpoints` on `/health`. Returns `counters` (per-metric totals with dimension breakdowns, e.g. runs by resolved mode, auto backend, compile fallback reason), `latencies` (count / avg / min / max / p50 / p95 in ms, backed by a bounded reservoir of the last 512 samples per metric), `gauges` (in-flight requests, active sessions + capacity + high-water mark, largest single delta append, host compile-cache entries, bound datafeed sessions and live watch connections), plus live `compile_cache` and `sessions` snapshots and the current `PYNE_DEBUG` configuration. Backed by the new dependency-free `pynescript.stats` registry (thread-safe counters / latencies / gauges, every update wrapped so a metrics failure can never fail a run). In-process only — counters reset on worker restart, which is honest for the single-worker gunicorn setup the live sessions require.
- **Engine + datafeed statistics** — `pynescript.stats` call sites now record interpreter bar-loop duration and bars evaluated (one-shot and per-session), compile cache hit/miss split by memory / sanitized / disk / IR-share, prewarm outcomes, delta append size and forming-bar tick latency, CCXT realtime stream subscribes and reconnects, historical provider fetches and bars, gateway fetch outcomes, dropped candles and WS watch connections.
- **Engine-owned OHLCV store** — PYNE Pro can now own market bars for every-tick live mode. Bars persist in SQLite under `PYNE_DATA_DIR` (default `data/`), keyed by the canonical series key `exchange|market|SYMBOL|interval` (for example `binance|spot|BTC/USDT|1h`). Upserts are keyed by unix-second `time`, and the later write wins. A forming bar is re-written in place. Implemented in `backend/datastore/series.py`, without Flask or CCXT. The wire contract is `docs/devops/engine-owned-data-plane.mdx` in the AXIS repo.
- **`/data/series*` routes** (`backend/api/data_series.py`) — `GET /data/series` (bounds; count 0 when unknown), `POST /data/series/provide` (upload closed bars, max 5,000 per request, otherwise `413 BATCH_TOO_LARGE`), `POST /data/series/fetch` (walks CCXT `fetch_ohlcv` pages forward from `now - history_bars` and persists; `history_bars` defaults to 5,000 and caps at 100,000; upstream failure is `502 UPSTREAM`, CCXT missing is `503 CCXT_UNAVAILABLE`), and `GET /data/series/bars` (newest window, ascending, `limit` defaults to 10,000 and caps at 100,000). The CCXT provider and candle mapping are shared with `/datafeed/ohlcv`.
- **`/data/session*` routes** (`backend/app.py`) — `POST /data/session` builds a live interpret session over the stored window and binds it to the series key. It returns the `/session` envelope plus `session_id`, `cache: "hit"`, and `data: {key, count, newest}`. When the store holds fewer than `history_bars` bars it returns `409 DATA_MISS` with `have` and `need`. `POST /data/session/<id>/tick` takes `{exchange, symbol}` only. It returns `409 SESSION_KEY_MISMATCH` for another series, fetches candles from two bars before the stored newest, persists closed bars, re-ticks the forming bar with `update_last_bar`, and appends newer bars with `append_bars`. The response adds `appended`, `forming`, and `unchanged`. Upstream failure is `502 UPSTREAM` and keeps the session. `DELETE /session/<id>` releases it as before.
- **Health `features`** — `live_modes: ["every-tick", "bar-close"]` and `data_session: true`, which AXIS uses for capability detection (D3). The `/data/*` routes are listed under `endpoints`.

### Changed

- **Docs export minifier no longer shreds identifiers** (`scripts/docs/generate-exports.mjs`). The markdown-emphasis strippers `_([^_]+)_` and `__([^_]+)__` were not word-boundary anchored, so they paired the underscores of *different* identifiers whenever two appeared in one sentence: `PYNE_DEBUG=1 and PYNE_DEBUG_SCOPE=x` matched `_DEBUG=1 and PYNE_` and shipped `PYNEDEBUG=1 and PYNESCOPE=x`. Every generated `llm.txt` therefore lost identifier spellings — `ADMIN_TOKEN` shipped as `ADMINTOKEN` (33 occurrences), plus `PYNEDEBUG`, `frombar`, `sessionid`, and others — degrading the packs AXIS and the agents read for exactly the env-var and field names they need most. Both patterns are now anchored with lookarounds, so real _emphasis_ / __strong__ still collapse while snake_case identifiers, `__bar_idx`, and env-var names survive intact.

### Fixed

Six long-standing failures, plus one defect in the docs export pipeline that made every generated LLM context pack lossy.

- **`chart.point.copy(pt)` silently dropped its argument.** `_call_prefers_array_method` returned True for *any* attribute receiver, so `chart.point.copy` was lowered to `array.copy` before the `chart.point` branch could run, emitting `array_copy_value(None)`. The point became `None`, `pt2.price` read through `udt_get_field(None, …)` as NaN, and the strategy/plot silently plotted nothing. The chart.point namespace is now recognised and excluded from the collection-method path (`_is_chart_point_namespace`).
- **A numeric multi-return UDF was forced into object mode.** `f(float a, float b) => [a + 1.0, b + 2.0]` is marked `func_returns_sequence` so a single-target `a = f()` keeps the tuple as a handle — but that same marker also demoted the multi-unpack `[u, w] = f()` to object mode, cutting the nopython stay rate for that shape. Such functions are now recognised as numeric-tuple UDFs (excluding string/UDT/import returns) and keep float series. The unpack also emits direct `__tup[i]` indexing: the `isinstance(__tup, (tuple, list))` guard cannot be narrowed by Numba, and it alone was enough to fail the njit warm-up.
- **Interpret and compile disagreed on every titled `fill()`.** Interpret wrote the per-bar band colour into the `series` column; compile packs series into float64 arrays and therefore *cannot* emit a colour string, so it emitted null. Any script using `fill(..., title="…")` therefore rendered differently depending on mode. The interpret fill column is now null; the band is still described completely by `plot_meta` (`kind="fill"`, `plot1`/`plot2`, `color`), so nothing is lost for the frontend.
- **The parity harness reported a hard MISMATCH for arbitrarily-titled fills.** `is_fill_background_key` matched series by *name* only, so `fill(p1, p2, title="BE Zone")` fell through to a numeric-parity failure even though the difference was colour-vs-null and there was no number to compare. Fill classification is now value-aware: a column whose every non-NA cell is an `rgb()`/`rgba()` string is a fill series regardless of its title. Numeric parity is unchanged — `_is_nonnumeric_only_difference` still hard-fails any cell that is numeric on both sides.
- **Two stale assertions, updated to the invariants that actually hold.** `test_udt_na_field_access_no_scalar_getitem` required the UDT guard to be inlined as `isinstance(__u, dict)`; commit `8bc8f41d` moved that guard into the `udt_get_field` builtin (the inlined walrus is a `SyntaxError` inside list comprehensions), so the test now accepts either spelling. `test_get_price_pine_series_endpoints` asserted `line.new` stores a `PineSeries`; `0ad37af0` began snapshotting endpoints to plain numbers so `export_for_api` could not re-read `.current` on the last bar and diverge from compile — a strictly newer, deliberate change — so the test now asserts the resolved values.

### Documentation

- **New endpoint pages for previously undocumented surface.** `api/endpoints/sessions` (O(1) forming-bar ticks vs the O(n) full re-walk, O(delta) appends, tick rollback semantics, TTL/capacity, the single-worker constraint, and response windowing), `api/endpoints/data-plane` (series key rules, the four `/data/series*` routes, `/data/session` binding, `DATA_MISS` / `SESSION_KEY_MISMATCH`, and the API-key requirement), and `api/endpoints/stats`. Five of the preceding ten commits had shipped user-facing routes with no docs page at all.
- **`devops/observability` rewritten** around `PYNE_DEBUG` with real captured trace excerpts — a cold compile run, a warm cache hit, and an O(delta) session append — plus `GET /stats`, per-process and reservoir-window invariants, and a failure-modes row for "no engine debug output" (gunicorn inherits its environment from the parent, not the operator's shell).
- **`api/index` endpoint table** extended with the session, data-plane, stats and runner rows. `index.mdx` "What's new" was stale at 0.6.7 and now covers 0.6.9 and the post-release work. `llms.txt` / `llm.txt` / exports are regenerated from `docs.json` via `scripts/docs/generate-exports.mjs`, never hand-edited. Every response shape in the new pages was captured from the running app rather than inferred from source.

## [0.6.9] — 2026-10-13

### Added

- **Response windowing on `POST /run`** — optional `from_bar` / `to_bar` request fields (inclusive bar indices into `data`, negative counts from the end, either side may be omitted). Trims the **serialized envelope only**: the bar loop still runs over every bar, so indicator values, strategy state, NaN warm-up, and Pine parity are untouched. Measured on 20k bars against a local Pro API: **1,068.8 KB → 28.0 KB (38x smaller)** for a 500-bar window, with the windowed series verified byte-equal to the full run's tail.
  Windowing is a **no-op when the fields are absent** — the unwindowed envelope is unchanged and gains no `window` key. When a window *is* applied the response carries `window: {from_bar, to_bar, bars, total_bars}`, because `count` still reports bars *evaluated*; a client seeing `count=20000` with a 500-long series needs that to tell a window from a short history. `meta.profile.bars` is rewritten to the windowed length and flagged `windowed`.
  Events and drawings carry `bar_index` and are filtered to the window; objects with only `bar_time` (strategy fills) have no index to match on and are **kept**, so trimming can never silently drop a fill.
  Implemented at the serialization boundary (`backend/middleware/window.py`) rather than inside the runtime, which leaves the compile path and every parity surface untouched.


- **Live evaluation sessions over HTTP** — `POST /session`, `GET /session/<id>`, `POST /session/<id>/tick`, `POST /session/<id>/append`, `DELETE /session/<id>`. A session keeps the parsed script, its series, and its TA state alive, so re-ticking the forming bar is O(1) instead of re-evaluating every bar. Measured on 20k bars: full run **1,087.8 ms** → `update_last_bar` **0.130 ms** (**8,343x**) and `append_bars` **0.127 ms** (**8,572x**). Session init costs ~443 ms, so a session breaks even after its **first** tick. Tick and append both accept the same optional `from_bar`/`to_bar` envelope window as `/run`; combined with a 500-bar window the same live update costs **0.227 ms and 37.2 KB**, against 1,087.8 ms and 1,068 KB for a full run. Interpret only — `compile` has no resumable evaluator state and is rejected with `MODE_UNSUPPORTED`.

### Changed

- **The Pro API now runs a single gunicorn worker** (`-w 1`, was `-w 2`) in `deploy/pynescript-api.service`, `deploy/pynescript-api.service.d/tuning.conf`, `docker/entrypoint-api.sh`, and `docker-compose.prod.yml`. Session state is per-process, so a second worker would 404 on roughly half of all follow-up calls — a session created on one worker is invisible on the other. Correctness, not tuning: gevent still handles thousands of concurrent connections per worker and `--max-requests` recycling is unchanged. **Both** systemd files had to change: the drop-in wins on conflict, so a stale `-w 2` there silently overrides the base unit — exactly the failure mode the file's own comment warns about. The Cloudflare container was already `GUNICORN_WORKERS=1`.
- Session store bounds: 15-minute idle TTL, 64 concurrent sessions, 30-second sweep. Capacity overflow returns 503 `SESSIONS_FULL` rather than growing until the OOM killer arrives.
- **Table export parity**: ``table.cell`` now stores all v6 style kwargs (width, height, halign, valign, size, font, formatting, tooltip) in reference positional order (``width, height, text_color, halign, valign, size, bgcolor, tooltip, font_family, formatting``), and both export paths (``export_for_api``, ``export_compile_events_for_api``) emit cell style, ``force_overlay``, frame/border widths, and ``merged_cells`` — AXIS bottom-panel tables get proportional columns, tooltips, and merges without a wire change on its side.
- **Compile drawing extras**: ``export_compile_events_for_api`` now emits the box text/border extras, label tooltip/text extras, and polyline curve/overlay/fill fields the interpret host already emitted. Also adds the missing ``text.align_*`` enum constants (halign + valign) and stores ``box.new`` text kwargs — both hosts produce identical dicts for AXIS paint.
- **OKF bundle**: `okf/` is an Open Knowledge Format v0.2 cache of the package, the Pro API, and the docs. The pre-commit hook drafts, links, and lints it. Generated parsers and the Pine corpora are left out of the map.

### Fixed

- **`/health` never advertised the live-session endpoints.** `POST /session`, `…/tick`, `…/append`, `GET`/`DELETE /session/<id>` were routable but absent from the health `endpoints` map, so the API reported 28 endpoints and no mention of sessions. `/health` is the discovery surface AXIS and agents read to learn what a host can do, so an unadvertised route reads as a route that does not exist. Two tests now guard it, in both directions: every session route is advertised, and every advertised session route is routable with keys byte-identical to Flask's rule strings so a rename in the decorator cannot desynchronise discovery from routing. Verified the guard fails when the entries are removed.
  The checks are deliberately scoped to the session routes rather than the whole map: `/health` advertises some routes only when a subsystem is enabled (`runner_enabled()` / `scheduler_enabled()`), so a whole-map invariant would flag that intentional conditional advertisement as drift.

- **Interpreter/compile parity harness could not classify bgcolor differences** (7 of 13 outstanding failures). `fill_background_only` was computed solely from keys present on *one* side, so a `Background` series present in **both** runs — with colour strings (`'rgba(...)'`) from interpret and `None` from compile — fell through to a hard `MISMATCH` and was unrepresentable as the known compile-path fill gap. `compare_series_maps` now routes such keys to a separate, reported `fill_value_diffs` bucket and lets them satisfy `fill_background_only`.
  The tolerance is deliberately narrow: `_is_nonnumeric_only_difference` returns False the moment any disagreeing cell is numeric on **both** sides, so a genuine numeric difference on a fill key is still a hard mismatch. Only colour/NA cells on fill-shaped keys are absorbed, and they stay visible in the result rather than being dropped.
- **`array.copy(na)` emitted a dead `list(None)` into generated code.** `array.copy` inlined `list(x) if isinstance(x, (list, tuple, np.ndarray)) else []`, which for a literal `None` argument renders as `pt2 = (list(None) if isinstance(None, ...) else [])`. It never executed — the `isinstance` guard is False — but the text reads like a crash and is what `test_chart_point_copy_not_list_none` guards against. Now routed through an `array_copy_value` builtin, matching how `array_sort` is already handled.

- **Generated docs packs no longer shred digits**: the emoji strip in ``scripts/docs/generate-exports.mjs`` used bare ``\p{Emoji}``, which also matches ASCII digits participating in keycap sequences. Every ``llm.txt`` / ``llms.txt`` therefore shipped mangled text — ``AGPL-3.0-only`` became ``AGPL-.-only``, ``ADR-001`` became ``ADR-``, ``/v/chat`` became ``/v/chat`` with digits eaten. Now strips ``\p{Extended_Pictographic}`` plus the skin-tone / variation / combining-keycap codepoints, so real emoji go and version numbers, ADR ids, and license identifiers survive.
- **AXIS docs pack pointed at the wrong repository**: the export pipeline hardcoded the PYNE repo URL for every product, so ``/axis/docs/llm.txt`` announced ``Repository: https://github.com/hoox-sh/pyne``. Each product now carries its own ``repoUrl``.
- **VPS Pro API memory growth**: gunicorn workers now recycle (``--max-requests``) on both the Hetzner systemd unit and the Docker entrypoint (``GUNICORN_MAX_REQUESTS``). Without recycling, workers grew past 1.6 GB each on the 3.8 GB VPS until swap filled 100% and even ``GET /health`` took 6–14 s, so AXIS reported the engine as down. The unit is now versioned at ``deploy/pynescript-api.service`` (+ ``cors.conf`` drop-in) and ``scripts/deploy_vps.sh`` installs it before restart.

### Security

- **undici TLS certificate validation bypass (CVE-2026-84961 / GHSA-w293-vg96-wgc3, high)** and five further undici advisories are closed in ``cf/`` by an ``overrides`` entry pinning ``undici`` to ``^7.29.1`` (resolves 7.30.0). ``BalancedPool`` used to deep-clone its constructor options through ``JSON.parse(JSON.stringify(...))``, which cannot represent functions — a ``connect``/``tls`` option carrying a ``checkServerIdentity`` callback was silently dropped before reaching the TLS layer, so a certificate the caller's validator was written to reject was accepted.
  ``undici`` reached ``cf/`` only as a transitive dev dependency (``wrangler`` → ``miniflare``); the sole runtime dependency is ``@cloudflare/containers``, so the vulnerable path never shipped. Fixed regardless — a silently-dropped certificate validator is the wrong thing to leave lying in a tree that runs in CI.
  Verified with a clean ``npm ci``: resolves 7.30.0, ``npm audit`` reports zero undici advisories, and ``wrangler`` still runs.
- **sharp librsvg CVE-2026-96889 (GHSA-wq5f-xc86-pv6w, high)** closed by pinning ``sharp`` to ``^0.35.5`` (resolves 0.35.5) in ``cf/``. Same ``wrangler`` → ``miniflare`` dev chain; the bump pulls matching ``@img/sharp-libvips-*`` 1.3.4 platform binaries and nothing else.
- **brace-expansion DoS (2 high, 1 medium)** closed in ``vscode-extension/`` by pinning ``brace-expansion`` to ``^5.0.12`` (resolves 5.0.12) under ``vscode-languageclient`` → ``minimatch``. The three advisories were stack exhaustion via uncontrolled recursion in ``expand_()`` (GHSA-qhr7-859c-m2p7) and ``parseCommaParts()`` (GHSA-6j4f-fj2g-mc7p), and quadratic-time expansion of ``{a},b}`` input (GHSA-q2hr-2g5m-vwhr). 5.0.12 is the strictest floor across all three.

  Both trees verified with a clean ``npm ci`` (not an incremental install): ``npm audit`` reports **0 vulnerabilities** in ``cf/`` and ``vscode-extension/``, ``wrangler`` still runs, and the extension still compiles. Dependabot is now at **zero open alerts** for this repository.

### Docs

- README version strings refreshed to 0.6.8 (PyPI + all three GHCR tags verified present).

### Known limitation

Sessions are **interpret-only** (``compile`` has no resumable evaluator state; ``create_session`` rejects it), and **strategy fills are not rolled back across ticks** — fills accumulate and strategy series history is overwritten rather than appended, the same caveat as the realtime tick loop in ``Runtime.run``. Indicators and ``alert()`` conditions are unaffected. A live *strategy* driven through ``/session/<id>/tick`` needs that fixed first.

## [0.6.8] - 2026-09-26

### Added

- **Tables in the bottom panel**: Users can now move tables drawn by a script into a separate tab in the chart's bottom panel. To move a script's tables to the panel, open the "More" menu in the script's status line and select the "Move tables to bottom" option. To move the tables back to the chart, select "Move tables to chart" from the "More" menu or from the context menu opened at the top of the panel's tab. Tables in the bottom panel have different positioning and cell-sizing rules from those on the chart. All tables stack vertically in order from first to last, regardless of the position and force_overlay arguments of each table.new() call. The cells of each table also stretch as necessary to fit the allocated width and height within the pane, without truncating the displayed text. Additionally, users can select and copy the text from tables in the bottom panel, unlike tables displayed on the chart.

- **Improved line wrapping in square brackets**: We've improved the line wrapping behaviors for code within square brackets ([ ]). Previously, all line-wrapped history-referencing operations or tuples required indenting each line after the first by any number of spaces that was not a multiple of four. The only exception was for square brackets enclosed in a set of parentheses, because code within parentheses can contain any amount of indentation, whether zero or a multiple of four spaces. We've extended the indentation flexibility for code in parentheses to all code between square brackets. Now, wrapped code within square brackets can use any amount of indentation without restriction.

### Changed

- Interpret hot path loads call-site, assignment, and TA state by attribute
  instead of ``getattr``, reuses each TA dict key across bars, and skips
  repeated argument checks for steady ``ta.sma`` / ``ema`` / ``rsi`` /
  ``stdev`` / ``bb`` / ``atr`` / ``highest`` / ``lowest``. Calendar names
  (``year``, ``month``, …) still materialize on first read. On a 2000-bar
  interpret bench, mixed TA went from 135 ms to 113 ms and ``plot(close)``
  from 12.5 ms to 10.0 ms.

### Fixed

- ``ta.uo`` no longer copies one buying-pressure ratio into all three
  averages. Interpret uses the three-window incremental kernel. Compile
  emits ``numba_uo`` in nopython mode.

## [0.6.6] - 2026-09-22

Runtime last-sample TA, convert-to-v6 identifier safety, webhook SSRF, LSP nested completion.

### Fixed

- ``ta.ao()`` no longer rebuilds ``hl2`` every bar when the identifier is
  absent; the full-recompute path returns the last SMA sample instead of
  ``None``. Period-only ``ta.stoch`` / ``ta.cci`` / ``ta.wpr`` skip series
  cap-slice copies on the incremental path. Period-only ``ta.dmi`` uses the
  same last-sample incremental path. Incremental ``ta.bb`` shares one SMA+stdev
  window instead of two nested deques. ``ta.cog`` / ``ta.mode`` use last-sample
  incremental kernels.
- Convert-to-v6 leaves ``n`` inside ``for n =`` bodies as the loop variable.
- Interpret ``color.*`` named constants use the Pine v6 palette (``color.green``
  is ``#22AB94``), matching compile ``_color_const``.
- Linter ``C001`` only fires on snake_case ``ta.*`` assignments (``fastMA`` /
  ``sma`` are quiet; ``pyne lint`` matches the LSP filter).
- Convert-to-v6 no longer rewrites v5 UDF definitions named ``security`` /
  ``financial`` / other ``request.*`` leaves to ``request.<name>(...) =>``.
  v3 ``period =`` / ``for n =`` stay user identifiers; ``n == 0`` still
  becomes ``bar_index``.
- LSP ``strategy.`` completion keeps nested ``risk.*`` insert text;
  completion resolve no longer restores a fully-qualified snippet after
  ``ta.``. Hover documents additional namespaces and drawing/collection
  types; bare ``line`` stays a type card.
- ``line.fill`` is cataloged as an alias of ``linefill.new`` so AXIS pre-eval
  does not suggest ``line.all``. Compile fill ``plot_meta`` stamps ``plot1`` /
  ``plot2``; interpret fill color is per-bar.

### Security

- Alert webhooks unwrap IPv4-mapped / 6to4 / decimal IPv4, refuse HTTP
  redirects, and re-check the URL at POST time. ``POST /run/batch`` now
  returns ``WEBHOOK_URL_BLOCKED`` instead of silently skipping.
- Oversized request bodies return JSON ``PAYLOAD_TOO_LARGE`` (413).
- Git OAuth device-flow ``verification_uri`` values are allowlisted to
  ``github.com`` / ``gitlab.com``.
- Hosted runner GET ``/scripts`` / ``/scripts/:id`` / ``/cron/jobs`` redact
  ``webhook_url`` when ``ADMIN_TOKEN`` is set and the request is unauthenticated.
- Client ``timeout_seconds`` is capped (default 120s, ``PYNE_RUN_TIMEOUT_MAX``)
  so a huge value cannot hold a gunicorn worker until SIGKILL.
- ``POST /preview/chart``, ``/preview/indicator``, and ``/backtest/quick``
  validate against their schemas (unknown fields rejected).

## [0.6.5] - 2026-09-14

Convert-to-v6 no longer rewrites user UDF names, parameters, or unpack targets.

### Fixed

- ``ta.*`` / ``math.*`` / ``ticker.*`` prefixes apply only to **calls**. UDF
  definitions (``hma(...) =>``), parameters named ``min``/``max``/``mode``, and
  unpack targets (``[rsi, dev] =``) stay user identifiers. set01–04 scripts
  older than v6 parse 323/323 after convert.

## [0.6.4] - 2026-09-14

Convert older Pine to v6 in the editor, LSP, CLI, and HTTP.

### Added

- Editor **Convert to Pine v6**: AXIS overflow menu + command palette, VS Code
  ``PYNE: Convert to Pine v6`` / lightbulb, LSP code action, and
  ``POST /lsp/convert``. Source-level rewrite from any older version (missing
  pragma = v1) — colors / ``n`` / timeframe idents, ``ta.*`` / ``math.*`` /
  ``request.*`` namespaces, ``study(``→``indicator(``, typed ``input.*()``,
  ``iff`` / ``offset``. Not a semantic v6 migrator.

### Changed

- ``pyne convert --to 6`` now runs the full v1-v5 pipeline, not only
  leftover ``study(`` / ``request.*`` names.

## [0.6.3] - 2026-09-14

Hosted script runner on Flask / VPS / container, plus `pyne runner` CLI.

### Added

- Optional Flask hosted runner (`PYNE_RUNNER=1`): SQLite script registry,
  `POST/GET/DELETE /scripts`, `GET/PUT /cron/jobs`, `POST /cron/run`.
  Background bar-close polling is a second switch (`PYNE_RUNNER_SCHEDULER=1`).
  Docker / VPS / Cloudflare Container pick it up via env; default remains off.
- CLI `pyne runner` talks to that API: `deploy`, `list`, `show`, `delete`,
  `tick`, `jobs`, `enable`, `disable` (`--url` / `PYNE_API_URL`).

## [0.6.2] - 2026-09-12

P1p plot-parity tail on official TV builtins.

### Fixed

- Interpret UDF series parameters: `s[1]` inside a function now tracks the
  per-call-site argument stream when the caller passed a scalar
  (`src = close; updown(src)`). Official Connors RSI and the TV builtin
  script set are 0 MISMATCH vs compile.

## [0.6.1] - 2026-09-12

Correctness follow-up on 0.6.0 dual-host risk, InterpretSession, and HTF
resample, plus the session API that landed after the `v0.6.0` tag.

### Added

- Persistent `InterpretSession`: delta `append_bars`, realtime
  `update_last_bar` ticks, TA rollback, confirm-on-append.

### Fixed

- `strategy.cash` as a qty-type identifier now selects cash mode on both
  interpret and compile (string `"cash"` was the only working form).
- Compile `begin_bar` receives bar time so day-scoped fill caps and
  consecutive-loss days roll on `Runtime.run(mode="compile")`.
- Pending fills are risk-gated at fill time on both brokers; covering
  leftover cannot reverse-open after an intraday halt.
- Session `barstate` no longer leaks across appends; confirm overwrites
  strategy history; `islast` is false on a confirmed bar when more bars
  follow; `_once_fired` rolls back with the bar-open snapshot.
- HTF `lookahead_on` leaks each bucket's **final** value from the period
  start on historical bars (not developing-as-of-this-bar); `close[1]`
  resamples previous HTF bars (same-TF falls back to chart history); bare
  D/W/M buckets follow `timeframe.change` (Monday weeks, `syminfo.timezone`).
- Codecov per-flag uploads set `disable_search` so reports stay isolated.

### Changed

- Disk IR cache v16 (`begin_bar` bar time, calendar `chart_timezone()`,
  `strategy.cash` qty-type emit).
- Docs: PyneTS as standalone package (no `pynets/` submodule); retired
  linter codes C003/W102/W103; version stamps **0.6.1**.

### Security

- wrangler 4.131.0 (sharp 0.35.4, GHSA-rgj7-g3m4-5g8c).

## [0.6.0] - 2026-09-10

Parity increments across strategy risk, realtime scope, timeframes,
`request.security` barmerge, and the linter.

### Added

- Strategy risk: `strategy.risk.max_intraday_loss(value, type)` honors
  percent-of-equity vs cash on both brokers; interpret enforces intraday
  loss plus the day-scoped `max_intraday_filled_orders` cap, with
  order-level fill counting on both hosts.
- Realtime: intrabar rollback of the `var` scope plus series currents on
  interpret realtime ticks (`varip` persists); `once` fires once from
  confirmed state.
- Timeframes: `timeframe.change` D/W/M on the exchange calendar
  (`syminfo.timezone`, UTC default; DST-aware days, Monday weeks, calendar
  months); compile routes calendar TFs through object mode.
- `request.security`: `gaps_on` / `lookahead_on` honored on the HTF resample
  paths (bucket-start na-gaps, forming-bucket reads); presence-vs-effect
  policy tags (`gaps_lookahead_provided` vs `gaps_applied` /
  `lookahead_applied`).

### Changed

- Docs: `once` on grammar/ASDL/builder/unparser, interpret + compile pages,
  compatibility, glossary, FAQ, missing-features. Version table **0.6.0**.
- `docs/known_divergences.md`: F-12…F-16 closed; D-02/D-04/D-06 narrowed to
  their documented residuals.
- Disk IR cache v14 (calendar routing changed codegen).

### Removed

- Linter: retired legacy rules `C003` (indented `if` without "braces"),
  `W102` (histogram → plotcandle), `W103` (`var int x = na` → 0); codes stay
  retired so history stays greppable. LSP `C003` noise filter removed with
  the rule.

## [0.5.0] - 2026-09-07

Performance release across the whole stack, plus several correctness fixes
surfaced by the work.

### Changed

- **Slotted AST nodes.** ASDL generator emits `@dataclass(slots=True)`; the
  shared `AST` base carries `__slots__` for evaluator call-site stamps.
  Removes the per-node `__dict__` (large scripts allocate tens of thousands
  of nodes). Regenerate via `python src/pynescript/ast/grammar/asdl/tool/generate.py`.
- **LSP typing latency (~3-5×).** `didChange` no longer runs two full ANTLR
  parses (the linter accepts a pre-built `tree=`), and parse+lint now run
  debounced (250ms, `PYNESCRIPT_LSP_DEBOUNCE_MS`) on a worker thread so the
  event loop stays responsive. Semantic tokens, inlay hints, hover decl maps,
  and workspace/symbol results are memoized per document version; completion
  items, fuzzy-filter fields, and categories are cached per metadata load;
  references/definitions dedupe is O(1) per line.
- **TA incremental coverage.** `ta.max` / `ta.min` / `ta.range` now use the
  incremental kernels; `ta.highest` / `ta.lowest` / `ta.wpr` / `ta.stoch`
  incremental use monotonic-deque sliding extremes (amortized O(1)/bar
  instead of O(period) scans); `ta.rci` rank computation is O(n log n)
  (was O(n²) per bar); `ta.vwma` incremental drops its O(period) na-scan.
- Per-bar `import` statements hoisted out of hot paths (`+=` assignment,
  subscript call-sites, `switch`, overload dispatch); `_commit_unwritten_history`
  iterates a cached `history ∩ var` intersection.
- Parse-cache hit scrub is a specialized stack walk (was generator BFS);
  `Runtime._parse_script` no longer performs a second redundant full-tree walk.
- Builder: single-line token fast path skips the per-node `stop.text`
  substring allocation; simple string literals skip `ast.literal_eval`.
- Backend: `/run` applies a server-side default timeout (`PYNE_RUN_TIMEOUT`,
  30s) so pathological scripts cannot kill a gunicorn worker; PBKDF2 key
  hashing is LRU-cached (~50-100ms → O(1) per authenticated request);
  SSRF DNS verdicts are TTL-cached; optional off-thread webhook delivery
  (`ALERT_WEBHOOK_ASYNC=1`); chart renderer uses the thread-safe OO
  matplotlib API (pyplot globals raced under `--threads 4`).
- OHLCV pack/list caches are bounded by tracked bars
  (`PYNE_OHLCV_CACHE_MAX_BARS`, default 2M), not just entry count.
- Strategy `position_size`/`position_avg_price`/`closedtrades` end-of-bar
  history is capped at 512 entries.

### Fixed

- Five compiler/evaluator subtree walks used `node.__dict__.values()`, which
  silently collected nothing on slotted nodes and broke UDF `var`-local and
  history-series detection; traversal now goes through `_fields`.
- `_as_series` same-bar cache could false-hit on a different series (single
  interned-int fingerprint): fingerprint uses the two newest samples and the
  host clears the cache every bar.
- OHLCV pack cache evicted from the *list* cache, so the pack cache was
  never bounded.
- `didChange` without a prior `didOpen` crashed the LSP handler (now treated
  as an empty open); closed documents leaked into the workspace parse-error
  set.

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

[0.6.8]: https://github.com/hoox-sh/pyne/compare/v0.6.7...v0.6.8
[0.6.7]: https://github.com/hoox-sh/pyne/compare/v0.6.6...v0.6.7
[0.6.6]: https://github.com/hoox-sh/pyne/compare/v0.6.5...v0.6.6
[0.6.5]: https://github.com/hoox-sh/pyne/compare/v0.6.4...v0.6.5
[0.6.4]: https://github.com/hoox-sh/pyne/compare/v0.6.3...v0.6.4
[0.6.3]: https://github.com/hoox-sh/pyne/compare/v0.6.2...v0.6.3
[0.6.2]: https://github.com/hoox-sh/pyne/compare/v0.6.1...v0.6.2
[0.6.1]: https://github.com/hoox-sh/pyne/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/hoox-sh/pyne/compare/v0.5.0...v0.6.0
[0.4.4]: https://github.com/hoox-sh/pyne/compare/v0.4.3...v0.4.4
[0.4.3]: https://github.com/hoox-sh/pyne/compare/v0.4.2...v0.4.3
[0.4.2]: https://github.com/hoox-sh/pyne/compare/v0.4.1...v0.4.2
[0.4.1]: https://github.com/hoox-sh/pyne/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/hoox-sh/pyne/compare/v0.3.18...v0.4.0
