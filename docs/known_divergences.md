# Known divergences from TradingView Pine

**Date:** 2026-08-10 (audit Wave A documentation)  
**Status:** intentional or residual gaps; track until closed or product-scoped

This page documents **semantic differences** between pynescript and TradingView Pine Script that affect numerical or strategy results. It is not a full feature matrix (see `docs/missing_features.md` and `COMPATIBILITY.md`).

---

## Strategy

### `strategy.exit` pending brackets (fixed Wave B — residual gaps)

**TradingView:** `strategy.exit` places a pending stop/limit (bracket) that fills when price path touches the level.

**pynescript (after Wave B):** stop/limit legs are pending orders (OCA cancel when both set), filled via OHLC / `process_pending_orders`. Market exit (no stop/limit) still closes immediately. Residual: `from_entry` filtering, trail stops, `qty_percent` edge cases.

**Track:** audit AGENT_03.

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

**TradingView:** ATR is `ta.rma(ta.tr, length)` (Wilder smoothing).

**pynescript (after Wave B):** interpret (`_atr` / `_atr_inc_update`) and Numba (`numba_atr` / `numba_atr_inc`) use **RMA of TR**. Supertrend/KC/other ATR consumers inherit the change; golden vectors may need refresh if any hard-code EMA-era values.

**Track:** audit AGENT_03.

### EMA seed differences (medium)

Incremental EMA may SMA-seed while some full/MACD paths use first-value seed.

**Impact:** Early bars differ; steady-state usually converges.

**Track:** audit AGENT_03.

---

## Evaluator / series

### `var` / `varip` realtime (partial Wave B)

**TradingView:** `varip` keeps values across realtime ticks differently than series; host-dependent.

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

**Impact:** MTF indicators and security-based strategies diverge from TV.

**Track:** audit AGENT_03.

---

## Linter (tooling, not runtime)

Several style rules are broken or inverted (e.g. always-on trailing newline `C004`). Lint noise is not a Pine semantic divergence but affects editor trust.

**Track:** audit AGENT_01; Wave C.

---

## Product scope notes

| Area | Policy |
|------|--------|
| Dual-host parity (interpret ↔ compile) | Primary correctness contract for supported surface |
| TradingView numerical fidelity | Best-effort; known gaps listed above |
| Free Pro API tier | Chart/mock data only; bar/script/rate/concurrency caps; SSRF-safe webhooks |
| Third-party corpora | Not required for CI; first-party fixtures under `tests/data/first_party/` |

When closing a gap, remove or update the corresponding section here and add a regression test under `tests/`.
