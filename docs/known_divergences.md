# Known divergences from reference Pine semantics

**Date:** 2026-09-10 (refresh)
**Status:** intentional or residual gaps; track until closed or product-scoped

This page documents **semantic differences** between pynescript and **reference Pine Script** language behavior (as described in the public Pine language docs) that affect numerical or strategy results. It is not a full feature matrix (see `docs/missing_features.md` and `COMPATIBILITY.md`).

---

## Status at a glance

Two tables, no prose. Every row links to its detail section below.
Tables verified 2026-09-10 against the working tree — re-verify a row
when moving it between tables.

### Open divergences

| ID | Area | Divergence | Details |
|----|------|------------|---------|
| D-01 | Strategy exits | Trail stops (`trail_*`) are OHLC-path approximations — no tick path | [§ Strategy → exits](#sec-exit-brackets) |
| D-02 | Strategy risk | No full reference risk engine: `max_position_size` is %-of-equity (reference: contracts); cash thresholds in account units without FX conversion; tick-accurate accounting | [§ Strategy → risk](#sec-risk-compile) |
| D-03 | Trade queries | Per-trade `max_drawdown` / `max_runup` are OHLC-path approximations, not tick-accurate | [§ Strategy → trade queries](#sec-trade-queries) |
| D-04 | Realtime `var` / `varip` | No live datafeed-driven ticks; no compile-mode realtime multi-pass; no deep rollback of in-place container mutations or broker side effects | [§ Evaluator → var/varip](#sec-varip) |
| D-06 | `request.security` | No full HTF expression re-eval engine; `gaps` / `lookahead` still unused on passthrough / provider / complex-na paths and for LTF requests | [§ Request → security](#sec-security) |

### Fixed

| ID | Area | Fix | In |
|----|------|-----|----|
| F-01 | Strategy exits | Pending stop/limit brackets + OCA (`process_pending_orders`) | Wave B ([details](#sec-exit-brackets)) |
| F-02 | Strategy exits | `from_entry` leg filtering, interpret + compile | Wave B ([details](#sec-exit-brackets)) |
| F-03 | Strategy exits | `qty_percent` on exit (`%` of target, capped at 100%) | Wave B ([details](#sec-exit-brackets)) |
| F-04 | Strategy exits | `profit` / `loss` in ticks (× mintick from entry avg) | Wave B ([details](#sec-exit-brackets)) |
| F-05 | Strategy risk | `strategy.risk.*` halt gates wired on the compile broker | Compile broker ([details](#sec-risk-compile)) |
| F-06 | TA | `ta.atr` is Wilder RMA of TR (interpret + Numba) | Wave B ([details](#sec-atr)) |
| F-07 | TA | EMA uses SMA seed over first `period` samples (all paths) | Fixed ([details](#sec-ema-seed)) |
| F-08 | Evaluator | `AugAssign` / tuple-unpack keep series wrappers | Wave B ([details](#sec-augassign)) |
| F-09 | Realtime | `var` / `varip` realtime window contract; `once` commits on confirmed bars | Partial Wave B / 0.4.4 ([details](#sec-varip)) |
| F-10 | Quotes | `bid` / `ask` no longer mocked — `na` when the host omits quotes | Closed ([details](#sec-bidask)) |
| F-11 | Linter | `C004` trailing-newline no longer `strip()`s before the check | Wave B ([details](#sec-linter)) |
| F-12 | Linter | Legacy rules retired: `C003` (indented `if` without “braces” — Pine has none), `W102` (histogram → plotcandle), `W103` (`var int x = na` → 0); LSP noise filter for `C003` removed with the rule | 0.6.0 ([details](#sec-linter)) |
| F-13 | Timeframes | `timeframe.change` D/W/M on the exchange calendar (`syminfo.timezone`, UTC default; DST-aware days, Monday weeks, calendar months); intraday unchanged; compile calendar TFs via object mode; disk IR cache v14 | 0.6.0 ([details](#sec-tf-change)) |
| F-14 | Realtime | Intrabar rollback of `var` scope + series currents on interpret realtime ticks (`varip` persists via `_varip_declarations`); `once` fires once from confirmed state | 0.6.0 ([details](#sec-varip)) |
| F-15 | Strategy risk | Intraday parity: `max_intraday_loss(value, type)` honors percent-of-equity vs cash on both brokers; interpret enforces intraday loss + day-scoped fill cap (previously store-only / empty stub); order-level fill counting on both hosts | 0.6.0 ([details](#sec-risk-compile)) |
| F-16 | `request.security` | `gaps_on` / `lookahead_on` honored on HTF resample paths (OHLCV + allowlisted `ta.*`): bucket-start na-gaps, forming-bucket reads with reference lookahead bias; presence-vs-effect policy tags (`gaps_lookahead_provided` vs `gaps_applied` / `lookahead_applied`) | 0.6.0 ([details](#sec-security)) |

---

## Strategy

<span id="sec-exit-brackets"></span>
### `strategy.exit` pending brackets (fixed Wave B — trail still OHLC-approx)

**Reference Pine:** `strategy.exit` places a pending stop/limit (bracket) that fills when price path touches the level.

**pynescript (current):**

| Piece | Status |
|-------|--------|
| Pending stop/limit brackets + OCA | **Fixed** (Wave B) — OHLC / `process_pending_orders`; market exit (no stop/limit/trail) still closes immediately |
| `from_entry` (interpret) | **Fixed** — filters open-trade legs; unknown id is soft no-op (`tests/test_order_fills.py`) |
| `from_entry` (compile) | **Fixed** — compiler emits `from_entry=` for market and stop/limit exits; multi-leg filter on compile broker (`tests/test_compiler_strategy.py`) |
| `qty_percent` on exit | **Fixed** (interpret + compile `close`) — `%` of target (whole pos or `from_entry`); wins over `qty`; `≤0`/na → no-op; `>100` capped at 100% |
| Trail stops (`trail_*`) | **Minimal (interpret + compile)** — `trail_offset` / `trail_points` (ticks × mintick) + optional `trail_price` activation; stop ratchets from bar high/low in `process_pending_orders` / compile `PendingOrder`. OHLC path approx (no tick path). |
| `profit` / `loss` | **Fixed** (interpret + compile) — ticks × mintick from entry avg (`_tick_offset_price`). `limit`/`stop` stay absolute prices. Absolute wins if both set. `na` / None / `≤0` ignore that leg. |

**Track:** audit AGENT_03 / AGENT_04; trail remains OHLC-approx (no tick path).

<span id="sec-risk-compile"></span>
### `strategy.risk.*` partial on compile path

**pynescript compile broker (`CompileStrategyBroker`)** — minimal halt cascade (not full TV risk engine):

| Call | Compile status |
|------|----------------|
| `strategy.risk.allow_entry_in` | **Wired** — stores state; blocks opposite-direction entries (`risk_blocked`) |
| `strategy.risk.max_position_size` | **Wired** — caps entry qty to `%` of equity at fill price |
| `strategy.risk.max_drawdown` | **Wired** — absolute and/or `%` of peak; sets `entries_blocked` when exceeded |
| `strategy.risk.max_cons_loss_days` | **Wired** — consecutive calendar-day loss tracking on closes; halt when N hit |
| `strategy.risk.max_intraday_loss` | **Wired** — day PnL as `%` of initial capital; halt when exceeded (stricter than interpret store-only) |
| `strategy.risk.max_intraday_filled_orders` | **Wired** — counts entry+exit fills per bar-time day bucket; blocks new entries when cap hit (day-scoped; resets on next day) |

**Impact:** common risk halt gates now share interpret-like `entries_blocked` + `risk_blocked` comments on compile (filled-order cap is day-scoped without permanent `entries_blocked`).

**Known residual:** `strategy.risk.max_position_size` caps entry notional as %-of-equity on both hosts; reference takes absolute contracts/shares. Changing it would break pinned behavior, so it stays documented until explicitly scheduled. Same for cash thresholds (account units, no FX) and tick-accurate risk accounting.

**Intraday parity (0.6.0):** `strategy.risk.max_intraday_loss(value, type)` honors `type` on both brokers — percent-of-initial-capital by default (`percent` / `strategy.percent_of_equity` / `%`), absolute account-currency cash for `cash` / `strategy.cash` (no FX conversion; unknown types fall back to percent). Percent and cash are mutually exclusive. Interpret now enforces intraday loss and the day-scoped fill cap in `_risk_allows_entry` (previously store-only / empty stub), with order-level fill counting (`_open_position_qty`, `_close_position`, flat market entries) matching compile's `_note_filled_order`. Loss halts are permanent once tripped on both hosts; the fill cap resets on day roll.

**Track:** audit AGENT_04; tests in `tests/test_compiler_strategy.py`, `tests/test_strategy_risk_intraday.py`.

<span id="sec-trade-queries"></span>
### Open/closed trade query surface (compile) — partial honesty

**Real (from `open_legs` / `closed_trade_records`):**

- counts: `strategy.opentrades` → `open_entry_count`; `strategy.closedtrades` → `closed_trades`
- open: `size`, `entry_price`, `entry_id`, `entry_bar_index`, `entry_time`, `commission`, `profit` (MTM), `entry_comment`, `max_drawdown` / `max_runup` (approx MAE/MFE from bar high/low)
- closed: `profit`, `size`, `entry_price`, `exit_price`, `commission`, `entry_id`, `exit_id`, `entry/exit_bar_index`, `entry/exit_time`, `entry_comment` / `exit_comment`, `max_drawdown` / `max_runup` (copied from open-leg extremes at close)

**Residual:** per-trade max_dd/runup are OHLC-path approximations (not tick-accurate); multi-leg close aggregates max extremes across reduced legs.

**Track:** audit AGENT_04; `tests/test_compiler_strategy.py` (`TestCompileTradeQueries`).

---

## Technical analysis

<span id="sec-atr"></span>
### `ta.atr` Wilder RMA (fixed Wave B — re-golden dependents)

**Reference Pine:** ATR is `ta.rma(ta.tr, length)` (Wilder smoothing).

**pynescript (after Wave B):** interpret (`_atr` / `_atr_inc_update`) and Numba (`numba_atr` / `numba_atr_inc`) use **RMA of TR**. Supertrend/KC/other ATR consumers inherit the change; golden vectors may need refresh if any hard-code EMA-era values.

**Track:** audit AGENT_03.

<span id="sec-ema-seed"></span>
### EMA seed (fixed — dual-host SMA seed)

Full-list `_ema` / `_ema_state_step` and incremental / Numba paths all use **SMA seed** over the first `period` finite samples (na until ready). Nested EMA and KC middle band inherit this contract. First-party bar-mode goldens gate residual dual-host drift (`tests/test_first_party_ta_goldens.py`, `tests/test_ta_incremental.py`).

---

## Evaluator / series

<span id="sec-varip"></span>
### `var` / `varip` realtime (partial Wave B)

**Reference Pine:** On a forming bar the host re-executes the script on each tick. Non-`varip` state is rolled back to the last confirmed bar; `varip` persists across ticks. Full rollback + committed-state snapshot is host-dependent.

**pynescript (current contract):**

| Mode | Behavior |
|------|----------|
| Historical default (`Runtime.run` without realtime kwargs) | `barstate.isrealtime=False` always. `var` and `varip` both **init-once** (first execution of the declaration). |
| `Runtime.run(..., realtime_last_bar=True)` | Last bar only: `isrealtime=True`, `ishistory=False`. Final tick sets `isconfirmed=True`; earlier multi-ticks unconfirmed. |
| `Runtime.run(..., realtime_ticks=N)` (`N>1`) | Re-visits the **last bar** `N` times with `isrealtime=True` (implies last-bar realtime). Intermediate ticks discard plot cells so series length stays one sample per bar. |
| `Runtime.run(..., realtime_bars=K)` (`K>0`) | Last *K* bars form a realtime window: each is multi-tick re-eval with `isrealtime=True`. Bars before the window stay historical (`ishistory=True`, `isrealtime=False`). |
| `Runtime.run(..., realtime_from_bar=I)` | Absolute window start: bars in `[I, n_bars)` are realtime-forming (overrides `realtime_bars` / last-bar-only for window extent). |
| When `isrealtime` | Evaluator **re-evaluates `varip` RHS** each visit; `var` does **not** re-init (keeps prior binding). This is a simplified stand-in for reference tick persistence — not a full rollback of non-`varip` series/strategy state between ticks. |

**`once` (0.4.4):** interpret commits the fired flag only when `barstate.isconfirmed` (so unconfirmed realtime ticks can re-run the body). Compile always treats the bar as confirmed. Side effects inside the body still follow the `var` / `varip` contract above — there is no extra snapshot of non-`varip` state just for `once`.

**Intrabar rollback (0.6.0):** on interpret realtime bars, intermediate ticks snapshot the `var` scope (context bindings + series `.current` + declaration set) and restore it after the visit, so every tick starts from confirmed state and only the final tick commits. `varip` names (tracked in `_varip_declarations`) are excluded and persist. Shallow by design: in-place mutations of referenced containers (arrays / matrices / UDTs) and broker side effects (fills, pending orders) are not rolled back; history pushes and the series-assign map are left alone so `x[1]` keeps working on forming bars.

**Not yet:** deep rollback of in-place container mutations or broker side effects, live datafeed-driven ticks, or compile-mode realtime multi-pass.

**Track:** audit AGENT_02; host kwargs in `pynescript.runtime.host.Runtime.run`.

<span id="sec-tf-change"></span>
### `timeframe.change` (calendar D/W/M, fixed-width otherwise)

**Reference Pine:** First bar of a new *higher* period on the **exchange calendar** (session-aware daily/weekly/monthly).

**pynescript:** Bare `D` / `W` / `M` (plus `1D` / `1W` / `1M`) resolve on the exchange calendar in `syminfo.timezone` — midnight-to-midnight days (DST-aware via zoneinfo), ISO Monday-start weeks, calendar months. The host leaves `syminfo.timezone` at UTC today, so UTC series already get real months (no more 30-day drift) and Monday weeks (no more epoch-Thursday buckets); non-UTC exchanges plug in when the host provides the zone. All other frames (intraday, multi-day like `3D`) keep fixed-width UTC buckets. Unusable timestamps or zones → `False` / UTC fallback, never raise.

**Dual-host:** interpret and compile-object-mode share `timeframe_period_changed` (interpret reads the zone from context `syminfo`). Constant calendar TFs compile in object mode — Numba cannot express tz rules — and dynamic TF strings resolve the same helper at run time, so both hosts agree. Unknown zones behave like UTC on both.

**Track:** `tests/test_timeframe_change.py` (DST spring-forward, Monday weeks, leap months, bad-zone fallback, syminfo wiring, weekly dual-host parity). Disk IR cache bumped to v14 (codegen routing changed).

<span id="sec-augassign"></span>
### `AugAssign` / tuple unpack series bind (fixed Wave B)

Both paths now call `_bind_series_name` so history-tracked names keep series wrappers.

<span id="sec-bidask"></span>
### Omitted bid/ask

When the host omits quotes, `bid`/`ask` are **na (`None`)**, not mock prices (`100.01` / `100.02`). Defaults are filled with `setdefault` so a host or `data_feed` still wins when it sets quotes.

**Impact:** Tick/spread scripts see `na` until the host injects real quotes.

**Track:** audit AGENT_02 (closed residual).

---

## Request / multi-timeframe

<span id="sec-security"></span>
### `request.security` is not a full HTF re-eval engine

**Reference Pine:** `request.security(symbol, timeframe, expression, gaps, lookahead)` re-evaluates *expression* on another symbol/timeframe series; `barmerge.gaps_*` controls na gaps vs fill; `barmerge.lookahead_*` controls whether the security series can peek at the forming HTF bar.

**pynescript (current — honest limited surface):**

| Case | Behavior |
|------|----------|
| Foreign ticker + host chart wired + no multi-symbol feed hit | **`na`** (no mock invent; matches compile foreign-na) |
| Same-symbol + **complex** pre-eval (UDF / nested / non-allowlist `ta.*`) + request TF ≠ chart TF | **`na`** — no full multi-TF re-eval engine (do not invent HTF structure) |
| Same-symbol + **simple OHLCV** + request TF **coarser** than chart bar spacing (parseable fixed TF, bar times present) | **Timestamp resample** of chart OHLCV (`htf_ohlcv_resample`): open/high/low/close/volume/time/hl2/hlc3/ohlc4 on **last completed** HTF bucket only (lookahead_off-style). |
| Same-symbol + **allowlisted simple ta.*** (`ta.sma` / `ta.ema` / `ta.rsi` / `ta.wma` / `ta.rma` with bare OHLCV source + const length; `ta.atr(length)`) + request TF **coarser** | **HTF series TA** (`htf_simple_ta_resample`): bucket chart bars → run interpret TA helper on unique completed HTF OHLCV → map last completed value to chart bars. Not arbitrary AST re-eval. |
| Same-symbol + **simple OHLCV** otherwise (same TF, LTF, history offsets like `high[1]`, unparseable TF, …) | Chart series **passthrough** / provider series (`same_tf_chart_eval` / `chart_passthrough_htf_stub`) |
| Same-symbol `ticker.heikinashi` | Chart OHLC → Heikin-Ashi transform (not raw chart candles) |
| `barmerge.gaps_on` / `gaps_off` | **Honored on HTF resample paths**, still unused elsewhere — see below |
| `barmerge.lookahead_on` / `lookahead_off` | **Honored on HTF resample paths**, still unused elsewhere — see below |
| Fundamentals / footprint / dividends / … | Mock or soft-fail (see module docstring) |
| Standalone evaluator (no chart identity) | Legacy mock OHLCV for bare string series names (offline demos) |

**HTF resample limits (intentional):** bare series fields (`close`, `open`, …) / string names, plus the allowlisted simple `ta.*` shapes above. Not `high[1]`, nested `ta.sma(ta.ema(...))`, multi-arg ATR, or UDF bodies. Monthly calendar TFs are not fixed-ms buckets and stay on the stub path. Expression must appear **inline** as the security third arg AST (pre-bound variables stay on the complex/na path).

**Barmerge on resample paths (0.6.0):** `gaps_on` delivers the resampled value only on the first chart bar of a newly completed HTF bucket (`na` elsewhere — previous bucket's final value, no future leak). `lookahead_on` reads the still-forming bucket as of the current bar (developing open/high/low/close/volume; TA helpers run over completed buckets + forming) — on historical bars this shows the bucket's final value from the period start, i.e. the documented reference lookahead bias (repaints like reference; combine with an offset expression such as `close[1]` to avoid it). The two compose: `gaps_on` + `lookahead_on` yields the forming value on bucket-start bars only. Single-bar charts fall back to chart-period inference and may take the passthrough stub on bar 0 (pre-existing edge, same as `gaps_off`).

Runtime **interpret** results expose honesty metadata when any `request.security` ran:

- `meta.request_security.htf_reeval` → always `false` (OHLCV/simple-ta resample is not a full expression re-eval engine)
- `meta.request_security.gaps_supported` / `lookahead_supported` → `true` once a resample call actually honored them (still `false` on passthrough / provider / complex-na paths)
- `meta.request_security.policies` → tags such as `htf_ohlcv_resample`, `htf_simple_ta_resample`, `complex_htf_na`, `chart_passthrough_htf_stub`, `foreign_na`, `gaps_lookahead_provided`, `gaps_applied`, `lookahead_applied`, `same_tf_chart_eval`, …
- `meta.request_security.notes` → short product notes (same text as evaluator)

Regression coverage: `tests/test_request_data_feed.py` (foreign-na, complex HTF na, HTF OHLCV resample hourly→daily / 1m→60m, HTF simple ta.sma/ema/rsi/atr/wma/rma, nested ta still na, gaps/lookahead on resample paths + unused-on-passthrough, Runtime meta).

**Impact:** MTF indicators that need full expression re-eval on HTF still diverge from reference Pine, as do LTF requests and provider-series merge args. Simple HTF OHLC and allowlisted simple `ta.*` on HTF now also honor `gaps` / `lookahead` per reference barmerge. Compile still maps same-symbol simple security to chart passthrough (no HTF resample at all) — pre-existing gap, unchanged by this increment.

**Track:** audit AGENT_03; full multi-TF host engine is out of product scope until explicitly scheduled.

---

<span id="sec-linter"></span>
## Linter (tooling, not runtime)

**Fixed (Wave B):** `C004` trailing-newline check no longer `strip()`s before `endswith("\n")`.

**Fixed (0.6.0):** legacy rules retired and codes left
retired so history stays greppable — `C003` (every indented `if`
flagged for missing “braces” in a braceless language), `W102`
(histogram plots nudged toward plotcandle, which is not a substitute),
`W103` (`var int x = na` nudged toward `0`, which changes semantics).
The LSP-side `C003` noise filter (`_c003_is_block_if`) was removed with
the rule. `C001` (camelCase for `ta.*` names) stays as a heuristic,
with the already-camelCase false hits still filtered downstream.

**Track:** `tests/test_linter.py` (`TestRetiredRules`); audit AGENT_01.

---

## Product scope notes

| Area | Policy |
|------|--------|
| Dual-host parity (interpret ↔ compile) | Primary correctness contract for supported surface |
| Runtime host SoT | **`pynescript.runtime`** (package owns bar loop); `backend.runtime` / `backend.evaluator` / `backend.series` are compat shims |
| Package façade tests | `tests/test_runtime_package.py` (import + interpret smoke + shim identity) |
| TA incremental / goldens | CI Core runtime: `test_ta_incremental`, `test_first_party_ta_goldens` |
| Reference Pine numerical fidelity | Best-effort; known gaps listed above |
| Free Pro API tier | Chart/mock data only; bar/script/rate/concurrency caps; SSRF-safe webhooks |
| Third-party corpora | Not required for CI; first-party fixtures under `tests/fixtures/first_party/` / `tests/data/first_party/` |
| pyne-worker / pine-worker | **Not colocated** — sibling `hoox-sh/pyne-worker` is a thin wrap over package Runtime; TS `hoox-sh/pine-worker` is a separate checkout |

When closing a gap, remove or update the corresponding section here and add a regression test under `tests/`.
