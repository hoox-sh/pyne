# Push local main to origin/main (time / ta)

from: oo-ops
objective: Fast-forward origin/main to local main `8ceedf51`. No force-push, no tag, no version bump, no VPS sync.
result: rejected by the pre-push hook. Not retried. VPS not synced.

## Range

`f9030034dceaeedf61f39a1df3b6fab3cdd48b42..8ceedf5105836f79e4f12a9e7fa4b4088d8c236b` (3 commits, not on origin)

```text
8ceedf5105836f79e4f12a9e7fa4b4088d8c236b fix(runtime): honor time and time_close timeframe buckets
e358daaf4fc7a6bb31080fd304ec6cb6fd4e353c fix(runtime): use the fill print for same-tick open and close extremes
3c8a9bc27e77265f170b81e01f045b38cb56361a fix(compiler): admit proven numeric ta kernels in library inline
```

## SHAs

- local HEAD before and after: `8ceedf5105836f79e4f12a9e7fa4b4088d8c236b`
- origin/main before fetch: `f9030034dceaeedf61f39a1df3b6fab3cdd48b42`
- origin/main after fetch: `f9030034dceaeedf61f39a1df3b6fab3cdd48b42` (did not move; no rebase)
- origin/main after the rejected push: `f9030034dceaeedf61f39a1df3b6fab3cdd48b42`
- HEAD equals origin/main: no

## Hook

Command: `git push origin main` (no `--no-verify`, no `--force`). Started 2026-11-19T03:33:00Z, hook exit 2026-11-19T03:39:53Z.

`✖ pre-push failed (1 failed, 4 passed, 0 skipped)`

Git: `Fehler: Fehler beim Versenden einiger Referenzen nach 'https://github.com/hoox-sh/pyne.git'`

| Step | Result |
| --- | --- |
| Format | pass, 0.0s |
| Lint | pass, 0.0s |
| Typecheck | pass, 0.2s |
| OKF | pass, 0.3s |
| Tests | fail, 411.8s |

Pytest duration printed by the hook: `2 failed, 5540 passed, 4 skipped, 1 xfailed, 9 warnings in 396.98s (0:06:36)`.

Failed:

- `tests/test_parity_r9_kernels.py::TestStrategyPositionHistory::test_multi_vwap_071_parity`
- `tests/test_set06_timestamp_valuewhen.py::test_set06_timestamp_timezone_corpus_runs[tests/data/set06/indicators/13676_ind_triexdev_superbuyselltrend_plus_plus.pine]`

Tail of the second failure: `RuntimeError: time() cannot use session on this bar feed` at `src/pynescript/ast/evaluator/builtins/timeframe.py:359`. The hook omitted the first failure's traceback (last 80 lines only). Not a dirty-tree refusal. Not retried.

## After

- `git status -sb`: `## main...origin/main [voraus 3]`
- ahead count: 3 (`voraus 3`, not 0)
- Unrelated dirt left unstaged, not committed: `.prettierignore`, `scripts/verify.sh`, `tests/test_cli_util_coverage.py`, `.vscode/`
- VPS not synced
