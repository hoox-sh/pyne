# Swarm merge DAG — 2026-08-15

Lead Architect resolution of five domain top-3 lists. Executable ASDL is already fully visited; this sprint is **contracts + interpreter fidelity + JIT stay-rate**, not new node kinds.

## Rejected / deferred

| Item | Agent | Why |
| --- | --- | --- |
| ASDL `FunctionDef.returns` | Frontend P3 | Cross-engine schema change. `Qualify` on a new field is a contract bomb. Next sprint. |
| Grammar left-factor `type? name` / `=` vs `:=` | Frontend P1 | Grammar last. Residual parse ms, not a runtime hole. |
| Default-on `PYNE_SERIES_RING` | Profiler P2 | Flagged Phase 2. Corpus + polarity still dual-path. Keep off. |
| Re-open AugAssign wrapper drop | prior P0-4 | **Closed.** `statements.py` `_bind_series_name` after `_elementwise_binary`. |

## Merge order

```
Wave 0  QA contracts          (always-on, no skip-on-both-error)
  Q1  close[5] dual-host lookback + neg/na → na, never 0
  Q3  var + := + acc[1] dual-host
  Q2  deferred to Wave 2 (state-vector layout; gates JIT inc kernels)

Wave 1  Interpreter correctness
  I1  Start-of-bar carry for unwritten var/varip history series
  I2  Evaluator make_series maxlen = host pineseries_history_length (≥1000)
  I3  AST-stamped call-expr history (id(Call) → node attr) — next patch

Wave 2  JIT stay-rate (after Q1/Q3 stay green)
  J1  hline/fill metadata without object_mode
  J2  Proven-numeric UDF stores/plots stay nopython
  J3  median/wpr/cmo incremental (needs Q2)

Wave 3  Interpreter perf
  P1  visit_Call arg scratch (no new list per call)

Wave 4  Frontend (optional)
  F2  Thread-local Lexer/Parser reuse
```

## Collision rules

- Interpret is the oracle. Compile must match carry: unwritten `var` forwards `arr[i-1]`; unwritten plain series stays `na`.
- Do **not** `self.visit()` type annotations (`Qualify` has no engine visitor).
- Incremental Numba kernels copy `technical_submodules/core.py` last-value, no third formula.
- Dual-host integer/lookback asserts use `atol=0`. Existing TA goldens keep `1e-6`.

## Shipped this turn

Wave 0 Q1 + Q3 and Wave 1 I1 + I2.

Wave 1 I3 (AST `_pine_site_id`), Wave 2 J1/J2 (hline/fill + numeric UDFs stay nopython),
J3 (`numba_median_inc`; `numba_cmo_inc` seeds on gap then incremental), Wave 3 P1
(visit_Call arg scratch), Wave 0 Q2 (state-vector bounds), Wave 4 F2 (TLS parse),
Frontend P3 (`FunctionDef.returns` on ASDL + builder/unparser).
