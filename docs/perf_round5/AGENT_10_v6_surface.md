# AGENT 10 — v6 / builtin surface P0 gaps

**AGENT_ID:** 10  
**ROLE:** v6 / builtin surface P0 product correctness  
**BASE_SHA:** ca5215ac33c34f9b60584f8c230bc281dc768782  
**Date:** 2026-07-30  

## 1. Scope & files touched

**Owns:** dispatch registration + `builtins/*` P0 from
`docs/perf_round4/08_v6_coverage_matrix.md` / `docs/missing_features.md`.

**Files changed this pass:**

| File | Change |
|------|--------|
| `src/pynescript/ast/evaluator/builtins/logging.py` | Fix printf/`%` formatting when `str.format` has no braces |
| `src/pynescript/ast/evaluator/names.py` | `chart.is_pnf` → `is_point_figure` host alias |
| `backend/runtime.py` | `Chart.is_pnf`, `left/right_visible_bar_time`; `_make_chart()` seeds viewport |
| `src/pynescript/compiler/compiler.py` | Chart mode flags (`is_standard` True; others False; unknown → `None`) |
| `tests/test_v6_surface_locks.py` | Locks for printf log, chart viewport/pnf, `strategy.cash` sizing |

## 2. Bugs found (severity, repro)

| Sev | Bug | Repro | Status |
|-----|-----|-------|--------|
| **High** (pre-existing, fixed in `cf8d08c0` before BASE) | `log.*(fmt, *args)` TypeError | `log.info("x={0}", close)` | Already closed |
| **High** (pre-existing) | Unknown attr → truthy qualified string | `chart.missing ? 1 : 0` → 1 | Already closed → `na` |
| **High** (pre-existing) | `strategy.percent_of_equity` / `.fixed` missing | default entry qty 1.0 | Already closed + sizing |
| **Med** | **printf log dropped args** | `log.info("x=%s", close)` → `"x=%s"` (`.format` no-op success) | **Fixed this pass** |
| **Med** | `chart.is_pnf` / visible bar times missing | attrs → `na` / false defaults only | **Fixed this pass** |
| **Med** | Compile `chart.is_standard` → truthy `"is_standard"` string | compile mode always 1 | **Fixed this pass** |
| **Med** (pre-existing) | polyline mutators missing | unknown builtin | Already closed in `cf8d08c0` |

## 3. Changes (what / why)

### Already at BASE (prior P0 close `cf8d08c0`)
- `log.info/warning/error` + `runtime.error` varargs via `format_log_message`
- `strategy.fixed` / `percent_of_equity` / `cash` constants + `_resolve_default_entry_qty`
- `polyline.get_points` / `set_*` / `copy` dispatch
- Unknown attr → `None` (na); chart `is_heikinashi` aliases on host + `_HOST_ATTR_ALIASES`
- TA aliases `ta.willr`/`ad`/`pvt` + `ta.ao`/`aroon`; import soft-stub warning

### This pass (residual fidelity)
1. **`format_log_message`:** only call `str.format` when `{` present; else try `%`; else join — restores printf corpus paths without breaking `{0}` style.
2. **Chart host:** `is_pnf`, `left_visible_bar_time`, `right_visible_bar_time`; Runtime seeds viewport from first/last bar time.
3. **Compile chart attrs:** boolean defaults aligned with interpret; unknown chart.* → `None` not `repr(attr)`.
4. **Tests** lock printf log, chart surface, `strategy.cash` qty (5000 / 50 → 100 contracts).

## 4. Benchmarks

N/A — correctness-only agent; no hot-path perf claims.

## 5. Tests run

```bash
PYTHONPATH=src:. python -m pytest \
  tests/test_v6_surface_locks.py \
  tests/test_pine_surface_gaps.py \
  tests/test_v6_features.py -q --tb=line
# 64 passed in ~1.9s
```

## 6. Residual risks / follow-ups

- `request.*` multi-symbol still mock/data_feed (by design) — not “fixed” to live TV data.
- Nested `method` inside `type` body = parser (Agent 08), not this surface.
- ATR EMA vs Wilder RMA re-baseline = explicit correctness track (out of scope).
- Official TA long-tail (`ta.trix`, Hilbert, …) still open (P1/P2).
- Compile left/right visible times remain `0.0` stubs (no viewport in njit path).
- Builtin metadata JSON not regenerated (no new dispatch *names* for LSP; chart attrs are host fields).

## 7. Out of scope / did not touch

- Full inventory rewrite / mass new builtins
- ATR TV re-baseline
- Grammar / generated ANTLR
- LSP metadata encrypt
- pyne-worker dual-host Chart class (document drift only)
- Strategy broker fill/OCA (Agent 07)
- Collections/matrix (Agent 09)

## Handoff summary (≤20 lines)

- Verified prior P0 close (`cf8d08c0`) still green: log `{0}` varargs, qty consts+sizing, polyline set_*, unknown-attr→na, chart heikinashi aliases, TA aliases, import stub warn.
- **New fixes:** printf `log.*` formatting; `chart.is_pnf` + visible bar times on host Runtime; compile chart flags (`is_standard` True, unknown→None).
- **Tests:** +4 locks in `test_v6_surface_locks.py`; suite **64 passed**.
- No metadata regen required; no commit/push.
