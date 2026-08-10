# Known divergences from TradingView Pine

**Date:** 2026-08-10 (audit Wave A documentation)  
**Status:** intentional or residual gaps; track until closed or product-scoped

This page documents **semantic differences** between pynescript and TradingView Pine Script that affect numerical or strategy results. It is not a full feature matrix (see `docs/missing_features.md` and `COMPATIBILITY.md`).

---

## Strategy

### `strategy.exit` is an immediate-close path (high)

**TradingView:** `strategy.exit` places a pending stop/limit (bracket) that fills when price path touches the level on a later bar (or same bar, depending on `process_orders_on_close` / fill model).

**pynescript:** The interpret path often treats exit as an **immediate close oracle** when stop/limit are not pending-processable the same way — fills can occur even when the mark sits between stop and limit.

**Impact:** Backtest PnL and trade counts diverge on stop/limit exits.

**Track:** audit AGENT_03; Wave B fix target (pending exit via OHLC / `process_pending_orders`).

### `strategy.risk.*` mostly no-op on compile path

**pynescript compile/Numba broker:** several `strategy.risk.*` calls are silent no-ops.

**Impact:** risk-capped strategies look unconstrained under compile mode.

**Track:** audit AGENT_04.

### Open/closed trade query surface incomplete (compile)

Many `strategy.opentrades.*` / `strategy.closedtrades.*` accessors return zeros on the compile broker.

**Track:** audit AGENT_04.

---

## Technical analysis

### `ta.atr` uses EMA-of-TR, not Wilder RMA (high)

**TradingView:** ATR is typically `ta.rma(ta.tr, length)` (Wilder smoothing).

**pynescript:** Both interpret and Numba paths use an **EMA-of-true-range** formulation (dual-host aligned).

**Impact:** ATR, Supertrend, Keltner, and any ATR-scaled logic diverge from TV charts.

**Track:** audit AGENT_03; Wave B — switch to RMA in both hosts and re-golden dependents.

### EMA seed differences (medium)

Incremental EMA may SMA-seed while some full/MACD paths use first-value seed.

**Impact:** Early bars differ; steady-state usually converges.

**Track:** audit AGENT_03.

---

## Evaluator / series

### `var` and `varip` are currently the same (critical for realtime)

**TradingView:** `varip` re-initializes / updates on **intrabar** realtime ticks for the same `bar_index`; `var` does not.

**pynescript:** Both modes use **init-once** on first execution of the declaration.

**Impact:** Live/realtime hosts that set `barstate.isrealtime` will not match TV for `varip` scripts. Historical bar-by-bar Runtime often hides this.

**Track:** audit AGENT_02; Wave B.

### `AugAssign` / tuple unpack can drop series history (high)

Some assignment paths store a scalar via elementwise ops instead of rebinding through `_bind_series_name`.

**Impact:** `x += 1` style updates on history-tracked series may lose lookback identity mid-script.

**Track:** audit AGENT_02; Wave B.

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
