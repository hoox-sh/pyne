# PYNE / pynescript — Round 7: 12 Subagents
# Focus: open backlog (H1/H2/C1/T1/T2/F2) + residual perf + newest techniques research
# Date: 2026-08-02
# BASE_SHA: 045190203a1991aa683147995b5f42ee71169756
# Prior: Round 6 (docs/perf_round6/00_summary.md) — do not rediscover shipped wins

You are one of 12 isolated subagents. Optimize **pynescript** (package
`pynescript`, product “pyne”) and complete **open roadmap residual IDs**.

## Goals (priority order)

1. **Correctness** — bar-by-bar Pine semantics; series offsets; `na`; `var`/`varip`;
   strategy event order. Prefer bit-identical vs current oracle.
2. **Open tasks** — ship or advance ROADMAP IDs: **H1** dual-host, **H2** warm
   compile, **C1** corpus residual, **T1** series cap, **T2** residual TA inc,
   **F2** pending-fill averaging.
3. **Performance** — measurable interpret/compile wins; no semantic “fixes” as
   speed hacks. Research newest techniques and apply only safe, proven patterns.
4. **Documentation** — agent report + update STATUS when done.

## Open backlog (canonical)

| ID | Item | Pri |
| --- | --- | --- |
| H1 | Dual-host: package-level Runtime unify / residual pyne-worker parity | P1 |
| H2 | Product warm-compile (SLOs, prewarm, IR cache on in deploy) | P1 |
| C1 | Corpus RUN_FAIL / TIMEOUT residual (set01–05) | P1 |
| T1 | Cap `current_series` to `max_bars_back` / `_SERIES_MAX` | P2 |
| T2 | Incremental TA for remaining heavy kernels (`ta.bb`, nested full paths) | P2 |
| F2 | Pending-fill averaging when pyramiding ≤ 0 | P2 |

Also residual from perf plan Phase 1–2:
- Parse/AST cache by `sha256(source)` for multi-run warm path
- Single chronological buffer / O(1) lookback (flagged)
- Lazy calendar fields / lighter plot registries
- Optional cProfile bottleneck map

## Repo map

- Core: `src/pynescript/`
- Runtime SoT: `backend/runtime.py`, `backend/evaluator.py`, `backend/series.py`
- Compiler: `src/pynescript/compiler/`
- Evaluator/TA: `src/pynescript/ast/evaluator/`
- Tests: `tests/`
- Bench: `scripts/bench_pipeline.py`
- Prior: `docs/perf_round6/00_summary.md`, `docs/ROADMAP.md`, `docs/missing_features.md`
- Perf skill: `.grok/skills/pynescript-perf/SKILL.md`
- Rules: `AGENTS.md`
- Sister: `/home/jango/Git/pyne-worker` (thin CF host; H1 only)

## Hard constraints

1. Zero correctness loss vs current oracle. Golden tests before behaviour change.
2. Do **not** vectorize whole scripts or parallelize bars of one run.
3. Do **not** silent-coerce `na` → 0 for speed.
4. Do **not** hand-edit generated grammar under `…/generated/`.
5. No stale backups in `src/`.
6. `from __future__ import annotations` on every new Python file.
7. Risky TA re-baselines (ATR Wilder, TV supertrend) need explicit goldens + docs.
8. New incremental TA / ring buffers / history caps → **behind flags** + goldens.
9. Do not re-implement Round 1–6 wins (see `docs/perf_round6/00_summary.md`).
10. Small, reviewable diffs. TA math in `src/pynescript/ast/evaluator/` first.
11. No secrets, no force-push, no commit of `.vsix` / `.metadata.key`.
12. Run targeted tests; report commands + numbers.

## Measurement

```bash
PYTHONPATH=src:. .venv/bin/python scripts/bench_pipeline.py
.venv/bin/python -m pytest tests/test_ta_incremental.py tests/test_evaluator.py \
  tests/test_parity.py tests/test_compiler_numba.py -q --tb=line
```

DoD for perf claims: ≥10–15% on a real path **or** structural win;
no >5% regression on `minimal`.

## Shared output

Write: `docs/perf_round7/AGENT_NN_<slug>.md` with:

- Role / ID
- What you did (files touched)
- Before/after bench or structural proof
- Tests run + pass/fail
- Residual / follow-ups
- Verdict: **win** | **partial** | **blocked** | **research-only**

Keep exclusive ownership of your assigned files; do not thrash other agents’ areas.
