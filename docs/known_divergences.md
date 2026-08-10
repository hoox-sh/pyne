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
| `from_entry` (compile) | **Mostly fixed** — `open_legs` multi-leg selection for stop/limit exits; market exit without levels may still map `id` only (compiler residual) |
| `qty_percent` on exit | **Fixed** (interpret + compile `close`) — `%` of target (whole pos or `from_entry`); wins over `qty`; `≤0`/na → no-op; `>100` capped at 100% |
| Trail stops (`trail_*`) | **Minimal (interpret)** — `trail_offset` / `trail_points` (ticks × mintick) + optional `trail_price` activation; stop ratchets from bar high/low in `process_pending_orders`. Compile path does **not** trail. OHLC path approx (no tick path). |
| `profit` / `loss` | **Residual** — still coerced as prices (not tick offsets from entry avg) |

**Track:** audit AGENT_03 / AGENT_04; sprint residual backlog.

### `strategy.risk.*` mostly no-op on compile path

**pynescript compile/Numba broker:** several `strategy.risk.*` calls are silent no-ops.

**Impact:** risk-capped strategies look unconstrained under compile mode.

**Track:** audit AGENT_04.

### Open/closed trade query surface incomplete (compile)

Many `strategy.opentrades.*` / `strategy.closedtrades.*` accessors return zeros on the compile broker.

**Track:** audit AGENT_04.

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

Gaps, lookahead flags, and true higher-timeframe series re-evaluation are incomplete or unused in places. Fundamentals/footprint paths may be mocked.

**Impact:** MTF indicators and security-based strategies diverge from reference Pine multi-timeframe behavior.

**Track:** audit AGENT_03.

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
