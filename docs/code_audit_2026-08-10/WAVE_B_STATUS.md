# Wave B implementation status — 2026-08-10

Semantic correctness fixes after Wave A (security/CI).

## Done

| Item | Status | Notes |
|------|--------|-------|
| Linter `C004` always-on | **Done** | Trailing newline check no longer uses `strip()` |
| Linter `W002` line number | **Done** | Char offset → 1-based line |
| Unparser `visit_Simple` | **Done** | Fixed typo `visit_Sipmle` |
| `AugAssign` series bind | **Done** | Routes through `_bind_series_name` |
| Tuple unpack series bind | **Done** | Same bind funnel |
| `varip` realtime re-init | **Partial** | Re-runs RHS when `barstate.isrealtime`; historical unchanged |
| `ta.atr` → Wilder RMA | **Done** | interpret + `numba_atr` / `numba_atr_inc`; disk meta v6 |
| `strategy.exit` pending | **Done** | OHLC-triggered pending brackets + OCA; market exit immediate |
| Compile broker exit | **Done** | Matches pending semantics |
| Parity fixture `strategy_06` | **Regenerated** | Reflects pending fills |

## Tests

Core CI gate + strategy suites green (170+ passed). 
`test_ta_incremental` still has **7 pre-existing EMA/KC residual failures** (not newly introduced by ATR RMA alone; still out of CI gate).

## Residual

- `from_entry` / trail / `qty_percent` on exit
- Supertrend/KC golden re-verify vs reference Pine
- EMA seed split (incremental vs full)
- Full `varip` tick model under a live host
