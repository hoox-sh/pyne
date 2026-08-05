# Agent 01 — Inventory

| Field | Value |
| --- | --- |
| **Role / ID** | 01 — measure only |
| **Verdict** | **measure-only** (partial inventory; heavy sweeps aborted under load) |
| **Date** | 2026-08-04 |

## Baselines completed

| Run | Result |
| --- | --- |
| set01 interpret (249, 25 bars) | **249/249 OK (100%)** |
| set01 compile Runtime OK (249, 25 bars) | **249/249 OK (100%)** |
| builtin smoke 50 @ 200 bars | 48 OK + 2 both_error_same (auto_fib_*) |
| Known MISMATCH list (pre-fix) | 7 scripts sampled from aborted 1000-run |

## Note

Full set02–04 Runtime and 632-script parity sweep were **killed** after host
overload (12 agents + multi-worker corpus → false TIMEOUT storm). Prefer
targeted residual lists over concurrent full-set sweeps while agents edit.

## Artifacts

- `.cache/runtime_corpus_set01_interpret_r8.csv` (+ summary)
- `.cache/runtime_corpus_set01_compile_r8.csv` (+ summary)
- `.cache/parity_r8_sample120.json` (limit default 50)
- `.cache/parity_r8_known_mismatch.json` / `parity_r8_post_fix.json`
