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
| **`from_entry` (compile multi-leg)** | `CompileStrategyBroker` `open_legs` | Per-entry legs for pyramid exits; unknown soft no-op. |
| **Compile market exit `from_entry` emit** | `compiler.py` strategy.exit | Always emits `from_entry=` (market and bracket); no longer remaps to bare `id`. |
| **Compile risk + trade queries** | `strategy_broker.py` + `compiler.py` | Risk halt cascade: `allow_entry_in` / `max_position_size` / `max_drawdown` / `max_cons_loss_days` / `max_intraday_loss` + `entries_blocked`; trade queries from `open_legs` / `closed_trade_records`. |
| **`qty_percent` on exit** | interpret + compile `close` | Percent of target size; wins over `qty`; edge caps documented. |
| **Trail (interpret + compile, minimal)** | `trail_offset` / `trail_points` / optional `trail_price` | Ratcheting stop on pending fills (both paths). OHLC approx only. |
| **`request.security` honesty + HTF resample** | `request.py` + Runtime meta | OHLCV bucket aggregate + allowlisted simple `ta.*` on HTF (`htf_simple_ta_resample`); complex still na. |
| **`varip` realtime host** | `Runtime.run(realtime_last_bar=, realtime_ticks=, realtime_bars=, realtime_from_bar=)` | Multi-tick window on last K bars or from bar index; historical default unchanged. |
| **Compile risk filled-orders + trade MAE/MFE** | `strategy_broker.py` | `max_intraday_filled_orders`; open/closed comments + OHLC-approx max_drawdown/max_runup. |
| **pine-worker series smoke** | `series_parity_smoke.test.ts` + subscript on PineSeries | Offset contract + trivial `close[1]`/SMA-like expressions. |
| **TA goldens / incremental in CI** | `.github/workflows/ci.yml` Core runtime | Gates: `tests/test_ta_incremental.py`, `tests/test_first_party_ta_goldens.py`, `tests/test_runtime_package.py` (plus prior parity/strategy/series set). |
| **pine-worker series polarity** | `pine-worker/src/evaluator/series.ts` | `series[1]` = previous bar; negatives → NA. README notes Python Runtime SoT. |
| **Dependabot high (vscode-extension)** | `brace-expansion` → 2.1.4 | Transitive patch; `npm audit` clean. |
| **Wave B semantics (prior)** | strategy pending exit, `ta.atr` RMA, `varip` partial, series bind, linter C004 | See `WAVE_B_STATUS.md`. |

## Remaining backlog

| Item | Pri | Notes |
|------|-----|-------|
| **Tick-path trail** | P2 | Minimal OHLC ratchet only (interpret + compile). |
| **pine-worker full Runtime** | P2 | Series + trivial expr smoke only; not package Runtime. |
| **Full HTF expression re-eval** | P2 | OHLCV + allowlisted ta.sma/ema/rsi/atr only; nested/UDF still na. |
| **Streaming tick feed** | P2 | Simulated multi-bar multi-tick only; no live data socket. |

## Quick smoke (local / CI-aligned)

```bash
FREE_RATE_LIMIT=0 FREE_MAX_CONCURRENT=0 ADMIN_TOKEN=ci \
  python -m pytest tests/test_runtime_package.py tests/test_first_party_ta_goldens.py -q
```

Core runtime PR gate also includes incremental TA, strategy, parity, series, free-limits (see `.github/workflows/ci.yml`).

## Security deps (Dependabot high — 2026-08-10)

Triage of open GitHub Dependabot **high** alerts (`gh api repos/hoox-sh/pyne/dependabot/alerts`).

| Package | Manifest | Severity | Action | Notes |
|---------|----------|----------|--------|-------|
| `brace-expansion` 2.1.0 → **2.1.4** | `vscode-extension/package-lock.json` | high (alerts #18, #21, #22) | **Fixed** | Transitive via `vscode-languageclient` → `minimatch@5.1.9` (`^2.0.1`). Safe patch within 2.x; `npm update brace-expansion`. `npm audit` clean. |

**Deferred:** none for open high alerts. No open high/critical alerts on Python manifests (`pyproject.toml`, `backend/requirements.txt`) or other npm trees at triage time. Root `package.json` / `pine-worker` had no Dependabot high findings; `bun audit` in `pine-worker` reported none.

## Doc pointers

| Doc | Role |
|-----|------|
| `WAVE_A_STATUS.md` | Security + CI honesty + first-party fixtures |
| `WAVE_B_STATUS.md` | Semantic fixes (pending exit, ATR RMA, series bind, …) |
| `SPRINT_STATUS.md` (this file) | Runtime SoT / EMA / from_entry / TA CI + residual backlog |
| `docs/known_divergences.md` | Living product-scope divergences |
| `docs/perf_round7/H1_unify_checklist.md` | Dual-host / package Runtime unify |
