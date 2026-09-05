# Known divergences from reference Pine semantics

**Date:** 2026-08-15 (refresh)
**Status:** intentional or residual gaps; track until closed or product-scoped

This page documents **semantic differences** between pynescript and **reference Pine Script** language behavior (as described in the public Pine language docs) that affect numerical or strategy results. It is not a full feature matrix (see `docs/missing_features.md` and `COMPATIBILITY.md`).

---

## Strategy

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

**Impact:** common risk halt gates now share interpret-like `entries_blocked` + `risk_blocked` comments on compile (filled-order cap is day-scoped without permanent `entries_blocked`). Remaining gaps: full TV risk types/currency units, tick-accurate risk accounting.

**Track:** audit AGENT_04; tests in `tests/test_compiler_strategy.py`.

### Open/closed trade query surface (compile) — partial honesty

**Real (from `open_legs` / `closed_trade_records`):**

- counts: `strategy.opentrades` → `open_entry_count`; `strategy.closedtrades` → `closed_trades`
- open: `size`, `entry_price`, `entry_id`, `entry_bar_index`, `entry_time`, `commission`, `profit` (MTM), `entry_comment`, `max_drawdown` / `max_runup` (approx MAE/MFE from bar high/low)
- closed: `profit`, `size`, `entry_price`, `exit_price`, `commission`, `entry_id`, `exit_id`, `entry/exit_bar_index`, `entry/exit_time`, `entry_comment` / `exit_comment`, `max_drawdown` / `max_runup` (copied from open-leg extremes at close)

**Residual:** per-trade max_dd/runup are OHLC-path approximations (not tick-accurate); multi-leg close aggregates max extremes across reduced legs.

**Track:** audit AGENT_04; `tests/test_compiler_strategy.py` (`TestCompileTradeQueries`).

---

## Technical analysis

### `ta.atr` Wilder RMA (fixed Wave B — re-golden dependents)

**Reference Pine:** ATR is `ta.rma(ta.tr, length)` (Wilder smoothing).

**pynescript (after Wave B):** interpret (`_atr` / `_atr_inc_update`) and Numba (`numba_atr` / `numba_atr_inc`) use **RMA of TR**. Supertrend/KC/other ATR consumers inherit the change; golden vectors may need refresh if any hard-code EMA-era values.

**Track:** audit AGENT_03.

### EMA seed (fixed — dual-host SMA seed)

Full-list `_ema` / `_ema_state_step` and incremental / Numba paths all use **SMA seed** over the first `period` finite samples (na until ready). Nested EMA and KC middle band inherit this contract. First-party bar-mode goldens gate residual dual-host drift (`tests/test_first_party_ta_goldens.py`, `tests/test_ta_incremental.py`).

---

## Evaluator / series

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

**Not yet:** true intrabar rollback of non-`varip` state, live datafeed-driven ticks, or compile-mode realtime multi-pass.

**Track:** audit AGENT_02; host kwargs in `pynescript.runtime.host.Runtime.run`.

### `timeframe.change` (UTC fixed-width buckets)

**Reference Pine:** First bar of a new *higher* period on the **exchange calendar** (session-aware daily/weekly/monthly).

**pynescript:** Interpret and compile compare UTC epoch buckets using the same widths as `timeframe.in_seconds` (`D` = 86400s, `W` = 7d, `M` ≈ 30d). Bar 0 is a new period. No-host / missing times → `False`. Not session- or DST-aware.

**Track:** `tests/test_timeframe_change.py`.

### `AugAssign` / tuple unpack series bind (fixed Wave B)

Both paths now call `_bind_series_name` so history-tracked names keep series wrappers.

### Omitted bid/ask

When the host omits quotes, `bid`/`ask` are **na (`None`)**, not mock prices (`100.01` / `100.02`). Defaults are filled with `setdefault` so a host or `data_feed` still wins when it sets quotes.

**Impact:** Tick/spread scripts see `na` until the host injects real quotes.

**Track:** audit AGENT_02 (closed residual).

---

## Request / multi-timeframe

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
| `barmerge.gaps_on` / `gaps_off` | **Accepted, unused** — no gap-fill / na-gap series |
| `barmerge.lookahead_on` / `lookahead_off` | **Accepted, unused** — no lookahead offset (HTF resample always last completed bar) |
| Fundamentals / footprint / dividends / … | Mock or soft-fail (see module docstring) |
| Standalone evaluator (no chart identity) | Legacy mock OHLCV for bare string series names (offline demos) |

**HTF resample limits (intentional):** bare series fields (`close`, `open`, …) / string names, plus the allowlisted simple `ta.*` shapes above. Not `high[1]`, nested `ta.sma(ta.ema(...))`, multi-arg ATR, or UDF bodies. Monthly calendar TFs are not fixed-ms buckets and stay on the stub path. Gaps never insert `na` holes between HTF bars. Expression must appear **inline** as the security third arg AST (pre-bound variables stay on the complex/na path).

Runtime **interpret** results expose honesty metadata when any `request.security` ran:

- `meta.request_security.htf_reeval` → always `false` (OHLCV/simple-ta resample is not a full expression re-eval engine)
- `meta.request_security.gaps_supported` / `lookahead_supported` → always `false`
- `meta.request_security.policies` → tags such as `htf_ohlcv_resample`, `htf_simple_ta_resample`, `complex_htf_na`, `chart_passthrough_htf_stub`, `foreign_na`, `gaps_lookahead_unused`, `same_tf_chart_eval`, …
- `meta.request_security.notes` → short product notes (same text as evaluator)

Regression coverage: `tests/test_request_data_feed.py` (foreign-na, complex HTF na, HTF OHLCV resample hourly→daily / 1m→60m, HTF simple ta.sma/ema/rsi/atr/wma/rma, nested ta still na, gaps/lookahead unused, Runtime meta).

**Impact:** MTF indicators that need full expression re-eval on HTF, gaps, or lookahead still diverge from reference Pine. Simple HTF OHLC and allowlisted simple `ta.*` on HTF are closer than chart passthrough but still not a full multi-TF engine.

**Track:** audit AGENT_03; full multi-TF host engine is out of product scope until explicitly scheduled.

---

## Linter (tooling, not runtime)

**Fixed (Wave B):** `C004` trailing-newline check no longer `strip()`s before `endswith("\n")`. Residual inverted/legacy style rules may still produce noise; that is tooling debt, not a Pine semantic divergence.

**Track:** audit AGENT_01.

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
