# Sprint status — 2026-08-10 (post Wave A/B polish)

Short residual snapshot after the audit waves and dual-host correctness sprint.
Authoritative gap list: [`docs/known_divergences.md`](../known_divergences.md).
H1 host unify: [`docs/perf_round7/H1_unify_checklist.md`](../perf_round7/H1_unify_checklist.md).

## Shipped this sprint

| Item | Where | Notes |
|------|--------|-------|
| **Runtime SoT** | `src/pynescript/runtime/` (`host.py`, `evaluator.py`, `series.py`) | Package owns the bar loop. `backend.runtime` / `backend.evaluator` / `backend.series` re-export / shim the same implementation. Smoke: `tests/test_runtime_package.py`. |
| **EMA seed unified** | interpret full `_ema` + `_ema_inc_update` + Numba | SMA seed over first `period` finite samples (na until ready). Closes prior full-list first-value vs incremental SMA split. |
| **`from_entry` (interpret)** | `strategy.exit` + pending fills | Filters open-trade legs; unknown id soft no-op. Covered in `tests/test_order_fills.py`. |
| **`from_entry` (compile multi-leg)** | `CompileStrategyBroker` `open_legs` | Per-entry legs for pyramid exits; unknown soft no-op. Market exit without stop/limit still maps id only (residual). |
| **`qty_percent` on exit** | interpret + compile `close` | Percent of target size; wins over `qty`; edge caps documented. |
| **Trail (interpret, minimal)** | `trail_offset` / `trail_points` / optional `trail_price` | Ratcheting stop on pending fills. Compile does not trail. |
| **TA goldens / incremental in CI** | `.github/workflows/ci.yml` Core runtime | Gates: `tests/test_ta_incremental.py`, `tests/test_first_party_ta_goldens.py`, `tests/test_runtime_package.py` (plus prior parity/strategy/series set). |
| **pine-worker series polarity** | `pine-worker/src/evaluator/series.ts` | `series[1]` = previous bar; negatives → NA. README notes Python Runtime SoT. |
| **Wave B semantics (prior)** | strategy pending exit, `ta.atr` RMA, `varip` partial, series bind, linter C004 | See `WAVE_B_STATUS.md`. |

## Remaining backlog

| Item | Pri | Notes |
|------|-----|-------|
| **Compile trail** / tick-path trail | P2 | Interpret trail is minimal OHLC ratchet only. |
| **Compile market exit `from_entry` emit** | P2 | Visitor should pass `from_entry=` for market exits without stop/limit. |
| **pine-worker full Runtime** | P2 | Series polarity fixed; still experimental evaluator, not package Runtime. |
| **`request.security` HTF** | P2 | Not a full higher-timeframe re-eval engine. |
| **`strategy.risk.*` / trade queries (compile)** | P2 | Several risk calls no-op; open/closed trade accessors incomplete on compile broker. |
| **Full `varip` tick model** | P2 | Historical OK; needs live `barstate.isrealtime` host. |

## Quick smoke (local / CI-aligned)

```bash
FREE_RATE_LIMIT=0 FREE_MAX_CONCURRENT=0 ADMIN_TOKEN=ci \
  python -m pytest tests/test_runtime_package.py tests/test_first_party_ta_goldens.py -q
```

Core runtime PR gate also includes incremental TA, strategy, parity, series, free-limits (see `.github/workflows/ci.yml`).

## Doc pointers

| Doc | Role |
|-----|------|
| `WAVE_A_STATUS.md` | Security + CI honesty + first-party fixtures |
| `WAVE_B_STATUS.md` | Semantic fixes (pending exit, ATR RMA, series bind, …) |
| `SPRINT_STATUS.md` (this file) | Runtime SoT / EMA / from_entry / TA CI + residual backlog |
| `docs/known_divergences.md` | Living product-scope divergences |
| `docs/perf_round7/H1_unify_checklist.md` | Dual-host / package Runtime unify |
