# Known divergences from reference Pine semantics

**Date:** 2026-08-10 (sprint residual refresh)  
**Status:** intentional or residual gaps; track until closed or product-scoped  
**Sprint status:** `docs/code_audit_2026-08-10/SPRINT_STATUS.md`

This page documents **semantic differences** between pynescript and **reference Pine Script** language behavior (as described in the public Pine language docs) that affect numerical or strategy results. It is not a full feature matrix (see `docs/missing_features.md` and `COMPATIBILITY.md`).

---

## Strategy

### `strategy.exit` pending brackets (fixed Wave B — residual gaps)

**Reference Pine:** `strategy.exit` places a pending stop/limit (bracket) that fills when price path touches the level.

**pynescript (current):**

| Piece | Status |
|-------|--------|
| Pending stop/limit brackets + OCA | **Fixed** (Wave B) — OHLC / `process_pending_orders`; market exit (no stop/limit/trail) still closes immediately |
| `from_entry` (interpret) | **Fixed** — filters open-trade legs; unknown id is soft no-op (`tests/test_order_fills.py`) |
| `from_entry` (compile) | **Fixed** — compiler emits `from_entry=` for market and stop/limit exits; multi-leg filter on compile broker (`tests/test_compiler_strategy.py`) |
| `qty_percent` on exit | **Fixed** (interpret + compile `close`) — `%` of target (whole pos or `from_entry`); wins over `qty`; `≤0`/na → no-op; `>100` capped at 100% |
| Trail stops (`trail_*`) | **Minimal (interpret + compile)** — `trail_offset` / `trail_points` (ticks × mintick) + optional `trail_price` activation; stop ratchets from bar high/low in `process_pending_orders` / compile `PendingOrder`. OHLC path approx (no tick path). |
| `profit` / `loss` | **Residual** — still coerced as prices (not tick offsets from entry avg) |

**Track:** audit AGENT_03 / AGENT_04; sprint residual backlog.

### `strategy.risk.*` partial on compile path

**pynescript compile broker (`CompileStrategyBroker`):**

| Call | Compile status |
|------|----------------|
| `strategy.risk.allow_entry_in` | **Wired** — stores state; blocks opposite-direction entries (`risk_blocked`) |
| `strategy.risk.max_position_size` | **Wired** — caps entry qty to `%` of equity at fill price |
| `strategy.risk.max_drawdown` / `max_cons_loss_days` / `max_intraday_*` | **Still no-op** (not full TV risk engine) |

**Impact:** risk-capped strategies that rely only on allow_entry_in / max_position_size can share interpret-like constraints; other risk gates remain unconstrained under compile.

**Track:** audit AGENT_04; tests in `tests/test_compiler_strategy.py`.

### Open/closed trade query surface (compile) — partial honesty

**Real (from `open_legs` / `closed_trade_records`):**

- counts: `strategy.opentrades` → `open_entry_count`; `strategy.closedtrades` → `closed_trades`
- open: `size`, `entry_price`, `entry_id`, `entry_bar_index`, `entry_time`, `commission`, `profit` (MTM)
- closed: `profit`, `size`, `entry_price`, `exit_price`, `commission`, `entry_id`, `exit_id`, `entry/exit_bar_index`, `entry/exit_time`

**Still stub (zeros / empty):** per-trade `max_drawdown` / `max_runup`, entry/exit comments.

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

**Reference Pine:** `varip` keeps values across realtime ticks differently than series; host-dependent.

**pynescript:** Historical bars: both init-once (same as before). When `barstate.isrealtime` is true, `varip` re-evaluates its RHS each update. Default Runtime host keeps `isrealtime=False`.

**Track:** audit AGENT_02.

### `AugAssign` / tuple unpack series bind (fixed Wave B)

Both paths now call `_bind_series_name` so history-tracked names keep series wrappers.

### Default mock bid/ask

When the host omits quotes, bid/ask may default to fixed mock values (`100.01` / `100.02`) rather than `na`.

**Impact:** Tick/spread scripts can run “successfully” with meaningless quotes.

**Track:** audit AGENT_02.

---

## Request / multi-timeframe

### `request.security` is not a full HTF re-eval engine

**Reference Pine:** `request.security(symbol, timeframe, expression, gaps, lookahead)` re-evaluates *expression* on another symbol/timeframe series; `barmerge.gaps_*` controls na gaps vs fill; `barmerge.lookahead_*` controls whether the security series can peek at the forming HTF bar.

**pynescript (current — honest limited surface):**

| Case | Behavior |
|------|----------|
| Foreign ticker + host chart wired + no multi-symbol feed hit | **`na`** (no mock invent; matches compile foreign-na) |
| Same-symbol + **complex** pre-eval (UDF / `ta.*`) + request TF ≠ chart TF | **`na`** — no multi-TF re-eval engine (do not invent HTF structure) |
| Same-symbol + **simple OHLCV** (or same TF as chart) | Chart series **passthrough** / provider series. Different TF is a **chart-TF stub**, not true HTF aggregation |
| Same-symbol `ticker.heikinashi` | Chart OHLC → Heikin-Ashi transform (not raw chart candles) |
| `barmerge.gaps_on` / `gaps_off` | **Accepted, unused** — no gap-fill / na-gap series |
| `barmerge.lookahead_on` / `lookahead_off` | **Accepted, unused** — no lookahead offset |
| Fundamentals / footprint / dividends / … | Mock or soft-fail (see module docstring) |
| Standalone evaluator (no chart identity) | Legacy mock OHLCV for bare string series names (offline demos) |

Runtime **interpret** results expose honesty metadata when any `request.security` ran:

- `meta.request_security.htf_reeval` → always `false`
- `meta.request_security.gaps_supported` / `lookahead_supported` → always `false`
- `meta.request_security.policies` → tags such as `complex_htf_na`, `chart_passthrough_htf_stub`, `foreign_na`, `gaps_lookahead_unused`, `same_tf_chart_eval`, …
- `meta.request_security.notes` → short product notes (same text as evaluator)

Regression coverage: `tests/test_request_data_feed.py` (foreign-na, complex HTF na, HTF OHLCV stub, gaps/lookahead unused, Runtime meta).

**Impact:** MTF indicators and security-based strategies that need true HTF re-eval, gaps, or lookahead diverge from reference Pine. Prefer `na` / chart-only stubs over silent wrong HTF structure.

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
| pine-worker | **Experimental** residual host; thin-wrap over package Runtime still open (H1) |

When closing a gap, remove or update the corresponding section here and add a regression test under `tests/`.
